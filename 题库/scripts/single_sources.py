"""Read mixed Word/PDF source packets without rewriting the original documents."""
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import hashlib
import posixpath
import re

from lxml import etree as ET
import pymupdf as fitz
from batch_content_xml import GLYPHS, M, RID, W, figpath, latex, omml


def doc_blocks(path, bank):
    """Keep the 1-based Word body index used by the print-position bookmarks."""
    with ZipFile(path) as z:
        root=ET.fromstring(z.read('word/document.xml'))
        rels={e.get('Id'):posixpath.normpath(posixpath.join('word', e.get('Target')))
              for e in ET.fromstring(z.read('word/_rels/document.xml.rels')) if e.get('TargetMode')!='External'}
        images={}
        def walk(n):
            k=ET.QName(n).localname
            if k=='object':
                obj=n.xpath('.//*[local-name()="OLEObject"]')
                if obj and (source:=rels.get(obj[0].get(RID+'id'))):
                    tex=latex(z.read(source))
                    if tex and not re.search(r'[\ud800-\uf8ff]',tex):return tex
                pic=n.xpath('.//*[local-name()="imagedata" or local-name()="blip"]')
                return walk(pic[0]) if pic else ''
            if k in ('imagedata','blip'):
                name=rels.get(n.get(RID+'embed') or n.get(RID+'id'))
                if name is None:return ''
                if name not in images:
                    raw=z.read(name)
                    glyph=GLYPHS.get(hashlib.sha256(raw).hexdigest()[:16])
                    images[name]=glyph or '⟦'+figpath(bank,raw,Path(name).suffix.lower())+'⟧'
                return images[name]
            if k=='oMath':return r'\('+omml(n)+r'\)'
            if k=='t':return n.text or ''
            if k=='tab':return '\t'
            if k in ('br','cr'):return '\n'
            if k=='AlternateContent':return walk(n[0]) if len(n) else ''
            if k=='tbl':return '\n'.join(' | '.join(' '.join(walk(p) for p in cell.findall(W+'p')) for cell in row.findall(W+'tc')) for row in n.findall(W+'tr'))
            if k in ('rPr','pPr','sectPr','tblPr'):return ''
            s=''.join(walk(c) for c in n)
            if k=='r':
                sup=n.find('./'+W+'rPr/'+W+'vertAlign')
                if sup is not None and s.strip():
                    return r'\({}'+('^' if sup.get(W+'val')=='superscript' else '_')+'{'+s+r'}\)'
            return s
        return {i:walk(b).strip() for i,b in enumerate(root.find(W+'body'),1)}


def localized(records):
    assets=[]
    def replace(m):
        key=m[1]
        if key not in assets:assets.append(key)
        return f'〔图{assets.index(key)+1}〕'
    return [(n,re.sub(r'⟦([^⟧]+)⟧',replace,t)) for n,t in records if t],assets


def numbered(blocks,n_max):
    """Locate complete consecutive sequences, allowing multiple printed copies of a paper."""
    result=[];current=[]
    for n,t in blocks.items():
        m=re.match(r'^\s*(\d{1,2})\s*[.．、]',t)
        if m and int(m[1])==len(current)+1:
            current.append(n)
            if len(current)==n_max:
                result.append(current);current=[]
    return result


def pdf_lines(doc):
    lines=[]
    for page in doc:
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                text=''.join(s['text'] for s in line['spans']).strip()
                text=text.encode('utf-16-le','surrogatepass').decode('utf-16-le','replace')
                x,y,x1,y1=line['bbox']
                if text:lines.append((page.number+1,y,x,x1,y1,text))
    return sorted(lines)


def crop(doc, start, end, outdir, name, bank, xlim=None):
    """Keep original glyphs, diagrams and aligned formulas, and strip empty answer space."""
    from PIL import Image,ImageChops
    result={'pages':[],'images':[],'regions':[]}
    for pg in range(start[0],end[0]+1):
        page=doc[pg-1]
        lo=start[1] if pg==start[0] else 34
        hi=end[1] if pg==end[0] else page.rect.height-36
        if hi<=lo+.1:continue
        x0,x1=xlim or (13,page.rect.width-13)
        rect=fitz.Rect(x0,lo,x1,hi)&page.rect
        pix=page.get_pixmap(matrix=fitz.Matrix(2.3,2.3),clip=rect,alpha=False)
        im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        box=ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L').point(lambda n:255 if n>34 else 0).getbbox()
        if not box:continue
        low=max(0,box[1]-5);high=min(im.height,box[3]+5)
        image=im.crop((0,low,im.width,high))
        dest=outdir/f'{name}-p{pg:02}.webp'
        image.save(dest,'WEBP',lossless=True,method=1)
        result['pages'].append(pg);result['images'].append(dest.relative_to(bank).as_posix())
        result['regions'].append({'page':pg,'bbox_pt':[round(x0,2),round(lo+low/2.3,2),round(x1,2),round(lo+high/2.3,2)]})
    if not result['images']:raise ValueError(f'Empty crop: {name} {start}–{end}')
    return result

def set_part_pages(question, paper_positions, solution_positions):
    """Map source bookmarks to the original printed page intervals, constrained by the verified question crops."""
    for part in question['parts']:
        source = part['source']
        for prefix, block_name, positions in (('question', 'paper_block_ids', paper_positions),
                                               ('solution', 'solution_block_ids', solution_positions)):
            field = prefix + '_pages'
            parent_pages = question['source'][field]
            if prefix == 'question' and set(part['material_ids']) & {'common-print', 'survey'}:
                # This part also displays the entire shared original diagram / table.
                source[field] = list(parent_pages)
                continue
            if source.get(field):
                if not set(source[field]) <= set(parent_pages):
                    raise ValueError(f"{part['id']} has a source outside its parent question")
                continue
            pages = set()
            keys = sorted(positions)
            for block in source.get(block_name, []):
                if block not in positions:
                    raise ValueError(f"{part['id']} missing {block_name} bookmark {block}")
                start_page, start_y = positions[block]
                pages.add(start_page)
                nxt = next((key for key in keys if key > block), None)
                if nxt is None:
                    pages.update(pg for pg in parent_pages if pg >= start_page)
                    continue
                stop_page, stop_y = positions[nxt]
                # A block can flow into the following page. An end bookmark
                # directly at the page's first content line does not add a page.
                if stop_page > start_page:
                    pages.update(range(start_page + 1, stop_page))
                    top = min(y for pg, y in positions.values() if pg == stop_page)
                    if stop_y > top + 2:
                        pages.add(stop_page)
            selected = [pg for pg in parent_pages if pg in pages]
            if not selected and source.get(block_name):
                raise ValueError(f"{part['id']} {field} has no overlap with its printed parent")
            source[field] = selected or list(parent_pages)
