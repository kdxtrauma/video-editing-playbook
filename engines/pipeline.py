"""Adapter-driven creative pipeline. Trusted local adapters only; no shell or provider assumptions.
The configured adapters must implement the protocol in protocol.md. No media is sent by this module itself.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from autonomy import evaluate, validate, load, ROOT, select_skills
from media_probe import run_media
sys.path.insert(0,str(ROOT/"skills"))
from retrieve import retrieve

class Blocked(RuntimeError):
    pass

def need(ok, message):
    if not ok:
        raise Blocked(message)

def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")

def within(path, root):
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False

class Pipeline:
    def __init__(self, config, brief, work, runner=subprocess.run, probe=run_media):
        self.config=config
        self.brief=brief
        self.work=Path(work).resolve()
        self.runner=runner
        self.probe=probe
        self.calls=0
        self.max_calls=config.get("max_calls",40)
        self.timeout=config.get("timeout_seconds",600)
        self.repairs=config.get("max_repairs",3)
        self.roles={r["id"]:r for r in load(ROOT/"agents/roles.json")}
        self.last_artifact=None
        self.genre=None
        self.constraint=None
        need(type(self.max_calls) is int and self.max_calls>=1,"invalid max_calls")
        need(type(self.repairs) is int and 0<=self.repairs<=10,"invalid max_repairs")
        need(type(self.timeout) is int and self.timeout>0,"invalid timeout")
        need(isinstance(config.get("adapters"),dict),"missing adapters")
        self.work.mkdir(parents=True,exist_ok=False)
    def knowledge(self, disciplines, limit):
        if self.genre:
            rows=retrieve(self.genre,disciplines,self.constraint,limit=limit)
            if not rows and self.constraint:
                rows=retrieve(self.genre,disciplines,limit=limit)
            if rows:
                return rows
        return [{"core":s} for s in select_skills(disciplines,limit)]
    def call(self, role, payload):
        need(self.calls<self.max_calls,"call budget exhausted")
        adapter=self.config["adapters"].get(role)
        need(isinstance(adapter,list) and adapter and all(isinstance(x,str) and x for x in adapter),"missing adapter: "+role)
        # Only operator-defined argv; model output never becomes a command.
        self.calls+=1
        task={"schema_version":1,"role":role,"role_contract":self.roles.get(role),
              "instruction":(ROOT/"agents/orchestrator.md").read_text(encoding="utf-8"),
              "work_dir":str(self.work),"payload":payload}
        # Local commands receive contracts directly; an API model cannot read a repository path.
        docs={"producer":["producing/README.md","handbook/06-genres.md"],
              "director_a":["directing/README.md","decision-trees/README.md"],
              "director_b":["directing/README.md","reference-analysis/README.md"],
              "judge":["quality-control/README.md"],
              "editor":["engines/README.md","decision-trees/README.md"],
              "repair":["engines/README.md","quality-control/README.md"],
              "critic":["quality-control/README.md"],
              "sound":["handbook/03-sound.md"],"color":["handbook/04-picture.md"],
              "motion":["handbook/04-picture.md"]}
        paths=list(docs.get(role,[]))
        if role in ("editor","repair") and self.config.get("plan_format")=="layered-v2":
            paths.append("engines/layered-executor.md")
        task["knowledge_documents"]={p:(ROOT/p).read_text(encoding="utf-8") for p in paths}
        task["plan_format"]=self.config.get("plan_format","cut-v1")
        # Local log may contain private data; use a private work directory.
        write_json(self.work/("%03d-%s-request.json"%(self.calls,role)),task)
        p=self.runner(adapter,input=json.dumps(task,ensure_ascii=False),text=True,
                      capture_output=True,timeout=self.timeout,cwd=str(self.work),shell=False)
        need(p.returncode==0,"adapter failed: "+role)
        try:
            result=json.loads(p.stdout)
        except (ValueError,TypeError):
            raise Blocked("invalid JSON from "+role)
        need(isinstance(result,dict),"non-object response: "+role)
        write_json(self.work/("%03d-%s-response.json"%(self.calls,role)),result)
        return result
    def run(self):
        try:
            result=self._run()
        except (Blocked, subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError) as e:
            result={"status":"blocked","reason":str(e),"calls":self.calls,"last_artifact":self.last_artifact}
        write_json(self.work/"result.json",result)
        return result
    def _run(self):
        need(isinstance(self.brief,dict),"brief must be object")
        need(isinstance(self.brief.get("sources"),list) and self.brief["sources"],"sources required")
        capabilities=self.call("capabilities",{"brief":self.brief})
        need(capabilities.get("execution_verified") is True,"execution smoke test not confirmed")
        need(capabilities.get("review_verified") is True,"review modality smoke test not confirmed")
        observed=self.call("observe",{"brief":self.brief,"capabilities":capabilities})
        need(isinstance(observed.get("observations"),list) and observed["observations"],"no observations")
        production=self.call("producer",{"brief":self.brief,"observed":observed})
        self.genre=self.brief.get("genre") or production.get("genre")
        self.constraint=self.brief.get("constraint") or production.get("constraint")
        # Same payload; B receives no A answer.
        shared={"brief":self.brief,"production":production,"observed":observed,
                "styles":load(ROOT/"style-library/catalog.json"),
                "skills":self.knowledge(["direction","story","perception","autonomy"],12)}
        a=self.call("director_a",shared)
        b=self.call("director_b",shared)
        concepts=[]
        for response in (a,b):
            rows=response.get("concepts")
            need(isinstance(rows,list) and rows,"director returned no concepts")
            for c in rows:
                need(isinstance(c,dict) and isinstance(c.get("treatment"),str) and c["treatment"].strip(),"concept missing treatment")
                clean={k:v for k,v in c.items() if k in ("treatment","promise","pov","arc","rhythm","picture","sound","risks","assets","first_scene","ending")}
                clean["id"]="C%02d"%(len(concepts)+1)
                concepts.append(clean)
        need(len(concepts)>=3 and len({c["treatment"].strip() for c in concepts})>=3,"three distinct concepts required")
        selected=self.call("judge",{"brief":self.brief,"production":production,"observed":observed,"concepts":concepts})
        winner=next((c for c in concepts if c["id"]==selected.get("id")),None)
        need(winner is not None and isinstance(selected.get("reason"),str) and selected["reason"].strip(),"judge must select a concept and reason")
        editor_payload={"brief":self.brief,"production":production,"observed":observed,"selected":winner,"selection_reason":selected["reason"],
                        "skills":self.knowledge(["cutting","footage","sound","color","motion","engineering"],24)}
        plan=self.call("editor",editor_payload).get("plan")
        # Merge specialist proposals into the typed plan. Never discard them silently.
        advice={}
        for role in ("sound","color","motion"):
            if role in self.config["adapters"]:
                advice[role]=self.call(role,{"brief":self.brief,"plan":plan,"observed":observed})
        if advice:
            merged=self.call("editor",{**editor_payload,"draft_plan":plan,"specialist_advice":advice,
                                      "instruction":"Merge feasible proposals into supported plan. List rejected proposals and reasons."})
            need(isinstance(merged.get("specialist_disposition"),dict) and set(advice)<=set(merged["specialist_disposition"]),"specialist disposition missing")
            plan=merged.get("plan")
        if self.config.get("plan_format","cut-v1") not in ("cut-v1","layered-v2"):
            raise Blocked("unsupported plan format")
        for attempt in range(self.repairs+1):
            errs=validate(plan)
            if isinstance(plan,dict) and plan.get("layers") and self.config.get("plan_format","cut-v1")=="cut-v1":
                errs.append("layers unsupported by cut-v1")
            if errs:
                need(attempt<self.repairs,"invalid plan: "+"; ".join(errs))
                plan=self.call("repair",{"plan":plan,"validation_errors":errs,"brief":self.brief}).get("plan")
                continue
            version_dir=self.work/("v%03d"%attempt)
            version_dir.mkdir()
            try:
                execution=self.call("executor",{"plan":plan,"version_dir":str(version_dir),"brief":self.brief,
                                                "specialist_advice":{}})
                path=execution.get("artifact")
                need(isinstance(path,str) and within(path,version_dir) and Path(path).is_file(),"executor artifact absent or outside version dir")
                need(isinstance(execution.get("readback"),dict) and execution["readback"],"executor readback required")
            except (Blocked,subprocess.SubprocessError,OSError,ValueError,KeyError,TypeError) as e:
                if attempt>=self.repairs:
                    raise
                plan=self.call("repair",{"plan":plan,"execution_error":str(e),"brief":self.brief,
                                         "instruction":"Repair a supported operation; do not invent evidence or change unrelated cuts."}).get("plan")
                continue
            self.last_artifact=path
            actual=self.probe(path,decode=True,timeout=self.timeout)
            write_json(version_dir/"probe.json",actual)
            review=self.call("critic",{"artifact":path,"probe":actual,"brief":self.brief,"sources":self.brief["sources"]})
            need(review.get("artifact_sha256")==actual["artifact_sha256"],"review artifact hash mismatch")
            # Machine-observed decode is authoritative. Critic must still supply other gate evidence.
            need(isinstance(review.get("gates"),dict),"review gates missing")
            review["gates"]["decode"]=actual["decode"]
            verdict=evaluate(review)
            write_json(version_dir/"verdict.json",verdict)
            if verdict["approved"]:
                return {"status":"approved","artifact":path,"artifact_sha256":actual["artifact_sha256"],"verdict":verdict,"calls":self.calls,"version":attempt}
            if attempt==self.repairs:
                return {"status":"blocked","artifact":path,"verdict":verdict,"calls":self.calls,"version":attempt}
            plan=self.call("repair",{"plan":plan,"review":review,"verdict":verdict,"brief":self.brief}).get("plan")
        raise Blocked("repair budget exhausted")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True);p.add_argument("--brief",required=True);p.add_argument("--work",required=True)
    a=p.parse_args()
    result=Pipeline(load(a.config),load(a.brief),a.work).run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return int(result["status"]!="approved")
if __name__=="__main__":
    raise SystemExit(main())
