"""서울 중계 서버(proxy/api/relay.py)를 실제로 띄워서 앱 쪽 호출과 함께 시험합니다."""

import importlib.util
import io
import json
import os
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

import requests

from landai.apis import http as api_http
from landai.apis import vworld

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("relay", ROOT / "proxy" / "api" / "relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)

TOKEN = "test-token-123"


class FakeUpstream:
    """urllib.request.urlopen 대신 쓰는 가짜 원 서버 응답."""
    calls: list = []

    def __init__(self, body: dict):
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self._buf = io.BytesIO(json.dumps(body).encode())

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen_factory(body):
    def fake(req, timeout=None):
        FakeUpstream.calls.append(req.full_url)
        return FakeUpstream(body)
    return fake


@mock.patch.dict(os.environ, {"PROXY_TOKEN": TOKEN})
class TestRelayServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), relay.handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/api/relay"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def post(self, body, token=TOKEN):
        return requests.post(self.base, json=body, headers={"X-Proxy-Token": token}, timeout=5)

    def test_ping_without_token(self):
        with mock.patch.object(relay.urllib.request, "urlopen",
                               side_effect=OSError("blocked here")):
            r = requests.get(self.base, params={"_target": "ping"}, timeout=5)
        body = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(body["token_set"])
        self.assertFalse(body["vworld_reachable"])

    def test_get_other_than_ping_rejected(self):
        r = requests.get(self.base, params={"_target": "vworld_data"}, timeout=5)
        self.assertEqual(r.status_code, 405)

    def test_wrong_token(self):
        self.assertEqual(self.post({"target": "vworld_data", "params": {}}, token="x").status_code, 401)

    def test_disallowed_target(self):
        r = self.post({"target": "https://evil.example", "params": {}})
        self.assertEqual(r.status_code, 400)
        r = self.post({"target": "datagokr", "path": "../../etc", "params": {}})
        self.assertEqual(r.status_code, 400)

    def test_bad_body(self):
        r = requests.post(self.base, data="not json", headers={"X-Proxy-Token": TOKEN}, timeout=5)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post([1, 2]).status_code, 400)

    def test_forward_vworld(self):
        FakeUpstream.calls.clear()
        up = {"response": {"status": "OK"}}
        with mock.patch.object(relay.urllib.request, "urlopen", fake_urlopen_factory(up)):
            r = self.post({"target": "vworld_data", "params": {"key": "K", "data": "LP_PA_CBND_BUBUN"}})
        self.assertEqual(r.json(), up)
        self.assertTrue(FakeUpstream.calls[0].startswith("https://api.vworld.kr/req/data?"))
        self.assertIn("key=K", FakeUpstream.calls[0])

    def test_forward_datagokr_path(self):
        FakeUpstream.calls.clear()
        with mock.patch.object(relay.urllib.request, "urlopen", fake_urlopen_factory({"ok": 1})):
            r = self.post({"target": "datagokr", "path": "1613000/arLandUseInfoService/DTarLandUseInfo",
                           "params": {"serviceKey": "S"}})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(FakeUpstream.calls[0].startswith(
            "https://apis.data.go.kr/1613000/arLandUseInfoService/DTarLandUseInfo?"))

    def test_app_side_through_proxy_end_to_end(self):
        """앱(vworld.parcels_at) → 중계 서버 → (가짜) 브이월드 전체 경로."""
        feats = [{"type": "Feature", "geometry": None, "properties": {"pnu": "1"}}]
        up = {"response": {"status": "OK", "result": {"featureCollection": {"features": feats}}}}
        env = {"PROXY_URL": self.base.rsplit("/api/relay", 1)[0], "VWORLD_KEY": "K",
               "VWORLD_DOMAIN": "http://localhost"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(relay.urllib.request, "urlopen", fake_urlopen_factory(up)):
            self.assertEqual(vworld.parcels_at(127.1, 35.8), feats)

    def test_app_side_wrong_token_message(self):
        # 시험에서는 중계 서버와 앱이 같은 환경변수를 쓰므로, 앱 쪽 키 읽기만 바꿔서 틀린 토큰을 보냄
        fake = {"PROXY_URL": self.base.rsplit("/api/relay", 1)[0], "PROXY_TOKEN": "wrong"}
        with mock.patch.object(api_http, "get_key", side_effect=fake.get):
            with self.assertRaises(api_http.ApiError) as cm:
                api_http.fetch_json("vworld_data", {"key": "K"})
        self.assertIn("토큰", str(cm.exception))


class TestDirectHint(unittest.TestCase):
    def test_connection_error_hint_without_proxy(self):
        with mock.patch.dict(os.environ, {"PROXY_URL": ""}), \
             mock.patch("requests.get", side_effect=requests.ConnectionError()):
            with self.assertRaises(api_http.ApiError) as cm:
                api_http.fetch_json("vworld_data", {})
        self.assertIn("중계 서버", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
