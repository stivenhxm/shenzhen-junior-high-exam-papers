"""Look up a source before parsing it. The catalog is regenerated from validated paper manifests."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = '已解析试卷.json'


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


def lookup(entries, source, repo=ROOT.parent):
    sha = file_digest(source)
    body = None
    for row in entries:
        for role in ('paper', 'solution'):
            if row[role]['sha256'] == sha:
                return '已解析', row, role
    if source.suffix.lower() == '.docx':
        body = word_content_digest(source)
        for row in entries:
            if row['paper'].get('docx_content_sha256') == body:
                return '已解析', row, '原卷正文及嵌入资源相同'
    for row in entries:
        for role in ('paper', 'solution'):
            if (repo/row[role]['git_path']).resolve() == source.resolve():
                return '来源有更新，需复核', row, role
    return '未登记', None, None


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='查询原卷或解析版是否已经入库')
    cli.add_argument('source', type=Path, help='原始文件路径')
    args = cli.parse_args()
    records = json.loads((ROOT/'generated'/NAME).read_text(encoding='utf8'))['papers']
    status, row, role = lookup(records, args.source)
    print(status, row['id'] if row else '', role or '')
