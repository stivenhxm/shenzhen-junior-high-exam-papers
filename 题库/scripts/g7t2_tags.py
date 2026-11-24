"""Match Grade 7 spring tasks to the published v0.2 taxonomy, preserving the evidence for each unit."""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from batch_tags import references
from g7_tags import aggregate, explicit_focus, infer as autumn_match

HERE = Path(__file__).resolve().parent

# The optional third column explains a discrepancy between the printed task and
# the target in v0.2. A knowledge-only assignment never implies an exam target.
RULE_TEXT = r"""
E.N01.06.01|科学[记计]数|转换科学记数
E.N01.06.02|四舍五入|按精度取近似数
E.N02.01.01|算术平方根|求算术平方根
E.N02.02.01|立方根|求立方根
E.N02.03.01|无理数的(概念|定义)|辨别无理数
E.N02.04.01|估算无理数|估计无理数的范围
E.N02.05.01|实数的?(混合)?(运算|计算)|实数混合运算
E.N03.01.02|整体代入|整体代入求值
E.N03.02.01|多项式的项与次数|辨认项与次数
E.N03.02.02|同类项的定义|由同类项的指数相等求参数
E.N03.03.01|合并同类项|去括号与合并同类项
E.N03.03.02|与.{0,12}(取值)?无关|通过系数分析参数
E.N03.04.01|同底数幂|整数指数幂的运算
E.N03.05.01|多项式乘|整式乘法
E.N03.06.01|平方差公式|识别并应用乘法公式
E.N03.06.02|(?=.{0,65}(?:和与积|和与差|已知.{0,16}和.{0,16}积)).{0,70}对称式|用已知和积求对称式
E.N03.07.01|提(?:取)?公因式|提公因式分解
E.N03.08.01|公式法(分解|因式)|用公式分解因式
M.N03.05|单项式除|整式除法|该问考查整式除法，现有整式乘法细目只覆盖乘积展开。
M.N03.06|几何背景|从图形面积解释乘法公式|以面积割补解释乘法恒等式，细目侧重识别与使用。
M.N03.08|十字相乘|分解二次三项式|该问所用分解方法超出现有公式法细目。
E.N03.09.01|第.{0,22}(个图形|个图案|幅图案)|由图形或数列规律归纳一般式
E.N03.09.02|用代数式(说明|证明)|用代数变形解释结论
E.N06.02.01|解一元一次方程|解一元一次方程
E.N06.03.01|加减消元|解二元一次方程组
E.N06.03.02|方程组.{0,42}的解.{0,12}(相同|满足|为正|互为)|由方程组解的条件求参数
E.N06.04.01|列(二元)?一次方程组|建立数量关系与一次模型
E.N09.01.01|不等式的?(基本)?性质|辨析不等式的变形
E.N09.01.02|解集.{0,12}数轴|在数轴上表示不等式的解集
E.N09.02.01|解一元一次不等式[，。;；：:]|解一元一次不等式
E.N09.02.02|不等式组的?(公共)?解集|解不等式组
E.N09.03.01|一元一次不等式的应用|把实际限制转为不等式
E.N09.03.02|(采购|租车|租用|购买|运输|调配).{0,15}(有几种|有哪些|方案)|列举满足约束的整数方案
M.N10.01|因变量|辨认变量与数量关系|该问要求区分自变量、因变量或常量。
E.N10.01.01|函数的(概念|定义)|根据对应规则判断函数关系
E.N10.01.02|自变量的?(实际)?取值范围|确定自变量的取值范围
E.N10.02.01|函数的表示(法|方法)|用表格、图象或式子表示变量关系
E.N10.02.02|(函数|变化)图[象像]|读取图象的变化过程
E.N11.02.01|待定系数法求一次函数|确定一次函数表达式
E.N11.04.03|分段收费|分段计费与比较方案
E.G01.01.01|线段中点的(定义|性质)|利用线段中点求长度
E.G01.02.01|角的和差|用角的和差计算
E.G01.02.02|角平分线的定义|利用角平分关系求角
E.G01.03.01|对顶角相等|由对顶角、邻补角求角
M.G01.03|三线八角|识别截线所成的角|该问要求辨认角的位置，未要求据此判定平行或计算角度。
M.G01.03|垂线段最短|判断点到直线的最短路径|须解释距离比较，目录细目侧重确定垂足与距离。
M.G01.02|互为余角|余角与补角|该问以互余、互补的定义为核心。
E.G01.03.02|点到直线的?距离|确定垂足或点到直线的距离
E.G01.04.01|平行线的?(判定|判断)|用截线所成角判断平行
E.G01.04.02|添加.{0,15}(条件|结论).{0,18}平行|补充能推出平行的条件
M.G01.04|平行公理|平行公理及其推论|该问考查平行公理，未要求使用截线所成角。
E.G01.05.01|平行线的?性质|用平行线性质求角
E.G01.05.02|(过|作|引).{0,35}(平行线|平行于).{0,45}(内错角|同位角|同旁内角)|作平行辅助线传递角关系
E.G01.06.01|(线段的?)?(垂直平分线|中垂线)的?性质|借助垂直平分线得到等距
E.G01.06.02|(垂直平分线|中垂线)的?判定|确定等距点的位置
E.G01.07.01|角平分线的性质|由角平分线推出到两边等距
E.G01.07.02|角平分线的判定|由等距判断角平分线
E.G02.01.01|三角形的?三边关系|用三角形三边关系确定长度范围
E.G02.01.02|三角形的?(内角和|外角)|用三角形内外角关系求角
M.G02.01|三角形的稳定性|三角形的稳定性|题目考查结构稳定性，现有细目覆盖边长和角的数量关系。
E.G02.02.01|三角形的高|识别或作出三角形的重要线段
E.G02.02.02|三角形的?中线|用中线的性质识别结构
E.G02.03.01|多边形的?(内角和|外角和)|用多边形内外角和求值
E.G02.04.01|割补法|分割与补形求面积
E.G02.04.02|等底等高|用底高关系处理面积
E.G03.01.01|全等三角形的?性质|用全等对应关系求边角
E.G03.01.02|全等图形的(概念|定义)|识别全等图形的对应结构
E.G03.02.01|全等三角形的?判定|运用充分条件证明全等
E.G03.02.02|构造.{0,12}全等|构造全等关系证明边角结论
E.G03.02.03|(不能判定|不能证明|条件不足).{0,30}全等|检查全等判定的条件缺口
E.G04.01.01|等腰三角形的?性质|使用等腰三角形的边角性质
E.G04.01.02|等腰三角形的?判定|判定等腰三角形
E.G04.01.03|是否存在.{0,55}等腰三角形|分类寻找满足等腰条件的位置
E.G04.02.01|等边三角形的?性质|使用等边三角形的性质
E.G04.02.02|等边三角形的?判定|证明三角形为等边
E.G04.03.01|直角三角形的?性质|利用直角三角形的角或斜边中线性质
E.G04.04.01|勾股定理|利用勾股关系计算边长
E.G04.05.01|勾股定理的?逆定理|判断三角形是否为直角三角形
E.G05.04.01|正方形的性质|利用正方形边角或对角线性质
M.G07.01|(是|属于|不是)轴对称图形|判断图形是否轴对称|任务侧重辨认轴对称图形，目录细目侧重寻找具体对应点并作图。
E.G07.01.01|轴对称的?性质|确定轴对称的对应关系
E.G07.01.02|折叠的?性质|把折叠转成角度与长度的关系
E.G07.02.01|平移的?(性质|作图)|利用平移的对应关系
E.G07.03.01|中心对称图形|判断旋转或中心对称的对应关系
E.G07.03.02|旋转的性质|利用旋转的对应边角
E.G09.01.01|象限|用坐标定位点
E.G09.02.01|关于.{0,11}轴对称的点|由对称或平移确定坐标
E.G12.01.01|尺规作图|按步骤完成基本尺规作图
E.G12.01.02|作图痕迹|从作图痕迹辨认目标
E.G12.02.01|作三角形|按基本条件构作三角形
E.G12.03.01|作图(原理|依据)|说明尺规构造的依据
E.G13.01.01|逆命题|辨认命题的条件与结论
M.G13.02|(真|假)命题|判断命题真假|题面要求判断真伪，未明确要求反例或论证。
E.G13.02.01|举.{0,5}反例|构造反例
E.G13.03.01|推理的依据|补全几何论证依据
E.S01.02.02|频数(分布)?直方图|读取分组与频数
E.S01.04.01|估计.{0,20}(全校|该校|该地区|该批|全年级|全市|全区).{0,60}(人数|多少|总数|件数|数量)|按样本比例估计总体数量
E.S03.01.01|随机事件|判断事件类型与发生的可能性
E.S03.02.01|概率公式|在等可能情形下求概率
E.S03.02.02|游戏.{0,20}公平|用概率比较游戏规则
E.S03.03.01|频率估计概率|用试验频率估计概率
M.S03.02|几何概率|根据长度、面积的比例求几何概率|目录的考点以有限、等可能结果的列举为主。
""".strip()

