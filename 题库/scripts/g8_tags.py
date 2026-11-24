"""Classify each printed Grade 8 task against the bank's shared v0.2 taxonomy."""
from functools import lru_cache
import json
from pathlib import Path
import re

from batch_tags import references
from g7_tags import aggregate, explicit_focus, infer as autumn_match, pending
from g7t2_tags import algebra, compact, geometric_method, vocabulary


HERE = Path(__file__).resolve().parent

# Specific tasks precede properties mentioned in their setup. A knowledge ID
# is intentional where the published exam targets do not describe the task.
RULES = r"""
M.N08.01 分式方程的?(概念|定义|识别)|是分式方程的|属于分式方程
E.N08.02.01 分式方程的?(实际)?应用|列.{0,10}分式方程|建立分式方程|可列(?:方程|分式方程).{0,3}为
E.N08.01.02 分式方程.{0,26}(无解|没有解|增根)|增根问题
E.N08.01.01 解(?:下列|这个|关于.{0,4}的)?分式方程|分式方程的解法|经检验.{0,36}是原(?:分式)?方程的解
E.N04.01.02 分式.{0,36}(值为[零0]|值等于[零0])|分式的值为零
E.N04.01.01 分式.{0,44}(有意义|无意义)|分母不(能为|等于)0
M.N04.01 分式的?(概念|定义|识别)|是分式(的|有)|属于分式|最简分式
E.N04.04.02 选.{0,15}(合适|恰当|适当|喜欢|使分式有意义).{0,10}(整数|值|数)(?:代入|求|使)|从.{0,20}(选|取).{0,15}(代入|求值)
E.N04.04.01 分式的?(加减|混合|化简求值)|分式化简|通分.{0,10}(加减|计算)
E.N04.03.01 分式的?(乘除|乘方|乘法|除法)
E.N04.02.01 约分|通分
M.N04.02 分式的?基本性质|分式的值.{0,14}(扩大|缩小|不变|变化)
M.N05.02 分母有理化
E.N05.01.01 二次根式.{0,32}(有意义|取值范围)|被开方数.{0,8}(非负|大于等于)
E.N05.02.02 二次根式的?(性质|化简).{0,15}绝对值|开平方.{0,5}绝对值
E.N05.02.01 最简二次根式|化简二次根式|二次根式的化简
E.N05.03.01 同类二次根式|二次根式的?(加减|加法|减法)
E.N05.04.01 二次根式的?(乘除|乘法|除法|混合运算|运算)
E.N02.01.02 非负(?:数|量)的?(性质|和)|非负性.{0,12}(为零|等于零|为0)
E.N02.04.01 估算无理数|无理数的?(估算|估计)|估计.{0,25}(大小|在哪|值)|在哪两个.{0,8}整数|最接近.{0,8}整数
E.N02.03.01 是无理数|无理数的?(识别|概念|定义|有|个数|是)|辨别无理数|无限不循环小数
E.N02.03.02 实数的?大小比较|比较实数|实数.{0,8}(最大|最小)
E.N02.01.01 算术平方根|平方根(?!号)
E.N02.02.01 立方根|开立方
E.N02.05.01 实数的?(混合)?(计算|运算)
E.N03.07.01 提(?:取)?公因式
E.N03.08.01 公式法.{0,9}分解|分解.{0,9}公式法|平方差公式分解|完全平方公式分解
M.N03.08 因式分解的?(定义|意义|概念)|从左到右.{0,12}(分解因式|因式分解)|是(因式分解|分解因式)的|十字相乘
E.N06.01.01 二元一次方程(组)?的解的?(定义|概念)|是.{0,20}方程组?的(?:一个|一组)?解
E.N06.03.02 方程组.{0,40}(解满足|解相同|解是正|解为正|的解互)|方程组的解.{0,10}(满足|为正|互为)
E.N06.04.01 二元一次方程组的?(实际)?应用|列.{0,8}(二元一次)?方程组|一次方程组模型
E.N06.03.01 消元法|解.{0,4}二元一次方程组|解(?:下列)?方程组|代入消元|加减消元
M.N06.03 二元一次方程(组)?的?(概念|定义)|属于二元一次方程|二元一次方程组有
E.N07.05.01 一元二次方程的?(实际)?应用|列.{0,9}一元二次方程
E.N07.03.02 判别式.{0,16}(范围|取值)
E.N07.03.01 判别式|根的情况
E.N07.02.01 解.{0,5}一元二次方程|求根公式|因式分解法解方程
E.N09.01.02 数轴上表示.{0,13}解集|解集.{0,16}数轴
E.N09.02.02 不等式组.{0,38}(整数解|解集)|解.{0,6}不等式组|不等式组的?(整数解|解法|解集)
E.N09.03.02 (方案|购买|调配|购进|运输|租车).{0,20}(有几种|几种.{0,8}方案|列出所有)|有几种.{0,12}方案
E.N09.03.01 (一元一次)?不等式(组)?的?(实际)?应用|由实际问题抽象出.{0,12}不等式|列(?:出)?(?:一元一次)?不等式
E.N09.01.01 不等式的?(基本)?性质|不等号.{0,10}(改变|方向)
E.N09.02.01 解(?:下列|一元一次)?不等式(?!组)|一元一次不等式的解法
E.N11.04.03 分段(?:计费|收费|计价|定价)|分段函数的?(实际)?应用
E.N11.04.02 (总?费用最(少|低)|利润最[高大]|最大利润|最小费用|费用最低|最省钱)
E.N11.03.02 (依据|根据|利用|观察|由)函数?图[像象].{0,30}(不等式|解集)|一次函数与(?:一元一次)?不等式|从函数的角度看不等式|(不等式|解集).{0,12}(图[像象]|图解法)
E.N11.03.01 两(?:个|条)(?:一次函数|直线).{0,15}交点|一次函数与(?:二元一次)?方程组
E.N11.02.01 待定系数法求一次函数|求.{0,12}(?:直线[A-Z]{0,2}|一次函数|正比例函数)的?(表达式|解析式|关系式)|直线[A-Z]{1,2}的(表达式|解析式)|确定一次函数表达式
E.N11.01.02 比较.{0,10}函数值|一次函数图[象像]上点的坐标特征|函数值的大小
E.N11.01.01 一次函数.{0,13}(增减|图[象像]与系数|图[象像]的位置|的性质)|正比例函数的?(性质|图[象像])|一次函数图[象像].{0,10}(系数|增减|象限|性质)|随.{0,5}的?增大而(增大|减小)
M.N11.01 (一次|正比例)函数的?(定义|概念)|是(一次|正比例)函数的|属于一次函数
M.N11.04 一次函数的?(综合|实际)?应用
E.G09.02.01 关于.{0,13}(坐标原点|[xy]轴|原点).{0,10}对称|坐标.{0,6}(平移|轴对称)|平移.{0,6}(坐标|后点)|点的.{0,5}对称点
E.G09.01.02 方位角|方向和距离|方位与距离
E.G09.01.01 象限|到[xy]轴的距离|点到坐标轴的距离|坐标确定位置|点的坐标特征
E.G09.03.02 面积为.{0,10}(求|时).{0,12}(点|坐标)|使.{0,8}面积.{0,10}点的坐标
E.G02.03.01 多边形的?(内角|外角)|正多边形的?(内角|外角)|多边形.{0,15}(内角和|外角和)
E.G04.04.02 (证明|验证).{0,8}勾股定理|勾股定理的?(证明|验证)|弦图|赵爽
E.G04.06.02 表面.{0,20}(最短|爬行|爬到)|沿.{0,10}表面.{0,24}(路线|爬|距离)|平面展开.{0,5}最短路径
E.G04.05.01 勾股定理的?逆定理|勾股数|以.{0,8}长.{0,14}直角三角形|能(组成|构成).{0,6}直角三角形
E.G04.06.01 勾股定理的实际应用|测量.{0,10}(旗杆|竹竿|梯子).{0,6}(高|长)
E.G04.04.01 勾股定理|勾股关系|斜边的平方
E.G04.01.03 (存在|找出).{0,36}等腰三角形|等腰三角形.{0,12}(存在性|所有位置)
E.G04.01.02 等腰三角形的?判定|等角对等边
E.G04.01.01 等腰(?:直角)?三角形的?性质|等边对等角|三线合一
E.G04.02.02 等边三角形的?判定
E.G04.02.01 等边三角形的?性质
E.G04.03.01 直角三角形的?性质|斜边上的?中线|含30[度°].{0,8}直角三角形
E.G05.05.02 中点四边形|连接各边中点
E.G05.05.01 三角形的?中位线
E.G05.01.02 平行四边形的?判定|(证明|求证).{0,20}(?:是|为)平行四边形
E.G05.01.01 平行四边形的?性质|平行四边形的?(对边|对角线|邻角)
E.G05.02.02 (矩形|长方形)的?判定|(证明|求证).{0,20}(?:是|为)矩形
E.G05.02.01 (矩形|长方形)的?性质
E.G05.03.02 菱形的?判定|(证明|求证).{0,20}(?:是|为)菱形
E.G05.03.01 菱形的?(性质|面积公式)
E.G05.04.02 正方形的?判定|(证明|求证).{0,20}(?:是|为)正方形
E.G05.04.01 正方形的?性质
E.G07.01.02 翻折变换|折叠的?性质
M.G07.01 轴对称图形的?(识别|定义|判定)|是(?:轴对称图形|轴对称)|有.{0,3}条对称轴|对称轴的条数
M.G07.03 中心对称图形的?(识别|定义|概念)|是中心对称图形|中心对称图形是
E.G07.03.02 旋转的?性质|旋转角.{0,8}(为|大小)|旋转中心所连
E.G07.03.01 作图.{0,3}旋转变换|画出.{0,28}旋转.{0,24}(三角形|图形|位置)
E.G07.02.01 平移的?性质|平移变换|平移作图
E.G12.03.01 作图的?(依据|原理)|作法的依据
E.G12.01.02 作图痕迹.{0,15}(判断|可知|得到)
E.G13.01.01 逆命题|命题的条件和结论
E.G13.02.01 反例
M.G13.02 (真|假)命题|命题的真假
E.S02.06.02 结合.{0,13}统计(量|数据).{0,12}(选择|推荐|评价)|根据.{0,15}(数据|统计量).{0,22}(推荐|哪个班|哪位)
E.S02.03.02 (稳定|整齐).{0,12}(哪个|判断|更|比较|选)|((哪|较|更加|更|比较).{0,8}稳定)|稳定性
E.S02.03.01 方差|标准差
E.S02.02.01 众数|中位数
E.S02.01.02 已知.{0,14}平均数.{0,12}(求|则).{0,6}(缺|未知)|由平均数.{0,9}(未知|数据)
E.S02.01.01 加权平均|权重|所占[的]?权
M.S02.01 平均数|平均成绩|平均分
E.S02.04.01 四分位数
E.S02.05.01 箱线图
E.S01.04.01 估计.{0,32}(全校|该校|全年级|全区|该区|该地|全市).{0,50}(人数|有多少|人|名|数量)
""".strip()


