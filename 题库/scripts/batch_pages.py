"""Print paired source DOCX files and locate original body blocks on exact PDF pages.

Rendering requires Microsoft Word for Windows, pywin32, lxml and PyMuPDF.
Canonical pages and crop names are relative to the question-bank root.
"""
import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import re
import tempfile
import zipfile

from lxml import etree
import pymupdf as fitz

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
NS = {'w': W, 'm': M}
BK = 'BankBlock'
BANK = Path(__file__).resolve().parents[1]
QNUM = re.compile(r'^\s*(\d{1,2})(?:[.．、]|\s+(?=\S))')
SECTION = re.compile(r'^\s*(?:第[一二三四五六]部分|[一二三四五六七八]\s*[、.．]\s*(?:单项|单选|选择|填空|计算|解答|综合|作图|非选择|判断|实践))')
ANCHOR_VERSION = 1
CROP_VERSION = 1


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


def write_json(path, data):
    path.parent.mkdir(exist_ok=True, parents=True)
    pending = path.with_suffix('.tmp')
    pending.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    pending.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_selection(papers):
    identifiers=set()
    for paper in papers:
        pid=paper['id']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',pid) or pid in identifiers:
            raise ValueError(f'无效或重复的试卷 ID：{pid}')
        identifiers.add(pid)
        for role in ('paper','solution'):
            path=(BANK.parent/paper[role]).resolve()
            if not path.is_relative_to(BANK.parent) or path.suffix.lower()!='.docx':
                raise ValueError(f'原卷和配套解析必须引用仓库内的 DOCX：{path}')


def annotate(source, output):
    """Bookmarks add zero visible characters and preserve native Office math and graphics."""
    qn = lambda local: f'{{{W}}}{local}'
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, 'w') as marked:
        for entry in original.infolist():
            data = original.read(entry)
            if entry.filename == 'word/document.xml':
                document = etree.fromstring(data)
                body = document.find(qn('body'))
                numeric = [int(v) for v in document.xpath('//w:bookmarkStart/@w:id', namespaces=NS) if v.isdecimal()]
                first_id = max(numeric, default=0) + 1
                blocks = []
                for idx, block in enumerate(body, 1):
                    if block.tag == qn('p'):
                        paragraph = block
                    elif block.tag == qn('tbl'):
                        paragraph = block.find('.//' + qn('p'))
                    else:
                        continue
                    if paragraph is None:
                        continue
                    content = ''.join(block.xpath('.//w:t/text() | .//m:t/text()', namespaces=NS)).strip()
                    name = BK + f'{idx:06d}'
                    mark_id = str(first_id + idx)
                    begin = etree.Element(qn('bookmarkStart'), {qn('id'): mark_id, qn('name'): name})
                    end = etree.Element(qn('bookmarkEnd'), {qn('id'): mark_id})
                    paragraph.insert(int(len(paragraph)>0 and paragraph[0].tag == qn('pPr')), begin)
                    paragraph.append(end)
                    blocks.append({'index': idx, 'text': content, 'table': block.tag == qn('tbl')})
                margins = body.find('.//' + qn('pgMar'))
                limits = {k: int(margins.get(qn(k), 0)) / 20 for k in ('top','bottom')} if margins is not None else {}
                data = etree.tostring(document, encoding='UTF-8', xml_declaration=True, standalone=True)
            marked.writestr(entry, data)
    return blocks, limits


def question_marks(blocks, count):
    """Backtrack through the expected printed sequence, ignoring numbered instructions."""
    by_number = {}
    for b in blocks:
        match = QNUM.match(b['text'])
        if match and not b['table']:
            by_number.setdefault(int(match[1]), []).append(b['index'])
    result = {}
    ceiling = len(blocks) + 2
    for n in range(count, 0, -1):
        choices = [idx for idx in by_number.get(n, []) if idx < ceiling]
        if not choices:
            raise ValueError(f'Cannot locate question {n} of {count}')
        result[n] = ceiling = choices[-1]
    return dict(sorted(result.items()))


