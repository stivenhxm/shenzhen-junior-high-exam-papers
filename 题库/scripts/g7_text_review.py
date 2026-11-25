"""Printed-page checks for recurring MathType conversion defects and reviewed source answers."""
from functools import lru_cache
import json
from pathlib import Path
import re

FORMULA = re.compile(r'\\\((.*?)\\\)',re.S)
# The Word equation object's preview retains these bars, which the legacy
# MathType reader exported as a lone right delimiter. Verified against the PDF.
LOST_FORMULAS = {
    'SZ-G7-T1-9417220145-Q20':r'|a|=2',
    'SZ-G7-T1-49608367EB-Q09':r'|a|=2',
    'SZ-G7-T1-F20647EC92-Q20':r'|a|=2',
    'SZ-G7-T1-5213143AC0-Q20':r'|a|=2',
    'SZ-G7-T1-7CA8E9585B-Q08':r'|c|>|a|',
}

def fix_formula(match, missing):
    inner=match[1]
    if inner.strip()==r'\right .' and missing:
        inner=missing
    inner=re.sub(r'\\(pi|otimes)(?=[a-z])',r'\\\1 ',inner)
    inner=inner.replace(r'\@#',r'\#')
    # The second script lies on the same printed baseline, e.g. C_{n+1}.
    inner=re.sub(r'([_^])\s*\{\s*([mn])\s*\}\s*\1\s*\{\s*(\+\s*(?:1|n))\s*\}',r'\1{\2\3}',inner)
    return r'\('+inner+r'\)'

def normalize_equations(value, missing):
    if isinstance(value,str):
        return FORMULA.sub(lambda match:fix_formula(match,missing),value)
    if isinstance(value,list):
        return [normalize_equations(v,missing) for v in value]
    if isinstance(value,dict):
        return {k:normalize_equations(v,missing) for k,v in value.items()}
    return value

@lru_cache(maxsize=1)
def supplements():
    path=Path(__file__).with_name('g7_solution_reviews.json')
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else {}

def review(q):
    q=normalize_equations(q,LOST_FORMULAS.get(q['id']))
    if q['id'] in ('SZ-G7-T1-F20647EC92-Q20','SZ-G7-T1-5213143AC0-Q20'):
        note='资料把倒数等于自身的数只列为 1，漏掉 −1。两种取值都符合原题。'
        parts=q['parts']
        answers=[r'\(a=\pm2,\ b=3,\ c=\pm1\)。','0 或 2。']
        steps=[[r'由 \(|a|=2\) 得 \(a=\pm2\)；−3 的相反数是 3。',
                r'由 \(c=1/c\) 得 \(c^2=1\)，所以 \(c=1\) 或 \(c=-1\)。'],
               [r'因为 \(a>c\)，且 \(a=\pm2,c=\pm1\)，所以 \(a=2\)，而 \(c\) 的两种取值均可。',
                r'代入 \(2a-b+c=1+c\)。当 \(c=-1\) 时为 0，当 \(c=1\) 时为 2。']]
        for part,ans,sol in zip(parts,answers,steps,strict=True):
            part.update(answer=ans,solution_steps=sol,solution_origin='source_checked_with_correction',review_note=note)
        q.update(answer='\n'.join(p['label']+p['answer'] for p in parts),
                 solution_steps=[s for seq in steps for s in seq],solution_origin='source_checked_with_correction',review_note=note)
        q['solution']='\n'.join(q['solution_steps'])
    if q['id']=='SZ-G7-T1-98172A2C96-Q22':
        note='资料第 11 页的答案栏只列出第一空，解答中又将正数 a+4 去绝对值时变了号，误得 −2。第二空的距离和应为 6。'
        for part in q['parts']:
            part.setdefault('solution_origin','source_transcribed')
        second=next(p for p in q['parts'] if p['id']==q['id']+'-P02')
        second.update(answer=r'第一空为 \(\lvert a+4\rvert\)，第二空为 \(6\)。',
                      solution_steps=[
                          r'表示 \(a\) 与 \(-4\) 的两点之间的距离为 \(\lvert a-(-4)\rvert=\lvert a+4\rvert\)。',
                          r'由 \(-4<a<2\)，得 \(a+4>0\)，\(a-2<0\)。',
                          r'所以 \(\lvert a+4\rvert+\lvert a-2\rvert=(a+4)+(2-a)=6\)。'],
                      solution_origin='source_checked_with_correction',review_note=note)
        q.update(answer='\n'.join(p['label']+' '+p['answer'] for p in q['parts']),
                 solution_steps=[(p['label']+' ' if i==0 else '')+step
                                 for p in q['parts'] for i,step in enumerate(p['solution_steps'])],
                 solution_origin='source_checked_with_correction',review_note=note)
        q['solution']='\n'.join(q['solution_steps'])
    added=supplements().get(q['id'])
    if added and q['solution_origin']=='source_answer_only':
        if isinstance(added,list): added={'steps':added}
        q.update(solution_steps=added['steps'],solution='\n'.join(added['steps']),
                 solution_origin='editorial_solution',review_note='资料只列答案。下列步骤按原题补写，可对照答案页。')
        if 'answer' in added:q['answer']=added['answer']
    return q