def make_rules(lines):
    return [(code, re.compile(pattern, re.I)) for code, pattern in
            (line.split(' ', 1) for line in lines.splitlines())]


TASK_RULES = make_rules(RULES)


@lru_cache(maxsize=1)
def reviews():
    path = HERE / 'g8_tag_reviews.json'
    return json.loads(path.read_text('utf8')) if path.exists() else {}


NOTES = {
    'M.N04.01': '题目要求识别分式的形式，目录细目侧重取值条件。',
    'M.N04.02': '题目考查分式基本性质或式值变化，目录细目只列约分与通分。',
    'M.N05.02': '本题要求分母有理化，已有细目关注化为最简根式及开方的符号条件。',
    'M.N03.08': '本题考查分解形式、概念或其他方法，目录没有完全对应的细目。',
    'M.N06.03': '本题辨认方程或方程组的结构，细目侧重消元与利用已知解。',
    'M.N08.01': '本题辨认分式方程，已有细目侧重求解、验根及无解原因。',
    'M.N11.01': '本题辨认一次或正比例函数，已有细目侧重图象和增减性。',
    'M.N11.04': '已能确定为一次函数应用，细目所需的方案比较、最值或分段条件尚未充分体现。',
    'M.G07.03': '题目要求识别中心对称图形，细目要求确定变换的对应图形或由旋转建立关系。',
    'M.G07.01': '本题辨认轴对称图形或计数对称轴，细目侧重确定变换对应关系。',
    'M.S02.01': '本题涉及算术平均数，题面未给出加权或反求缺失值的要求。',
}


