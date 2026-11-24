"""Restore Word symbol-font glyphs and contiguous scripts in the printed spring papers."""
import re
from g7_text_review import FORMULA, fix_formula

SYMBOLS = str.maketrans({'\uf05c':'∴','\uf0d0':'∠','Ð':'∠','\uf02a':'*'})

def formula(match):
    source = fix_formula(match,None)
    source = re.sub(r'\^\s*\{\s*m\s*\}\s*\^\s*\{\s*-n\s*\}',r'^{m-n}',source)
    return re.sub(r'S_\{\s*(正方形|\\vartriangle)\s*\}\s*_\{\s*([A-Z]+)\s*\}',r'S_{\1 \2}',source)

def normalize(value):
    if isinstance(value,str):
        return FORMULA.sub(formula,value.translate(SYMBOLS))
    if isinstance(value,list):
        return [normalize(v) for v in value]
    if isinstance(value,dict):
        return {k:normalize(v) for k,v in value.items()}
    return value

def review(question):
    q=normalize(question)
    if q['id']=='SZ-G7-T2-344B113D97-Q12':
        q.update(answer='A',solution_origin='source_checked_with_correction',
                 review_note='答案栏印 C。按原图分别作平行辅助线并用三角形外角性质可验证四个结论均成立，与原详解一致，选 A。')
    if q['id']=='SZ-G7-T2-6AEA890D22-Q08':
        q.update(answer='A',solution_origin='source_checked_with_correction',
                 review_note='资料答案栏为 A，详解末行误写 B。边长 x 的正方形比边长 x−1、x+1 的长方形面积大 1，对应 A。')
        q['solution_steps']=[re.sub(r'故选\s*[：:]?\s*B','故选 A',s) for s in q['solution_steps']]
        q['solution']='\n'.join(q['solution_steps'])
    return q