# Variants are matched with the subject and verb together wherever possible.
VARIANTS = {
    'E.N03.02.01': r'单项式的?系数|多项式的?(项数|次数)', 'E.N03.02.02':r'若.{0,40}与.{0,40}(互为|是)同类项',
    'E.N03.04.01': r'积的乘方|幂的乘方|指数幂|负指数|零指数|指数相加|指数相减|底数不变',
    'E.N03.05.01': r'多项式的乘法|单项式乘|整式的?乘法|展开.{0,18}多项式|运用分配律展开',
    'E.N03.06.01': r'完全平方(公式|式)|乘法公式|平方差[）)(，：。]|两数和.{0,12}平方',
    'E.N03.06.02': r'(已知|因为|∵).{0,9}a\+b=.{0,18}ab=.{0,50}(a\^|平方)|利用完全平方公式.{0,12}(整体代入|对称式)',
    'E.N03.08.01': r'公式法.{0,9}因式分解|因式分解.{0,9}公式法|利用平方差公式分解|利用完全平方公式分解',
    'M.N03.05':r'多项式除以单项式|整式的?除法', 'M.N03.06':r'用图形面积.{0,16}(公式|恒等式)',
    'E.N03.09.01':r'找规律|图形的变化规律|数字变化(类|规律)|数字规律|依此规律|按此规律|根据(上述|以上|图中)的?规律',
    'E.N06.03.01':r'代入消元|解(?:下列)?(?:二元一次)?方程组|方程组的解法',
    'E.N06.04.01':r'一元一次方程的应用|列(出)?(?:二元一次)?方程组|设.{0,33}(由题意得|根据题意得).{0,20}方程',
    'E.N09.02.02':r'一元一次不等式组|解不等式组',
    'M.N10.01':r'自变量是|常量(是|与变量)|变量与常量|常量与变量|自变量与因变量',
    'E.N10.02.01':r'关系式表示|用关系式表示|写出.{0,35}(函数)?关系式|建立.{0,20}(函数)?关系式|函数(关系|解析)式|的关系式(为|是|可以表示|_{2,})|之间的关系式|根据.{0,20}表格.{0,22}关系式',
    'E.N10.02.02':r'图[象像]大致是|图[象像]信息|[从由]图[象像]可知|根据图[象像].{0,12}(获|读|可|确|求|判断)|变化.{0,25}大致图[象像]|图[象像](反映|可以大致)|分段函数的图[象像]|(横|纵)坐标(看出|可知)',
    'E.N11.02.01':r'用待定系数法|确定一次函数的?(解析式|关系式)',
    'E.G01.02.02':r'平分角|角平分线平分', 'E.G01.03.01':r'邻补角的?(定义|性质)|对顶角的?(性质|定义)',
    'M.G01.03':r'同位角的(定义|识别)|内错角的定义|内错角.{0,6}(是哪|有几对|是哪个)|点到直线的垂线段最短',
    'M.G01.02':r'余角的?(性质|定义)|同角的(余|补)角|余角和补角|补角的?(性质|定义)',
    'E.G01.04.01':r'内错角相等.{0,4}两直线平行|同旁内角互补.{0,4}两直线平行|同位角相等.{0,4}两直线平行|证明.{0,8}(∥|\\parallel)',
    'E.G01.05.01':r'两直线平行.{0,8}(内错角|同旁内角|同位角)',
    'E.G01.06.01':r'垂直平分线上的点|线段垂直平分线的性质',
    'E.G02.01.01':r'三角形.{0,18}(第三边|三边长)|两边之和.{0,4}(大于|>).{0,6}(第三边|另一边)|能[否够]构成三角形',
    'E.G02.01.02':r'外角.{0,14}内角.{0,6}和|内角和.{0,6}(180|定理)',
    'E.G02.02.01':r'画出.{0,14}(高线|边上的高|三角形的高)|作.{0,12}边上的高',
    'E.G02.02.02':r'中线.{0,10}面积|中线的?(性质|定义)',
    'E.G02.04.01':r'面积(割补|的和差)|分割.{0,18}(求|计算)面积|求.{0,6}阴影.{0,7}面积',
    'E.G02.04.02':r'同底等高|等高.{0,8}面积比|面积之比.{0,8}底边',
    'E.G03.01.01':r'全等三角形对应|全等.{0,7}对应(角|边)相等',
    'E.G03.02.01':r'三角形全等的?(判定|条件)|证明.{0,40}(?:≌|\\cong)|(?:SAS|SSS|AAS|ASA|斜边.{0,4}直角边).{0,26}(全等|判定)|判定两个三角形全等|补充.{0,15}条件.{0,25}(全等|\\cong|≌)',
    'E.G03.02.02':r'截长补短|倍长中线|构造全等三角形',
    'E.G04.01.01':r'等边对等角|三线合一|等腰直角三角形的性质',
    'E.G04.02.01':r'等边三角形的三条边|等边三角形.{0,10}角.{0,6}60',
    'E.G04.03.01':r'直角三角形的两个锐角|直角三角形斜边上的中线',
    'M.G07.01':r'轴对称图形的?(识别|概念|判定)|轴对称图形有|对称轴的条数|有.{0,4}条对称轴',
    'E.G07.01.01':r'关于.{0,15}对称的(点|图形)|轴对称作图|对称点的性质',
    'E.G07.01.02':r'将.{0,22}(折叠|翻折)|折叠.*重合|沿.{0,12}(折叠|翻折)',
    'E.G12.01.01':r'作一个角等于已知角|作一条线段等于已知线段|以.{0,18}为圆心.{0,20}画弧',
    'E.G12.03.01':r'作法的?(几何)?依据|作图的数学原理',
    'E.S03.01.01':r'必然事件|不可能事件|确定事件|可能性大小',
    'E.S03.02.01':r'摸到.{0,23}概率|取出.{0,16}概率|求.{0,30}的概率|列举.{0,15}(等可能|概率)|列表法|画树状图|等可能.{0,15}(结果|事件)',
    'E.S03.02.02':r'游戏规则.{0,15}公平|判断.{0,22}公平',
    'E.S03.03.01':r'大量重复试验|频率.{0,15}(逐渐|稳定)|用频率.{0,9}估计',
    'M.S03.02':r'几何概型|转盘.{0,23}面积.{0,10}概率|面积比.{0,20}概率',
}

