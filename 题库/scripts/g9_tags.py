"""Classify the printed task of each Grade 9 question or independently answered part."""
from functools import lru_cache
import json
import re
from pathlib import Path

from batch_tags import references
from g7_tags import aggregate, explicit_focus, pending
from g8_tags import classify as foundation, make_rules, matched, norm, tags


# These cues name an operation or a precise result. Put conditions and topics
# that require the shared setup in contextual(), so mentioning a curve or a
# tangent in the preamble does not assign its properties to every part.
PRINTED = make_rules(r"""
E.N01.02.02 相反数|互为倒数|的倒数
E.N01.06.01 科学[记计]数法
E.G11.02.01 主视图|左视图|俯视图|三视图
E.G11.01.01 展开图|展开与折叠|正方体.{0,30}(相对|对面)
E.G11.02.02 平行投影|中心投影|正投影
E.G11.02.02 (画出|确定).{0,32}(影子|光源)|灯.{0,16}(影长|影子)
E.G08.01.01 比例尺
E.G10.01.02 特殊(?:角|锐角).{0,8}三角函数值
E.G08.01.03 黄金分割|黄金比
E.G08.01.02 平行线分线段|平行线等分线段
E.G08.01.01 成比例线段|比例线段|比例的?(基本)?性质
E.G07.04.02 画出.{0,60}位似|位似.{0,22}(放大|缩小)
E.G09.02.02 位似.{0,64}(坐标|坐标轴)|坐标.{0,20}位似
E.G07.04.01 位似中心|位似比
E.G08.03.02 相似.{0,25}面积比|面积[之的]?比.{0,20}相似比
E.G08.03.01 相似.{0,18}(周长[之的]?比|对应边[之的]?比)
E.G08.02.01 (求证|证明).{0,48}(相似|∽|\\sim)|判定.{0,12}三角形相似|相似三角形的判定条件
E.G10.03.02 坡度|坡比
E.G06.06.02 (求证|证明|试说明).{0,48}(切线|相切)|切线的判定
E.G06.05.01 点与圆的位置关系|直线与圆的位置关系
E.G06.04.01 圆内接四边形.{0,22}(互补|对角)
E.G06.02.01 垂径定理|弦心距
E.G06.03.02 同弧.{0,12}圆周角相等|同弦.{0,12}圆周角相等
E.G06.03.01 圆周角定理|圆周角与圆心角|直径所对的圆周角
E.G06.09.01 外心|三点确定.{0,3}圆
E.G06.09.02 内心|三角形的内切圆圆心
E.G06.07.01 正.{0,8}边形的?中心角
E.G13.01.02 定义.{0,22}(四边形|三角形|几何图形).{0,22}(称为|叫做)
E.S03.01.01 必然事件|不可能事件|是随机事件|确定性事件
E.S03.02.02 (游戏|规则|方案).{0,36}公平|公平.{0,10}(游戏|规则)
E.S03.03.01 频率.{0,20}(稳定|估计概率|估计|接近)|用频率估计|大量重复[实试]验
E.S03.02.01 树状图|树形图|列表法|列举.{0,16}等可能
E.N07.01.01 一元二次方程的?(定义|一般形式|二次项系数)|是一元二次方程|化为.{0,5}一般[形式]+
E.N07.01.02 (方程.{0,70}(的一个根[为是]|的一个解[是为])|是.{0,35}方程的一个根)|一元二次方程(根|解)的定义
E.N07.02.01 配方法解|因式分解法解|公式法解|解.{0,5}一元二次方程|用配方法.{0,10}方程
E.N07.04.02 利用根与系数的关系.{0,10}(式|值)
E.N07.04.01 韦达定理|根与系数的关系
E.N12.01.02 反比例函数.{0,20}(几何意义|面积的关系)
E.N12.02.01 (求|确定|写出).{0,10}反比例函数.{0,10}(解析式|表达式|关系式)
E.N13.01.02 抛物线.{0,65}平移|平移.{0,40}抛物线|二次函数图[像象]的?平移
E.N13.02.01 (求|确定|写出).{0,15}(二次函数|抛物线)的?(解析式|表达式|函数关系式)
E.N13.02.02 (一般式|二次函数).{0,25}(化为|转化为).{0,10}顶点式
""".strip())


