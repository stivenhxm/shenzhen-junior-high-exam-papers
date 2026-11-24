"""Reviewed answer summaries and original-page corrections for three Shenzhen mock exams."""

summaries = {
    '605B79D6C4':[
        ['1','33','−6','−37'], '6 或 0', ['三视图见〔图2〕','32 平方厘米','9 个'],
        ['B 地在 A 地以东 20 千米','25 千米','9 升'],['6.4 万辆','3.8 万辆','61.3 万辆'],
        [r'\(\frac{6^2}{5\times7}\)，\(\frac{7^2}{6\times8}\)',r'\(\frac{12}{7}\)'],
        ['24 个单位长度','2 秒或 4 秒','正确，持续 0.5 秒，定值为 6 个单位长度']],
    '63B44AB70E':[
        ['12','−1','8','−24'],r'\(2xy-3x^2y+3xy^2\)，值为 8。',
        ['4 种','见〔图2〕','见〔图3〕'],[r'\(b<a<0<c<-b\)',r'\(a+c=0\)'],
        ['星期二，1.11 米；星期日，0.35 米','比上周末上升 0.35 米','至少补油 12.5 升'],
        [r'250，\(5x-25\)，200，\(4x\)（元）',r'甲店 \(5x+225\) 元，乙店 \(4x+200\) 元','甲店 375 元，乙店 320 元，选乙店'],
        [r'\(x=5\) 或 \(-1\)；最小值为 5',r'\(-3\) 或 \(4\)；\(-5\) 或 \(\frac{11}{3}\)',r'最小值为 17，\(-4\le x\le-1\)']],
    '7923F98999':[
        ['−10','39'],[r'\(x=\frac{2}{7}\)',r'\(x=-3\)'],r'\(a^2b+ab^2-4\)，值为 −2。',
        [r'\(k=2\)',r'\(m+n=-4\)'],[r'250，\(5x-25\)，200，\(4x\)（元）',r'甲店 \(5x+225\) 元，乙店 \(4x+200\) 元','甲店 375 元，乙店 320 元，选乙店'],
        ['是','30°、20° 或 40°','9、12 或 18 秒','2.4、4 或 6 秒'],
        ['1；11',r'① \(\frac{9}{8}\) 秒；② \(\frac{12}{5}\)、\(4\)、\(\frac{4}{3}\) 或 \(\frac{4}{5}\) 秒']]
}

def corrected(q, replacements, note):
    for index, steps in replacements.items():
        part=q['parts'][index-1]
        part.update(solution_origin='source_checked_with_correction',review_note=note,solution_steps=steps)
    q.update(solution_origin='source_checked_with_correction',review_note=note)
    q['solution_steps']=[p['label']+' '+s if i==0 else s for p in q['parts'] for i,s in enumerate(p['solution_steps'])]
    q['solution']='\n'.join(q['solution_steps'])

def answer_key(paper_id):
    rows = summaries.get(paper_id.rsplit("-",1)[-1], [])
    return {i:(v if isinstance(v,str) else "\n".join(f"（{n}）{a}" for n,a in enumerate(v,1)))
            for i,v in enumerate(rows,14)}

def apply(paper_id, qs):
    code=paper_id.rsplit("-",1)[-1]
    if code=='63B44AB70E':
        q=qs[16]
        q['parts'][1]['solution_steps'].append(r'由图可见 \(a<0<c\)，又有 \(|a|=|c|\)，所以 \(a+c=0\)。')
        q['solution_steps'].append(q['parts'][1]['solution_steps'][-1])
        q['solution']='\n'.join(q['solution_steps'])
        corrected(qs[17],{3:[r'将各段航程的绝对值相加，\(12+8+15+6+12+7+11+4=75\)（千米）。',
            r'还需补油 \(75\times0.5-25=12.5\)（升）。']},'资料在第（3）问把题干中的 −7 千米抄成了 −4 千米。按原卷数据重新计算。')
        corrected(qs[18],{1:[r'每盒球价 \(20\div4=5\) 元，两店分别收球拍费 \(5\times50=250\) 元和 \(250\times0.8=200\) 元。',
            r'甲店赠送 5 盒，球费为 \(5(x-5)\) 元；乙店球费为 \(5x\times0.8=4x\) 元。'],
            2:[r'甲店共收 \(250+5(x-5)=5x+225\) 元。',r'乙店共收 \(200+4x\) 元。'],
            3:[r'代入 \(x=30\)，甲店应付 \(5\times30+225=375\) 元，乙店应付 \(4\times30+200=320\) 元。',
               '320 元较少，选择乙店。']},'题干写明 4 盒共 20 元。资料按每盒 20 元计算，且第（3）问代入时另有常数项笔误。参考解答按题干单价计算。')
    if code=='7923F98999':
        q=qs[18]
        part=q['parts'][1]
        if '深入研究' in part['prompt']:
            before,after=part['prompt'].split('深入研究',1)
            part['prompt']=part['stem_text']=before.rstrip()
            q['materials'].append({'id':'rotation','kind':'text','text':after.lstrip('：:\n ').strip(),'paper_blocks':[98,99,100]})
            for later in q['parts'][2:]:
                later['material_ids'].append('rotation')
    return qs