@lru_cache(maxsize=1)
def vocabulary():
    result={}
    specs=[]
    exams,knowledge=references()
    for row in RULE_TEXT.splitlines():
        # Parse from both ends so alternatives inside the regex remain intact.
        fields=row.split('|')
        code=fields[0]
        tail=2 if code.startswith('M.') else 1
        title=fields[-tail]
        note=fields[-1] if tail==2 else ''
        pattern='|'.join(fields[1:-tail])
        if code not in exams and code not in knowledge: raise ValueError(code)
        result.setdefault(code,(title,note))
        variants=VARIANTS.get(code)
        specs.append((code,re.compile(pattern+'|'+variants if variants else pattern,re.I)))
    return result,specs

@lru_cache(maxsize=1)
def overrides():
    path=HERE/'g7t2_tag_reviews.json'
    return json.loads(path.read_text('utf8')) if path.exists() else {}

def compact(s):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',s or ''))

def math_text(s):
    s=re.sub(r'\\(?:left|right|mathrm|rm|bigg?)(?![a-zA-Z])','',s)
    s=s.replace(r'\(','').replace(r'\)','').replace('{','').replace('}','').replace('﹣','-').replace('−','-')
    return s.replace(r'\cdot','·').replace(r'\times','×').replace(r'\div','÷').replace(r'\left','').replace(r'\right','')

