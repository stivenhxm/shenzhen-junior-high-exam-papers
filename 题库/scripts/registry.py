"""Look up a source before parsing it. The catalog is regenerated from validated paper manifests."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = '已解析试卷.json'
G7_INVENTORY = '七年级上学期来源清单.json'
G7_T2_INVENTORY = '七年级下学期来源清单.json'
G8_T1_INVENTORY = '八年级上学期来源清单.json'
G8_T2_INVENTORY = '八年级下学期来源清单.json'
G9_T1_INVENTORY = '九年级上学期来源清单.json'
G9_T2_INVENTORY = '九年级下学期来源清单.json'


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def word_content_digest(path):
    """Ignore ZIP metadata and Office editing history, retain text, math objects and drawings."""
    if path.suffix.lower() != '.docx':
        return None
    digest = hashlib.sha256()
    with ZipFile(path) as archive:
        members = sorted(name for name in archive.namelist() if
                         name in ('word/document.xml', 'word/_rels/document.xml.rels', 'word/numbering.xml')
                         or name.startswith(('word/media/', 'word/embeddings/')))
        if 'word/document.xml' not in members:
            raise ValueError(f'找不到 Word 正文：{path}')
        for name in members:
            digest.update(name.encode('utf8') + b'\0')
            with archive.open(name) as member:
                digest.update(hashlib.file_digest(member, 'sha256').digest())
    return digest.hexdigest()


def make_entry(repo, paper, part_count):
    entry = {key: paper[key] for key in ('id', 'school', 'title', 'grade', 'semester', 'academic_year', 'exam_type')}
    entry.update(status='已解析', questions=len(paper['question_ids']), parts=part_count)
    if 'ingestion' in paper:
        entry.update(batch=paper['ingestion']['batch'])
    for role, source in paper['sources'].items():
        entry[role] = {key: source[key] for key in ('git_path', 'sha256')}
    entry['paper']['docx_content_sha256'] = word_content_digest(repo / entry['paper']['git_path'])
    return entry


def as_json(entries):
    for key in ('sha256', 'docx_content_sha256', 'git_path'):
        seen = {}
        for row in entries:
            value = row['paper'].get(key)
            if not value:
                continue
            if value in seen:
                raise ValueError(f"原卷重复登记（{key}）：{seen[value]} 与 {row['id']}")
            seen[value] = row['id']
    return json.dumps({'version': 1, 'papers': entries}, ensure_ascii=False, indent=2) + '\n'

def attach_inventory(root, entries, *, audit=False, inventory=None):
    """Attach alternate editions and answer sheets to their reviewed paper IDs."""
    if inventory is None:
        for path in sorted((root/'batches').glob('*来源清单.json')):
            attach_inventory(root,entries,audit=audit,inventory=path.name)
        return
    path = root/'batches'/inventory
    if not path.exists():
        if audit:
            raise ValueError(f'缺少来源清单：{path}')
        return
    data = json.loads(path.read_text(encoding='utf8'))
    repo = root.parent.resolve()
    folder = (repo/data['directory']).resolve()
    if not folder.is_relative_to(repo) or not folder.is_dir():
        raise ValueError('来源清单须指向仓内原卷目录')
    by_id = {row['id']:row for row in entries}
    known = {}
    for src in data['files']:
        rel = src['git_path']
        disk = (repo/rel).resolve()
        if Path(rel).is_absolute() or rel in known or not disk.is_relative_to(folder) or src['paper_id'] not in by_id:
            raise ValueError(f'来源清单有重复路径、未知试卷或目录越界：{rel}')
        known[rel] = src
        entry = by_id[src['paper_id']]
        if any(pid not in by_id for pid in src.get('also_used_by',[])):
            raise ValueError(f'来源清单包含未知的共用来源试卷：{rel}')
        if not disk.is_file() or file_digest(disk) != src['sha256']:
            raise ValueError(f'来源文件有变化，请复核：{rel}')
        if rel not in (entry['paper']['git_path'],entry.get('solution',{}).get('git_path')):
            entry.setdefault('alternate_sources',[]).append({k:src[k] for k in ('git_path','sha256','role')})
    if audit:
        # Word creates a temporary owner file next to a document while it is open.
        actual = {p.relative_to(repo).as_posix() for p in folder.rglob('*')
                  if p.is_file() and not (p.name.startswith('~$') and p.suffix.lower() in ('.doc', '.docx'))}
        if actual != known.keys():
            raise ValueError('来源目录与清单不同：'+'、'.join(sorted(actual.symmetric_difference(known))))
        for row in entries:
            for field in ('paper','solution'):
                if field not in row:
                    continue
                source=row[field]
                if (repo/source['git_path']).is_relative_to(folder):
                    match = known[source['git_path']]
                    if row['id'] not in [match['paper_id'],*match.get('also_used_by',[])]:
                        raise ValueError(f"{row['id']} 的 {field} 与来源清单指向不同试卷")
    return data

def source_records(row):
    for role in ('paper','solution'):
        if role in row:
            yield role,row[role]
    for src in row.get('alternate_sources',[]):
        yield src['role'],src


def lookup(entries, source, repo=ROOT.parent):
    sha = file_digest(source)
    for row in entries:
        for role, record in source_records(row):
            if (repo/record['git_path']).resolve() == source.resolve():
                return ('已解析' if record['sha256']==sha else '来源有更新，需复核'), row, role
    for row in entries:
        for role, record in source_records(row):
            if record['sha256'] == sha:
                return '已解析', row, role
    if source.suffix.lower() == '.docx':
        body = word_content_digest(source)
        for row in entries:
            if row['paper'].get('docx_content_sha256') == body:
                return '已解析', row, '原卷正文及嵌入资源相同'
    return '未登记', None, None


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='查询原卷或解析版是否已经入库')
    cli.add_argument('source', nargs='?', type=Path, help='原始文件路径')
    cli.add_argument('--audit-g7', action='store_true', help='逐文件核对七上来源清单及其内容指纹')
    cli.add_argument('--audit-g7-t2', action='store_true', help='逐文件核对七下来源清单及其内容指纹')
    cli.add_argument('--audit-g8', action='store_true', help='逐文件核对八年级两个学期的来源清单及其内容指纹')
    cli.add_argument('--audit-g9', action='store_true', help='核对九年级上下学期及中考模拟资料的来源清单和文件指纹')
    args = cli.parse_args()
    records = json.loads((ROOT/'generated'/NAME).read_text(encoding='utf8'))['papers']
    if args.audit_g7 or args.audit_g7_t2 or args.audit_g8 or args.audit_g9:
        manifests = [json.loads(f.read_text(encoding='utf8')) for f in (ROOT/'papers').glob('*.json')]
        entries = [make_entry(ROOT.parent,p,0) for p in manifests]
        for selected, name in ((args.audit_g7,G7_INVENTORY),(args.audit_g7_t2,G7_T2_INVENTORY),
                               (args.audit_g8,G8_T1_INVENTORY),(args.audit_g8,G8_T2_INVENTORY),
                               (args.audit_g9,G9_T1_INVENTORY),(args.audit_g9,G9_T2_INVENTORY)):
            if selected:
                data = attach_inventory(ROOT,entries,audit=True,inventory=name)
                print(f"{name}覆盖 {len(data['files'])} 个文件，关联 {len({r['paper_id'] for r in data['files']})} 份试卷。")
    elif args.source:
        status, row, role = lookup(records, args.source)
        print(status, row['id'] if row else '', role or '')
    else:
        cli.error('请给出原始文件路径，或使用 --audit-g7')