@lru_cache(maxsize=1)
def reviews():
    path = Path(__file__).with_name('g9_tag_reviews.json')
    return json.loads(path.read_text('utf8')) if path.is_file() else {}


def contextual(p, s, shared):
    """Use common conditions to identify the object of this specific task."""
    ctx = p + shared
    tests = lambda pattern: re.search(pattern, p, re.I)
    uses = lambda pattern: re.search(pattern, s, re.I)
    has = lambda pattern: re.search(pattern, ctx, re.I)
    math = lambda text: text.replace('{', '').replace('}', '')
    s=s.replace(r'\backsim','∽').replace(r'\sim','∽')
    quadratic = has(r'抛物线|二次函数|y=[-+a-z0-9{}\\]*(?:x\^|x²|\(x[-+])')
    inverse = has(r'反比例|双曲线|y=\\(?:d?frac)\{[-a-z0-9]+\}\{x\}')
    equation = has(r'一元二次方程|关于x的方程|方程.{0,60}x\^')
    expression = tests('关系式|表达式|解析式')
    if has('销售|售价|利润|进货|成本') and tests('利润.{0,5}最[大高]|最[大高].{0,4}利润|获利最[大多]') and uses(r'顶点|对称轴|开口向下|[a-z]\^\{?2|二次函数'):
        return ['E.N13.04.02']
    if tests('圆心角|所占百分比|补全统计图') and has('扇形统计图|条形统计图|统计图表'):
        return ['E.S01.03.01']
    if tests('阴影.{0,10}面积|弓形.{0,10}面积') and uses('扇形|弓形'):
        return ['E.G06.08.02']
    if re.fullmatch(r'[^\n。]{1,75}=.{1,22}[;.。]?',p) and re.search(r'x_1=.{0,55}x_2=',math(s)) and not tests('参数|求值|范围'):
        return ['E.N07.02.01']
    if tests('取值范围|的范围|可以取') and uses(r'(?:\\Delta|Δ).{0,14}(?:[<>≥≤]|\\ge|\\le)|判别式.{0,18}(?:大于|小于)'):
        return ['E.N07.03.02']
    if tests('根|值') and re.search(r'x_1\+x_2=|x_1x_2=',math(s)) and ('两根' in s or '两个根' in s or '根与系数' in s or '两个实数根' in s):
        return ['E.N07.04.02'] if re.search(r'x_1x_2.{0,18}x_1|x_1\^|x_2\^|x_1.x_2.{0,10}=',math(p)) else ['E.N07.04.01']
    if tests('利润|降价|售价|销售|增长|养殖场|养鸡场|花圃|比赛|球队') and uses(r'(?:[xyz]_?\{?1\}?=|[xyz]\^\{?2\}?|一元二次方程)'):
        result=['E.N07.05.01']
        if uses('舍去|不合题意|不符合|应取|不符题意'):result.append('E.N07.05.02')
        return result
    if tests('求|多少|几|数量') and '\\begin{cases}' in s and uses('设.{0,80}[xy]') and not has('坐标|函数|直线|图象|图像'):
        return ['E.N06.04.01']
    if tests('影子|影长|路灯的位置') and (tests('画|作|确定') or uses('光源|中心投影')): return ['E.G11.02.02']
    if tests('角|tan|sin|cos') and re.search(r'(?:tan|sin|cos)(?:30|45|60)',math(s)) and (tests('度数|值|余弦|正切|正弦') or uses('特殊角')):return ['E.G10.01.02']
    if tests('高|距|宽|的长') and uses(r'Rt△|直角三角形') and uses('sin|tan|cos') and not has('仰角|俯角|坡度|坡比'):
        return ['E.G10.02.02'] if uses('过.{0,18}作.{0,6}⊥|如图.{0,20}⊥') else ['E.G10.02.01']
    if tests('概率|可能性') and tests('公平'): return ['E.S03.02.02']
    if (tests('概率|可能性') or has('试验|摸球|发芽')) and (tests('频率.{0,25}(稳定|接近|估计)|估计.{0,30}(概率|球|发芽)') or uses('用频率估计|频率稳定')):
        return ['E.S03.03.01']
    if tests('概率') and (has('转盘|阴影') and uses('面积比|面积之比|所占面积|圆心角.*360')):
        return ['M.S03.02']
    if tests('概率') and (has('随机|摸出|掷|抽取|任取|抛掷|任意取') or uses('等可能|画树|列表|共有.{0,12}种')):
        return ['E.S03.02.01']
    if has('坡度|坡比') and tests('坡度|坡比|坡面|坡长|坡角'): return ['E.G10.03.02']
    if has('仰角|俯角') and (tests('仰角|俯角|高|长|宽|距') or uses('sin|cos|tan|三角函数')): return ['E.G10.03.01']
    if tests('仰角|俯角') and uses('tan|sin|cos|解直角'): return ['E.G10.03.01']
    if tests(r'计算|求值|结果') and tests(r'(?:sin|cos|tan)[{(]*(?:30|45|60)'):
        return ['E.G10.01.02','E.N02.05.01'] if tests(r'√|\^\{?-|\|') else ['E.G10.01.02']
    if tests(r'正弦|余弦|正切|(?:sin|cos|tan)(?:∠|[A-Zα-ω])') and not tests('高度|长为|坡度|仰角|俯角'):
        return ['E.G10.01.01']
    if quadratic:
        if tests('平移') and tests('图[象像]|抛物线|单位'): return ['E.N13.01.02']
        if expression and tests('直线|一次函数') and not tests('(求|确定).{0,8}(二次函数|抛物线)'): pass
        elif expression and tests('求|写出|确定|为|是'): return ['E.N13.02.01']
        if tests('通过|能否|安全|碰到|越过|穿过|净高') and has('桥|拱|球|隧道|门洞'): return ['E.N13.04.03']
        if tests('最[大小多少高低]|最高点') and has('利润|销售|售价|拱桥|农场|鸡场|篮球|足球|喷泉|隧道'): return ['E.N13.04.02']
        if tests('最[大小]值|有最大|有最小') and (tests('取值范围|当|区间|≤|≥|自变量') or uses('区间|对称轴|顶点')): return ['E.N13.04.01']
        if tests('交点.{0,12}个数|相交.{0,12}不同的|只有一个公共点') and tests('取值|范围|值'): return ['E.N13.03.03']
        if tests('不等式|函数值.{0,12}(正数|负数|大于|小于)|[yy][^。]{0,12}[<>≥≤].{0,16}范围'): return ['E.N13.03.02']
        if tests('与.{0,12}[x横]轴.{0,16}交点|交点.{0,16}[x横]轴') and uses('令|方程|解得'): return ['E.N13.03.01']
        if tests('顶点|对称轴|开口|增大而|增减性|图[像象].{0,12}(性质|正确|经过)'):
            return ['E.N13.01.03'] if tests('参数|取值范围|[abc].{0,12}的范围') else ['E.N13.01.01']
    if inverse:
        if expression and not tests('二次函数|抛物线'):
            result=[]
            if tests('反比例|双曲线') or (not tests('直线|一次函数')): result.append('E.N12.02.01')
            if tests('直线|一次函数'): result.append('E.N11.02.01')
            return result
        if tests('面积') and (uses('几何意义|系数.{0,10}面积|面积.{0,10}系数') or has('坐标轴|[xy]轴|原点') and uses(r'\\frac\{1\}\{2\}.{0,18}k|\|k\|')): return ['E.N12.01.02']
        if tests('交点.{0,12}坐标|另一交点') and has('一次函数|直线'): return ['E.N12.03.01']
        if tests('不等式|取值范围') and has('一次函数|直线') and uses('交点|图[象像]'): return ['E.N12.03.02']
        if tests(r'(?:k|比例系数|常数).{0,8}(值|等于|为)|系数.{0,5}是'): return ['E.N12.02.01']
        if tests('象限|分支|增大|越大|大小关系|比较.{0,12}函数值') or uses('反比例函数的性质') and tests('大小|次序|正确'):
            return ['E.N12.01.01']
    if equation:
        if tests('实数根|实根|根的情况|判别式|两个不相等|两个相等'):
            return ['E.N07.03.02'] if tests('范围|参数|实数.{0,8}(取值|可取)') else ['E.N07.03.01']
        if tests('一个根|一根|的一个解') and tests('参数|的值|为|等于'): return ['E.N07.01.02']
        if tests('两根|两个根|两个实数根|两实根') and uses('根与系数|韦达|两根之和|两根之积'):
            return ['E.N07.04.02'] if re.search(r'x_1\^|x_2\^|x_1-x_2|x_2-x_1',math(p)) else ['E.N07.04.01']
        if tests('解.{0,4}方程') and not tests('不等式|分式|参数|范围'): return ['E.N07.02.01']
    if (tests('增长率|下降率|降低率|平均增长|平均下降') and (uses('方程|解得|列式') or tests('列|方程'))) or (tests('列.{0,20}方程') and uses('一元二次|增长率')):
        return ['E.N07.05.01']
    if tests('弧长|弧.{0,6}的长|扇形.{0,18}面积') and has('圆|扇形') and not has('统计'): return ['E.G06.08.01']
    if tests('阴影.{0,10}面积') and uses('扇形|弓形'): return ['E.G06.08.02']
    if tests('切线长') and uses('切线长定理|切线长相等'): return ['M.G06.06']
    if tests('相似|∽') and tests('面积比|面积之比'): return ['E.G08.03.02']
    if tests('相似|∽') and tests('周长比|周长之比|边长|对应边'): return ['E.G08.03.01']
    if uses('∽|\\\\sim(?![a-z])|三角形相似|相似三角形') and not tests('概率|函数关系|解析式'):
        if tests('测|树高|高度|身高|影长|河宽') and uses('比例|成比例|∽|\\\\sim'): return ['E.G08.04.01']
        if tests('不变|定值') and uses('定值|不变'): return ['E.G08.04.02']
        if tests('面积比|面积之比') and uses('面积比|面积的比|相似比的平方'): return ['E.G08.03.02']
        if tests('长度|的长|距离|周长|比值|的值|之比') and uses('对应边|比例|∽|\\\\sim'): return ['E.G08.03.01']
    return []


