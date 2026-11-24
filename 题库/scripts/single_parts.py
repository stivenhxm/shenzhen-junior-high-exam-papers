"""Visual subquestion alignment and source diagrams printed alongside a different question."""
import re
from single_sources import crop
from batch_content import refs

# Page coordinates were checked on the school's supplied print layouts. Some
# papers place several numbered diagrams in one strip after the preceding item.
EXTERNAL_DIAGRAMS={
    '46FC9E2D79':{12:(3,69,461,315,615)},
    'D74446848E':{10:(2,64,344,160,447),12:(2,194,341,294,448),13:(2,305,345,520,448)},
    'E797F7FA34':{6:(1,418,415,490,524)},
    '8E074DB196':{5:(2,94,386,175,476),12:(2,67,702,362,790)},
    'CB535CA804':{12:(2,263,500,507,577)},
}
def external_diagram(q,doc,folder,bank,code):
    bounds=EXTERNAL_DIAGRAMS.get(code,{}).get(q['number'])
    if not bounds:return
    pg,x,y,x1,y1=bounds
    clip=crop(doc,(pg,y),(pg,y1),folder,q['id']+'-shared',bank,(x,x1))
    asset=clip['images'][0];q['figures'].append(asset)
    token='〔图%d〕'%len(q['figures']);q['stem']+='\n'+token
    source=q['source'];source['supplemental_question_regions']=clip['regions']
    if pg not in source['question_pages']:
        source['question_pages'].extend(clip['pages']);source['question_images'].extend(clip['images']);source['question_regions'].extend(clip['regions'])

def char_labels(chunk,doc,pattern):
    found=[]
    for pg in range(chunk['start'][0],chunk['end'][0]+1):
        lines=doc[pg-1].get_text('rawdict')['blocks']
        for b in lines:
            for line in b.get('lines',[]):
                chars=[c for s in line['spans'] for c in s['chars']]
                txt=''.join(c['c'] if not 0xd800<=ord(c['c'][0])<=0xdfff else '�' for c in chars)
                for m in pattern.finditer(txt):
                    x,y,*_=chars[m.start()]['bbox']
                    if not chunk['start']<=(pg,y)<chunk['end']:continue
                    tail=txt[m.end():].lstrip()
                    if tail.startswith(('的条件','的结论','的基础','的结果','的式子','中的')):continue
                    found.append((m[1],pg,y,x,tail))
    return found
PAREN=re.compile(r'(?<!图)[（(]\s*([1-9])\s*[）)]')
TASK=re.compile(r'任务([一二三四五])\s*[：:]')
CIRCLE=re.compile('([①②③④⑤])')
def arranged(source,alphabet):
    # Math super/subscripts in adjoining problems can place label 4 several
    # points above label 3 on the same line. Group by baseline before ordering.
    ordered=[]
    for pg in sorted({v[1] for v in source}):
        rows=[]
        for v in sorted((v for v in source if v[1]==pg),key=lambda v:v[2]):
            if not rows or v[2]-rows[-1][0][2]>8:rows.append([])
            rows[-1].append(v)
        for row in rows:
            for v in sorted(row,key=lambda v:v[3]):
                if len(ordered)<len(alphabet) and v[0]==alphabet[len(ordered)]:
                    ordered.append(v)
    return ordered if len(ordered)>=2 else []
def part_crop(marks,index,chunk,doc,folder,bank,name):
    _,pg,y,x,_=marks[index]
    row=[v for v in marks if v[1]==pg and abs(v[2]-y)<=8]
    left=x-2 if len(row)>1 else 14
    rights=[v[3]-2 for v in row if v[3]>x+4]
    right=min(rights) if rights else doc[pg-1].rect.width-14
    start=max(chunk['start'],(pg,max(0,min(v[2] for v in row)-8)))
    following=[v for v in marks if v[1]>pg or v[1]==pg and v[2]>y+8]
    end=min(chunk['end'],(following[0][1],following[0][2]-8)) if following else chunk['end']
    if end<=start:return None
    return crop(doc,start,end,folder,name,bank,(max(11,left),right))