def algebra(prompt,sol):
    """Detect the printed structure even when the solution contains only equations."""
    p=math_text(prompt)
    s=math_text(sol)
    if re.search(r'\([^-+()]{1,20}[-+][^-+()]{1,20}\)\^2\+\([^-+()]{1,20}[-+][^-+()]{1,20}\)\^2=0',s):
        return ['E.N02.01.02','E.N03.06.01']
    if re.search(r'(?:x|a|m)\+(?:y|b|n)=',p) or re.search(r'(?:x|a|m)-(?:y|b|n)=',p):
        if re.search(r'(?:xy|ab|mn|x\^2|a\^2|m\^2)',p) and re.search(r'\)\^2|a\^2-b\^2|a\^2\+b\^2',s):
            return ['E.N03.06.02']
    if '面积' in p and re.search(r'两种|等式|验证',p) and re.search(r'\)\(|\)\^2',s):
        return ['M.N03.06'] if re.search(r'\)\^2|a\^2-b\^2',s) else ['E.N03.05.01','M.G02.04']
    if re.search(r'\^2\+[a-z]\^2.*\)\^2[-+]2[a-z]{2}',s) and re.search('等式|结论|值',p):
        return ['E.N03.06.02']
    only=re.sub(r'计算|化简|求值|求下列各式的值|直接写出(?:答案|结果)|结果是|解[:：]|原式|的结果为|的结果是|下列各题|〔图\d+〕','',p)
    if re.search('[一-鿿]',only) or not re.search(r'\^|\)\(|[a-z]\(|[·×÷]',only):return []
    if re.search(r'\^(?:0|-[1-9])',p) and not re.search(r'[abxyzmn](?:\^|\)|[+\-])',p):
        return ['E.N03.04.01']
    if re.search(r'\([^()]*[a-z0-9][+\-][a-z0-9][^()]*\)\^2',p):
        return ['E.N03.06.01']
    if re.search(r'\)\(',p):
        if any(''.join([left,'+',right,')(',left,'-',right]) in p or ''.join([left,'-',right,')(',left,'+',right]) in p
               for left,right in re.findall(r'\(([-\w^]+)[+-]([-\w^]+)\)',p)):
            return ['E.N03.06.01']
        return ['E.N03.05.01']
    if re.search(r'\([^()]{0,50}\+[^()]{0,50}\)÷|\([^()]+(?<!\^)-[^()]+\)÷',p):
        return ['M.N03.05','E.N03.04.01']
    if re.search(r'(?:[a-z]|\d)\([^()]*(?:\+|(?<!\^)-)[^()]*\)',p):
        return ['E.N03.05.01']
    if '^' in p and ('÷' in p or '·' in p or '×' in p or re.search(r'\)\^[0-9mna-z]',p)):
        return ['E.N03.04.01']
    return []