TOPICS = make_rules(r"""
M.N13.04 二次函数的?(实际)?应用
M.N13.01 二次函数的?(性质|图[像象])|抛物线
M.N12.03 反比例函数的?(实际|综合)应用
M.N12.01 反比例函数
M.N07.05 一元二次方程的?(实际)?应用
M.N07.04 根与系数
M.N07.02 一元二次方程的解法
M.G06.08 圆锥.{0,8}(侧面积|侧面展开图)|弧长|扇形面积
M.G06.06 切线长定理|切线
M.G06.02 垂径定理
M.G06.03 圆周角
M.G06.01 圆心角|弦与弧
M.G08.03 相似比
M.G08.02 相似三角形|三角形相似
M.G08.01 比例线段
M.G10.02 解直角三角形
M.G07.04 位似
M.S03.02 概率公式
""".strip())


def scoped_methods(p, s, shared):
    """Recognize the requested result together with a method used in its worked solution."""
    def math_text(value):
        return value.replace(r'\backsim','∽').replace(r'\sim','∽').replace('{','').replace('}','')
    p,s,shared=map(math_text,(p,s,shared))
    body=p+shared
    ask=lambda rx: re.search(rx,p)
    work=lambda rx: re.search(rx,s)
    ctx=lambda rx: re.search(rx,body)
    if ask('取值范围|范围|取什么值') and work(r'有.{0,8}(?:实数根|实根)|判别式|(?:△|Δ|\\Delta)=.{0,100}[>≥≤<]'):
        return ['E.N07.03.02']
    if ask(r'∽|相似') and ask('求证|证明|说明理由|判断.{0,12}是否相似'):
        return ['E.G08.02.01']
    if work('∽|相似三角形|三角形相似') and ask('旗杆|影长|身影|树高|楼高|河宽|建筑高度'):
        return ['E.G08.04.01']
    if work('∽|相似三角形|三角形相似'):
        if ask('格点|网格|构造|作.{0,8}点') and ask('∽|相似'):return ['E.G08.02.02']
        if ask('面积之比|面积比') and work('面积比|平方|相似比'):return ['E.G08.03.02']
        if ask(r'长度|的长|长为|长是多少|之比|的比|[A-Z]{2}[:/][A-Z]{2}|求[线段]*[A-Z]{2}(?:[。.;,，；]|$)') and not ask('概率|面积'):
            return ['E.G08.03.01']
        if ask('相似|上述结论|数量关系|判断|求证|证明|成立|边长|的值') and work('∽') and work(r'\\frac|对应边|成比例|比例式'):
            return ['M.G08.02']
    roots=work(r'([a-z])_1=.{0,75}\1_2=|([a-z])\^2.{0,36}=0|一元二次方程')
    if ask('利润|售价|降价|增长率|价格|销售额|销售量|销售收入|销售|收入|养鸡场|围栏|草坪|花圃') and roots and work('设|整理得|解得|列方程'):
        result=['E.N07.05.01']
        if work('舍去|不符|优惠|让利|实惠|减少库存|尽快|多售|尽量|不合题意'):result.append('E.N07.05.02')
        return result
    if ask('销售|销量|人数|票价|收入|金额') and ('代入' in s or work(r'\d+[×+\-]\d+')) and not roots and not ask('概率|统计|频数|总体|抽样'):
        return ['E.N03.01.02']
    if ask('方案|利润|能否') and work(r'(?:△|Δ|\\Delta).{0,80}<0') and work('无实数根|没有实数根'):return ['E.N07.03.01']
    if ask(r'方程|^[（(①②12.）);]*[a-z].{0,35}=0') and roots and work(r'公式法|配方法|解得|因式分解|[a-z]_1='):
        return ['E.N07.02.01']
    if ask('方程|转化') and work('本题考查配方法|配方,得'):return ['E.N07.02.01']
    if ask('方程|的根|的一个根') and work('是.{0,40}方程的一个根|一元二次方程的解') and not ask('是否为一元二次方程'):return ['E.N07.01.02']
    if ask('求|的值|两根|根的关系') and work(r'x_1\+x_2=') and work(r'x_1x_2='):return ['E.N07.04.02']
    if ask('求|几|测') and work('tan|sin|cos|利用三角函数') and work('直角三角形|Rt△|作.{0,12}⊥') and not ask('面积|周长'):
        return ['E.G10.02.02'] if work('作.{0,12}⊥') else ['E.G10.02.01']
    if ask('画|绘制|列表|描点|连线|补全') and ctx('函数图[像象]|函数.{0,40}图[像象]|列表.{0,40}描点|描点.{0,40}连线|平滑.{0,12}各点'):
        return ['E.N10.02.01']
    if ask('下列说法|变化|关系|范围|是多少') and work('根据函数图[像象]|由函数图[像象]可知|根据图[像象]所给信息') and not ctx('反比例|二次函数|抛物线'):
        return ['E.N10.02.02']
    if ctx('等邻边四边形') and ask('画|作|判断|是否|证明.{0,25}等邻边'):return ['E.G13.01.02']
    if ask('图象|函数|代入|表') and work('代入') and work(r'y=[-0-9]+/x|y=\\frac[-0-9]+x') and work('求出|时|分别得'):return ['M.N12.02']
    if ask('样本|全校|该校|总人数') and ask('估计|约有|估算') and work(r'占|比例|×|\\frac'):return ['E.S01.04.01']
    if work('三角形中位线|中位线定理') and ask('长|的值|长度|中点'):return ['E.G05.05.01']
    if ask('平行|直线|线段') and work(r'[a-z]∥[a-z]∥[a-z]') and work(r'\\frac'):return ['E.G08.01.02']
    if work('设a=.{0,10},b=.{0,10},c=|设a=.{0,10},c=') and ask(r'\\frac|三边长|比例'):return ['E.G08.01.01']
    if ask('面积') and ctx('菱形') and work('对角线|菱形.{0,16}面积'):return ['E.G05.03.01']
    if ask('求证|证明|数量关系') and work('≌|三角形全等') and work(r'ASA|SAS|AAS|SSS|∴.{0,26}≌'):
        return ['E.G03.02.01'] if ask('≌|全等') else ['E.G03.02.02']
    if ask('求|长度|多长') and work('勾股定理|勾股关系') and not ask('证明|求证'):return ['E.G04.04.01']
    if ask('切线|求证|角') and work(r'是.{0,15}切线.{0,18}(?:90|⊥)'):return ['E.G06.06.01']
    return []


