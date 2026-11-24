"""Layered SDR/CFR adapter: cut assembly, B-roll, still overlays, titles, audio cues, global grade.
All media must be authorized and normalized by the operator. No arbitrary filters or shell.
"""
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from ffmpeg_executor import render
from autonomy import validate
from media_probe import run_media

def req(condition,message):
    if not condition: raise ValueError(message)
def num(value,lo,hi):
    req(type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi,"numeric value outside allowed range")
    return float(value)
def integer(value,lo,hi):
    req(type(value) is int and lo<=value<=hi,"integer value outside allowed range")
    return value
def shape(obj,allowed,required=()):
    req(isinstance(obj,dict) and set(obj)<=set(allowed) and set(required)<=set(obj),"unknown or missing fields")
def checked_path(assets,id):
    req(isinstance(id,str) and id in assets,"unknown approved layer asset")
    p=Path(assets[id]).resolve(strict=True)
    req(p.is_file(),"asset is not file")
    return str(p)
def ff(args,cwd):
    return subprocess.run(args,cwd=str(cwd),capture_output=True,check=True,text=True).stdout
def media_info(path,cwd):
    return json.loads(ff(["ffprobe","-v","error","-show_streams","-show_format","-of","json",path],cwd))
def compile_layers(plan,brief,root):
    errors=validate(plan); req(not errors,"; ".join(errors))
    layers=plan.get("layers",{})
    shape(layers,("visual","titles","audio","grade"))
    w=integer(brief.get("width",1920),2,7680);h=integer(brief.get("height",1080),2,4320)
    req(w%2==0 and h%2==0,"even dimensions required")
    fps=Fraction(plan["fps"]["num"],plan["fps"]["den"])
    rate=str(fps.numerator)+"/"+str(fps.denominator)
    n=plan["duration_frames"]; total=float(Fraction(n,1)/fps)
    approved=brief.get("layer_assets",{}); req(isinstance(approved,dict),"layer_assets must be object")
    inputs=[]; graph=[]; v="0:v"; audio="0:a"; counter=0; inp=1; cues=[]
    def label(prefix):
        nonlocal counter
        counter+=1
        return prefix+str(counter)
    def bounds(layer):
        start=integer(layer["in"],0,n-1);end=integer(layer["out"],start+1,n)
        return start,end,float(Fraction(start,1)/fps),float(Fraction(end-start,1)/fps)
    def items(key):
        arr=layers.get(key,[]);req(isinstance(arr,list) and len(arr)<=64,"too many or invalid "+key+" layers");return arr
    grade=layers.get("grade",{})
    shape(grade,("brightness","contrast","saturation","gamma"))
    if grade:
        b=num(grade.get("brightness",0),-.2,.2);c=num(grade.get("contrast",1),.5,1.5);s=num(grade.get("saturation",1),0,2);g=num(grade.get("gamma",1),.5,2)
        nv=label("v");graph.append("[%s]eq=brightness=%g:contrast=%g:saturation=%g:gamma=%g[%s]"%(v,b,c,s,g,nv));v=nv
    for layer in items("visual"):
        shape(layer,("asset_id","kind","in","out","source_in_seconds","x","y","width","height","fit","fade_frames"),("asset_id","kind","in","out"))
        start,end,t,dur=bounds(layer);kind=layer["kind"];req(kind in ("video","image"),"invalid visual kind")
        path=checked_path(approved,layer["asset_id"]);meta=media_info(path,root)
        streams=[s for s in meta["streams"] if s["codec_type"]=="video"];req(bool(streams),"visual stream required")
        if kind=="image":
            req(Path(path).suffix.lower() in (".png",".jpg",".jpeg",".webp"),"still image extension required")
            req(layer.get("source_in_seconds",0)==0,"image cannot have source offset")
            inputs+=["-loop","1","-framerate",rate,"-t",str(dur),"-i",path]
        else:
            offset=num(layer.get("source_in_seconds",0),0,86400)
            try: length=float(streams[0].get("duration") or meta["format"]["duration"])
            except (KeyError,ValueError,TypeError): raise ValueError("video layer duration unknown")
            req(offset+dur<=length+1e-6,"video layer source too short")
            inputs+=["-ss",str(offset),"-t",str(dur),"-i",path]
        ww=integer(layer.get("width",w),2,w);hh=integer(layer.get("height",h),2,h)
        x=integer(layer.get("x",0),0,w-ww);y=integer(layer.get("y",0),0,h-hh)
        req(ww%2==0 and hh%2==0,"even overlay dimensions required")
        fit=layer.get("fit","contain");req(fit in ("contain","cover"),"invalid fit")
        size=("scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black@0"%(ww,hh,ww,hh)) if fit=="contain" else ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"%(ww,hh,ww,hh))
        fade=integer(layer.get("fade_frames",0),0,(end-start)//2)
        filters="fps=%s,trim=end_frame=%d,setpts=PTS-STARTPTS,format=rgba,%s,setsar=1"%(rate,end-start,size)
        if fade:
            filters+=",fade=t=in:s=0:n=%d:alpha=1,fade=t=out:s=%d:n=%d:alpha=1"%(fade,end-start-fade,fade)
        filters+=",setpts=PTS+%s/TB"%format(t,".12g")
        ov=label("ov");nv=label("v")
        graph.append("[%d:v]%s[%s]"%(inp,filters,ov));inp+=1
        graph.append("[%s][%s]overlay=x=%d:y=%d:eof_action=pass:repeatlast=0:enable='gte(n,%d)*lt(n,%d)'[%s]"%(v,ov,x,y,start,end,nv));v=nv
    for layer in items("titles"):
        shape(layer,("in","out","text","x","y","size","color","box"),("in","out","text"))
        start,end,t,dur=bounds(layer);txt=layer["text"]
        req(isinstance(txt,str) and 0<len(txt)<=400 and "\x00" not in txt,"invalid title")
        x=integer(layer.get("x",int(w*.05)),0,w-1);y=integer(layer.get("y",int(h*.8)),0,h-1)
        size=integer(layer.get("size",max(12,int(h*.045))),8,min(300,h))
        color=layer.get("color","white");req(color in ("white","black","yellow","red","cyan"),"invalid title color")
        box=layer.get("box",True);req(type(box) is bool,"invalid box")
        filename="title-%d.txt"%counter
        (root/filename).write_text(txt,encoding="utf-8")
        nv=label("v")
        graph.append("[%s]drawtext=textfile=%s:expansion=none:fontcolor=%s:fontsize=%d:x=%d:y=%d:box=%d:boxcolor=black@0.65:boxborderw=8:enable='gte(n,%d)*lt(n,%d)'[%s]"%(v,filename,color,size,x,y,int(box),start,end,nv));v=nv
    # Audio layer source and timing in integer samples, fixed stereo output.
    for layer in items("audio"):
        shape(layer,("asset_id","in","out","source_in_seconds","gain_db","fade_in_frames","fade_out_frames"),("asset_id","in","out"))
        start,end,t,dur=bounds(layer);path=checked_path(approved,layer["asset_id"]);meta=media_info(path,root)
        streams=[s for s in meta["streams"] if s["codec_type"]=="audio"];req(bool(streams),"audio stream required")
        offset=num(layer.get("source_in_seconds",0),0,86400)
        try: length=float(streams[0].get("duration") or meta["format"]["duration"])
        except (KeyError,ValueError,TypeError): raise ValueError("audio layer duration unknown")
        req(offset+dur<=length+1e-6,"audio layer source too short")
        gain=num(layer.get("gain_db",-12),-60,6);fi=integer(layer.get("fade_in_frames",0),0,end-start);fo=integer(layer.get("fade_out_frames",0),0,end-start);req(fi+fo<=end-start,"overlapping fades")
        samples0=round(Fraction(start*48000,1)/fps);samples1=round(Fraction(end*48000,1)/fps);count=samples1-samples0
        ss=round(offset*48000); fin=round(Fraction(fi*48000,1)/fps);fout=round(Fraction(fo*48000,1)/fps)
        inputs+=["-i",path]
        filt="aresample=48000,aformat=channel_layouts=stereo,atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS,volume=%gdB"%(ss,ss+count,gain)
        if fin:filt+=",afade=t=in:ss=0:ns=%d"%fin
        if fout:filt+=",afade=t=out:ss=%d:ns=%d"%(count-fout,fout)
        filt+=",adelay=%dS:all=1"%samples0
        out=label("cue");graph.append("[%d:a]%s[%s]"%(inp,filt,out));inp+=1;cues.append(out)
    if cues:
        a0=label("a");graph.append("[0:a]aresample=48000,aformat=channel_layouts=stereo[%s]"%a0)
        audio=label("a");graph.append("".join("[%s]"%i for i in [a0]+cues)+"amix=inputs=%d:duration=first:normalize=0,alimiter=limit=0.95:level=false:latency=1[%s]"%(1+len(cues),audio))
    vo=label("v");graph.append("[%s]format=yuv420p[%s]"%(v,vo))
    # Raw base audio can be mapped directly; filter output needs brackets.
    am="[ %s ]"%audio if cues else "0:a:0";am=am.replace(" ","")
    return inputs,graph,vo,am,rate,n,w,h

def execute(plan,brief,version_dir):
    root=Path(version_dir).resolve(strict=True)
    req(root.is_dir(),"version directory required")
    # Compile/validate all layer operations before starting base render.
    inputs,graph,v,a,rate,n,w,h=compile_layers(plan,brief,root)
    base=dict(plan);base.pop("layers",None)
    rough=root/"base";rough.mkdir()
    source=render(base,brief["source_paths"],rough,w,h)["artifact"]
    out=root/"master.mp4"
    cmd=["ffmpeg","-nostdin","-v","error","-xerror","-n","-i",source]+inputs+["-filter_complex",";".join(graph),"-map","["+v+"]","-map",a,"-r",rate,"-frames:v",str(n),"-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",str(out)]
    ff(cmd,root)
    meta=json.loads(ff(["ffprobe","-v","error","-count_frames","-show_streams","-of","json",str(out)],root))
    stream=next(x for x in meta["streams"] if x["codec_type"]=="video")
    req(int(stream["nb_read_frames"])==n and stream["width"]==w and stream["height"]==h and Fraction(stream["avg_frame_rate"])==Fraction(rate),"layered output readback mismatch")
    result=run_media(out,decode=True)
    req(result["decode"]=="pass","output decode failed")
    return {"artifact":str(out),"readback":{"video_frames":n,"width":w,"height":h,"fps":rate,"artifact_sha256":result["artifact_sha256"],"layer_counts":{k:len(plan.get("layers",{}).get(k,[])) for k in ("visual","titles","audio")},"grade_applied":bool(plan.get("layers",{}).get("grade")),"limits":"SDR CFR; no automatic masks, tracking, HDR, dynamic reframing or sidechain; creative QC still required"}}
if __name__=="__main__":
    try:
        q=json.load(sys.stdin);req(q["role"]=="executor","executor only");p=q["payload"]
        # Specialist suggestions must be encoded in supported plan, not silently discarded.
        req(not any(p.get("specialist_advice",{}).values()),"encode specialist advice into validated layers before execution")
        print(json.dumps(execute(p["plan"],p["brief"],p["version_dir"]),ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as e:
        print("layered executor failed: "+str(e)[:500],file=sys.stderr);raise SystemExit(1)
