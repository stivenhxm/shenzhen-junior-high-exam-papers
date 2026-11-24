"""Import the Chinese OOXML original/solution pairs used by the question bank.

Requires Python 3.11, lxml, Pillow, olefile and mtef-py 1.0.1. All source paths in the
selection manifest are relative to the Git repository. Run --help for the CLI.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from batch_content_xml import NUMBER, sections


TEX = re.compile(r'\\\((.*?)\\\)', re.S)
FIG = re.compile(r'〔图(\d+)〕')
CIRCLE = '①②③④⑤⑥⑦⑧⑨'
CN = '一二三四五六七八九'
PAREN = re.compile(r'[（(]\s*([1-9])\s*[）)]')
DETAIL_MARK = re.compile(r'【小问\s*(\d+)\s*详解】')
STANDARD = re.compile(r'(?:问题|任务|活动)\s*([1-9一二三四五六七八九])\s*[：:|]')
CHOICE = re.compile(r'(?<![A-Za-z])([A-D])[.．、]\s*')


def plain_number(value):
    return CN.index(value)+1 if value in CN else int(value)


def normalized(s):
    # Word occasionally typesets the *label itself* as an independent equation.
    def replace(match):
        inner = re.sub(r'\\(?:left|right|rm|mathrm)\b|[{}\s]','',match[1])
        if re.fullmatch(r'[（(][1-9][）)]',inner):
            return '（'+inner[1]+'）'
        if inner in CIRCLE and len(inner)==1:
            return inner
        if re.fullmatch('[1-9]',inner) and re.search(r'(?:问题|任务|小问|活动)\s*$',s[:match.start()]):
            return inner
        return match[0]
    # The two adjacent MathType subscript objects in the recurrence on the
    # October paper represent a single n−1 index (checked against printed p.3).
    s=s.replace('a_{ n } _{ -1 }','a_{n-1}')
    # This bank's reused Equation object retains a stale expression in its OLE
    # payload. The Word preview and the printed source both show only C.
    s=s.replace(r'\(C-y+1-m=0\)',r'\(C\)')
    return TEX.sub(replace,s)


@dataclass
class DocumentText:
    content: str
    ranges: list

    @classmethod
    def from_blocks(cls,blocks,strip_number=False):
        texts=[]
        ranges=[]
        offset=0
        for i,(block,text) in enumerate(blocks):
            text=normalized(text)
            if i==0 and strip_number:
                text=NUMBER.sub('',text,count=1)
            texts.append(text)
            ranges.append((offset,offset+len(text),block))
            offset+=len(text)+1
        return cls('\n'.join(texts),ranges)

    def ids(self, start, end):
        return [i for a,b,i in self.ranges if a<end and b>start]


def masked(s):
    return TEX.sub(lambda m:'~'*len(m[0]),s)


def source_marks(s):
    # A reference such as "在（1）的条件下" must stay inside the prompt.
    text=masked(s)
    matches=[]
    for m in PAREN.finditer(text):
        pos=m.start()
        if pos and text[pos-1] in '图在如由问第据用合班组':
            continue
        if text[m.end():].lstrip().startswith(('的条件','的结论','的结果','班')):
            continue
        if text[:pos].rstrip().endswith('|') and text[m.end():].lstrip().startswith('|'):
            continue
        if int(m[1])==len(matches)+1:
            matches.append((int(m[1]),m.start(),m.end(),m[0]))
    return matches if len(matches)>=2 else []


def special_marks(s):
    matches=[]
    for m in STANDARD.finditer(masked(s)):
        n=plain_number(m[1])
        if n==1 or matches and n==matches[-1][0]+1:
            matches.append((n,m.start(),m.end(),m[0].rstrip('：:| ')))
    return matches if len(matches)>=2 else []


def circle_marks(s):
    found=[]
    for m in re.finditer('['+CIRCLE+']',masked(s)):
        n=CIRCLE.index(m[0])+1
        if n==len(found)+1:
            found.append((n,m.start(),m.end(),m[0]))
    return found if len(found)>=2 else []


def split_at(s,marks):
    return [(s[b:marks[i+1][1] if i+1<len(marks) else len(s)].strip(),b,
             marks[i+1][1] if i+1<len(marks) else len(s),label) for i,(_,_,b,label) in enumerate(marks)]


def remove_heading(value):
    return re.sub(r'^【(?:详解|解答)】\s*','',value).strip()


def solution_steps(s):
    s=re.split(r'【(?:点睛|点评)】',s,maxsplit=1)[0].strip()
    detail=list(re.finditer(r'【(?:详解|解答)】',s))
    if detail:
        s=s[detail[0].end():].strip()
    elif (first:=DETAIL_MARK.search(s)) is not None:
        s=s[first.start():]
    s=remove_heading(s)
    lines=[p.strip() for p in s.splitlines() if p.strip()]
    return lines or []


def details(whole):
    worked=re.search(r'【(?:详解|解答)】',whole)
    # Classic source layout may put all "分析" before the worked solution.
    start=worked.end() if worked else 0
    end=re.search(r'【(?:点睛|点评)】',whole[start:])
    return start,start+end.start() if end else len(whole)


def solution_chunks(whole, source_type, expected):
    explicit=[(int(m[1]),m.start(),m.end(),m[0]) for m in DETAIL_MARK.finditer(whole)]
    if len(explicit)==expected:
        end=re.search(r'【(?:点睛|点评)】',whole)
        content=whole[:end.start()] if end and end.start()>explicit[-1][1] else whole
        return split_at(content,explicit)
    start,end=details(whole)
    fragment=whole[start:end]
    marks=source_type(fragment)
    if len(marks)!=expected:
        return []
    return [(txt,start+a,start+b,label) for txt,a,b,label in split_at(fragment,marks)]


def answer_chunks(answer, marks_func, count):
    marks=marks_func(answer)
    if len(marks)==count:
        return [v[0] for v in split_at(answer,marks)]
    elif marks_func is not circle_marks:
        alternate=circle_marks(answer)
        if len(alternate)==count:
            return [v[0].lstrip('.．、 ') for v in split_at(answer,alternate)]
    numbered=list(re.finditer(r'(?<!\S)(\d{2})[.．]\s+', masked(answer)))
    if (len(numbered)==count and numbered[0].start()==0 and
            all(int(m[1])==int(numbered[0][1])+i for i,m in enumerate(numbered))):
        return [answer[m.end():numbered[i+1].start() if i+1<count else len(answer)].strip()
                for i,m in enumerate(numbered)]
    # Some answer keys omit printed numbers and use one semicolon between tasks.
    filtered=masked(answer)
    sep=list(re.finditer(r'[；;]\s*',filtered))
    bounds=[0]+[x.end() for x in sep]+[len(answer)]
    parts=[answer[a:b].strip('；; \t\n') for a,b in zip(bounds,bounds[1:])]
    parts=[p for p in parts if p]
    return parts if len(parts)==count else []


def refs(text):
    return list(dict.fromkeys(int(m[1]) for m in FIG.finditer(text)))


def section_type(heading):
    if re.search('选择|单选',heading):
        return '选择题'
    if '填空' in heading:
        return '填空题'
    return '计算题' if '计算题' in heading else '解答题'


def choices_of(text):
    matches=[]
    for mark in reversed(list(CHOICE.finditer(masked(text)))):
        if mark[1]==chr(68-len(matches)):
            matches.append(mark)
            if len(matches)==4:
                break
    if len(matches)!=4:
        raise ValueError('未能定位四个选项：'+text[:160])
    matches.reverse()
    opts=[{'label':m[1],'text':text[m.end():matches[i+1].start() if i<3 else len(text)].strip()}
          for i,m in enumerate(matches)]
    if any(not v['text'] for v in opts):
        raise ValueError('选择题选项为空：'+str(opts))
    return text[:matches[0].start()].strip(),opts


def title_from(stem):
    text=TEX.sub('',stem)
    text=FIG.sub('',text)
    text=re.sub(r'^[（(]1[）)]|【[^】]*】','',text).strip(' ，：:；;．。')
    candidates=[s.strip() for s in re.split('[：:，,；;．。？！?!\n]',text) if s.strip()]
    primary=next((s for s in candidates if len(s)>=4),None)
    if not primary:
        return '数学计算'
    return primary if len(primary)<=32 else primary[:31]+'…'


def make_parts(q,pdoc,sdoc,answer,worked,worked_offset):
    stem=pdoc.content
    spans=special_marks(stem)
    finder=special_marks
    if not spans:
        spans=source_marks(stem)
        finder=source_marks
    if not spans:
        return
    if q['type']=='填空题' and re.search(r'其中.{0,8}(?:正确|错误).{0,12}(?:有|个数)',stem) and not answer_chunks(answer,finder,len(spans)):
        return
    materials=q['materials']
    material_blocks={}
    def material(id_,kind,text,ids):
        if not text.strip():
            return
        materials.append({'id':id_,'kind':kind,'text':text.strip(),'paper_blocks':ids})
        material_blocks[id_]=ids
    material('context','text',stem[:spans[0][1]],pdoc.ids(0,spans[0][1]))
    # Inline illustrations (including equations rendered as images) stay inside
    # their own prompts; diagram-only paragraphs and external tables can be shared.
    for a,b,idx in pdoc.ranges:
        block=stem[a:b].strip()
        if b<=spans[0][1]:
            continue
        if re.fullmatch(r'(?:〔图\d+〕\s*)+',block):
            material('fig-'+str(idx),'figure',block,[idx])
        elif not any(a<=start<b for _,start,_,_ in spans) and any(block==t['text'] for t in q['tables']):
            material('table-'+str(idx),'table',block,[idx])
    shared=[m['id'] for m in materials]
    source_answers=answer_chunks(answer,finder,len(spans))
    source_details=solution_chunks(worked,finder,len(spans))
    pieces=split_at(stem,spans)
    mapped=[]
    for i,(prompt,a,b,label) in enumerate(pieces):
        stage=re.search(r'(?m)^\s*环节[一二三四五][：:]',prompt) if finder is special_marks else None
        inherited=shared.copy()
        if stage:
            pos=stem.index(prompt,a,b)+stage.start()
            mat=f'stage-{i+2}'
            material(mat,'text',stem[pos:b],pdoc.ids(pos,b))
            shared=[*shared,mat]
            b=pos
            prompt=prompt[:stage.start()].strip()
        part_answer=source_answers[i] if source_answers else ''
        part_answer=re.split(r'(?m)^\s*环节[一二三四五][：:]',part_answer,maxsplit=1)[0].strip()
        sol,sa,sb,_=source_details[i] if source_details else ('',0,0,'')
        children=circle_marks(prompt)
        nested_answers=answer_chunks(part_answer,circle_marks,len(children)) if children else []
        nested_sol=solution_chunks(sol,circle_marks,len(children)) if children else []
        if q['id'].endswith('MONTH-1B735BB8-Q19') and label in ('（2）','(2)') and len(children)==3 and not nested_sol:
            # The source labels the third derivation “（2）由（1）可知” in place
            # of ③. Keep the original combined solution verbatim on the parent.
            third=sol.find('（2）由（1）可知')
            first_two=circle_marks(sol)
            if len(first_two)==2 and third>first_two[-1][2]:
                nested_sol=split_at(sol,[*first_two,(3,third,third+3,'③')])
        # Numbered claims offered for judgement are part of the prompt. Split only
        # when the worked source or answer key also marks separate answers.
        independent=all(re.search(r'求|填|计算|若|证明|探究|讨论|比较|写出|多少|_{2,}',v[0]) for v in split_at(prompt,children)) if children else False
        if children and (len(circle_marks(part_answer))==len(children) or (independent and nested_sol)):
            submat=f'condition-{i+1}'
            material(submat,'text',prompt[:children[0][1]],pdoc.ids(a,a+children[0][1]))
            deps=inherited+([submat] if submat in material_blocks else [])
            for j,(pp,x,y,lab) in enumerate(split_at(prompt,children)):
                tt,t1,t2,_=nested_sol[j] if nested_sol else ('',0,0,'')
                mapped.append((i,pp,a+x,a+y,label+lab,nested_answers[j] if nested_answers else '',
                               tt,sa+t1,sa+t2,deps,part_answer,sol))
        else:
            mapped.append((i,prompt,a,b,label,part_answer,sol,sa,sb,inherited,answer,worked))
    index_ids={}
    prior_parts={}
    # These particular tasks refer to the preceding completed table, method
    # or drawing without printing a numbered reference. The pairs were checked
    # against the source, and use the fixed paper fingerprint / question number.
    implied={
        ('9860D2F4',15,4):[1,2,3], ('9860D2F4',19,2):[1], ('9860D2F4',19,3):[1,2],
        ('F139AE08',19,3):[1,2], ('CC59C319',18,2):[1], ('CC59C319',18,3):[2],
        ('CC59C319',20,2):[1], ('CC59C319',20,3):[2], ('AAB74635',16,2):[1],
        ('1B735BB8',17,3):[2], ('2453CED5',23,2):[1], ('90DB1707',18,2):[1],
        ('B538FF37',22,2):[1],
    }
    for idx,(group,prompt,a,b,label,ans,sol,sa,sb,deps,key_all,solution_all) in enumerate(mapped,1):
        deps=list(deps)
        for m in materials:
            if m['id'] in deps and m['kind'] in ('figure','table') and prompt.strip()!=m['text']:
                prompt=prompt.replace(m['text'],'').strip()
        if not prompt:
            prompt=stem[a:b].strip()
        req=[]
        for n in re.finditer(r'(?:在|由|根据|利用|结合|从|依据)\s*(?:第)?\s*[（(](\d+)[）)]',masked(prompt)):
            req.extend(index_ids.get(int(n[1])-1,[]))
        for n in re.finditer(r'(?:在|由|根据|利用|结合)(任务|问题)([1-9一二三四五六七八九])',masked(prompt)):
            label_ref=n[1]+n[2]
            for g,(_,_,_,orig_label) in enumerate(pieces[:group]):
                if orig_label.replace(' ','')==label_ref:
                    req.extend(index_ids.get(g,[]))
        for g in implied.get((q['paper_id'].rsplit('-',1)[-1],q['number'],group+1),[]):
            req.extend(index_ids.get(g-1,[]))
        req=list(dict.fromkeys(req))
        for key in req:
            prior=prior_parts[key]
            mat_id='prior-'+key.rsplit('-',1)[-1]
            # Preserve the quantities introduced only in a previous question.
            # If the key says "see solution", also supply the diagram/derivation.
            if mat_id not in material_blocks:
                inherited='前问'+prior['label']+'的题面：'+prior['prompt']
                if '见解析' in prior['answer'] or '见详解' in prior['answer']:
                    prior_figs=q['given_solution_figures']
                    def remap(m):
                        asset=prior_figs[int(m[1])-1]
                        if asset not in q['figures']:
                            q['figures'].append(asset)
                        return f"〔图{q['figures'].index(asset)+1}〕"
                    summary='\n'.join(prior['solution_steps'])
                    inherited+='\n前问作答依据：'+FIG.sub(remap,summary)
                material(mat_id,'text',inherited,prior['source']['paper_block_ids'])
            deps.append(mat_id)
            deps.extend(k for k in prior['material_ids'] if k.startswith('condition-'))
        deps=list(dict.fromkeys(deps))
        pid=q['id']+f'-P{idx:02d}'
        index_ids.setdefault(group,[]).append(pid)
        note=''
        if not sol:
            sol=solution_all
            sa,sb=0,len(worked)
            note='资料采用合并详解，此处保留相应原文。'
        steps=solution_steps(sol) or solution_steps(worked)
        if not steps:
            raise ValueError(pid+' 无参考解法')
        given_answer=ans
        if not ans:
            # Use the source's separately marked solution where the answer strip
            # combines several questions and does not label this value.
            ans=steps[-1] if sol!=solution_all else key_all
            note+='答案栏未单列该问，答案取自配套资料。'
        answer_ids=sdoc.ids(worked_offset+sa,worked_offset+sb)
        block_ids=sorted(set(pdoc.ids(a,b)+[v for mid in deps for v in material_blocks[mid]]))
        q['parts'].append({'id':pid,'label':label,'prompt':prompt,'stem_text':prompt,
            'material_ids':deps,'requires':list(dict.fromkeys(req)),'given_answer':given_answer,'answer':ans,
            'given_solution':sol,'solution_steps':steps,'solution_figure_ids':refs(ans+'\n'+sol),
            'source':{'paper_block_ids':block_ids,'solution_block_ids':answer_ids},
            'review_note':note})
        prior_parts[pid]=q['parts'][-1]


def assemble(paper_rows,solution_rows,paper_id,worked_answers=None):
    if len(paper_rows)!=len(solution_rows):
        raise ValueError(f'{paper_id} 原卷{len(paper_rows)}题，解析版{len(solution_rows)}题')
    questions=[]
    for paper,source in zip(paper_rows,solution_rows):
        n=paper['number']
        if n!=source['number']:
            raise ValueError(f'{paper_id} 题号未能对齐')
        qid=paper_id+f'-Q{n:02d}'
        pd=DocumentText.from_blocks(paper['blocks'],True)
        sd=DocumentText.from_blocks(source['blocks'])
        am=re.search(r'【答案】',sd.content)
        sm=re.search(r'【解析】',sd.content)
        if not sm:
            sm=re.compile(r'【(?:详解|解答)】').search(sd.content,am.end() if am else 0)
        if not sm or (am and sm.start()<am.end()) or sd.content.count('【答案】')>1:
            raise ValueError(qid+' 未能唯一配对答案与解析')
        supplied=sd.content[am.end():sm.start()].strip() if am else ''
        answer=supplied or (worked_answers or {}).get(n, '')
        worked=sd.content[sm.end():].strip()
        start=sd.content.index(worked,sm.end())
        if not answer or not worked:
            raise ValueError(qid+' 缺少资料答案或解析')
        typ=section_type(paper['section'])
        stem,choices=choices_of(pd.content) if typ=='选择题' else (pd.content,[])
        steps=solution_steps(worked)
        if not steps:
            raise ValueError(qid+' 参考解答为空')
        pts=re.search(r'每(?:小)?题\s*(\d+)\s*分',paper['section'])
        q={'id':qid,'paper_id':paper_id,'number':n,'type':typ,'points':int(pts[1]) if pts else None,
           'title':title_from(stem),'stem':stem,'choices':choices,'figures':paper['figures'],
           'tables':[{'text':normalized(t['text']),'rows':[[[normalized(v) for v in cell] for cell in row] for row in t['rows']]} for t in paper['tables']],
           'given_answer':supplied,'answer':answer,'given_solution':worked,'given_solution_figures':source['figures'],
           'solution':'\n'.join(steps),'solution_steps':steps,'solution_origin':'source_transcribed' if supplied else 'source_solution_summary',
           'solution_figure_ids':refs(answer+'\n'+worked),'materials':[],'parts':[],'review_note':'',
           'source':{'paper_body_blocks':[paper['blocks'][0][0],paper['blocks'][-1][0]],
                     'solution_body_blocks':[source['blocks'][0][0],source['blocks'][-1][0]]}}
        if not choices:
            make_parts(q,pd,sd,answer,worked,start)
            if not supplied:
                for part in q['parts']:
                    part['given_answer']=''
        questions.append(q)
    return questions


def parse_pair(paper_docx, solution_docx, paper_id, bank_root):
    import g7_mock_reviews
    questions = assemble(sections(Path(paper_docx),Path(bank_root)),
                         sections(Path(solution_docx),Path(bank_root)),paper_id,g7_mock_reviews.answer_key(paper_id))
    return g7_mock_reviews.apply(paper_id,questions)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--bank',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    items=json.loads(args.selection.read_text(encoding='utf-8-sig'))['papers']
    from batch_import import pending
    items, skipped = pending(args.bank.resolve(), items)
    if skipped:
        print(f'已跳过 {len(skipped)} 份已登记或重复试卷。')
    args.output.mkdir(parents=True,exist_ok=True)
    for row in items:
        paths=[args.bank.parent/row[k] for k in ('paper','solution')]
        for k,path in zip(('paper','solution'),paths):
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row[k+'_sha256']:
                raise ValueError(f'{path} 与所登记指纹不符')
        questions=parse_pair(*paths,row['id'],args.bank)
        if row.get('answer_markers') and len(questions)!=row['answer_markers']:
            raise ValueError(row['id']+' 正文与答案数量不一致')
        path=args.output/(row['id']+'.json')
        tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(questions,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        tmp.replace(path)
        print(f'{row["id"]} {len(questions)} 题，{sum(len(q["parts"]) for q in questions)} 小问',flush=True)


if __name__=='__main__':
    main()
