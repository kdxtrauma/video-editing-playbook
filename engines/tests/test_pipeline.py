import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import Pipeline
from autonomy import ROOT, WEIGHTS, GATES, load

class PipelineTests(unittest.TestCase):
    def simulate(self, mode="good"):
        plan=load(ROOT/"engines/example-plan.json")
        requests=[]
        roles="capabilities observe producer director_a director_b judge editor executor critic repair".split()
        def runner(argv, **kw):
            req=json.loads(kw["input"])
            role=req["role"]; p=req["payload"]; requests.append(req)
            if role=="capabilities": r={"execution_verified":True,"review_verified":True}
            elif role=="observe": r={"observations":[{"evidence":"synthetic"}]}
            elif role=="producer": r={"goal":"test"}
            elif role=="director_a": r={"concepts":[{"treatment":"A"},{"treatment":"B"}]}
            elif role=="director_b": r={"concepts":[{"treatment":"C"}]}
            elif role=="judge": r={"id":"C01","reason":"test"}
            elif role in ("editor","repair"): r={"plan":plan}
            elif role=="executor":
                artifact=Path(p["version_dir"])/"fake.mp4";artifact.write_bytes(b"synthetic not media")
                r={"artifact":str(artifact),"readback":{"synthetic":True}}
            elif role=="critic":
                r={"artifact_sha256":("b" if mode=="hash" else "a")*64,"gates":dict.fromkeys(GATES,"pass"),
                   "scores":dict.fromkeys(WEIGHTS,4),"evidence":dict.fromkeys(WEIGHTS,"synthetic"),"defects":[]}
                if mode=="defect": r["defects"]=[{"severity":"P1","evidence":"synthetic defect"}]
            return SimpleNamespace(returncode=0,stdout=json.dumps(r))
        def probe(path,**kw):
            return {"artifact_sha256":"a"*64,"decode":"fail" if mode=="decode" else "pass"}
        with tempfile.TemporaryDirectory() as tmp:
            config={"adapters":{r:[r] for r in roles},"max_repairs":1}
            result=Pipeline(config,{"sources":["synthetic"]},Path(tmp)/"run",runner=runner,probe=probe).run()
        return result,requests
    def test_flow(self):
        r,q=self.simulate()
        self.assertEqual(r["status"],"approved")
        a,b=[x["payload"] for x in q if x["role"].startswith("director_")]
        self.assertEqual(a,b)
        self.assertEqual(sum(x["role"]=="executor" for x in q),1)
    def test_hash(self):
        self.assertEqual(self.simulate("hash")[0]["status"],"blocked")
    def test_p1_repair(self):
        r,q=self.simulate("defect")
        self.assertEqual(r["status"],"blocked")
        self.assertEqual(sum(x["role"]=="executor" for x in q),2)
    def test_decode(self):
        self.assertEqual(self.simulate("decode")[0]["status"],"blocked")
