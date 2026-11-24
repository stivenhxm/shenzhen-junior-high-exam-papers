"""重建已登记的 12 种七上混合排版原件。

在试卷仓库根目录执行 python 题库/scripts/single_packets.py <临时工作目录> --render。
工具从题库/papers 封面的相对原件路径和指纹读取输入，Word 原件需 Windows Word、
pywin32，PDF 使用 PyMuPDF。输出位于工作目录/stage，原始 Word 不作改动。
指定 --only 并传入以逗号分隔的十位大写指纹，可重建单份。自定义输入可在工作
目录放置 groups.json 数组，使用现有登记的 id、paper、solution 及双方的 sha256。

罗湖外语答案有部分“略”，福外东校区第 8 题实际只有三个选项。光明区第 17
题评分标准接受两种统计结果。评分表未给推导的题保持 source_answer_only。
跨题印刷的原图定位见 single_parts.EXTERNAL_DIAGRAMS，坐标单位为 PDF 点。
"""
from __future__ import annotations
import argparse, hashlib, json, re, traceback
from pathlib import Path
import pymupdf as fitz
from single_sources import crop, doc_blocks, localized, pdf_lines, set_part_pages
from batch_content import DocumentText, choices_of, make_parts, masked, refs, solution_steps, title_from

NUM=re.compile(r'^\s*(\d{1,2})\s*[.．、]')
SECTION=re.compile(r'^\s*(?:[一二三四][.．、]|第[ⅡⅠI二一]+卷|参考答案与试题解析|答案和解析|声明[：:])')
TAG={'knowledge_ids':[],'exam_ids':[],'coverage':'待标注','tag_note':'等待按 v0.2 分类核对。','tag_reason':''}
SCHOOLS=['深圳高级中学北校区等多校联考','宝安中学（集团）初中部','宝安区七校联考','深圳实验学校坂田部','福田外国语学校（东校区）','罗湖外语初中学校','龙岗区华附集团校','深圳市龙岗区（区级试卷）','深圳市光明区（区级试卷）','深圳市宝安区（区级试卷）','深圳市福田区（区级试卷）','深圳市亚迪学校']
PACKET_CODES=['46FC9E2D79','1A891DDAE8','E797F7FA34','DD916F1810','05AC16DA58','D74446848E','8E074DB196','653FC64CEA','CB535CA804','FC88383916','EAE70A5E76','A342F28115']
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
    tmp=path.with_suffix('.tmp');tmp.write_bytes(text.encode('utf8'));tmp.replace(path)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def seq(data, first, last):
    # Read numbering backward so that instructions numbered 1–5 do not displace the exam.
    out=[]
    for idx,text in reversed(list(data.items())):
        m=NUM.match(text)
        if m and int(m[1])==last-len(out):
            out.append(idx)
            if len(out)==last-first+1:return list(reversed(out))
    raise ValueError(('sequence',first,last,out[::-1]))
def sectionend(b,start,end):
    for i in range(start+1,end):
        if SECTION.match(b.get(i,'')) or b.get(i,'').startswith(('2024-2025学年广东省','2024–2025学年广东省')):return i
    return end
class Word:
    def __init__(self, source, pdf, anchors,bank):
        self.pdf=pdf
        self.blocks=doc_blocks(source,bank)
        a=json.loads(anchors.read_text('utf8'))
        self.pos={v['index']:tuple(v['position']) for v in a['blocks'] if v['position']}
        self.stop=max(self.blocks)+1
    def position(self,i):
        if i in self.pos:
            pg,y=self.pos[i]
            return (pg,max(0,y-3))
        return (len(self.pdf),self.pdf[-1].rect.height-33)
    def chunk(self,a,b):
        b=sectionend(self.blocks,a,b)
        return {'records':[(i,self.blocks[i]) for i in range(a,b)],'start':self.position(a),'end':self.position(b),'native':True}
