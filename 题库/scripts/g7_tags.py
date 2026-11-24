"""Tag G7 source tasks from reviewed duplicates, individual assignments or explicit textual evidence."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from batch_tags import TOPICS, assignment, references


HERE = Path(__file__).resolve().parent
FIELDS = ('knowledge_ids', 'exam_ids', 'coverage', 'tag_note', 'tag_reason')
ADDITIONAL = {
    'basic': ('M.N01.05', '运用有理数的运算法则'),
    'alg': ('M.N03.01', '分析代数式中的数量关系'),
    'geoangle': ('M.G01.02', '分析角的度量关系'),
    'propline': ('M.G01.01', '辨析直线、射线与线段'),
    'pattern': ('M.N03.09', '观察并解释数量规律'),
    'rand': ('E.S03.02.01', '列出等可能结果并计算概率'),
    'event': ('E.S03.01.01', '辨别随机事件与确定事件'),
    'median': ('E.S02.02.01', '确定数据的中位数或众数'),
    'irr': ('E.N02.03.01', '辨别有理数与无理数'),
    'perp': ('E.G01.03.02', '辨认垂足和点到直线的距离'),
    'parang': ('E.G01.05.01', '用平行线的性质求角'),
    'oppangle': ('E.G01.03.01', '利用对顶角或邻补角的关系求角'),
    'selectchart': ('E.S01.03.02', '根据统计目的选择图表'),
    'investigate': ('M.S01.01', '依据调查目的选择调查方式'),
    'remangle': ('M.G01.02', '判断余角与补角的关系'),
    'middle': ('M.G01.01', '识别线段中点与距离的关系'),
    'notation': ('M.N03.01','辨认代数式的写法与表示规范'),
    'sympoly': ('M.N03.03','交换字母并比较多项式验证对称性'),
    'tel': ('M.N03.09','利用裂项相消或错位相减求和'),
    'uniterm': ('M.N03.02','按定义辨认单项式、多项式和同类项'),
    'sides': ('M.G02.01','用三角形两边之和大于第三边比较线段'),
    'sectarea': ('E.G06.08.01','由圆心角与半径求弧长或扇形面积'),
    'sectsum': ('E.G06.08.02','通过扇形割补求组合面积'),
}

# Apply these patterns to the task being asked, before considering a longer shared
# introduction. The order disambiguates e.g. estimating a population from merely
# reading a percentage, and cube count from recognising a view.
PATTERNS = [
    ('estimate', r'(估计|估算|推算|预测|请估测).{0,65}(全(校|市|区|县|体)|该校|全年级|该市|该地区|该批|这批|总体|七年级|学生中).{0,65}(多少|约有|人数|名|人|数量|件|个|本)|用样本(估计|推断)总体.{0,15}(人数|数量)|估计.{0,50}(约有多少[人名]|有多少名|所占人数|获奖人数)'),
    ('sci',r'科学(记|计)数法|用科学[记计]数'),
    ('near',r'近似数|精确到.{0,16}位|保留.{0,8}(有效数字|位小数).{0,5}(正确|结果)|按四舍五入'),
    ('ind',r'与.{0,24}(取值)?无关|无论.{0,22}代数式的值(都|总|始终)'),
    ('zero',r'非负(数|性|量).{0,28}(之和|和为|性质|同时|等于|为零)|平方和.{0,6}(为零|等于零)'),
    ('simval',r'先化简.{0,6}(再|后)求值|化简.{0,8}(然后|再)求|化简求值'),
    ('like',r'(?:是|互为|若为|作为|属于)同类项|同类项的定义|同类单项式'),
    ('term',r'单项式.{0,40}(次数|系数)|多项式.{0,40}(次数|项数|几次|二次项|常数项|几项式)|几次.{0,3}项式|几次单项式|多项式的项|整式的概念'),
    ('simp',r'合并同类项|去括号(法则|并|后|是|正确|的)|整式的(加减|化简)|多项式的加减'),
    ('eqdef',r'(属于|是一|为一|是关于|是元|是|不属于|不是)(字母)?[a-z]?的一元一次方程|一元一次方程的定义|(?:下列|关于).{0,35}(是一元一次方程|是一元一次式)|关于.{0,30}是一元一次方程'),
    ('equal',r'等式的(基本)?性质|等式变形|方程(的)?变形.{0,10}(正确|依据|错误)|根据等式|等式两边(都|同时)'),
    ('check',r'方程的解是.{0,14}(则|求)|若.{0,22}是(关于.{0,24})?方程.{0,38}的(一个)?解|关于.{0,30}方程.{0,32}的解是|方程的解相同|两个方程同解|将.{0,15}代入方程'),
    ('cost',r'比较.{0,25}(优惠|收费|方案|划算)|哪(家|种个|个|种).{0,18}(合算|划算|便宜|优惠|省钱|更省)|怎样(购买|选择|租用|租车).{0,18}(合算|划算|便宜|优惠|省钱)|分段收费'),
    ('plan',r'(有几种|所有|有哪些|多少种|设计|不同的).{0,14}(购买|租车|调配|分配|安排|分组|采购|运输|进货)方案|列出.{0,16}(整数解|方案)'),
    ('model',r'列.{0,7}(一元一次)?方程|等量关系.{0,18}方程|一元一次方程的应用|方程模型'),
    ('eq',r'解(下列)?(一元一次)?方程|一元一次方程的解法|方程.{0,56}的解[为是]|方程求解'),
    ('sector',r'圆心角|扇形.{0,20}所对的角'),
    ('selectchart',r'选(择|用)?.{0,8}(哪种|合适|什么).{0,8}统计图|用.{0,10}统计图.{0,15}(最合适|较合适|比较合适)|采用.{0,8}统计图.{0,10}(合适|直观)'),
    ('sample',r'代表性|抽样方案|抽取的样本.{0,30}(合理|随机|代表)'),
    ('survey',r'样本容量|总体与个体|个体和总体|总体[、，]个体|调查的(总体|样本|个体)|其中(的)?样本是|以下.{0,12}个体是'),
    ('investigate',r'全面调查|抽样调查|普查|抽查|调查方式'),
    ('freq',r'频数|频率'),
    ('chart',r'条形统计图|扇形统计图|折线统计图|补全.{0,8}(条形|统计图|统计表)|统计图表|统计图提供'),
    ('median',r'中位数|众数'),
    ('avg',r'加权平均数|平均数的计算'),
    ('event',r'随机事件|必然事件|不可能事件|确定事件'),
    ('rand',r'概率|等可能事件'),
    ('cubes',r'(正方体|立方块|小方块|立方体).{0,20}(最多|最少|个数|块数)|最[多少].{0,18}(正方体|立方块|小方块|立方体)|搭(成|出|建).{0,15}(至少|最多|最少)|保持.{0,28}(视图|看到).{0,28}(最多|添加|增加)'),
    ('view',r'主视图|左视图|俯视图|三视图|从(上|左|正|前|右)(面|边|方)(观察|看到|看)|从(不同|三个)方向(看|观察)|画.{0,26}看到的(平面)?(图形|形状)'),
    ('cross',r'截面|平面去截|用.{0,4}平面截|截得的图形|截一个'),
    ('vol',r'体积[比是多少为的]|体积相(等|同)|求.{0,28}体积'),
    ('surface',r'表面积|侧面积|侧面展开.{0,16}(面积|周长)'),
    ('net',r'展开图|展成平面|展开后|相对(面|的面)|对面(的字|写|是|为)|折(成|叠成).{0,12}(正方体|立方体|长方体)'),
    ('sweep',r'点动成线|线动成面|面动成体|面动成面|绕.{0,12}旋转一周|旋转一周.{0,18}立体|旋转得到的(立体|几何体)'),
    ('euler',r'欧拉(公式|关系)|顶点数.{0,40}棱数.{0,40}面数|顶点数.{0,40}面数.{0,40}棱数'),
    ('solid',r'棱柱|棱锥|几何体的特征|立体图形|柱体|锥体|几何体的(分类|认识)|面的个数|面都是平面'),
    ('abs',r'绝对值.{0,23}(的数|等于|最小|最大|为|是|意义)|的绝对值|绝对值的(性质|定义|意义)'),
    ('sign',r'化简.{0,8}绝对值|去(绝对值|掉绝对值)|化简.{0,20}\||绝对值符号'),
    ('motion',r'数轴.{0,65}(同时|同时出发|动点|速度)|在数轴上运动|动点.{0,35}数轴|沿数轴.{0,16}(运动|移动)|在运动过程中.{0,40}(相遇|相距)'),
    ('dist',r'数轴上.{0,43}(距离|相距)|到(原点|点).{0,12}(距离|相距)|数轴上两点间.{0,7}距离|数轴的距离'),
    ('opp',r'相反数|互为相反'),
    ('rec',r'倒数|互为倒数'),
    ('cmp',r'比较.{0,26}(大小|有理数)|从小到大|从大到小|最大的数|最小的数|有理数的大小|下列(实数|有理数|各数|数).{0,20}(最小|最大)|大于.{0,24}而小于.{0,24}整数'),
    ('irr',r'无理数'),
    ('class',r'(属于|不属于|有几个|有多少|个数|是|集合|称为|列)有理数|有理数的分类|填(入|在).{0,14}(集合|圈里)|非负整数|正整数集|非正整数'),
    ('pos',r'相反意义|意义相反|记[作为].{0,12}[+＋\-−].{0,30}(那么|则|表示|记)|正数和负数的意义|超[出过].{0,20}记[作为]|收入.{0,20}支出'),
    ('axis',r'数轴|原点.{0,8}单位长度|在数轴上表示'),
    ('draw',r'尺规作图|用直尺和圆规|用尺规|作一(条|个)角|作一个角等于|作.{0,8}线段.{0,16}使'),
    ('perp',r'点到直线.{0,6}距离|垂线段最短|垂足'),
    ('oppangle',r'对顶角|邻补角'),
    ('remangle',r'余角|补角'),
    ('bis',r'角平分线|平分.{0,16}(∠|角)|角的平分线|平分角'),
    ('parang',r'平行线的性质|两直线平行.{0,4}(同位角|内错角|同旁内角)'),
    ('rot',r'绕点.{0,20}转(动|过)|旋转角|旋转.{0,12}多少度'),
    ('line',r'两点(之间|间)线段最短|两点确定(一条)?直线|经过两点有且只有一条直线'),
    ('seg',r'线段.{0,35}(长|中点|三等分)|线段中点|中点|求.{0,20}线段的长度'),
    ('propline',r'直线、射线|射线、线段|直线.{0,20}射线|射线的(条数|定义)'),
    ('angle',r'角的(和差|度量|计算)|平角|周角|度分秒|时钟.{0,18}(夹角|所成)|时针.{0,18}分针|多少度|角度|∠|\\angle'),
    ('polygon',r'对角线'),
    ('ar',r'阴影.{0,16}面积|面积.{0,14}(阴影|之差)|分割法.{0,8}面积'),
    ('seq',r'(按|观察|探究|发现|找出|寻找|按照|表示)规律|一般规律|规律.{0,38}第|第.{0,10}个图(案|形).{0,15}(多少|个|根)|用含.{0,25}(代数式|式子).{0,18}第|数列的规律'),
    ('new',r'新(运算|定义|符号)|定义.{0,12}(运算|为|一种)|规定.{0,16}运算'),
    ('expr',r'列代数式|用含.{0,35}(代数式|式子)表示|用代数式表示|表示的实际意义'),
    ('val',r'代数式.{0,48}(的值|求值)|求.{0,7}式子的值|整体代入|代入求值'),
    ('num',r'有理数.{0,10}(运算|计算|乘法|除法|乘方|加法|减法)|乘法分配律|乘法的运算律|乘方的意义|正负数加减|有理数和或差'),
]
PATTERNS[:0] = [
    ('neg',r'举(出)?(一?个)?反例'),
    ('sign',r'化简.{0,50}绝对值|化简[:：]?\\?\(?[|]|(?:去掉|去)(?:上式的)?绝对值符号'),
    ('angle',r'度[、,，]分[、,，]秒.{0,12}(换算|转化)|角度的单位换算'),
    ('term',r'单项式和多项式的(相关)?概念|单项式的(系数|次数)|单项式、多项式'),
    ('seg',r'线段的和差|线段和差倍分'),
    ('view',r'从正面[、和与]左面.{0,12}(看到|观察)|从正面、侧面.{0,20}形状图'),
    ('estimate',r'全(?:校|年级)学生中.{0,25}人数大约|估计该.{0,12}共有.{0,30}(名学生|人)|请估计.{0,28}有多少(?:人|名学生)'),
    ('costnum',r'计件工资制|起步价|分段计(价|费)|按.{0,8}(折扣|收费规则).{0,25}(多少元|费用)'),
    ('model',r'设.{0,32}[为是了]?\\?\(?[xy].{0,30}(另一|则乙|则甲|那么乙|那么甲)|依据题意列出方程|解得[：:]?\\?\(?x=.{0,14}(人|辆|件|元|台|个|千米|小时)'),
]
RULES = tuple((code,re.compile(pattern,re.I)) for code,pattern in PATTERNS)


def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text or ''))


def fingerprint(q):
    text = norm(q.get('stem',''))
    if len(text) < 18:
        return None
    options = [norm(c.get('text','')) for c in q.get('choices', [])]
    figures = [Path(f).name for f in q.get('figures', [])]
    content = json.dumps([text, options, figures],ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


@lru_cache(maxsize=1)
def reviewed_questions():
    root=HERE.parent/'questions'
    by_key = {}
    # The historical pilot and 30-paper batch carry item-specific reviewed labels.
    for p in sorted(root.glob('SZ-*/*.json')):
        if p.parent.name.startswith('SZ-G7-T1-'):
            continue
        q=json.loads(p.read_text(encoding='utf8'))
        key=fingerprint(q)
        if key: by_key[key]=q
    return by_key


@lru_cache(maxsize=1)
def overrides():
    f=HERE/'g7_tag_reviews.json'
    return json.loads(f.read_text(encoding='utf8')) if f.exists() else {}


def assigned(codes):
    records=[]
    for code in codes.split('+'):
        if code in TOPICS:
            records.append(assignment(code))
        else:
            target,title=ADDITIONAL[code]
            knowledge=references()[0][target]['primary_knowledge_id'] if target.startswith('E.') else target
            exam=[target] if target.startswith('E.') else []
            records.append(dict(knowledge_ids=[knowledge],exam_ids=exam,coverage='完整匹配' if exam else '仅知识点',
                                tag_note='' if exam else '当前标签能确定该知识主题，题目任务与现有细分考点不完全一致。', tag_reason=title+'。'))
    return aggregate(records)


def aggregate(records):
    def collect(key):
        return list(dict.fromkeys(i for r in records for i in r[key]))
    mids,eids=collect('knowledge_ids'),collect('exam_ids')
    coverage = '待标注' if not mids else '仅知识点' if not eids else (
        '完整匹配' if all(r['coverage']=='完整匹配' for r in records) else '部分匹配')
    return dict(knowledge_ids=mids,exam_ids=eids,coverage=coverage,
                tag_note=' '.join(dict.fromkeys(r['tag_note'] for r in records if r.get('tag_note'))),
                tag_reason=' '.join(dict.fromkeys(r['tag_reason'] for r in records if r.get('tag_reason'))))


def pending():
    return dict(coverage='待标注', knowledge_ids=[],exam_ids=[],
                tag_note='尚无足够的可核对证据来确定 v0.2 标签。',tag_reason='')


def topic_name(code):
    first=code.split('+')[0]
    return (TOPICS if first in TOPICS else ADDITIONAL)[first][1]


def explicit_focus(solution):
    return '。'.join(re.findall(r'(?:本题(?:主要)?(?:考查|考察)(?:的是|了)?|【考点】)[:：]?([^。．\n]{2,100})',solution or ''))


def infer(task,q):
    is_part=task is not q
    prompt=task.get('prompt') if is_part else q.get('stem')
    solution=(task.get('given_solution') or '\n'.join(task.get('solution_steps',[])) or '')
    material='\n'.join(m['text'] for m in q.get('materials',[]) if m['id'] in task.get('material_ids',[]))
    texts=[('题面',prompt),('解析指明',explicit_focus(solution)),('解法',solution),('公共材料',material)]
    for origin,text in texts:
        if not text: continue
        compact=norm(text)
        if origin=='题面':
            math=re.sub(r'\\[a-zA-Z]+',lambda m:'R' if m[0] in ('\\sqrt','\\angle','\\circ','\\degree','\\pi') else '',compact)
            math=re.sub(r'计算(?:下列各题)?|直接写出结果|的结果是|的值是|直接写出答案','',math)
            if (re.fullmatch(r"[0-9０-９+\-−×·÷*^.,，、：:;；。！？!?_\[\]()\\{}=/%|⁻¹²³⁴⁵⁶⁷⁸⁹\s]+",math)
                    and re.search(r'[+\-−×÷*^/|]|\\(?:frac|times|div)',compact) and re.search(r'\d',math)):
                out=assigned('num')
                out['tag_reason']='题面给出含具体有理数与四则或乘方运算的算式。'
                return 'num',out
            if (re.match(r'(解方程[：:]?)?\\?\(',compact) and '=' in compact
                    and re.search(r'[xy]',math) and not re.search(r'[一-鿿]',math)):
                out=assigned('eq')
                out['tag_reason']='本小问给出单未知数方程，配套解法展示移项或合并步骤。'
                if re.search(r'解得|移项|去分母|解[:：]',solution):
                    return 'eq',out
        for code,pattern in RULES:
            hit=pattern.search(compact)
            if hit:
                if code=='sector' and not re.search(r'统计|人数|扇形图|频率|百分比|所占比例',compact+norm(q.get('stem',''))):
                    if '面积' in compact and ('半径' in compact or '半径' in norm(q.get('stem',''))):
                        code='sectsum' if '阴影' in compact else 'sectarea'
                    else:
                        continue
                out=assigned(code)
                # An evidence quote is a plain-text search hint. Slicing a
                # TeX expression would leave unbalanced delimiters in the browser.
                excerpt=re.sub(r'\\[A-Za-z]+|[\\$(){}\[\]]',' ',hit[0])
                excerpt=' '.join(excerpt.split())[:45].strip()
                out['tag_reason']=(f'{origin}含“{excerpt}”。' if excerpt else '')+out['tag_reason']
                # A subject named only in setup is insufficient evidence for a precise test objective.
                if origin=='公共材料':
                    out.update(exam_ids=[],coverage='仅知识点',tag_note='公共材料明确涉及该知识点，小问的具体考查目标尚待核对。')
                return code,out
    return None,pending()


def apply_tags(q):
    old=reviewed_questions().get(fingerprint(q))
    all_overrides=overrides()
    reviewed=all_overrides.get(q['id'])
    records=[]
    titles=[]
    parts=q.get('parts',[])
    uniform_parent=reviewed and not any(p['id'] in all_overrides for p in parts)
    for task in parts or [q]:
        code=all_overrides.get(task['id'])
        if not code and uniform_parent:
            code=reviewed
        if code:
            details=assigned(code)
            details['tag_source']='逐题核对'
        else:
            prev=None
            if old:
                if task is q and not old['parts']:prev=old
                elif task is not q:
                    prev=next((p for p in old['parts'] if norm(p.get('prompt'))==norm(task.get('prompt')) and p.get('label')==task.get('label')),None)
            if prev:
                details={f:prev.get(f,'') for f in FIELDS}
                details['tag_source']='同题已审标签'
                details['tag_reference_id']=prev['id']
            else:
                code,details=infer(task,q)
                details['tag_source']='题文匹配' if code else '待核'
        task.pop('tag_reference_id',None)
        task.update(details)
        records.append(details)
        if code:titles.append(topic_name(code))
    if q.get('parts'):
        q.update(aggregate(records),tag_source='小问标签汇总')
    if old and old.get('title'):
        q['title']=old['title']
    elif titles:
        q['title']='、'.join(list(dict.fromkeys(titles))[:3])
    elif not q.get('title'):
        q['title']='原卷第'+str(q.get('number',''))+'题'
    return q