def geometric_method(prompt,solution,whole_stem):
    def geom(s):
        s=math_text(s)
        for a,b in [(r'\vartriangle','△'),(r'\triangle','△'),(r'\Delta','△'),(r'\angle','∠'),
                    (r'\parallel','∥'),('//','∥'),(r'\cong','≌'),(r'\equiv','≌'),
                    (r'\perp','⊥'),(r'\bot','⊥'),(r'\circ','°'),(r'\because','∵'),(r'\therefore','∴')]:
            s=s.replace(a,b)
        return s
    p=geom(prompt);s=geom(solution);w=geom(whole_stem)
    if '证明' in p or '求证' in p or '说明' in p:
        if re.search(r'(求证|证明|说明)[:：,，]?[A-Z]{2}.{0,4}∥[A-Z]{2}',p):return ['E.G01.04.01']
    if re.search(r'△[A-Z′\'_0-9]{3,9}≌△?[A-Z′\'_0-9]{3,9}|全等三角形|三角形全等',s):
        if re.search(r'证明|求证|说明|成立|关系|猜想',p) and not re.search(r'≌|全等',p):
            return ['E.G03.02.02']
        if re.search(r'≌|全等',p) and re.search('条件|判[定断]|证明|求证',p):
            return ['E.G03.02.01']
        return ['E.G03.01.01'] if ('由' in s[:12] or '≌' in p) else ['E.G03.02.01','E.G03.01.01']
    if re.search(r'过.{0,6}(?:点[A-Z])?.{0,3}作.{2,20}(∥|平行线)',s) and '∠' in s:
        return ['E.G01.05.02']
    if '∥' in s and '∠' in s:
        return ['E.G01.05.01'] if not re.search('判断.{0,10}平行|位置关系',p) else ['E.G01.04.01']
    if re.search(r'三角形两锐角互余|直角三角形.{0,12}(锐角|90)|两锐角互余',s):
        return ['E.G04.03.01']
    if re.search(r'等边三角形|等边△',s):return ['E.G04.02.01']
    if re.search(r'等腰(?:直角)?(?:三角形|△)',s) and ('∠' in s or '腰' in p):return ['E.G04.01.01']
    if re.search(r'平分∠|∠.{1,5}的平分线',p) and '∠' in s:return ['E.G01.02.02']
    if '∠' in s and re.search(r'180\^?°?[-ー−].{1,25}[-ー−]|内角和',s) and ('△' in w or '三角' in w):
        return ['E.G02.01.02']
    if '面积' in p and re.search('等积|同高|等高|共边',s):return ['E.G02.04.02']
    if '面积' in p and re.search(r'面积差|割补|S_.{1,35}-S_',s):return ['E.G02.04.01']
    return []