def render_role(app, paper, role, work):
    src = BANK.parent / paper[role]
    pid = paper['id']
    root = BANK/'assets'/pid
    root.mkdir(exist_ok=True, parents=True)
    final = root / (role+'.pdf')
    manifest = work/'anchors'/f'{pid}-{role}.json'
    digest = sha(src)
    if digest != paper[role+'_sha256']:
        raise ValueError(f'{pid}/{role}: source has changed')
    if final.is_file() and manifest.is_file():
        previous = read_json(manifest)
        if previous.get('version')==ANCHOR_VERSION and previous['sha256']==digest and previous['rendered_sha256']==sha(final):
            return
    with tempfile.TemporaryDirectory(prefix='math-paper-print-') as folder:
        folder = Path(folder)
        tmp_doc = folder/'source.docx'
        tmp_pdf = folder/'source.pdf'
        blocks, margins = annotate(src, tmp_doc)
        doc = app.Documents.Open(str(tmp_doc), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False, Visible=False)
        try:
            doc.ExportAsFixedFormat(str(tmp_pdf),17,False,0,0,1,1,0,False,True,2,True,True,False)
        finally:
            doc.Close(0)
        with fitz.open(tmp_pdf) as pdf:
            destinations = {}
            toc = pdf.get_toc(simple=False)
            for _, title, _, dest in toc:
                if title.startswith(BK) and title[len(BK):].isdigit() and 'to' in dest:
                    destinations[int(title[len(BK):])] = [dest['page']+1, round(float(dest['to'].y),2)]
            for block in blocks:
                block['position'] = destinations.get(block['index'])
            missing = [b['index'] for b in blocks if b['text'] and not b['position']]
            if missing:
                raise ValueError(f'{pid}/{role}: missing printed bookmarks for body blocks {missing}')
            page_count = len(pdf)
            # Discard the temporary paragraph markers from the PDF outline.
            pdf.set_toc([])
            pending = final.with_suffix('.tmp')
            pdf.save(pending, garbage=3, deflate=True)
            pending.replace(final)
    write_json(manifest, {'version':ANCHOR_VERSION,'sha256':digest,'rendered_sha256':sha(final),
                          'print_page_count':page_count,'rendered_pdf':final.relative_to(BANK).as_posix(),
                          'margins':margins,'blocks':blocks})


def render_group(papers, work):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx('Word.Application')
    try:
        app.Visible = False
        app.DisplayAlerts = 0
        app.AutomationSecurity = 3
        app.Options.UpdateLinksAtOpen = False
        app.Options.SaveNormalPrompt = False
        errors = []
        for paper in papers:
            for role in ('paper','solution'):
                try:
                    render_role(app, paper, role, work)
                    print('Printed',paper['id'],role,flush=True)
                except Exception as error:
                    errors.append(f"{paper['id']} {role}: {error}")
                    print('FAILED',errors[-1],flush=True)
        return errors
    finally:
        app.Quit(0)
        pythoncom.CoUninitialize()


class PrintedPages:
    """Keep the native print layout, including image-only continuations of a question."""

    def __init__(self, pdf, margins):
        self.pdf=pdf
        self.margins=margins
        self.scale=2.2
        self.cache={}

    def page(self, number):
        import numpy as np
        from PIL import Image
        if number not in self.cache:
            page=self.pdf[number-1]
            pix=page.get_pixmap(matrix=fitz.Matrix(self.scale,self.scale),alpha=False,colorspace=fitz.csRGB)
            image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            left=round(12*self.scale)
            right=pix.width-left
            image=image.crop((left,0,right,pix.height))
            ink=(np.asarray(image).min(axis=2)<234).any(axis=1)
            # Word's body starts at its section margins. Keep a small allowance for
            # inline formula ascenders and floating diagrams without counting page numbers.
            top=max(5,self.margins.get('top',42)-12)
            bottom=page.rect.height-max(5,self.margins.get('bottom',42)-12)
            self.cache[number]=(image,ink,left,round(top*self.scale),round(bottom*self.scale))
        return self.cache[number]

    def region(self,start,end):
        import numpy as np
        for number in range(start[0],end[0]+1):
            image,ink,left,top,bottom=self.page(number)
            low=max(0,round(start[1]*self.scale)) if number==start[0] else top
            high=min(image.height,round(end[1]*self.scale)) if number==end[0] else bottom
            if high<=low:
                continue
            visible=np.flatnonzero(ink[low:high])
            if not len(visible):
                continue
            a=max(low,low+int(visible[0])-5)
            b=min(high,low+int(visible[-1])+6)
            yield number,image,left,a,b

    def crop(self, start, end, out, prefix):
        result={key:[] for key in ('pages','images','regions')}
        for number,image,left,low,high in self.region(start,end):
            dest=out/f'{prefix}-p{number:02}.webp'
            crop=image.crop((0,low,image.width,high))
            crop.save(dest,format='WEBP',lossless=True,method=2)
            result['pages'].append(number)
            result['images'].append(dest.relative_to(BANK).as_posix())
            result['regions'].append({'page':number,'bbox_pt':[round(v/self.scale,2) for v in (left,low,left+image.width,high)]})
        if not result['pages']:
            raise ValueError(f'Empty printed crop {prefix} at {start} – {end}')
        return result


