"""Read Word body blocks, typeset embedded equations and preserve original illustrations."""
from __future__ import annotations

import contextlib
from functools import lru_cache
import hashlib
from io import BytesIO
from pathlib import Path
import posixpath
import re
from zipfile import ZipFile

from lxml import etree as ET
from olefile import OleFileIO
from PIL import Image
from mtef_records import EquationRecords


RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NUMBER = re.compile(r'^\s*(\d{1,2})(?:[.．、]\s*|\s+(?=\S))')
SECTION = re.compile(r'^\s*(?:[一二三四五六七八]\s*[、．.]\s*|第[一二三四五六]部分\s*)')
GLYPHS = dict.fromkeys(['46f198427d5e83c7','0588df34b385b507','27f5e6424121d961','242c7b955f15e46e'],'的')
GLYPHS.update({'d21221f5a6ab94c8':'.','605fa2c1788bd59f':'【','3e6444b39c5a8180':'【',
               'db201656909c85e3':'为','970c86f897d97f22':'为','c3a1b03e2e2825a4':'是','ecbb2cee6dceed1c':'是'})
GLYPHS.update({'4eb3157a5c23429b':'的','747228c1b52dc98e':'.','d943dfab765ebfa3':'【',
               '8da58972ef5b32b1':'为','f3efcf2f07a8c998':'是','22a21e97eeed223b':'在',
               '28c66c92eb8cd192':r'\(3b\)'})


class SilentOutput:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


class EquationStream(BytesIO):
    """Allow the parser's end-of-record check but stop repeated EOF reads."""
    def read(self, size=-1):
        data = super().read(size)
        if size > 0 and not data and getattr(self, 'at_end', False):
            raise ValueError('Truncated Equation Native stream')
        self.at_end = bool(size > 0 and not data)
        return data


@lru_cache(maxsize=6144)
def latex(blob):
    return decode_equation(blob, EquationRecords)


def decode_equation(blob, records):
    # mtef-py emits verbose diagnostics on stdout. A rejected expression falls
    # back to the exact preview image stored alongside the Equation object.
    try:
        with contextlib.redirect_stdout(SilentOutput()):
            with OleFileIO(BytesIO(blob)) as ole:
                if not ole.exists('Equation Native'):
                    return ''
                data = ole.openstream('Equation Native').read()
            header = int.from_bytes(data[:2], 'little')
            size = int.from_bytes(data[8:12], 'little')
            if header != 28 or size < 1 or len(data) < header + size:
                return ''
            m = records()
            m.reader = EquationStream(data[header:header+size])
            m.readRecord()
            m.makeAST()
            tex = m.Translate().strip().strip('$').strip()
    except (ValueError, IndexError, TypeError, KeyError, AttributeError, ArithmeticError, OSError):
        return ''
    tex = re.sub(r'\{\\text\{\[U\+([0-9A-Fa-f]+)\]\}\}',lambda h:chr(int(h[1],16)),tex)
    tex = re.sub(r'(?<!\\)%',r'\\%',tex)
    tex = re.sub(r'\s+\\$','',tex)
    if (not tex or '[U+' in tex or '\x00' in tex or '\u0802' in tex or
            re.search(r'\\begin\{(?:array|matrix)\}',tex) or
            any(0xe000<=ord(c)<=0xf8ff for c in tex)):
        return ''
    return r'\(' + re.sub(r'\s+',' ',tex) + r'\)'


def figpath(bank, raw, suffix):
    if suffix not in {'.png','.jpg','.jpeg','.webp','.gif','.svg'}:
        with Image.open(BytesIO(raw)) as image:
            if suffix in ('.wmf','.emf'):
                image.load(dpi=192)
            buf=BytesIO()
            image.convert('RGB').save(buf, format='PNG')
        raw, suffix = buf.getvalue(), '.png'
    digest=hashlib.sha256(raw).hexdigest()
    rel=f'assets/figures/{digest[:2]}/{digest}{suffix}'
    dest=bank/rel
    if not dest.is_file():
        dest.parent.mkdir(exist_ok=True,parents=True)
        dest.write_bytes(raw)
    return rel


def local(node):
    return ET.QName(node).localname


def omml(n):
    k=local(n)
    if k=='t':
        return (n.text or '').replace('%',r'\%')
    if k.endswith('Pr'):
        return ''
    if k=='f':
        return r'\frac{'+omml(n.find(M+'num'))+'}{'+omml(n.find(M+'den'))+'}'
    if k in ('sSup','sSub','sSubSup'):
        return '{'+omml(n.find(M+'e'))+'}'+''.join(
            sym+'{'+omml(z)+'}' for kind,sym in [('sub','_'),('sup','^')] if (z:=n.find(M+kind)) is not None)
    if k=='rad':
        return r'\sqrt{'+omml(n.find(M+'e'))+'}'
    if k=='d':
        p=n.find(M+'dPr')
        def delim(k,default):
            val=p.find(M+k) if p is not None else None
            c=val.get(M+'val',default) if val is not None else default
            return {'{':r'\{','}':r'\}'}.get(c,c)
        return delim('begChr','(')+','.join(omml(e) for e in n.findall(M+'e'))+delim('endChr',')')
    return ''.join(omml(c) for c in n)


