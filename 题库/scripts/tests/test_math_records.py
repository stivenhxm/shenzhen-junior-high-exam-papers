import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from batch_content_xml import latex
except ModuleNotFoundError:
    latex = None


@unittest.skipUnless(latex, 'Requires Word equation import dependencies')
class MathTypeFontStyleTest(unittest.TestCase):
    def test_geometry_statement_after_font_style(self):
        root = Path(__file__).resolve().parents[3] / '初中数学试卷' / '深圳9下数学（含中考模拟）'
        source, = root.rglob('*33校联考*中考二模数学试题（解析版）.docx')
        with ZipFile(source) as doc:
            self.assertEqual(latex(doc.read('word/embeddings/oleObject294.bin')), r'\(AG\parallel BC\)')
            self.assertEqual(latex(doc.read('word/embeddings/oleObject295.bin')), r'\(BD\)')
