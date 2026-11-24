"""Search an operator-approved local asset manifest. No download or rights inference."""
import argparse
import json
import re
from pathlib import Path
def tokens(value):
    return set(re.findall(r"[^\W_]+",value.casefold(),flags=re.UNICODE))
def rank(manifest,query,kind=None,limit=10):
    if not 1<=limit<=100: raise ValueError("limit must be 1..100")
    q=tokens(query)
    if not q:return []
    result=[]
    for item in manifest:
        if item.get("rights")!="cleared" or (kind and item.get("kind")!=kind):continue
        fields=[item.get(k,"") for k in ("subject","action","context","description","tags","material","perspective")]
        words=tokens(" ".join(" ".join(str(x) for x in v) if isinstance(v,list) else str(v) for v in fields))
        score=len(words&q)
        if not score:continue
        # Return original metadata; do not assert semantic relevance from lexical overlap.
        result.append({"id":item["id"],"score":score,"asset":item})
    return sorted(result,key=lambda x:(-x["score"],x["id"]))[:limit]
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("query");p.add_argument("--kind");p.add_argument("--limit",type=int,default=10);a=p.parse_args()
    print(json.dumps(rank(json.loads(Path(a.manifest).read_text(encoding="utf-8")),a.query,a.kind,a.limit),ensure_ascii=False,indent=2))
