import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils.adapters import note_detail_app_v2
from utils.video_metadata import extract_video_metadata


APP_V2_VIDEO_DETAIL = {
    "data": {"data": [{"video_info_v2": {"media": {
        "stream": {"h264": [{"master_url": "https://video.example.test/video.mp4"}]},
        "video": {"subtitles": {"zh-CN": [{"url": "https://subtitle.example.test/video.srt"}]}},
    }}}]}
}


class VideoMetadataTests(unittest.TestCase):
    def test_extracts_app_v2_video_and_chinese_subtitle_urls(self):
        metadata = extract_video_metadata(APP_V2_VIDEO_DETAIL)
        self.assertEqual(metadata["video_url"], "https://video.example.test/video.mp4")
        self.assertEqual(metadata["subtitle_url"], "https://subtitle.example.test/video.srt")
        self.assertEqual(metadata["subtitle_language"], "zh-CN")

    def test_keeps_video_url_when_chinese_subtitles_are_absent(self):
        raw = {"video_info_v2": {"media": {"stream": {"h265": [{"masterUrl": "https://video.example.test/video.mp4"}]}, "video": {"subtitles": {}}}}}
        metadata = extract_video_metadata(raw)
        self.assertEqual(metadata["video_url"], "https://video.example.test/video.mp4")
        self.assertEqual(metadata["subtitle_url"], "")

    def test_app_v2_adapter_preserves_metadata_for_the_transcript_step(self):
        normalized = note_detail_app_v2(APP_V2_VIDEO_DETAIL, {"note_id": "video-1"})
        note_card = normalized["data"]["data"]["items"][0]["noteCard"]
        self.assertEqual(note_card["videoUrl"], "https://video.example.test/video.mp4")
        self.assertEqual(note_card["_video_metadata"]["subtitle_url"], "https://subtitle.example.test/video.srt")


if __name__ == "__main__":
    unittest.main()