def qsequences(word, n, combined, inline):
    b=word.blocks
    if combined and not inline:
        mid=next(i for i,t in b.items() if '参考答案与试题解析' in t or t.strip()=='答案和解析')
        pre={i:t for i,t in b.items() if i<mid}
        orig=seq(pre,1,n);sol=seq({i:t for i,t in b.items() if i>mid},1,n)
        qs=[word.chunk(a,e) for a,e in zip(orig,orig[1:]+[mid])]
        ans=[]
        for a,e in zip(sol,sol[1:]+[word.stop]):
            at=next((i for i in range(a,e) if re.search(r'【(?:考点|答案|分析|解析|解答)】',b[i])),None)
            if at is None:raise ValueError(('solution marker',a,e))
            ans.append(word.chunk(at,e))
        return qs,ans
    ids=seq(b,1,n)
    qs=[];ans=[]
    for a,e in zip(ids,ids[1:]+[word.stop]):
        if inline:
            at=next(i for i in range(a,e) if '【答案】' in b[i] or '【解析】' in b[i])
            qs.append(word.chunk(a,at));ans.append(word.chunk(at,e))
        else:qs.append(word.chunk(a,e))
    return qs,ans
def word_solutions(w,code,n):
    b=w.blocks
    if code=='DD916F1810':
        arr=seq(b,1,n);return [w.chunk(i,j) for i,j in zip(arr,arr[1:]+[w.stop])]
    arr=seq(b,14,n)
    tables=[i for i,t in b.items() if re.search(r'(题号|选项).*?\|',t) and ' | ' in t and i<arr[0]]
    ans=[]
    def table(i):
        t=b[i].splitlines()
        answers=t[-1].split(' | ')[1:]
        for cell in answers:
            c=w.chunk(i,i+1);c['records']=[(i,cell.strip())];c['answer_only']=True;ans.append(c)
    table(tables[0])
    if len(tables)>1:table(tables[1])
    else:
        for i in (9,10,11,12,13):
            c=w.chunk(i,i+1);c['answer_only']=True;ans.append(c)
    assert len(ans)==13,(code,len(ans))
    return ans+[w.chunk(i,j) for i,j in zip(arr,arr[1:]+[w.stop])]

def pdf_starts(lines,first,last):
    arr={}
    for i,(p,y,x,x1,y1,t) in enumerate(lines):
        if x<150 and NUM.match(t) and not re.match(r'^\d+\.\d+(?:\s|$)',t):
            arr[i]=t
    ids=seq(arr,first,last)
    return [(lines[i][0],max(0,lines[i][1]-2.7)) for i in ids]
def pdf_chunk(lines,a,e,xlim=None):
    rr=[(i,t) for i,(pg,y,x,x1,y1,t) in enumerate(lines) if a<=(pg,y)<e and (not xlim or xlim[0]-1<=x<xlim[1]+1)]
    return {'start':a,'end':e,'records':rr,'xlim':xlim,'native':False}
def pdf_questions(d,n):
    lines=pdf_lines(d);starts=pdf_starts(lines,1,n);out=[]
    for a,e in zip(starts,starts[1:]+[(len(d),d[-1].rect.height-30)]):
        section=next(((p,y-2) for p,y,x,x1,y1,t in lines if a<(p,y)<e and SECTION.match(t)),e)
        out.append(pdf_chunk(lines,a,section))
    return out
def pdf_solutions(d,code,n):
    lines=pdf_lines(d)
    if code=='8E074DB196':
        return pdf_questions(d,n)
    first=pdf_starts(lines,14,n)
    full=[pdf_chunk(lines,a,e) for a,e in zip(first,first[1:]+[(len(d),d[-1].rect.height-30)])]
    # In these two source PDFs keys are in aligned rows. Include each original cell.
    if code=='CB535CA804':
        letters='BABCADBA'; lo,hi=194,248;xs=[186+i*34 for i in range(9)]
        fills=[r'\(-\frac{1}{6}\)','7','1','13','320']
        fxs=[86,149,201,253,316,390];flo,fhi=273,309
    else:
        letters='CBBDBAAD';lo,hi=153,201;xs=[91+i*51.9 for i in range(9)]
        fills=['','心','1','20','2023'];fxs=[88,220,271,312,360,475];flo,fhi=240,286
    ans=[]
    for i,cell in enumerate([*letters,*fills]):
        j=i if i<8 else i-8
        x=xs if i<8 else fxs;y0,y1=(lo,hi) if i<8 else (flo,fhi)
        c=pdf_chunk(lines,(1,y0),(1,y1),(x[j],x[j+1]))
        c['answer_only']=True;c['cell_text']=cell;ans.append(c)
    return ans+full

