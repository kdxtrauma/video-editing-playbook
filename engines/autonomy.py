"""Deterministic offline control helpers. Does not invoke models or an NLE."""
import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = dict(story=25, rhythm=15, picture=15, sound=20, graphics=10, style=10, delivery=5)
GATES = ("truth", "rights", "privacy", "decode", "specs", "observation")
STAGES = ("BRIEF", "OBSERVE", "CONCEPT", "SELECT", "PLAN", "EXECUTE", "REVIEW")
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
def integer(x):
    return type(x) is int
def validate(plan):
    errors = []
    if not isinstance(plan, dict):
        return ["plan must be object"]
    fps = plan.get("fps", {})
    if not isinstance(fps, dict) or not all(integer(fps.get(k)) and fps[k] > 0 for k in ("num","den")):
        errors.append("invalid rational fps")
    duration = plan.get("duration_frames")
    if not integer(duration) or duration <= 0:
        errors.append("invalid duration_frames")
        duration = 0
    assets = {}
    raw_assets = plan.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        errors.append("missing assets")
        raw_assets = []
    for a in raw_assets:
        if not isinstance(a, dict) or not isinstance(a.get("id"), str) or not a["id"] or a["id"] in assets:
            errors.append("invalid/duplicate asset id")
            continue
        assets[a["id"]] = a
        if not integer(a.get("duration_frames")) or a["duration_frames"] <= 0:
            errors.append("invalid asset duration: " + a["id"])
        if a.get("rights") != "cleared":
            errors.append("rights not cleared: " + a["id"])
    tracks = {}
    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        return errors + ["missing clips"]
    for i,c in enumerate(clips):
        prefix = "clip %d: " % i
        if not isinstance(c,dict):
            errors.append(prefix+"not object")
            continue
        sid = c.get("asset_id")
        a = assets.get(sid) if isinstance(sid,str) else None
        if a is None:
            errors.append(prefix+"unknown asset")
        keys = ("source_in","source_out","timeline_in","timeline_out")
        if not all(integer(c.get(k)) for k in keys):
            errors.append(prefix+"integer frame boundaries required")
            continue
        si,so,ti,to = (c[k] for k in keys)
        if not (0 <= si < so and 0 <= ti < to <= duration):
            errors.append(prefix+"invalid half-open interval")
        if a and integer(a.get("duration_frames")) and so > a["duration_frames"]:
            errors.append(prefix+"source out of range")
        if so-si != to-ti:
            errors.append(prefix+"retime unsupported in v1")
        if c.get("transition","cut") != "cut":
            errors.append(prefix+"transition unsupported in v1")
        track = c.get("track")
        if not isinstance(track,str) or not track:
            errors.append(prefix+"missing track")
        else:
            tracks.setdefault(track,[]).append((ti,to,i))
        if not isinstance(c.get("reason"),str) or not c["reason"].strip():
            errors.append(prefix+"missing editorial reason")
    for track, spans in tracks.items():
        spans.sort()
        for prev,cur in zip(spans,spans[1:]):
            if cur[0] < prev[1]:
                errors.append("overlap on "+track)
        if track=="V1":
            if spans[0][0]!=0 or spans[-1][1]!=duration or any(b[0]!=a[1] for a,b in zip(spans,spans[1:])):
                errors.append("V1 must cover timeline without gaps in v1")
    if "V1" not in tracks:
        errors.append("V1 missing")
    return errors
def evaluate(review, threshold=4.0):
    if not isinstance(review,dict):
        return {"approved":False,"score":None,"blockers":["invalid review"]}
    blockers=[]
    sha=review.get("artifact_sha256")
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",sha):
        blockers.append("artifact hash missing")
    gates=review.get("gates")
    gates=gates if isinstance(gates,dict) else {}
    for k in GATES:
        if gates.get(k)!="pass":
            blockers.append("gate "+k+" not passed")
    scores=review.get("scores")
    scores=scores if isinstance(scores,dict) else {}
    evidence=review.get("evidence")
    evidence=evidence if isinstance(evidence,dict) else {}
    values={}
    for k in WEIGHTS:
        v=scores.get(k)
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=5:
            blockers.append("missing/invalid score "+k)
        else:
            values[k]=v
        if not isinstance(evidence.get(k),str) or not evidence[k].strip():
            blockers.append("missing evidence "+k)
    defects=review.get("defects")
    if not isinstance(defects,list):
        blockers.append("missing defect list")
        defects=[]
    for d in defects:
        if not isinstance(d,dict) or d.get("severity") not in ("P0","P1","P2") or not isinstance(d.get("evidence"),str) or not d["evidence"].strip():
            blockers.append("invalid defect record")
        elif d["severity"] in ("P0","P1"):
            blockers.append(d["severity"]+": "+d["evidence"])
    score=sum(values[k]*WEIGHTS[k] for k in WEIGHTS)/100 if len(values)==len(WEIGHTS) else None
    if score is not None and score<threshold:
        blockers.append("score below threshold")
    return {"approved":not blockers,"score":round(score,3) if score is not None else None,"blockers":blockers}
def next_stage(stage, *, review=None, attempt=0, max_attempts=3, plan=None):
    if not integer(attempt) or not integer(max_attempts) or attempt<0 or max_attempts<1:
        raise ValueError("invalid attempt bounds")
    if stage in ("RELEASE","BLOCKED"):
        return stage
    if stage=="REVIEW":
        if review is None:
            raise ValueError("review required")
        if evaluate(review)["approved"]:
            return "RELEASE"
        return "REPAIR" if attempt<max_attempts else "BLOCKED"
    if stage=="REPAIR":
        return "PLAN"
    if stage=="PLAN" and (plan is None or validate(plan)):
        return "PLAN"
    if stage not in STAGES:
        raise ValueError("unknown stage")
    return STAGES[STAGES.index(stage)+1]
def select_skills(disciplines,limit=10):
    data=load(ROOT/"skills/catalog.json")["skills"]
    wanted=set(disciplines)
    # Round-robin disciplines so first category cannot consume entire budget.
    groups=[[s for s in data if s["discipline"]==d] for d in dict.fromkeys(disciplines)]
    result=[]
    for i in range(max((len(g) for g in groups),default=0)):
        for g in groups:
            if i<len(g) and len(result)<limit:
                result.append(g[i])
    return result
def main():
    p=argparse.ArgumentParser()
    sp=p.add_subparsers(dest="cmd",required=True)
    s=sp.add_parser("skills");s.add_argument("disciplines",nargs="+");s.add_argument("--limit",type=int,default=10)
    for cmd in ("validate","review"):
        s=sp.add_parser(cmd);s.add_argument("path")
    s=sp.add_parser("next");s.add_argument("stage");s.add_argument("--review");s.add_argument("--plan");s.add_argument("--attempt",type=int,default=0);s.add_argument("--max-attempts",type=int,default=3)
    a=p.parse_args()
    if a.cmd=="skills":
        if a.limit<1: p.error("limit must be positive")
        result=select_skills(a.disciplines,a.limit); code=0
    elif a.cmd=="validate":
        e=validate(load(a.path));result={"valid":not e,"errors":e};code=int(bool(e))
    elif a.cmd=="review":
        result=evaluate(load(a.path));code=int(not result["approved"])
    else:
        result={"next":next_stage(a.stage,review=load(a.review) if a.review else None,plan=load(a.plan) if a.plan else None,attempt=a.attempt,max_attempts=a.max_attempts)};code=0
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return code
if __name__=="__main__":
    raise SystemExit(main())
