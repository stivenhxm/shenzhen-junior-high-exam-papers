import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import registry


class RegisteredSources(unittest.TestCase):
    def test_known_alternate_moved_renamed_and_revised(self):
        with tempfile.TemporaryDirectory() as prefix:
            repo = Path(prefix)
            card = repo/'答题卡.pdf'
            card.write_bytes(b'answer sheet')
            entry = {'id':'P', 'paper':{'git_path':'paper.pdf','sha256':'p'},
                     'solution':{'git_path':'solution.pdf','sha256':'s'},
                     'alternate_sources':[{'git_path':card.name,'sha256':registry.file_digest(card),'role':'答题卡'}]}
            renamed = repo/'copy.pdf'
            renamed.write_bytes(card.read_bytes())
            for path in (card,renamed):
                self.assertEqual(registry.lookup([entry],path,repo),('已解析',entry,'答题卡'))
            card.write_bytes(b'revised answer sheet')
            self.assertEqual(registry.lookup([entry],card,repo)[0],'来源有更新，需复核')

    def test_lookup_repacked_or_revised_word_document(self):
        with tempfile.TemporaryDirectory() as prefix:
            root = Path(prefix)
            source = root/'原卷.docx'
            copy = root/'重新打包.docx'

            def word(path, body, timestamp):
                with ZipFile(path, 'w', compression=ZIP_DEFLATED) as archive:
                    archive.writestr('word/document.xml', body)
                    archive.writestr('word/media/image1.png', b'one figure')
                    archive.writestr('docProps/core.xml', timestamp)

            word(source, b'question', b'1')
            entry = {'id':'original', 'paper':{'git_path':source.name, 'sha256':registry.file_digest(source),
                                               'docx_content_sha256':registry.word_content_digest(source)},
                     'solution':{'git_path':'solution.docx', 'sha256':'other'}}
            self.assertEqual(registry.lookup([entry], source, root)[0], '已解析')
            word(copy, b'question', b'2')
            self.assertNotEqual(registry.file_digest(copy), entry['paper']['sha256'])
            self.assertEqual(registry.lookup([entry], copy, root)[0], '已解析')
            word(source, b'revised question', b'2')
            self.assertEqual(registry.lookup([entry], source, root)[0], '来源有更新，需复核')
            duplicate = dict(entry, id='second', paper=dict(entry['paper'], git_path=copy.name, sha256='other2'))
            with self.assertRaisesRegex(ValueError, '原卷重复登记'):
                registry.as_json([entry, duplicate])
