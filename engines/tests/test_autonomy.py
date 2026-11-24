import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from autonomy import validate,evaluate,next_stage,select_skills,load,ROOT,WEIGHTS,GATES

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.plan=load(ROOT/"engines/example-plan.json")
        self.review={"artifact_sha256":"a"*64,"gates":dict.fromkeys(GATES,"pass"),"scores":dict.fromkeys(WEIGHTS,4),"evidence":dict.fromkeys(WEIGHTS,"synthetic test evidence"),"defects":[]}
    def test_valid(self):
        self.assertEqual(validate(self.plan),[])
    def test_bad_rights(self):
        self.plan["assets"][0]["rights"]="unknown"
        self.assertTrue(validate(self.plan))
    def test_retime_rejected(self):
        self.plan["clips"][0]["source_out"]=99
        self.assertTrue(validate(self.plan))
    def test_gap(self):
        self.plan["clips"][0]["timeline_in"]=1
        self.plan["clips"][0]["source_in"]=11
        self.assertTrue(validate(self.plan))
    def test_unknown_asset(self):
        self.plan["clips"][0]["asset_id"]="absent"
        self.assertTrue(validate(self.plan))
    def test_review(self):
        self.assertTrue(evaluate(self.review)["approved"])
    def test_gate(self):
        self.review["gates"]["observation"]="unknown"
        self.assertFalse(evaluate(self.review)["approved"])
    def test_p1(self):
        self.review["defects"]=[{"severity":"P1","evidence":"speech masked"}]
        self.assertFalse(evaluate(self.review)["approved"])
    def test_missing_evidence(self):
        del self.review["evidence"]["sound"]
        self.assertFalse(evaluate(self.review)["approved"])
    def test_budget(self):
        self.review["gates"]["decode"]="fail"
        self.assertEqual(next_stage("REVIEW",review=self.review,attempt=3,max_attempts=3),"BLOCKED")
    def test_plan_gate(self):
        self.assertEqual(next_stage("PLAN",plan=self.plan),"EXECUTE")
        self.assertEqual(next_stage("PLAN",plan={}),"PLAN")
    def test_repair(self):
        self.review["gates"]["decode"]="fail"
        self.assertEqual(next_stage("REVIEW",review=self.review,attempt=0),"REPAIR")
    def test_selection(self):
        result=select_skills(["direction","footage"],2)
        self.assertEqual([x["discipline"] for x in result],["direction","footage"])
    def test_catalog(self):
        data=load(ROOT/"skills/catalog.json")
        ids=[s["id"] for s in data["skills"]]
        self.assertEqual(len(ids),len(set(ids)))
        for s in data["skills"]:
            self.assertTrue((ROOT/s["reference"]).is_file(),s["id"])
            self.assertTrue((ROOT/s["implementation"]).is_file(),s["id"])
if __name__=="__main__":
    unittest.main()
