"""서울 지역 중계 함수 (Vercel, icn1).

해외 서버(Streamlit Cloud)에서 막히는 국내 공공 API 를 서울에서 대신 호출합니다.

POST /api/relay   본문 {"target": 대상, "params": {...}, "path": 공공데이터포털 경로}
                  헤더 X-Proxy-Token 필요. 키는 본문에만 담겨 접속 기록(URL)에 남지 않음
GET  /api/relay?_target=ping   접속 점검 (토큰 불필요)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

TARGETS = {
    "vworld_data": "https://api.vworld.kr/req/data",
    "vworld_address": "https://api.vworld.kr/req/address",
    "vworld_search": "https://api.vworld.kr/req/search",
    "juso": "https://business.juso.go.kr/addrlink/addrLinkApi.do",
}
DATA_GO_KR = "https://apis.data.go.kr/"
DATA_PATH_RE = re.compile(r"^[0-9]{7}/[A-Za-z0-9_]+(/[A-Za-z0-9_]+){0,3}$")
TIMEOUT = 20
UA = {"User-Agent": "landai-proxy/1.0", "Accept": "application/json, */*"}


def ping() -> dict:
    """서울에서 브이월드에 닿는지 확인 (키 없이 불러서 응답이 오는지만 봄)."""
    url = TARGETS["vworld_address"] + "?service=address&request=getcoord&format=json"
    info = {"ok": True, "region": os.environ.get("VERCEL_REGION", "알 수 없음"),
            "token_set": bool(os.environ.get("PROXY_TOKEN"))}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
            info.update(vworld_reachable=True, vworld_http=r.status)
    except urllib.error.HTTPError as e:
        info.update(vworld_reachable=True, vworld_http=e.code)
    except Exception as e:
        info.update(vworld_reachable=False, vworld_error=f"{type(e).__name__}: {e}")
    return info


def build_url(target: str, params: dict, path: str | None) -> str | None:
    forward = [(str(k), str(v)) for k, v in (params or {}).items()]
    if target in TARGETS:
        base = TARGETS[target]
    elif target == "datagokr" and path and DATA_PATH_RE.match(path):
        base = DATA_GO_KR + path
    else:
        return None
    return base + ("?" + urllib.parse.urlencode(forward) if forward else "")


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj: dict) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        if q.get("_target") == "ping":
            return self._json(200, ping())
        return self._json(405, {"error": "점검(ping) 외의 요청은 POST 로 보내세요"})

    def do_POST(self):  # noqa: N802
        token = os.environ.get("PROXY_TOKEN", "")
        if not token:
            return self._json(500, {"error": "중계 서버에 PROXY_TOKEN 환경변수가 없습니다"})
        if self.headers.get("X-Proxy-Token", "") != token:
            return self._json(401, {"error": "토큰이 없거나 맞지 않습니다"})
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 100_000)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "본문이 JSON 이 아닙니다"})
        if not isinstance(body, dict) or not isinstance(body.get("params") or {}, dict):
            return self._json(400, {"error": "본문 형식이 맞지 않습니다"})

        target = str(body.get("target", ""))
        url = build_url(target, body.get("params") or {}, body.get("path"))
        if url is None:
            return self._json(400, {"error": f"허용되지 않은 대상: {target}"})

        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=TIMEOUT) as r:
                self._send(r.status, r.read(), r.headers.get("Content-Type", "application/json"))
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read(), e.headers.get("Content-Type", "text/plain"))
        except Exception as e:
            self._json(502, {"error": f"원 서버 접속 실패: {type(e).__name__}"})

    def log_message(self, *args):  # 요청 주소(키 포함)를 로그에 남기지 않음
        pass
