"""Executable V1 cut-only adapter. CFR sources with audio; multiple assets; no silent degradation."""
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from autonomy import validate

def run(args):
    p=subprocess.run(args,capture_output=True,text=True,check=True)
    return p.stdout

def render(plan, source_paths, version_dir, width=1920, height=1080):
    errors=validate(plan)
    if errors:
        raise ValueError("; ".join(errors))
    if any(c["track"]!="V1" for c in plan["clips"]):
        raise ValueError("FFmpeg V1 adapter supports only V1 cuts with source audio")
    if type(width) is not int or type(height) is not int or min(width,height)<2 or width%2 or height%2:
        raise ValueError("positive even output dimensions required")
    target=Path(version_dir).resolve(strict=True)
    output=target/"master.mp4"
    if output.exists():
        raise ValueError("output already exists")
    rate=Fraction(plan["fps"]["num"],plan["fps"]["den"])
    fps=str(rate.numerator)+"/"+str(rate.denominator)
    if rate>120 or rate<1:
        raise ValueError("unsupported frame rate")
    clip_paths=[]
    sources={}
    for c in sorted(plan["clips"],key=lambda c:c["timeline_in"]):
        asset=c["asset_id"]
        if asset not in source_paths:
            raise ValueError("source path missing")
        if asset not in sources:
            src=Path(source_paths[asset]).resolve(strict=True)
            if not src.is_file() or src==output:
                raise ValueError("invalid source path")
            meta=json.loads(run(["ffprobe","-v","error","-count_frames","-show_streams","-of","json",str(src)]))
            v=next((x for x in meta["streams"] if x["codec_type"]=="video"),None)
            a=next((x for x in meta["streams"] if x["codec_type"]=="audio"),None)
            if not v or not a or Fraction(v["avg_frame_rate"])!=rate or Fraction(v["r_frame_rate"])!=rate:
                raise ValueError("CFR normalized source with audio required: "+asset)
            if v.get("nb_read_frames") in (None,"N/A"):
                raise ValueError("source frame count unavailable")
            # Nominal/average rates alone do not establish CFR: check successive decoded frame PTS.
            frames=json.loads(run(["ffprobe","-v","error","-select_streams","v:0","-show_frames","-show_entries","frame=best_effort_timestamp","-of","json",str(src)]))["frames"]
            pts=[int(x["best_effort_timestamp"]) for x in frames]
            tb=Fraction(v["time_base"])
            period=1/rate
            if not pts or any(y<=x or abs((y-x)*tb-period)>tb for x,y in zip(pts,pts[1:])):
                raise ValueError("non-CFR frame timestamps: "+asset)
            if len(pts)!=int(v["nb_read_frames"]):
                raise ValueError("inconsistent source frame count")
            # V1 assumes normalized timestamps and no source AV offset.
            if "start_time" not in v or "start_time" not in a or abs(float(v["start_time"])-float(a["start_time"]))>0.001 or abs(float(v["start_time"]))>0.001:
                raise ValueError("normalize source AV start timestamps first")
            sources[asset]=(src,len(pts))
        src,count=sources[asset]
        if c["source_out"]>count:
            raise ValueError("actual source shorter than plan")
        start,end=c["source_in"],c["source_out"]
        # Integer frame video boundaries. Audio sample intervals rounded independently from rational timeline.
        s0=round(Fraction(start*48000,1)/rate);s1=round(Fraction(end*48000,1)/rate)
        out=target/("segment-%04d.mkv"%len(clip_paths))
        vf="trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"%(start,end,width,height,width,height)
        af="aresample=48000,atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS"% (s0,s1)
        subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-n","-i",str(src),"-map","0:v:0","-map","0:a:0","-vf",vf,"-af",af,"-r",fps,"-c:v","ffv1","-c:a","pcm_s16le","-ac","2",str(out)],check=True,capture_output=True)
        clip_paths.append(out)
    # Inputs have matching video/audio formats; concatenate decoded streams, not AAC packets.
    args=["ffmpeg","-nostdin","-v","error","-xerror","-n"]
    for path in clip_paths:
        args+=["-i",str(path)]
    labels="".join("[%d:v:0][%d:a:0]"%(i,i) for i in range(len(clip_paths)))
    args+=["-filter_complex",labels+"concat=n=%d:v=1:a=1[v][a]"%len(clip_paths),"-map","[v]","-map","[a]","-r",fps,"-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",str(output)]
    subprocess.run(args,check=True,capture_output=True)
    probe=json.loads(run(["ffprobe","-v","error","-count_frames","-show_streams","-of","json",str(output)]))
    v=next(x for x in probe["streams"] if x["codec_type"]=="video")
    if int(v["nb_read_frames"])!=plan["duration_frames"] or Fraction(v["avg_frame_rate"])!=rate or v["width"]!=width or v["height"]!=height:
        raise ValueError("output readback mismatch")
    return {"artifact":str(output),"readback":{"video_frames":int(v["nb_read_frames"]),"fps":fps,"width":width,"height":height,"segments":len(clip_paths),"limits":"V1 CFR cuts, stereo source audio, no creative effects or color transform"}}

def main():
    request=json.load(sys.stdin)
    if request.get("role")!="executor":
        raise ValueError("executor only")
    p=request["payload"]
    brief=p["brief"]
    if any(p.get("specialist_advice",{}).values()):
        raise ValueError("specialist advice cannot be executed by cut-only adapter")
    result=render(p["plan"],brief["source_paths"],p["version_dir"],brief.get("width",1920),brief.get("height",1080))
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