def tags(codes, reason, source, gap=''):
    exams, know = references()
    eids = [c for c in dict.fromkeys(codes) if c in exams]
    mids = list(dict.fromkeys(exams[c]['primary_knowledge_id'] if c in exams else c for c in codes))
    for mid in mids:
        if mid not in know:
            raise ValueError(mid)
    notes = [NOTES.get(c, '该问涉及“'+know[c]['name']+'”，现有细分考点仅能覆盖部分要求。')
             for c in dict.fromkeys(codes) if c in know]
    if gap:
        notes.append(gap)
    return dict(knowledge_ids=mids, exam_ids=eids,
                coverage='仅知识点' if not eids else '部分匹配' if notes else '完整匹配',
                tag_reason=reason, tag_note=' '.join(notes), tag_source=source)


def norm(text):
    s = compact(text).replace(r'\(','').replace(r'\)','')
    s = re.sub(r'\{\\rm\{([^{}]*)\}\}',r'\1',s).replace('{}','')
    for src, dst in ((r'\left',''),(r'\right',''),(r'\sqrt[]','√'),(r'\sqrt','√'),
                     (r'\triangle','△'),(r'\vartriangle','△'),(r'\angle','∠'),
                     (r'\circ','°'),(r'\cong','≌'),(r'\parallel','∥'),(r'\perp','⊥'),(r'\bot','⊥'),
                     (r'\because','∵'),(r'\therefore','∴'),(r'\div','÷'),(r'\times','×'),
                     (r'\geq','≥'),(r'\leq','≤'),('﹣','-'),('−','-')):
        s = s.replace(src,dst)
    return s


