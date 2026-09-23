import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deep_analyze import get_analysis_texts


class TranscriptContentStatsTests(unittest.TestCase):
    def test_prefers_transcript_and_falls_back_to_note_description(self):
        details = [
            {
                "note": {"desc": "视频简介"},
                "transcript": {"text": "这是完整的口播文本"},
            },
            {"note": {"desc": "这是图文正文"}},
        ]

        self.assertEqual(get_analysis_texts(details), ["这是完整的口播文本", "这是图文正文"])


if __name__ == "__main__":
    unittest.main()