def classify(unit, q):
    row = reviews().get(unit['id'])
    if row:
        ids, reason, *note = row
        return tags(ids.split('+'), reason, '逐题核对', *note)
    if unit.get('tag_source')=='逐题核对' and unit.get('knowledge_ids') and unit.get('tag_reason'):
        return {key:unit[key] for key in ('knowledge_ids','exam_ids','tag_reason','tag_note','coverage','tag_source')}
    prompt = unit.get('prompt', q['stem'])
    solution = unit.get('given_solution') or '\n'.join(unit.get('solution_steps', []))
    p, s = norm(prompt), norm(solution)
    shared = norm(' '.join(m['text'] for m in q.get('materials', []) if m['id'] in unit.get('material_ids', [])))
    focus = norm(explicit_focus(solution))
    detail = contextual(p,s,shared) or scoped_methods(p,s,shared)
    evidence = '本问题面与解答'
    if not detail:
        for text, label in [(p,'题面'),(focus,'解析指明'),(s,'本问解答')]:
            code, cue = matched(PRINTED,text)
            if code:
                evidence, detail = label, [code]
                break
    if not detail:
        code, cue = matched(TOPICS,focus or p)
        if code: evidence, detail = '题目所考知识', [code]
    if detail:
        exams, knowledge = references()
        names = '、'.join((exams.get(i) or knowledge[i])['name'] for i in detail)
        return tags(detail, evidence+'对应“'+names+'”。','题文匹配')
    result = foundation(unit,q)
    # Single characters for an angle, point or length in the common diagram
    # identify neither the knowledge being tested nor an exam objective.
    if result['tag_reason'].startswith('题目涉及“') and re.search(r'“(?:∠|△|面积|坐标|垂直|垂足|三角形|图象|图像)”',result['tag_reason']):
        return dict(pending(), tag_source='待核')
    return result


def apply_tags(q):
    parts = q.get('parts', [])
    for unit in parts or [q]:
        unit.update(classify(unit,q))
    if parts:
        q.update(aggregate(parts),tag_source='小问标签汇总')
    ids = q['exam_ids'] or q['knowledge_ids']
    preserve_printed_title = q.get('choices_in_facsimile') or (q.get('title') and q.get('source', {}).get('question_regions') and not q['source'].get('paper_body_blocks') and '〔图' in q['stem'])
    if ids and not preserve_printed_title and '〔图' != q['stem'][:2]:
        exams, knowledge = references()
        q['title'] = '、'.join((exams.get(i) or knowledge[i])['name'] for i in ids[:2])
    return q