def structural(p, solution, shared):
    """Match operators, unknown denominators and requested conclusions together."""
    frac = bool(re.search(r'\\(?:d?frac)\{(?:[^{}]|\{[^{}]*\})+\}\{[^{}]*[a-z]',p))
    ctx = p + shared
    radical = '√' in p
    if ('有意义' in p or '无意义' in p):
        if radical and frac:
            return ['E.N05.01.01','E.N04.01.01']
        if radical: return ['E.N05.01.01']
        if frac: return ['E.N04.01.01']
    if frac and re.search('的?值(为|等于)[0零]',p):
        return ['E.N04.01.02']
    if frac and re.search('解方程|分式方程',p) and not re.search('应用|列|辨别|个数|下列|无解|增根|是分式',p):
        return ['E.N08.01.01']
    if frac and re.search('计算|化简|求值|的结果|原式',p+solution[:12]) and '=' not in p.split('其中')[0]:
        if re.search('选择|选取|选一个|选.{0,6}合适',p): return ['E.N04.04.01','E.N04.04.02']
        if re.search(r'}[+-]\\?(frac|dfrac)|}[+-]\d|[a-z][+-]\\frac',p) or '通分' in solution:
            return ['E.N04.04.01']
        return ['E.N04.03.01'] if re.search('[÷×]|[}]\\^',p) else ['M.N04.04']
    if 'cases' in p:
        if re.search('[<>≤≥]|\\\\(?:gt|lt|le|ge)',p): return ['E.N09.02.02']
        if not re.search('的解|同解|实数|参数|正数|相同|下列',p) and p.count('=')>=2 and re.search('[xy]',p): return ['E.N06.03.01']
    if re.search(r'不等式的?解集|不等式.{0,60}的解集|不等式.{0,16}的解为',p) and '不等式组' not in p:
        return ['E.N11.03.02'] if re.search('直线|一次函数|函数|图[象像]',ctx) else ['E.N09.02.01']
    if re.search(r'证明|求证|判断|说明',p):
        for figure,code in (('平行四边形','E.G05.01.02'),('菱形','E.G05.03.02'),('矩形','E.G05.02.02'),('正方形','E.G05.04.02'),('等边三角形','E.G04.02.02'),('等腰三角形','E.G04.01.02')):
            if re.search(r'(?:证明|求证|判断|说明)[^。;；]{0,36}(?:为|是|是否)(?:一个|个)?'+figure,p):
                return [code]
    if ('坐标' in p or '坐标系' in ctx) and (re.search('平移|对称点|关于.{0,7}(轴|原点).{0,4}对称',p) and '坐标' in p):
        return ['E.G09.02.01']
    if re.search('坐标|直线.{0,12}图[像象]',ctx) and re.search('面积',p):
        if re.search('坐标|位置',p[p.rfind('面积')+2:]): return ['E.G09.03.02']
        if re.search('求.{0,12}面积|面积[为是_]|面积的值',p): return ['E.G09.03.01']
    if re.search('等腰三角形',ctx) and '坐标' in p and ('存在' in p or '所有' in p):
        return ['E.G04.01.03','E.G09.03.03']
    if re.search(r'一次函数|直线[A-Z]|y=[-+0-9akxb×/]{2,}',ctx):
        if re.search('(?:求|确定|写出).{0,35}(?:解析式|表达式|函数关系式)',p): return ['E.N11.02.01']
        if re.search('交点.{0,12}坐标|交于点.{0,9}则',p) and re.search('方程组|联立',solution): return ['E.N11.03.01']
        if re.search('不等式.{0,35}(解集|的解)|[yy]_.{0,12}[<>].{0,12}的.{0,5}(范围|取值)',p): return ['E.N11.03.02']
    if radical and re.search('计算|化简|求值|的结果|^√|原式',p+solution[:8]) and not re.search('方程|方差|√[^{]?\\[3\\]',p):
        if re.search('有理化',solution): return ['M.N05.02','E.N05.04.01'] if re.search('÷|×',p) else ['M.N05.02']
        if re.search('[a-z]',p.replace(r'\frac','')) and re.search('绝对值|\\|',solution):
            return ['E.N05.02.02']
        if re.search('立方根|√\\[3\\]|\\^\\{-[0-9]|\\^\\{0\\}|\\|',p): return ['E.N02.05.01']
        if re.search(r'÷|×|·|\}√|√\{[^{}]*\}\(|\)\(|\\frac\{[^{}]*√',p): return ['E.N05.04.01']
        if p.count('√')>=2 and re.search('[+-]',p): return ['E.N05.03.01']
        if p.count('√')==1 and not re.search('[A-Za-z]|[一-鿿]{9}',p): return ['E.N05.02.01']
    return []


