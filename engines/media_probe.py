"""Read-only media inventory and optional full AV decode. Requires FFmpeg/ffprobe."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def run_media(path, decode=False, timeout=3600):
    p=Path(path).resolve(strict=True)
    if not p.is_file():
        raise ValueError("not a file")
    h=hashlib.sha256()
    with p.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    probe=subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(p)],capture_output=True,text=True,check=True,timeout=timeout)
    data=json.loads(probe.stdout)
    result={"artifact_sha256":h.hexdigest(),"metadata":data,"decode":"unknown"}
    if decode:
        proc=subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(p),"-map","0:v?","-map","0:a?","-f","null","-"],capture_output=True,text=True,timeout=timeout)
        result["decode"]="pass" if proc.returncode==0 else "fail"
        result["decode_errors"]=proc.stderr[-4000:]
    return result
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("file");parser.add_argument("--decode",action="store_true");parser.add_argument("--timeout",type=int,default=3600)
    args=parser.parse_args()
    result=run_media(args.file,args.decode,args.timeout)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(int(result["decode"]=="fail"))
