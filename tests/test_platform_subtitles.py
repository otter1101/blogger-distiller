import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from utils.transcript import transcript_from_srt


class PlatformSubtitleTests(unittest.TestCase):
    def test_converts_srt_into_the_existing_transcript_shape(self):
        result = transcript_from_srt("1\n00:00:00,000 --> 00:00:01,500\n大家好\n\n2\n00:00:01,500 --> 00:00:03,000\n欢迎使用 <i>博主蒸馏器</i>\n")
        self.assertEqual(result["text"], "大家好\n欢迎使用 博主蒸馏器")
        self.assertEqual(result["language"], "zh-CN")
        self.assertEqual(result["source"], "platform_subtitle")
        self.assertEqual(result["word_count"], len(result["text"]))
        self.assertEqual(result["duration"], 3.0)

    def test_returns_none_for_srt_without_caption_text(self):
        self.assertIsNone(transcript_from_srt("1\n00:00:00,000 --> 00:00:01,000\n"))


if __name__ == "__main__":
    unittest.main()