def opts(text):
    text=re.sub(r'(?m)^A(?=\s|〔|\\\()','A. ',text)
    try:return choices_of(text)
    except ValueError:
        matches=list(re.finditer(r'([A-D])[.．、]',masked(text)))
        selected=[]
        for m in matches:
            if m[1]==chr(65+len(selected)):
                selected.append(m)
                if len(selected)==4:break
        if len(selected)<2:raise
        options=[{'label':m[1],'text':text[m.end():selected[i+1].start() if i+1<len(selected) else len(text)].strip()} for i,m in enumerate(selected)]
        if not all(x['text'] for x in options):raise
        return text[:selected[0].start()].strip(),options
def pdf_options(doc,c,bank,folder,key):
    # Use original character boxes so scanned geometry, aligned fractions and artwork remain intact.
    found=[]
    for pg in range(c['start'][0],c['end'][0]+1):
        page=doc[pg-1]
        marks=[]
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines',[]):
                chars=[a for s in line['spans'] for a in s['chars']]
                t=''.join(a['c'] for a in chars)
                for m in re.finditer(r'([A-D])\s*[．.、]',t):
                    x,y,x1,y1=chars[m.start()]['bbox']
                    if c['start']<=(pg,y)<c['end']:marks.append((m[1],pg,y,x))
        for label in 'ABCD':
            candidates=[v for v in marks if v[0]==label]
            if any(v[0]==label for v in found):continue
            if candidates:found.append(candidates[-1])
    found.sort()
    if ''.join(v[0] for v in found)!='ABCD':return []
    result=[]
    for i,(label,pg,y,x) in enumerate(found):
        pg_end,ey=c['end']
        next_rows=[v for v in found[i+1:] if v[1]==pg and v[2]>y+9]
        if next_rows:pg_end,ey=pg,min(a[2] for a in next_rows)-7
        col=[v[3] for v in found[i+1:] if v[1]==pg and abs(v[2]-y)<9 and v[3]>x+2]
        x1=min(col)-1 if col else doc[pg-1].rect.width-21
        if pg_end!=pg:ey=doc[pg-1].rect.height-30
        try:
            image=crop(doc,(pg,max(c['start'][1] if pg==c['start'][0] else 0,y-10)),(pg,ey),folder,key+'-opt'+label,bank,(max(0,x-1),x1))
        except ValueError:return []
        result.append((label,image['images'][0]))
    return result
def unpack_solution(sdoc,c,code,typ,images):
    text=sdoc.content; text=NUM.sub('',text,count=1).strip()
    only=c.get('answer_only')
    if only and c['native']:return text,text,'','source_answer_only',0
    if only:
        value=c.get('cell_text') or '〔图1〕'
        return value,value,'','source_answer_only',0
    if not c['native']:
        pics='\n'.join('〔图%d〕'%i for i in range(1,len(images)+1))
        m=re.search(r'【答案】\s*([A-D])',text)
        return (m[1] if m else ''),(m[1] if m else pics),pics,'source_facsimile',0
    am=re.search(r'【答案】',text);sm=re.search(r'【(?:解析|分析|详解|解答)】',text)
    answer=text[am.end():sm.start() if sm else len(text)].strip() if am else ''
    if not am and code=='DD916F1810' and sm:answer=text[:sm.start()].strip()
    worked=text[sm.end():].strip() if sm else text
    start=sdoc.content.find(worked)
    if answer:return answer,answer,worked,'source_transcribed',start
    m=re.search(r'故选\s*[：:]?\s*([A-D])|故答案为\s*[：:]\s*([^\n]+)',worked)
    if m and typ!='解答题':summary=(m[1] or m[2]).strip('．。；;')
    else:summary=worked.split('【点评】')[0].split('【解答】')[-1].strip()
    return '',summary,worked,'source_solution_summary',max(0,start)
from single_parts import external_diagram, make_visual_parts

