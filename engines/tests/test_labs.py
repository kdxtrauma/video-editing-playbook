import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"skills"))
from retrieve import retrieve
def read(p):
    return json.loads((ROOT/p).read_text(encoding="utf-8"))
class LabsTest(unittest.TestCase):
    def test_counts(self):
        catalog=read("skills/catalog.json");index=read("skills/labs/index.json")
        ids={x["id"] for x in catalog["skills"]}
        self.assertEqual(len(ids),index["core"])
        labs=[]
        for d in index["disciplines"]:
            rows=read(d["path"]);self.assertEqual(len(rows),d["labs"])
            self.assertEqual(len({(x["skill"],x["genre"],x["constraint"]) for x in rows}),len(rows))
            self.assertTrue(all(x["skill"] in ids for x in rows));labs.extend(rows)
        self.assertEqual(len(labs),index["labs"])
        self.assertEqual(len({x["id"] for x in labs}),len(labs))
        self.assertEqual(len(ids)+len(labs),2210)
    def test_retrieval(self):
        rows=retrieve("podcast",["direction","sound"],limit=8)
        self.assertTrue(rows);self.assertTrue(all(x["lab"]["genre"]=="podcast" for x in rows))
        self.assertEqual(len({x["core"]["id"] for x in rows}),len(rows))