def method(p,s,w):
    """Use a part's own worked steps when the command only says '求值' or '证明'."""
    clean = lambda v: v.replace('{','').replace('}','').replace('^°','°')
    sp, ss = clean(p), clean(s)
    ctx = p+' '+w
    if re.search(r'移动|平移',p) and re.search(r'画出|作出|画图|作图',p): return ['E.G07.02.01']
    if re.search(r'旋转|逆时针|顺时针',p) and re.search(r'画出|作出|画图|作图',p): return ['E.G07.03.01']
    if re.search('中心对称|对称中心',p) and re.search('坐标|画出|作出',p): return ['E.G07.03.01']
    if re.search('图.{0,6}(描出|标出)|建立.{0,6}直角坐标系|点[A-Z].{0,6}的坐标[是为]',p): return ['E.G09.01.01']
    if re.search('函数|直线|图[象像]',ctx) and re.search('求.{0,14}(?:k|b|系数).{0,8}值|直线.{0,20}(?:解析式|表达式|关系式)',p) and re.search('代入|经过|直线|函数|解析式',s):
        return ['E.N11.02.01']
    if re.search(r'图[象像]|函数关系|y[_(]?\d?=?k|行程',ctx) and re.search('相遇|追上|停留|路程|时间|读数|千米',p) and re.search('图[象像]|当.{0,18}=.{0,18}[,，].{0,15}=',s):
        return ['E.N10.02.02']
    if re.search('函数|直线|图[像象]',ctx) and re.search('函数.{0,8}最[大小]值|函数.{0,15}(性质|变化)|[ab]满足的数量关系',p) and re.search('绝对值|\\|[^|]+\\||新函数|探究',ctx):
        return ['E.N10.02.03']
    if re.search('合算|划算|费用相同|费用相间|何时.{0,7}(相同|一样)|较便宜',p):
        return ['E.N11.04.01'] if re.search(r'[xy]=|\b[xy]\b|[<>]|函数',ss) else ['M.N11.04']
    if re.search('不超过|不能超过|至少|最多|不低于|不少于|至多|最少',p) and re.search(r'\\(?:ge|le)(?![a-z])|[<>≤≥]|不等式',s) and re.search('购|元|件|米|人|方案|数量|工程',p):
        return ['E.N09.03.01']
    if re.search(r'设|根据题意|依题意|由题意',s) and re.search('价|购买|销售|产|工程|个|本|时间|人|天|元|件|盒|速度|批|辆|小时|物种|资源|千米',p):
        if re.search(r'\\frac\{[^{}]{1,15}\}\{[^{}]{0,12}[xy][^{}]{0,15}\}',s) and '=' in s:
            return ['E.N08.02.01']
        if 'cases' in s and re.search('[xy]',s): return ['E.N06.04.01']
        if re.search(r'解得[:：]?[xy]=|[xy]=\d',s) and not re.search('图象|图像|坐标|函数',p): return ['E.N06.04.01']
    if re.search('由实际问题抽象出分式方程|列出分式方程',s): return ['E.N08.02.01']
    if '方程组' in ctx and 'cases' in s and re.search('取值范围|参数|整数值',p): return ['E.N06.03.02']
    if '因式分解' in ctx or '分解因式' in ctx:
        if re.search('^.{0,5}(分解因式|因式分解)|公因式|分解因式|因式分解',p) or not re.search('[一-鿿]{3}',p):
            if re.search('提(?:取)?公因式',s): return ['E.N03.07.01']
            if re.search(r'\([^()]{1,15}[+-][^()]{1,15}\)\^2|\([^()]{1,16}[+][^()]{1,16}\)\([^()]{1,16}[-][^()]{1,16}\)',ss):
                codes=['E.N03.08.01']
                if re.search(r'=[-]?(?:\d*[a-z]+|\d+)\(',ss): codes.insert(0,'E.N03.07.01')
                return codes
            if re.search(r'=[-]?(?:\d*[a-z]+|\d+)\(',ss): return ['E.N03.07.01']
    if re.search(r'\|[^|]+\|[+]√[^=]{1,38}=0|√[^=]{1,25}[+]\|[^|]+\|=0|\)\^2[+]\([^()]+\)\^2=0',sp): return ['E.N02.01.02']
    if '√' in p and not re.search('[一-鿿]',re.sub('计算|化简','',p)):
        if re.search(r'√\[3\]|\|[^|]+\||\^(?:0|-\d)',sp): return ['E.N02.05.01']
        if p.count('√')>=2: return ['E.N05.04.01'] if re.search('×|÷|\\\\frac|\\)\\(',p) else ['E.N05.03.01']
    if re.search('小数部分|整数部分',p) and '√' in p:return ['E.N02.04.01']
    if '√' in p and '\\frac' in p and re.search(r'\((?:\{)?√[^)]{1,50}\)\((?:\{)?√',s): return ['M.N05.02']
    if re.search(r'\|[^|]{1,18}\|',p) and re.search('[<>≤≥]|\\\\(?:ge|le)',p) and re.search(r'\|[^|]+\|=',s):
        return ['E.N01.03.02']
    if re.search('周长最小|.{0,6}和.{0,3}最小|的值最小|最短距[离]|最短路[线径]',p) and re.search('对称点|对称|折叠|两点之间线段最短|轴上找一点|轴上求作一点',ctx+s):
        return ['E.G07.01.01','E.G01.01.02']
    if re.search('圆柱|长方体|正方体',ctx) and re.search('最短|爬行|展开图|沿.{0,5}表面',p+s[:160]): return ['E.G04.06.02']
    if re.search(r'[A-Z]{2}\^2[+][A-Z]{2}\^2=[A-Z]{2}\^2',ss) and re.search('是直角三角形|为直角三角形|∴∠.{1,4}=90',ss):
        return ['E.G04.05.01']
    if re.search(r'[A-Z]{2}\^2=[A-Z]{2}\^2[-+][A-Z]{2}\^2|[A-Z]{2}=√.{0,14}\^2[-+].{0,14}\^2',ss):
        return ['E.G04.04.01']
    if '面积' in p and re.search(r'面积=.{0,20}[×*].{0,20}[-]|S_.{0,38}[-]S_|面积之差|割补',ss): return ['E.G02.04.01']
    if '求' in p and '面积' in p and re.search(r'S_.{0,15}=|面积=|面积为',s): return ['M.G02.04']
    if re.search('坐标',p) and re.search('是否存在|若存在|所有|位置|点P|点E',p):
        if re.search('等腰|平行四边形|矩形|正方形|菱形|垂直|直角|∠.{1,9}=90',p): return ['E.G09.03.03']
        if re.search('面积.{0,35}(相等|等于|为|倍)|面积之比',p): return ['E.G09.03.02']
        if re.search('长度|距离|[A-Z]{2}=|[A-Z]{2}的',p): return ['M.G09.03']
    if re.search('求证|证明|判断',p) or re.search('^.{0,3}[A-Z]{2}[∥⊥=][A-Z]{2}',sp):
        if re.search('≌|AAS|ASA|SAS|HL|SSS',s): return ['E.G03.02.02']
        if re.search('等腰|等边对等角|等角对等边',s): return ['E.G04.01.01']
        if re.search('垂直平分|中垂线',s): return ['E.G01.06.01']
    return []


