"""Machine QC flags: not a substitute for independent playback. FFmpeg required."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from media_probe import run_media

def scan(path,timeout=3600):
    src=str(Path(path).resolve(strict=True))
    result=run_media(src,decode=True,timeout=timeout)
    scans={}
    for key,args in {
        "black_freeze":["-map","0:v:0","-vf","blackdetect=d=0.08:pix_th=0.10,freezedetect=n=-50dB:d=0.5","-an"],
        "silence_loudness":["-map","0:a:0","-af","silencedetect=n=-45dB:d=0.5,ebur128=peak=true","-vn"]
    }.items():
        p=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-v","info","-i",src]+args+["-f","null","-"],capture_output=True,text=True,timeout=timeout)
        lines=p.stderr.splitlines()
        flags=[line.strip() for line in lines if re.search(r"black_start:|freeze_start:|freeze_end:|freeze_duration:|silence_start:|silence_end:",line)]
        summary=p.stderr.rsplit("Summary:",1)[-1].strip()[-2000:] if key=="silence_loudness" and "Summary:" in p.stderr else None
        scans[key]={"status":"measured" if p.returncode==0 else "unknown","flags":flags[:1000],"truncated":len(flags)>1000,"loudness_summary":summary}
    result["scans"]=scans
    result["interpretation"]="Flags are candidates, not defects. Check intentional black, freeze, silence, thresholds and delivery loudness specification on actual playback."
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("file");p.add_argument("--timeout",type=int,default=3600);a=p.parse_args()
    print(json.dumps(scan(a.file,a.timeout),ensure_ascii=False,indent=2))
