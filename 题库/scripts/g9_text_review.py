"""Normalize the notation of the printed grade-nine geometry and algebra sources."""
import re

INLINE = re.compile(r'\\\((.*?)\\\)', re.DOTALL)
PRIMED_LENGTH = re.compile(r"(?<![a-zA-Z])([A-Z](?:'?[A-Z])*')(?=\s*\^)")
AREA_SUBSCRIPT = re.compile(r'S_\{\s*(矩形|菱形|\\vartriangle)\s*\}\s*_\{\s*([A-Z]+)\s*\}')
LITERALS = {
    r'S_{ 四边形OCED } _{ 最大 }': r'S_{\text{四边形}OCED,\max}',
    r'C_{ _{ 四边形 } } _{ _{ BDE } _{ C } }': r'C_{\text{四边形}BDEC}',
    r'OB{}^\text{2} ^ { 2 } +OC{}^\text{2} ^ { 2 }': r'OB^2+OC^2',
    r'a & _{ 9 }': r'a_{9}',
    r'DF=3x- & \frac': r'DF=3x-\frac',
}


def notation(match):
    expr = match[1]
    expr = PRIMED_LENGTH.sub(r'{\1}', expr)
    expr = AREA_SUBSCRIPT.sub(r'S_{\1 \2}', expr)
    for old, new in LITERALS.items():
        expr = expr.replace(old, new)
    if expr.strip() == r'\therefore \frac { OQ } { MQ }=\frac { GQ } { OQ }' + '\\':
        expr = expr.strip()[:-1]
    return r'\(' + expr + r'\)'


def normalize(value):
    if isinstance(value, str):
        return INLINE.sub(notation, value) if r'\(' in value else value
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    return value
