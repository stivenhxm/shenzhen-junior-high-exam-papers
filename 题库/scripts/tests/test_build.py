import argparse
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


class SeedPapers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = build.Bank(build.ROOT)

    def test_longhua_spring_scan_and_final_scoring_are_linked_to_their_own_exams(self):
        scan='SZ-G7-T2-9568EFD345'
        mid='SZ-G7-T2-AA58AC3E62'
        final='SZ-G7-T2-ECE61A19B5'
        for pid in (scan,mid,final):
            self.assertEqual(self.bank.papers[pid]['semester'],'下学期')
        answers=self.bank.shards
        scan_result=answers['answers/'+scan+'-Q21-P02']
        self.assertIn('6',scan_result['answer'])
        self.assertIn('10',answers['answers/'+mid+'-Q21-P02']['answer'])
        for pid in (scan, mid):
            self.assertEqual(set(self.bank.rows[pid+'-Q20-P02']['exam_ids']),
                             {'E.G01.04.01','E.G12.01.01'})
        corrected=answers['answers/'+final+'-Q17']
        self.assertEqual(corrected['given_answer'],'4')
        self.assertEqual(corrected['supplemental_solutions'][0]['pages'],[1])
        self.assertNotEqual(corrected['answer'],corrected['given_answer'])

    def test_g7_review_and_editorial_solution_preserve_the_original_source(self):
        qid = 'SZ-G7-T1-63B44AB70E-Q18-P03'
        corrected = self.bank.shards['answers/'+qid]
        self.assertEqual(corrected['solution_origin'],'source_checked_with_correction')
        self.assertIn('12.5',corrected['answer'])
        self.assertIn('11',corrected['given_solution'])
        self.assertTrue(corrected['source']['solution_pages'])
        supplied = self.bank.shards['answers/SZ-G7-T1-D74446848E-Q09']
        self.assertEqual(supplied['solution_origin'],'editorial_solution')
        self.assertEqual(supplied['given_solution'],'')
        self.assertTrue(supplied['given_answer'] and supplied['solution_steps'])

    def test_lowest_matching_tasks_and_school_filter(self):
        bank = self.bank
        experiment = "SZ-SY-CZB-2024-25-G7-T1-FINAL-Q16-P04"
        senior = "SZ-GJ-2024-25-G7-T1-FINAL-Q17-P04"
        matches = bank.shards["tags/E.S01.04.01"]["results"]
        seed_schools = {bank.rows[experiment]["paper_id"],bank.rows[senior]["paper_id"]}
        self.assertEqual({r["id"] for r in matches if r["paper_id"] in seed_schools}, {experiment, senior})
        school=bank.papers[bank.rows[experiment]["paper_id"]]["school"]
        args=argparse.Namespace(exam="E.S01.04.01",knowledge=None,paper=None,items=None,school=school)
        selection=build.subset(bank,args)
        ids={r["id"] for r in selection["results"]}
        self.assertIn(experiment,ids)
        self.assertNotIn(senior,ids)
        item = selection["data"]["items/"+experiment]
        self.assertTrue(item["html"] and item["source"]["question_pages"])
        self.assertNotIn("review_note",item)
        self.assertNotIn("given_answer",item)
        self.assertTrue(selection["data"]["answers/"+experiment]["solution_steps"])
        self.assertIn(item["source"]["paper_pdf"],selection["assets"])

    def test_paper_preserves_order_and_only_exports_its_references(self):
        paper="SZ-SY-CZB-2024-25-G7-T1-FINAL"
        args=argparse.Namespace(exam=None,knowledge=None,paper=paper,items=None,school=None)
        selection=build.subset(self.bank,args)
        self.assertEqual([r["number"] for r in selection["results"]],list(range(1,21)))
        self.assertEqual([p["id"] for p in selection["data"]["catalog"]["papers"]],[paper])
        for key,part in selection["data"].items():
            if key.startswith("items/"):
                self.assertEqual(part["paper_id"],paper)
                for ref in part["figures"]+part["source"]["question_images"]:
                    self.assertIn(ref,selection["assets"])

    def test_drawing_figures_follow_selected_units_into_exports(self):
        whole = 'SZ-GJ-2024-25-G7-T1-FINAL-Q14'
        first, second = [row['id'] for row in self.bank.shards['items/'+whole]['parts']]
        for selected, children in [(whole, [first, second]), (first, [first])]:
            args = argparse.Namespace(exam=None, knowledge=None, paper=None, items=[selected], school=None)
            practice = build.subset(self.bank, args)
            worked_figures = set(practice['data']['answers/'+selected]['solution_figures'])
            self.assertTrue(worked_figures)
            self.assertLessEqual(worked_figures, practice['assets'].keys())
            for child in children:
                self.assertLessEqual(set(practice['data']['answers/'+child]['solution_figures']), worked_figures)
            if selected == first:
                self.assertNotIn('items/'+second, practice['data'])


class Regeneration(unittest.TestCase):
    def test_retag_drops_obsolete_shards_and_failed_build_preserves_previous(self):
        class Dataset:
            def __init__(self,shards):
                self.shards=shards
                self.registry_json=build.registry.as_json([])
        first = Dataset({"catalog":{"tags":["M.1"]},"tags/M.1":{"id":"M.1"}})
        second = Dataset({"catalog":{"tags":["M.2"]},"tags/M.2":{"id":"M.2"}})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(build,"Bank",side_effect=[first,second,RuntimeError("failed")]):
                build.publish(root)
                build.publish(root)
                with self.assertRaises(RuntimeError):
                    build.publish(root)
            directory=root/"generated"
            self.assertFalse((directory/"tags/M.1.js").exists())
            self.assertEqual((directory/"tags/M.2.js").read_text("utf8"),build.expression("tags/M.2",second.shards["tags/M.2"]))
            second.root=root
            build.check_generated(second)
            (directory/"catalog.js").write_text("stale",encoding="utf8")
            with self.assertRaises(ValueError):
                build.check_generated(second)

    def test_prompt_content_is_escaped_and_real_math_is_renderable(self):
        safe=build.tokens(r'<script>alert(1)</script> \(2^{64}\) 〔图1〕',["assets/fig.png"])
        self.assertNotIn("<script>",safe)
        self.assertIn("data-tex=",safe)
        self.assertIn('src="assets/fig.png"',safe)
        self.assertIn('data-display="block"',build.tokens(r'\[x+1\]', []))
        with self.assertRaises(ValueError):
            build.tokens("〔图2〕",["assets/fig.png"])


if __name__=="__main__":
    unittest.main()
