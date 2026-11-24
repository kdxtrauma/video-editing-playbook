import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ffmpeg_executor import render
from media_probe import run_media

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
class FFmpegTest(unittest.TestCase):
    def test_two_sources(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            for i,color in enumerate(("red","blue")):
                subprocess.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i","color=c="+color+":s=160x90:r=25:d=2","-f","lavfi","-i","sine=frequency="+str(440+i*220)+":sample_rate=48000:duration=2","-c:v","ffv1","-c:a","pcm_s16le",str(root/("%d.mkv"%i))],check=True,capture_output=True)
            version=root/"version";version.mkdir()
            plan={"fps":{"num":25,"den":1},"duration_frames":50,"assets":[{"id":str(i),"duration_frames":50,"rights":"cleared"} for i in range(2)],"clips":[{"asset_id":str(i),"source_in":5,"source_out":30,"timeline_in":i*25,"timeline_out":(i+1)*25,"track":"V1","reason":"synthetic color change"} for i in range(2)]}
            result=render(plan,{str(i):str(root/("%d.mkv"%i)) for i in range(2)},version,160,90)
            self.assertEqual(result["readback"]["video_frames"],50)
            self.assertEqual(run_media(result["artifact"],decode=True)["decode"],"pass")
