"""Contextual knowledge retrieval; no dependencies and no network."""
import argparse
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
def load(p):
    return json.loads(p.read_text(encoding="utf-8"))
def retrieve(genre, disciplines, constraint=None, query="", limit=8):
    if not 1<=limit<=100:
        raise ValueError("limit outside 1..100")
    cat=load(BASE/"catalog.json")
    index=load(BASE/"labs/index.json")
    by_id={x["id"]:x for x in cat["skills"]}
    allowed={x["discipline"] for x in index["disciplines"]}
    if set(disciplines)-allowed:
        raise ValueError("unknown discipline")
    terms=set(query.casefold().split())
    out=[]
    for d in dict.fromkeys(disciplines):
        candidates=[]
        for x in load(BASE/"labs"/(d+".json")):
            if x["genre"]!=genre or (constraint and x["constraint"]!=constraint):
                continue
            core=by_id[x["skill"]]
            words=set((" ".join([core["name"],core["when"],core["procedure"],x["brief"]])).casefold().split())
            candidates.append((len(words&terms),x["id"],{"core":core,"lab":x}))
        candidates.sort(key=lambda x:(-x[0],x[1]))
        out.append(candidates)
    result=[]; seen=set()
    while any(out) and len(result)<limit:
        for group in out:
            while group:
                row=group.pop(0)[2]
                if row["core"]["id"] in seen:
                    continue
                seen.add(row["core"]["id"]);result.append(row);break
            if len(result)>=limit: break
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("genre");p.add_argument("disciplines",nargs="+");p.add_argument("--constraint");p.add_argument("--query",default="");p.add_argument("--limit",type=int,default=8)
    a=p.parse_args();print(json.dumps(retrieve(a.genre,a.disciplines,a.constraint,a.query,a.limit),ensure_ascii=False,indent=2))
