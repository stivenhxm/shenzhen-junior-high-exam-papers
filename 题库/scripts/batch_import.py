"""Plan a batch against canonical manifests, then publish checked questions and print locations."""
import argparse
import json
from pathlib import Path
import tempfile

import build
import registry


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def pending(root, candidates):
    # The manifests remain authoritative even if a run was interrupted before rebuilding indexes.
    entries = [registry.make_entry(root.parent, p, 0) for p in
               (build.read(f) for f in sorted((root/'papers').glob('*.json')))]
    ready, skipped = [], []
    for row in candidates:
        pid = build.stable_id(row['id'])
        sources = {}
        for role in ('paper', 'solution'):
            path = build.local(root.parent, row[role])
            digest = registry.file_digest(path)
            build.require(digest == row[role+'_sha256'], f'{pid} {role} 来源与批次指纹不符')
            sources[role] = {'git_path':row[role], 'sha256':digest}
        original = root.parent/row['paper']
        status, match, _ = registry.lookup(entries, original, root.parent)
        if status == '已解析':
            build.require(match['solution']['sha256'] == sources['solution']['sha256'],
                          f"{pid} 原卷已登记为 {match['id']}，但解析版有更新，请先校对版本")
            skipped.append((pid, match['id']))
            continue
        build.require(match is None, f'{pid} 同路径的来源有更新，请先校对版本')
        build.require(all(e['id'] != pid for e in entries), f'{pid} 已被其他原卷使用')
        sources['paper']['docx_content_sha256'] = registry.word_content_digest(original)
        entries.append({'id': pid, **sources})
        ready.append(row)
    return ready, skipped


def exact_pages(blocks, locations, allowed, task):
    if not blocks:
        return allowed
    pages = set()
    for block in blocks:
        pages.update(locations.get(str(block), []))
    # A shared answer header can appear before the answer crop, or an empty paragraph may
    # flow onto the next page. Only link to original pages containing this question.
    relevant = [page for page in allowed if page in pages]
    build.require(relevant, f'{task} 的正文块没有落在记录的原卷页上')
    return relevant


def attach_pages(q, printed):
    loc = printed['questions'][str(q['number'])]
    q['source'].update(loc)
    materials = {m['id']: m for m in q['materials']}
    for part in q['parts']:
        origin = part.setdefault('source', {})
        blocks = list(origin.get('paper_block_ids', []))
        for mid in part['material_ids']:
            blocks.extend(materials[mid].get('paper_blocks', []))
        for prefix, role, ids in [('question','paper',blocks),
                                  ('solution','solution',origin.get('solution_block_ids', []))]:
            field = prefix+'_pages'
            origin[field] = exact_pages(ids, printed['block_pages'][role], loc[field], part['id'])


def assemble(row, work, batch, revision):
    from batch_tags import apply_tags
    pid = row['id']
    printed = build.read(work/'pages'/(pid+'.json'))
    questions = build.read(work/'content'/(pid+'.json'))
    numbers = [q['number'] for q in questions]
    build.require(numbers == list(range(1,len(questions)+1)) and
                  len(numbers) == len(printed['questions']) == row['answer_markers'],
                  f'{pid} 题号、打印版或资料答案计数不一致')
    for q in questions:
        build.require(q['paper_id'] == pid and q['id'] == f"{pid}-Q{q['number']:02d}", f'{pid} 题 ID 与原卷不符')
        q.update(schema_version='1.0', taxonomy_version='0.2')
        apply_tags(q)
        attach_pages(q, printed)
    ids = [q['id'] for q in questions]
    sources = {role: dict(printed['sources'][role], git_path=row[role], sha256=row[role+'_sha256'])
               for role in ('paper','solution')}
    p = {key:row[key] for key in ('id','school','title','academic_year','exam_type')}
    p.update(schema_version='1.0', taxonomy_version='0.2', subject='数学', municipality='深圳市',
             grade='七年级', semester='上学期', question_ids=ids, sources=sources,
             ingestion={'batch':batch, 'answer_origin':'source_transcribed'})
    if revision:
        p['source_revision'] = revision
    return p, questions


def install(root, stage, manifests):
    for p in manifests:
        pid = p['id']
        folder = root/'questions'/pid
        staged = stage/'questions'/pid
        if folder.exists():
            # A previously interrupted import may have published this complete question
            # directory just before its manifest. Resume only if every byte agrees.
            old = {f.name:f.read_bytes() for f in folder.iterdir() if f.is_file()}
            new = {f.name:f.read_bytes() for f in staged.iterdir()}
            build.require(old == new, f'{pid} 已存在内容不同的题目目录')
        else:
            staged.rename(folder)
        (stage/'papers'/(pid+'.json')).rename(root/'papers'/(pid+'.json'))


def apply(root, selection, batch, revision):
    work = selection.resolve().parent/'work'
    with build.publish_lock(root):
        rows, skipped = pending(root, build.read(selection)['papers'])
        if rows:
            # install() compares any interrupted, not-yet-registered directories byte for byte.
            current = build.Bank(root, unpublished={row['id'] for row in rows})
            taxonomy = build.read(root/'taxonomy/taxonomy.v0.2.json')
            km = build.unique_map(taxonomy['knowledge_points'], '知识点')
            em = build.unique_map(taxonomy['exam_points'], '考点')
            with tempfile.TemporaryDirectory(prefix='.question-import-',dir=root.parent) as temp:
                stage = Path(temp)
                manifests = []
                for row in rows:
                    p, questions = assemble(row, work, batch, revision)
                    for doc in p['sources'].values():
                        rendered = build.local(root, doc['rendered_pdf'])
                        build.require(build.file_hash(rendered) == doc['rendered_sha256'], '打印版指纹不符')
                    for q in questions:
                        current.add_question(p, q, km, em, {})
                        save(stage/'questions'/p['id']/(q['id']+'.json'), q)
                    save(stage/'papers'/(p['id']+'.json'), p)
                    manifests.append(p)
                install(root, stage, manifests)
    # Rebuild even on a no-op retry in case a previous process stopped after installing manifests.
    built = build.publish(root)
    build.check_generated(built)
    print(f'新登记 {len(rows)} 份，跳过 {len(skipped)} 份，题库共 {len(built.papers)} 份。')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=['plan','apply'])
    cli.add_argument('selection', type=Path)
    cli.add_argument('--output', type=Path, help='plan 输出待处理清单')
    cli.add_argument('--batch', help='apply 使用的批次名称')
    cli.add_argument('--source-revision', help='原始资料所在本地 Git 提交')
    args = cli.parse_args()
    if args.action == 'plan':
        ready, skipped = pending(build.ROOT, build.read(args.selection)['papers'])
        if args.output:
            build.require(args.output.resolve() != args.selection.resolve(), '请另选清单输出文件，以便保留原批次')
            save(args.output, {'papers':ready})
        print(f'需处理 {len(ready)} 份，已登记或批内重复 {len(skipped)} 份。')
        for input_id, registered in skipped:
            print(f'{input_id} → {registered}')
    elif not args.batch:
        cli.error('apply 需提供 --batch')
    else:
        apply(build.ROOT, args.selection, args.batch, args.source_revision)