def sections(path, bank, question_starts=None):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
        rel_root = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
        rels={e.get('Id'):posixpath.normpath(posixpath.join('word',e.get('Target'))) for e in rel_root
              if e.get('TargetMode')!='External'}
        number=0
        active=None
        category=''
        rows=[]
        images={}
        cache={}
        def img(n):
            rel=rels[n.get(RID+'embed') or n.get(RID+'id')]
            if rel not in images:
                blob=archive.read(rel)
                glyph=GLYPHS.get(hashlib.sha256(blob).hexdigest()[:16])
                path=None if glyph else figpath(bank,blob,Path(rel).suffix.lower())
                glyph=glyph or GLYPHS.get(Path(path).stem[:16])
                images[rel]=(glyph or path,bool(glyph))
            name,literal=images[rel]
            if literal:
                return name
            if name not in active['figures']:
                active['figures'].append(name)
            return f"〔图{active['figures'].index(name)+1}〕"
        def walk(n):
            k=local(n)
            if k=='object':
                ole=n.xpath('.//*[local-name()="OLEObject"]')
                if ole:
                    target=rels[ole[0].get(RID+'id')]
                    if target not in cache:
                        cache[target]=latex(archive.read(target))
                    if cache[target]:
                        return cache[target]
                preview=n.xpath('.//*[local-name()="imagedata" or local-name()="blip"]')
                if not preview:
                    raise ValueError(f'{path.name} 第{number}题嵌入对象缺少预览')
                return img(preview[0])
            if k in ('imagedata','blip'):
                return img(n)
            if k=='t':
                return n.text or ''
            if k=='tab':
                return '\t'
            if k in ('br','cr'):
                return '\n'
            if k=='AlternateContent':
                return walk(n[0]) if len(n) else ''
            if k=='oMath':
                return r'\('+omml(n)+r'\)'
            if k=='r' and n.tag.startswith(W):
                sup=n.find('./'+W+'rPr/'+W+'vertAlign')
                result=''.join(walk(c) for c in n)
                if sup is not None and result.strip():
                    return r'\({}'+('^' if sup.get(W+'val')=='superscript' else '_')+'{'+result+r'}\)'
                return result
            if k=='sym':
                char=n.get(W+'char','')
                try: return chr(int(char,16))
                except ValueError: return ''
            return ''.join(walk(c) for c in n)
        def table_cells(table):
            def cell_paragraphs(cell):
                paragraphs=[]
                for item in cell:
                    if item.tag==W+'p':
                        paragraphs.append(walk(item).strip())
                    elif item.tag==W+'tbl':
                        paragraphs.append(table_text(table_cells(item)))
                return paragraphs
            return [[cell_paragraphs(tc) for tc in tr.findall(W+'tc')] for tr in table.findall(W+'tr')]

        def table_text(cells):
            return '\n'.join(' | '.join(' '.join(c) for c in row) for row in cells)

        body=root.find('.//'+W+'body')
        for bidx,block in enumerate(body,1):
            if local(block)=='sectPr':
                continue
            plain=''.join(block.xpath('.//*[local-name()="t"]/text()')).strip()
            if re.fullmatch(r'第[ⅠⅡ一二12]卷',plain):
                active=None
                category=''
                continue
            if (SECTION.match(plain) and re.search('题|部分',plain[:18])) or re.match(r'^(?:选择|单项选择|填空|解答)题\s*[:：（(]',plain):
                category=plain
                active=None
                continue
            match=NUMBER.match(plain)
            # Ignore numbered instructions in the exam cover.
            if question_starts is not None:
                begins = question_starts.get(bidx) == number + 1
            else:
                begins = match and int(match[1]) == number+1 and category
            if begins:
                number+=1
                active={'number':number,'section':category or '选择题','blocks':[],'figures':[],'tables':[]}
                rows.append(active)
            if active is None:
                continue
            if local(block)=='tbl':
                cells=table_cells(block)
                text=table_text(cells)
                if text.strip():
                    active['tables'].append({'text':text,'rows':cells})
            else:
                text=walk(block).strip()
            if text.strip():
                active['blocks'].append((bidx,text.strip()))
        if not rows:
            raise ValueError(f'未找到按卷顺序编号的题目：{path.name}')
        return rows
