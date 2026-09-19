import os
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from crawl_xhs import get_all_details, supplement_video_urls_for_whisper
from utils.adapters import note_detail_app_v2


def app_v2_video_response():
    return {"data": {"data": [{"noteId": "video-1", "desc": "视频描述", "video_info_v2": {"media": {"stream": {"h264": [{"master_url": "https://video.example.test/v.mp4"}]}, "video": {"subtitles": {"zh-CN": [{"url": "https://subtitle.example.test/v.srt"}]}}}}}]}}


class FakeClient:
    def __init__(self, response):
        self.response, self.calls = response, []

    def _request(self, method, path, params=None, **kwargs):
        self.calls.append((method, path, params))
        return self.response


class FakeDetailClient:
    def __init__(self, response):
        self.response = response

    def fetch_note_detail(self, note_id, xsec_token="", note_type=""):
        return note_detail_app_v2(self.response, {"note_id": note_id})


class VideoTranscriptFlowTests(unittest.TestCase):
    platform_result = {"text": "平台字幕", "duration": 3.0, "language": "zh-CN", "word_count": 4, "source": "platform_subtitle"}

    def test_main_detail_flow_uses_platform_subtitle_before_whisper(self):
        notes = {"video-1": {"id": "video-1", "type": "video", "title": "test"}}
        with tempfile.TemporaryDirectory() as output_dir, patch("utils.transcript.transcript_from_subtitle_url", return_value=self.platform_result), patch("utils.transcript.get_whisper_model") as get_model:
            details = get_all_details(FakeDetailClient(app_v2_video_response()), notes, output_dir, "tester", transcript=True)
        self.assertEqual(details[0]["transcript"], self.platform_result)
        self.assertEqual(get_model.call_count, 0)

    def test_supplement_uses_app_v2_subtitle_without_loading_whisper(self):
        details = [{"_feed_id": "video-1", "_meta": {"note_type": "video", "xsec_token": "token", "list_title": "test"}}]
        client = FakeClient(app_v2_video_response())
        with patch("utils.transcript.transcript_from_subtitle_url", return_value=self.platform_result), patch("utils.transcript.get_whisper_model") as get_model:
            supplement_video_urls_for_whisper(details, client, transcript=True)
        self.assertEqual(details[0]["transcript"], self.platform_result)
        self.assertEqual(get_model.call_count, 0)
        self.assertEqual(client.calls, [("GET", "/api/v1/xiaohongshu/app_v2/get_video_note_detail", {"note_id": "video-1"})])


if __name__ == "__main__":
    unittest.main()