def locate_role(meta,role,count,starts=None):
    blocks=meta['blocks']
    starts=starts or question_marks(blocks,count)
    positions={b['index']:b['position'] for b in blocks if b['position']}
    headings=[b['index'] for b in blocks if SECTION.match(b['text']) or re.match(r'^(?:第[ⅠⅡ]卷$|(?:选择|填空|解答)题\s*[:：（(])',b['text'])]
    with fitz.open(BANK/meta['rendered_pdf']) as pdf:
        raster=PrintedPages(pdf,meta['margins'])
        end=[len(pdf),pdf[-1].rect.height-max(5,meta['margins'].get('bottom',42)-12)]
        indices=list(positions)
        # A block may span pages. On the following page count only actual body ink
        # before the next paragraph starts, never an empty page margin.
        block_pages={}
        for i,idx in enumerate(indices):
            start=positions[idx]
            stop=positions[indices[i+1]] if i+1<len(indices) else end
            if start[0]==stop[0]:
                block_pages[idx]=[start[0]]
            else:
                pages=[n for n,*_ in raster.region(start,stop)]
                block_pages[idx]=pages or [start[0]]
        output={}
        for n,idx in starts.items():
            next_q=starts.get(n+1,len(blocks)+1)
            finish=min((h for h in headings if idx<h<next_q),default=next_q)
            if role=='solution':
                answer_block=next((b for b in blocks if idx<=b['index']<finish and
                                    b['text'].startswith(('【答案】','【详解】','【解答】','【解析】'))),None)
                if answer_block is None:
                    raise ValueError(f'Question {n}: no printed answer or worked solution')
                idx=answer_block['index']
            part=raster.crop(positions[idx],positions.get(finish,end),
                             (BANK/meta['rendered_pdf']).parent, f'{role}-q{n:02}')
            group='question' if role=='paper' else 'solution'
            output[n]={f'{group}_{k}':v for k,v in part.items()}
        return output,block_pages


def crop_paper(paper,work):
    pid=paper['id']
    try:
        output={}
        sources={}
        block_pages={}
        manifest=work/'pages'/(pid+'.json')
        for role in ('paper','solution'):
            meta=read_json(work/'anchors'/f'{pid}-{role}.json')
            sources[role]={k:meta[k] for k in ('rendered_pdf','rendered_sha256','print_page_count')}
            boundaries = work/'boundaries'/(pid+'.json')
            starts = ({int(q):idx for q,idx in read_json(boundaries)[role].items()}
                      if boundaries.is_file() else None)
            rows,block_pages[role]=locate_role(meta,role,paper['answer_markers'],starts)
            for n,row in rows.items():
                output.setdefault(n,{}).update(row)
        write_json(manifest,{'version':CROP_VERSION,'sources':sources,'questions':output,'block_pages':block_pages})
        print('Located',pid,len(output),'questions',flush=True)
    except Exception as error:
        print('FAILED',pid,str(error),flush=True)
        return f'{pid}: {error}'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection',type=Path)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--stage',choices=['all','render','crop'],default='all')
    args=parser.parse_args()
    selection=read_json(args.selection)
    work=args.selection.resolve().parent/'work'
    from batch_import import pending
    papers, skipped = pending(BANK, selection['papers'])
    if skipped:
        print(f'已跳过 {len(skipped)} 份已登记或重复试卷。')
    if not papers:
        print('无待处理试卷。')
        return
    if args.workers<1:
        parser.error('--workers 须为正整数')
    validate_selection(papers)
    workers=min(args.workers,len(papers))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        if args.stage in ('all','render'):
            jobs=[pool.submit(render_group,papers[i::workers],work) for i in range(workers)]
            errors=[e for job in as_completed(jobs) for e in job.result()]
            if errors:
                raise SystemExit('\n'.join(errors))
        if args.stage in ('all','crop'):
            jobs=[pool.submit(crop_paper,p,work) for p in papers]
            errors=[result for job in as_completed(jobs) if (result:=job.result())]
            if errors:
                raise SystemExit('\n'.join(errors))


if __name__ == '__main__':
    main()
