import json
import os
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from utils.endpoint_router import EndpointRouter
from utils.tikhub_client import TikHubError


class EndpointRouterTests(unittest.TestCase):
    def test_xhs_endpoint_policy_keeps_only_verified_fallbacks(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "utils", "xhs_endpoints.json")
        with open(path, encoding="utf-8") as file:
            pools = json.load(file)["pools"]
        self.assertEqual([item["group"] for item in pools["search_notes"]], ["app_v2"])
        self.assertEqual([item["group"] for item in pools["search_users"]], ["app_v2"])
        self.assertEqual([item["group"] for item in pools["fetch_user_notes"]], ["app_v2"])
        self.assertEqual([item["group"] for item in pools["fetch_note_detail_image"]], ["app_v2"])
        self.assertEqual([item["group"] for item in pools["fetch_note_comments"]], ["app_v2"])
        self.assertEqual([item["group"] for item in pools["fetch_user_info"]], ["app_v2", "web_v3"])
        self.assertEqual([item["group"] for item in pools["fetch_note_detail_video"]], ["app_v2", "web_v3"])
        self.assertEqual(pools["fetch_note_detail_video"][1]["required_args"], ["xsec_token"])

    def test_does_not_call_a_fallback_when_its_required_token_is_missing(self):
        config = {"pools": {"fetch_note_detail_video": [{"group": "web_v3", "path": "/web_v3/fetch_note_detail", "params": {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}, "required_args": ["xsec_token"], "adapter": "note_detail_web_v3"}]}}
        calls = []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file:
            json.dump(config, file)
            path = file.name
        try:
            router = EndpointRouter(lambda *args, **kwargs: calls.append((args, kwargs)) or {"code": 200}, config_path=path)
            with self.assertRaises(TikHubError):
                router.call("fetch_note_detail_video", {"note_id": "video-1"})
        finally:
            os.unlink(path)
        self.assertEqual(calls, [])

    def test_startup_probe_does_not_spend_a_request_on_token_gated_fallback(self):
        config = {"pools": {"fetch_note_detail_video": [{"group": "web_v3", "path": "/web_v3/fetch_note_detail", "params": {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}, "required_args": ["xsec_token"], "adapter": "note_detail_web_v3"}]}}
        calls = []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file:
            json.dump(config, file)
            path = file.name
        try:
            router = EndpointRouter(lambda *args, **kwargs: calls.append((args, kwargs)) or {"code": 200}, config_path=path)
            router.auto_probe_and_reorder()
        finally:
            os.unlink(path)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