def make_visual_parts(q,ps,ss,pcl,scl,pdf,sdf,folder,bank,tag):
    code=q['paper_id'].rsplit('-',1)[-1];n=q['number']
    if code=='CB535CA804' and n==17:
        return survey(q,pcl,ss,sdf,folder,bank,tag)
    pattern,alpha=(TASK,'一二三四五') if code=='46FC9E2D79' and n==19 else (PAREN,'123456789')
    p=arranged(char_labels(ps,pdf,pattern),alpha)
    s=arranged(char_labels(ss,sdf,pattern),alpha)
    if not p:return
    def tokens(assets,collection):
        out=[]
        for asset in assets:
            if asset not in collection:collection.append(asset)
            out.append(f'〔图{collection.index(asset)+1}〕')
        return '\n'.join(out)
    whole=tokens(pcl['images'],q['figures'])
    # The complete original problem retains diagrams, charts and definitions
    # below or next to the subquestion in the school's print layout.
    q['materials']=[{'id':'common-print','kind':'figure','text':whole}]
    for i,mark in enumerate(p):
        pclip=part_crop(p,i,ps,pdf,folder,bank,q['id']+f'-prompt{i+1:02d}') or pcl
        prompt=tokens(pclip['images'],q['figures'])
        sclip=part_crop(s,i,ss,sdf,folder,bank,q['id']+f'-work{i+1:02d}') if len(s)==len(p) else None
        work=tokens((sclip or scl)['images'],q['given_solution_figures'])
        label='任务'+mark[0] if pattern is TASK else '（'+mark[0]+'）'
        requires=[]
        if pattern is TASK and i==2:requires=[q['parts'][1]['id']]
        q['parts'].append(dict(tag,id=q['id']+f'-P{i+1:02d}',label=label,prompt=prompt,stem_text=mark[4] or q['title'],material_ids=['common-print'],requires=requires,
                              answer=work,given_answer='',given_solution=work,solution_steps=[work],solution_origin='source_facsimile',solution_figure_ids=refs(work),
                              source={'question_pages':pclip['pages'],'solution_pages':(sclip or scl)['pages']},review_note='' if sclip else '资料在同一区域合列各问，保留原题解答。'))
def survey(q,pcl,ss,sdf,folder,bank,tag):
    # The survey form uses circled numbers inside chart cells rather than separate paragraphs.
    prompts=['调查方式应填“普查”还是“抽样调查”？','本次调查一共调查了多少名学生？',
             '补全扇形统计图中③处的百分比。','补全④处的频数分布直方图。',
             '该校七年级有 500 名学生，估计其中 1 分钟跳绳次数大于等于 140 次的有多少人。']
    ans=['抽样调查','50 名','16%（评分标准也接受 18%）','','140 人或 150 人']
    marks=arranged(char_labels(ss,sdf,CIRCLE),'①②③④⑤')
    assert len(marks)==5
    q['materials']=[{'id':'survey','kind':'figure','text':q['stem']}]
    for i,prompt in enumerate(prompts):
        cl=part_crop(marks,i,ss,sdf,folder,bank,q['id']+f'-work{i+1:02d}')
        asset=cl['images'][0];q['given_solution_figures'].append(asset)
        token='〔图%d〕'%len(q['given_solution_figures'])
        q['parts'].append(dict(tag,id=q['id']+f'-P{i+1:02d}',label='①②③④⑤'[i],prompt=prompt,stem_text=prompt,material_ids=['survey'],requires=[],
                              answer=ans[i] or token,given_answer=ans[i] or token,given_solution=token,solution_steps=[token],solution_origin='source_facsimile',solution_figure_ids=refs(token),source={'solution_pages':cl['pages']},review_note=''))