def matched(rules, text):
    for code, pattern in rules:
        hit = pattern.search(text)
        if hit:
            return code,hit[0]
    return '', ''


def classify(unit, q):
    review = reviews().get(unit['id'])
    if review:
        codes, reason, *gap = review
        return tags(codes.split('+'), reason, '逐题核对', gap[0] if gap else '')
    prompt = unit.get('prompt') if unit is not q else q['stem']
    solution = unit.get('given_solution') or '\n'.join(unit.get('solution_steps',[]))
    p, s = norm(prompt),norm(solution)
    shared = ''
    if unit is not q:
        material_text = ' '.join(m['text'] for m in q.get('materials',[]) if m['id'] in unit.get('material_ids',[]))
        shared=norm(material_text or re.split(r'(?<!图)[（(]1[）)]',q['stem'],maxsplit=1)[0])
    focus = norm(explicit_focus(solution))
    details = structural(p,s,shared)
    exams, know = references()
    def evidenced(codes, location):
        names = [(exams.get(c) or know[c])['name'] for c in codes]
        return tags(codes, location+'对应“'+'、'.join(names)+'”。', '题文匹配')
    if details:
        return evidenced(details,'本问的式子结构和所求量')
    for section,label in ((p,'题面'),(focus,'解析点明的考查内容'),(s,'本问解答')):
        if label=='本问解答':
            details = method(p,s,shared)
            if details: return evidenced(details,'本问的要求和解答步骤')
        code,word = matched(TASK_RULES,section)
        if code:
            if code.startswith(('E.S02','M.S02')) and label=='题面' and '数据' in p and ('方差' in p or '平均' in p):
                codes=[c for kw,c in [('中位数','E.S02.02.01'),('众数','E.S02.02.01'),('方差','E.S02.03.01')] if kw in p]
                if code not in codes: codes.insert(0,code)
                if codes: return evidenced(list(dict.fromkeys(codes)),label)
            return evidenced([code],label)
        code,word=matched(vocabulary()[1],section)
        if code and code not in ('E.N10.02.01','E.G01.01.01','E.G01.02.02','E.G02.02.02','E.N10.02.02'):
            return evidenced([code],label)
    codes = algebra(compact(prompt),compact(solution)) or geometric_method(compact(prompt),compact(solution),q['stem'])
    if codes: return evidenced(codes,'本问的运算或证明步骤')
    legacy, info = autumn_match(unit,q)
    if legacy and legacy not in ('angle','seg','bis','term','simp','eq','cmp','axis','dist','num'):
        info['tag_source']='题文匹配'
        return info
    topic = SUBJECT.search(p+' '+s) or SUBJECT.search(shared)
    if topic:
        code = next(code for code,pattern in SUBJECTS if pattern.fullmatch(topic[0]))
        return tags([code],'题目涉及“'+topic[0]+'”，按题面与解答定位知识主题。','题文匹配')
    if legacy:
        return tags(info['knowledge_ids'],'题面或解答涉及'+info['tag_reason'],'题文匹配')
    return dict(pending(),tag_source='待核')


