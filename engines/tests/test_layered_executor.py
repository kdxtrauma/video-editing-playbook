import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from layered_executor import execute,compile_layers
@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
class LayeredTest(unittest.TestCase):
    def test_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"source.mkv";cut=root/"cut.mkv";cue=root/"cue.wav"
            for file,color in ((source,"red"),(cut,"blue")):
                subprocess.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i","color=c="+color+":s=160x90:r=25:d=2","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2","-c:v","ffv1","-c:a","pcm_s16le",str(file)],check=True,capture_output=True)
            subprocess.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i","sine=frequency=800:sample_rate=48000:duration=2",str(cue)],check=True,capture_output=True)
            out=root/"version";out.mkdir()
            plan={"fps":{"num":25,"den":1},"duration_frames":50,"assets":[{"id":"source","duration_frames":50,"rights":"cleared"}],"clips":[{"asset_id":"source","source_in":0,"source_out":50,"timeline_in":0,"timeline_out":50,"track":"V1","reason":"test"}],"layers":{"visual":[{"asset_id":"cut","kind":"video","in":10,"out":30,"fade_frames":2}],"titles":[{"in":5,"out":20,"text":"TEST","x":5,"y":5,"size":12}],"audio":[{"asset_id":"cue","in":10,"out":25,"gain_db":-20,"fade_in_frames":2,"fade_out_frames":2}],"grade":{"contrast":1.05}}}
            brief={"source_paths":{"source":str(source)},"layer_assets":{"cut":str(cut),"cue":str(cue)},"width":160,"height":90}
            r=execute(plan,brief,out)
            self.assertEqual(r["readback"]["video_frames"],50)
            self.assertEqual(r["readback"]["layer_counts"],{"visual":1,"titles":1,"audio":1})
            self.assertTrue(Path(r["artifact"]).is_file())
    def test_reject_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan={"fps":{"num":25,"den":1},"duration_frames":1,"assets":[{"id":"s","duration_frames":1,"rights":"cleared"}],"clips":[{"asset_id":"s","source_in":0,"source_out":1,"timeline_in":0,"timeline_out":1,"track":"V1","reason":"test"}],"layers":{"arbitrary_filter":"bad"}}
            with self.assertRaises(ValueError):compile_layers(plan,{},Path(tmp))