def ingest(row,idx,base,bank,logs):
    pid=row['id'];code=pid.rsplit('-',1)[-1];n=23 if code=='A342F28115' else 20
    combined=row['paper']==row['solution'];out=bank/'assets'/pid;folder=out/'single';folder.mkdir(exist_ok=True)
    roles={};sources={};stage=base/'stage'
    for role in ('paper','solution'):
        actual='paper' if combined else role
        path=out/(actual+'.pdf');doc=fitz.open(path);src=bank.parent/row[role]
        native=src.suffix=='.docx'
        word=Word(src,doc,base/'work'/'anchors'/(pid+'-'+actual+'.json'),bank) if native and (role=='paper' or not combined) else None
        roles[role]=(doc,word);sources[role]={'git_path':row[role],'sha256':row[role+'_sha256'],'rendered_pdf':path.relative_to(bank).as_posix(),'rendered_sha256':sha(path),'print_page_count':len(doc)}
    pdf,w=roles['paper'];sdf,sw=roles['solution']
    if w:qs,sol=qsequences(w,n,combined,code=='A342F28115')
    else:qs=pdf_questions(pdf,n);sol=[]
    if not sol:sol=word_solutions(sw,code,n) if sw else pdf_solutions(sdf,code,n)
    if len(qs)!=n or len(sol)!=n:raise ValueError((len(qs),len(sol),n))
    ids=[]
    for i,(pc,sc) in enumerate(zip(qs,sol),1):
        qid=pid+f'-Q{i:02d}';ids.append(qid)
        typ='选择题' if i<=(12 if n==23 else 8) else '填空题' if i<=(18 if n==23 else 13) else '解答题'
        pcl=crop(pdf,pc['start'],pc['end'],folder,f'q{i:02d}',bank)
        scl=crop(sdf,sc['start'],sc['end'],folder,f's{i:02d}',bank,sc.get('xlim'))
        pr,figs=localized(pc['records']);sr,sfigs=localized(sc['records'])
        def expose_labels(t):
            # Some Word sources put the subquestion number and its whole formula in one equation.
            return re.sub(r'\\\(\(([1-9])\)(?=[^\s])',lambda m:'（'+m[1]+'）'+r'\(',t)
        pd=DocumentText.from_blocks([(k,expose_labels(t)) for k,t in pr],True)
        sd=DocumentText.from_blocks([(k,expose_labels(t)) for k,t in sr])
        rendered_in_image=False
        if pc['native']:
            stem=pd.content;choices=[]
            if typ=='选择题':
                try:stem,choices=opts(stem)
                except ValueError:
                    stem='\n'.join(f'〔图{k+1}〕' for k in range(len(pcl['images'])));figs=list(pcl['images']);rendered_in_image=True
        else:
            figs=list(pcl['images']);stem='\n'.join(f'〔图{k+1}〕' for k in range(len(figs)));choices=[]
            if typ=='选择题':
                for lab,im in pdf_options(pdf,pc,bank,folder,f'q{i:02d}'):
                    figs.append(im);choices.append({'label':lab,'text':f'〔图{len(figs)}〕'})
                rendered_in_image=not choices
        if not sc['native']:sfigs=list(scl['images'])
        given,ans,worked,origin,offset=unpack_solution(sd,sc,code,typ,scl['images'])
        if not ans:ans='\n'.join(f'〔图{k+1}〕' for k in range(len(scl['images'])));sfigs=list(scl['images']);origin='source_facsimile'
        q=dict(TAG,id=qid,paper_id=pid,schema_version='1.0',taxonomy_version='0.2',number=i,type=typ,points=None,title=title_from(pd.content),stem=stem,choices=choices,figures=figs,
               tables=[],given_answer=given,answer=ans,given_solution=worked,given_solution_figures=sfigs,solution_steps=solution_steps(worked),
               solution_origin=origin,solution_figure_ids=refs(ans+'\n'+worked),materials=[],parts=[],review_note='',
               source=dict(extracted_text=pd.content,**{'question_'+k:v for k,v in pcl.items()},**{'solution_'+k:v for k,v in scl.items()}))
        if code=='05AC16DA58' and i==8:
            q['review_note']='原卷第 8 题仅列出 A、B、C 三项，参考答案为 C。'
        external_diagram(q,pdf,folder,bank,code)
        if rendered_in_image:q['choices_in_facsimile']=True
        if typ=='解答题':
            if pc['native'] and sc['native']:
                make_parts(q,pd,sd,ans,worked,offset)
            else:
                make_visual_parts(q,pc,sc,pcl,scl,pdf,sdf,folder,bank,TAG)
        set_part_pages(q, w.pos if w else {}, w.pos if combined else sw.pos if sw else {})
        for part in q['parts']:
            part.update(TAG)
        q['solution']='\n'.join(q['solution_steps'])
        write(stage/'questions'/pid/(qid+'.json'),q)
    idx=PACKET_CODES.index(code)
    school=SCHOOLS[idx];year='2023–2024' if n==23 else '2024–2025';exam='月考模拟' if n==23 else '期中考试' if idx<7 else '期末考试'
    paper=dict(id=pid,school=school,title=f'{school} {year} 学年七年级上学期数学{exam}',academic_year=year,exam_type=exam,schema_version='1.0',taxonomy_version='0.2',subject='数学',municipality='深圳市',grade='七年级',semester='上学期',question_ids=ids,sources=sources,ingestion={'batch':'2026-11-24-g7-complete','answer_origin':'source_transcribed'},source_revision=row.get('source_revision','4de209f680a738c18a841ac8f8090605cc13fa52'))
    variants={'46FC9E2D79':'学校联考原题及评分版，选择题次序与盐田精品解析版存在差异。','E797F7FA34':'七校联考学校稿，选择题选项与精品解析版存在差异。','8E074DB196':'集团校原题及评分版，第 1 题正确选项为 C。'}
    if code in variants:
        paper['edition_note']=variants[code]
        paper['title']+='（学校原题版）'
    write(stage/'papers'/(pid+'.json'),paper)
    print(pid,len(ids),'done',flush=True)