SUBJECTS=make_rules(r"""
M.G09.03 坐标与图形|平面直角坐标系
M.G05.05 中位线
M.G05.03 菱形
M.G05.02 矩形|长方形
M.G05.01 平行四边形
M.G05.04 正方形
M.G04.02 等边三角形
M.G04.01 等腰(?:直角)?三角形
M.G04.03 直角三角形|Rt△
M.G03.02 三角形全等|全等三角形|≌
M.G08.02 相似三角形|三角形相似|∽
M.G07.01 折叠|翻折|对称轴|轴对称
M.G07.03 旋转|中心对称
M.G07.02 平移
M.G01.06 垂直平分
M.G01.07 角平分线
M.G01.02 角度|∠
M.G02.04 面积
M.G09.01 坐标
M.G02.01 三角形|△
M.G01.03 垂直|垂足
M.N05.02 二次根式
M.N02.04 无理数
M.N11.01 一次函数|正比例函数
M.N10.02 图象|图像|函数关系
M.N04.04 分式
M.N09.02 不等式
M.N06.03 方程组
M.N03.08 因式分解|分解因式
M.N03.01 代数式
M.N03.09 规律
M.S01.03 统计表|统计图
M.S02.01 均值|平均
""".strip())
SUBJECT = re.compile('|'.join(p.pattern for _,p in SUBJECTS),re.I)


def apply_tags(q):
    parts=q.get('parts',[])
    for unit in parts or [q]:
        unit.update(classify(unit,q))
    if parts: q.update(aggregate(parts),tag_source='小问标签汇总')
    exams, know = references()
    targets = q['exam_ids'] or q['knowledge_ids']
    if targets and q['paper_id'] not in {'SZ-G8-T1-F33F12DEA8','SZ-G8-T1-60E5760908','SZ-G8-T2-141F62C4EA','SZ-G8-T2-C7DE0D31A7'}:
        q['title']='、'.join((exams.get(c) or know[c])['name'] for c in targets[:2])
    return q
