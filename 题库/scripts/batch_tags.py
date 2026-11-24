"""Apply the reviewed, source-specific topic assignments for the G7 batch.

Review keys address a source paper and the original number encoded in its
stable question ID. '/' separates printed subquestions, ':' their circled
subparts, '+' complementary skills, and '|' introduces a custom title.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
# Short names keep the review sheet readable. The canonical data uses only
# official v0.2 IDs. A knowledge-only assignment always states the gap.
TOPICS = {
    'pos': ('E.N01.01.01', '用正负数表示相对基准的变化'),
    'class': ('E.N01.01.02', '按给定标准分类有理数'),
    'axis': ('E.N01.02.01', '在数轴上定位并读数'),
    'opp': ('E.N01.02.02', '利用相反数关系求数'),
    'rec': ('E.N01.02.02', '利用倒数关系求数'),
    'abs': ('E.N01.03.01', '由绝对值确定距离或数值'),
    'sign': ('E.N01.03.02', '依据符号化简绝对值'),
    'dist': ('E.N01.03.01?', '用数轴上两点的距离建立数量关系', '考点直接针对到原点的距离，本题还涉及任意两点间的距离。'),
    'motion': ('E.N01.03.01? E.N06.04.01', '用数轴坐标和路程关系分析动点', '需把运动方向、相对位置和时间一起纳入数轴距离模型。'),
    'cmp': ('E.N01.04.01', '比较有理数的大小'),
    'num': ('E.N01.05.01', '按运算顺序计算有理数'),
    'new': ('E.N01.05.01?', '按题设的新运算规则计算', '先将题设的新符号或新运算翻译为通常运算，再按运算顺序计算。'),
    'sci': ('E.N01.06.01', '在普通记数与科学记数之间转换'),
    'near': ('E.N01.06.02', '按指定精度取近似数'),
    'zero': ('E.N02.01.02', '由非负量之和为零确定字母的值'),
    'expr': ('E.N03.01.01', '用代数式表示数量关系'),
    'algdef': ('M.N03.01', '辨认代数式与等式、不等式', '本问要求辨认代数式的形式，没有要求列式或代入。'),
    'val': ('E.N03.01.02', '利用已知数值或整体关系求式值'),
    'term': ('E.N03.02.01', '识别整式的项、系数与次数'),
    'like': ('E.N03.02.02', '根据同类项条件求参数'),
    'simp': ('E.N03.03.01', '去括号并合并同类项'),
    'simval': ('E.N03.03.01 E.N03.01.02', '先化简整式再代入求值'),
    'ind': ('E.N03.03.02', '由式值与字母无关求系数'),
    'power': ('E.N03.04.01', '利用幂的运算法则化简'),
    'mul': ('E.N03.05.01', '用分配律展开整式乘积'),
    'sq': ('E.N03.06.01', '利用乘法公式简化计算'),
    'seq': ('E.N03.09.01', '归纳图形或数表规律并表示一般项'),
    'next': ('E.N03.09.01?', '依照已发现的规律推算指定项', '主要要求求出下一项或某个数值，未要求写出一般式。'),
    'why': ('E.N03.09.02', '用代数运算解释数量规律'),
    'eqdef': ('M.N06.02', '依据定义辨别一元一次方程', '任务是辨认方程的次数和未知数个数，目录中的考点侧重解方程。'),
    'eq': ('E.N06.02.01', '解一元一次方程'),
    'check': ('E.N06.01.01', '检验已知数是否为方程的解'),
    'equal': ('E.N06.01.02', '判断等式变形是否保持原解'),
    'model': ('E.N06.04.01', '列一次方程解决数量关系问题'),
    'cost': ('E.N06.04.01?', '按计费规则比较方案并计算费用', '除建立一次关系外，还需区分适用条件或比较不同方案。'),
    'costnum': ('E.N01.05.01?', '按实际折扣或费率逐项计算并比较费用', '单纯的有理数运算只覆盖计算环节，还需区分收费或优惠条件。'),
    'plan': ('E.N09.03.02', '列举符合多重约束的整数方案'),
    'seg': ('E.G01.01.01', '利用点的位置关系求线段长度'),
    'line': ('E.G01.01.02', '利用线段或直线的基本事实说明理由'),
    'angle': ('E.G01.02.01', '用角的和差或度量关系求角'),
    'anglecmp': ('M.G01.02', '比较两个角的大小', '本问要求从叠合位置比较角，未要求角度换算或和差计算。'),
    'bis': ('E.G01.02.02', '利用角平分关系求角'),
    'draw': ('E.G12.01.01', '用尺规完成基本作图'),
    'ar': ('E.G02.04.01', '通过分割或补形求面积'),
    'polygon': ('M.G02.03', '由多边形的结构计算对角线或分割数量', '本题计算对角线或分割数量，现有考点聚焦内外角和。'),
    'solid': ('E.G11.01.01', '辨认基本几何体及其特征'),
    'net': ('E.G11.01.01', '判定展开折叠后对应的面与边'),
    'surface': ('E.G11.01.02', '由几何体及展开图求表面数量关系'),
    'vol': ('M.G11.01', '由立体尺寸求体积或体积比', '现有考点主要描述展开折叠和表面数量关系，没有专列体积计算。'),
    'euler': ('M.G11.01', '利用多面体的顶点、棱和面之间的数量关系', '需利用或探究多面体的欧拉关系，现有立体图形考点未单列该关系。'),
    'cross': ('M.G11.01', '判断平面截几何体所得的截面', 'v0.2 有立体图形知识点，暂无专门刻画截面形状的考点。'),
    'sweep': ('M.G11.01', '辨认点线面运动形成的图形', '现有考点未细分点动成线、线动成面和面动成体。'),
    'view': ('E.G11.02.01', '从指定方向观察并判断几何体视图'),
    'cubes': ('E.G11.02.01?', '根据视图约束还原小立方块的排布', '辨认视图后还需计数或求堆叠数量的范围。'),
    'fold': ('E.G07.01.02', '利用折叠前后的对应关系计算'),
    'rot': ('E.G07.03.02', '利用旋转前后的对应关系求角'),
    'survey': ('E.S01.01.01', '判断调查对象并选择普查或抽样'),
    'sample': ('E.S01.01.02', '评价抽样方式的代表性'),
    'dtype': ('M.S02.06', '区分定性数据与定量数据', '考点侧重比较数据分类方案，本题只要求辨识数据类型。'),
    'chart': ('E.S01.03.01', '联读统计图表补全调查信息'),
    'plot': ('M.S01.03', '根据逐日数据绘制折线统计图', '单独绘制指定统计图，未要求跨图表补全或选择图表类型。'),
    'freq': ('E.S01.02.01', '根据总数与比例补全频数或频率'),
    'sector': ('E.S01.03.01?', '由分组占比计算扇形圆心角', '使用统计图表中的占比求角，额外涉及比例与圆周角度的换算。'),
    'estimate': ('E.S01.04.01', '用样本比例估计总体数量'),
    'datause': ('M.S01.03', '根据统计图表解释现象或给出建议', '任务侧重解释或建议，并非仅补全图表中的缺项。'),
    'conj': ('E.P01.02.02', '从观察中形成猜想并检验'),
    'neg': ('E.G13.02.01', '构造反例检验断言'),
    'frac': ('E.N04.04.01', '运用分式变形完成运算'),
    'tri': ('E.G02.01.02', '运用三角形内外角关系推理'),
    'reg': ('E.G06.07.01', '从正多边形的对称结构求角'),
    'alt': ('E.G01.04.01', '由角的位置与数量关系判断平行'),
    'graph': ('E.N10.02.02', '读取图象中的阶段变化与数量关系'),
    'avg': ('E.S02.01.01', '计算并解释平均数'),
}

@lru_cache(maxsize=1)
def references():
    tax = json.loads((HERE.parent/'taxonomy'/'taxonomy.v0.2.json').read_text(encoding='utf8'))
    exams = {x['id']: x for x in tax['exam_points']}
    knowledge = {x['id']: x for x in tax['knowledge_points']}
    return exams, knowledge

@lru_cache(maxsize=1)
def review_book():
    return json.loads((HERE/'batch_tag_reviews.json').read_text(encoding='utf8'))

def assignment(codes):
    exams, knowledge = references()
    mids, eids, reasons, notes = [], [], [], []
    for code in dict.fromkeys(codes.split('+')):
        targets, reason, *gap = TOPICS[code]
        for target in targets.split():
            target = target.rstrip('?')
            if target.startswith('M.'):
                assert target in knowledge, target
                mids.append(target)
            else:
                eids.append(target)
                mids.append(exams[target]['primary_knowledge_id'])
        reasons.append(reason)
        notes.extend(gap)
    return dict(knowledge_ids=list(dict.fromkeys(mids)), exam_ids=list(dict.fromkeys(eids)),
                coverage='仅知识点' if not eids else ('部分匹配' if notes else '完整匹配'),
                tag_note=' '.join(dict.fromkeys(notes)), tag_reason='；'.join(reasons)+'。')

def apply_tags(question):
    paper_id, original_number = question['id'].rsplit('-Q',1)
    record = review_book().get(paper_id, {}).get(str(int(original_number)))
    if not record:
        raise ValueError(f"{question['id']} 缺少逐题标签复核记录，请先核对原卷和解析。")
    structure, _, title = record.partition('|')
    codes = structure.split('/')
    parts = question.get('parts',[])
    group_codes = []
    for index, part in enumerate(parts):
        m = re.search(r'[（(](\d+)[）)]',part.get('label',''))
        group = int(m[1])-1 if m else index
        base = codes[0] if len(codes)==1 else codes[group]
        # Some printed questions put several separately answerable tasks under
        # one parent number, e.g. (2)① and (2)②. Their targets may differ.
        if ':' in base:
            sub = re.search('[①②③④⑤⑥⑦⑧⑨]',part.get('label',''))
            base = base.split(':')['①②③④⑤⑥⑦⑧⑨'.index(sub[0])] if sub else base.replace(':','+')
        part.update(assignment(base))
        group_codes.append(base)
    question.update(assignment('+'.join(dict.fromkeys(group_codes or [c.replace(':','+') for c in codes]))))
    question['title'] = title or TOPICS[re.split('[+:]',codes[0])[0]][1]
    return question