def render(rows,base,bank,only):
    import shutil
    import pythoncom
    import win32com.client
    import batch_pages
    batch_pages.BANK=bank
    pythoncom.CoInitialize()
    app=win32com.client.DispatchEx('Word.Application')
    try:
        app.Visible=False;app.DisplayAlerts=0;app.AutomationSecurity=3;app.Options.UpdateLinksAtOpen=False
        for row in rows:
            if only and row['id'].rsplit('-',1)[-1] not in only.split(','):continue
            folder=bank/'assets'/row['id'];folder.mkdir(exist_ok=True,parents=True)
            for role in ('paper','solution'):
                if role=='solution' and row['paper']==row['solution']:continue
                src=bank.parent/row[role]
                if sha(src)!=row[role+'_sha256']:raise ValueError('原件指纹已改变：'+str(src))
                if src.suffix.lower()=='.docx':batch_pages.render_role(app,row,role,base/'work')
                else:shutil.copyfile(src,folder/(role+'.pdf'))
    finally:
        app.Quit(0);pythoncom.CoUninitialize()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('base',type=Path);p.add_argument('--only',default='');p.add_argument('--render',action='store_true',help='从原文件生成 Word 打印书签，原 PDF 按指纹复制。');p.add_argument('--bank',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args()
    base=args.base.resolve();bank=args.bank.resolve();manifest=base/'groups.json'
    if manifest.is_file():
        rows=json.loads(manifest.read_text('utf8'))
    else:
        rows=[]
        for code in PACKET_CODES:
            path=bank/'papers'/('SZ-G7-T1-'+code+'.json')
            paper=json.loads(path.read_text('utf8'))
            row={'id':paper['id'],'source_revision':paper.get('source_revision')}
            for role,src in paper['sources'].items():
                row[role]=src['git_path'];row[role+'_sha256']=src['sha256']
            rows.append(row)
    if args.render:
        render(rows,base,bank,args.only)
    failures=[]
    for i,r in enumerate(rows):
        if args.only and r['id'].split('-')[-1] not in args.only.split(','):continue
        try:ingest(r,i,base,args.bank.resolve(),[])
        except Exception:
            failures.append(r['id']);print(r['id'],traceback.format_exc(),flush=True)
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