def record(codes, reason, origin):
    exams,know=references()
    mids,eids,notes=[],[],[]
    for target in dict.fromkeys(codes):
        code=target.rstrip('?')
        if code!=target:
            notes.append('本问还引入复数及虚数单位，v0.2 中该细目仅对应其幂或代数展开步骤。')
        if code in exams:
            mids.append(exams[code]['primary_knowledge_id']);eids.append(code)
        elif code in know:
            mids.append(code)
            note={'M.G01.03':'可归到相交线、垂线及所成角关系，细目未完整覆盖这项要求。',
                  'M.N03.05':'题目涉及整式的综合运算，细目只覆盖简单乘积展开。',
                  'M.P01.04':'本问要求根据体育实践提出建议，未要求独立完成数学计算。'}.get(code)
            notes.append(note or vocabulary()[0].get(code,('', '题目考查该知识主题，任务与现有细分考点不完全一致。'))[1])
        else:raise ValueError(code)
    return {'knowledge_ids':list(dict.fromkeys(mids)), 'exam_ids':eids,
            'coverage':('仅知识点' if not eids else '部分匹配' if notes else '完整匹配'),
            'tag_note':' '.join(dict.fromkeys(notes)), 'tag_reason':reason, 'tag_source':origin}

def classify(task,q):
    prompt=task.get('prompt') if task is not q else q.get('stem')
    prompt=compact((prompt or '')+' '+(task.get('stem_text') or ''))
    solution=task.get('given_solution') or '\n'.join(task.get('solution_steps',[]))
    focus=compact(explicit_focus(solution))
    solution=compact(solution)
    override=overrides().get(task['id'])
    if override:
        codes=override.split('+')
        return record(codes,'按题面要求和原解所用方法核定。','逐题核对')
    from_math=algebra(prompt,solution)
    if from_math:
        return record(from_math,'根据题中算式的幂、乘积或平方结构，以及解答的变形方式归类。','题文匹配')
    specs=vocabulary()[1]
    for value,label in ((prompt,'题面'),(focus,'资料考点说明'),(solution,'解答')):
        if not value:continue
        found=[]
        for code,rule in specs:
            m=rule.search(value)
            if m:found.append((m.start(),code))
        if not found:continue
        codes=list(dict.fromkeys(c for _,c in sorted(found)))
        # Prefer the specific task over the more general pattern sharing its name.
        for narrower,wider in [('E.G04.05.01','E.G04.04.01'),('E.G03.02.03','E.G03.02.01'),
                ('E.G12.03.01','E.G12.01.01'),('E.G12.01.02','E.G12.01.01'),
                ('E.G01.04.02','E.G01.04.01'),('E.S03.02.02','E.S03.02.01'),
                ('E.S03.03.01','E.S03.02.01'),('M.S03.02','E.S03.02.01'),
                ('M.N03.06','E.N03.06.01'),('E.N03.08.01','E.N03.06.01')]:
            if narrower in codes and wider in codes:codes.remove(wider)
        if label=='解答':
            # Whole-solution prose can include incidental arithmetic in a proof.
            # Keep only the first evidenced method at this lowest priority.
            codes=codes[:1]
        else:codes=codes[:2]
        if all(c in ('E.G01.02.01','E.G01.01.01','M.G01.02') for c in codes):
            more=geometric_method(prompt,solution,q.get('stem',''))
            if more: return record(more,'按本问解答中出现的几何关系及所求结论归类。','题文匹配')
        names=[vocabulary()[0][code][0] for code in codes]
        return record(codes,label+'指向'+'、'.join(names)+'。','题文匹配')
    geometry=geometric_method(prompt,solution,q.get('stem',''))
    if geometry:
        return record(geometry,'按本问解答中出现的几何关系及所求结论归类。','题文匹配')
    if task is not q:
        shared=compact(q.get('stem',''))
        if re.search(r'图[象像]|纵坐标|横坐标',shared) and re.search(r'速度|相距|相遇|多长时间|多少.{0,2}(分钟|小时)|距离|千米|路程|米/秒|出发|追上|几时|分钟',prompt):
            return record(['E.N10.02.02'],'公共图象描述两个量的变化，本问据此读取时间、距离或比较变化率。','题文匹配')
        if re.search(r'关系式|函数|变量|变化.{0,12}(时间|关系)|随.{0,10}变化',shared) and re.search(r'由表|上述表格|由上表|表中数据|表格补充完整',prompt+solution[:50]):
            return record(['E.N10.02.01'],'本问依据给定变量关系与表中数据补全另一种表示。','题文匹配')
        if re.search(r'当.{1,20}=.{0,8}[，,].{0,20}=',solution) and re.search(r'求|此时|当|多少|变化到|若',prompt):
            return record(['E.N03.01.02'],'本问将指定数值代入已知表达式求值。','题文匹配')
    legacy_code,details=autumn_match(task,q)
    details['tag_source']='题文匹配' if legacy_code else '待核'
    return details

def apply_tags(q):
    parts=q.get('parts',[])
    groups=[]
    for unit in parts or [q]:
        unit.update(classify(unit,q));groups.append(unit)
    if parts:
        q.update(aggregate(groups),tag_source='小问标签汇总')
    exams,knowledge=references()
    ids=q['exam_ids'] or q['knowledge_ids']
    if ids:
        q['title']='、'.join((exams.get(i) or knowledge[i])['name'] for i in ids[:2])
    return q
