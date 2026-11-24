import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"integrations"))
from model_gateway import invoke
class GatewayTests(unittest.TestCase):
    def test_compatible(self):
        def fake(url,headers,payload,timeout):
            self.assertEqual(payload["model"],"mock")
            self.assertEqual(headers["Authorization"],"Bearer test")
            return {"choices":[{"message":{"content":'{"concepts":[]}'}}]}
        with patch.dict(os.environ,{"TEST_KEY":"test"}):
            self.assertEqual(invoke({"provider":"openai-compatible","url":"https://example.invalid","model":"mock","key_env":"TEST_KEY"},{"role":"director_a"},fake),{"concepts":[]})
    def test_no_fake_review(self):
        with patch.dict(os.environ,{"TEST_KEY":"test"}):
            with self.assertRaises(ValueError):
                invoke({"provider":"openai-compatible","url":"https://example.invalid","model":"mock","key_env":"TEST_KEY"},{"role":"critic"})
