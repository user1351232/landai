"""국내 공공 API 호출 경로.

브이월드 등은 해외 IP 요청을 막습니다. 그래서
- PROXY_URL·PROXY_TOKEN 이 설정돼 있으면 서울 중계 서버(Vercel, proxy/ 폴더)를 거쳐 부르고
- 없으면 직접 부릅니다 (국내 노트북에서 실행할 때).
"""

from __future__ import annotations

import requests

from landai.config import get_key

TARGET_URLS = {
    "vworld_data": "https://api.vworld.kr/req/data",
    "vworld_address": "https://api.vworld.kr/req/address",
    "vworld_search": "https://api.vworld.kr/req/search",
    "juso": "https://business.juso.go.kr/addrlink/addrLinkApi.do",
}
DATA_GO_KR = "https://apis.data.go.kr/"


class ApiError(RuntimeError):
    pass


def using_proxy() -> bool:
    return bool(get_key("PROXY_URL"))


def fetch_json(target: str, params: dict, *, path: str | None = None, timeout: int = 20) -> dict:
    proxy = get_key("PROXY_URL")
    try:
        if proxy:
            r = requests.post(proxy.rstrip("/") + "/api/relay",
                              json={"target": target, "params": params, "path": path},
                              headers={"X-Proxy-Token": get_key("PROXY_TOKEN") or ""},
                              timeout=timeout)
            if r.status_code == 401:
                raise ApiError("중계 서버 토큰이 맞지 않습니다. Secrets 의 PROXY_TOKEN 과 "
                               "Vercel 환경변수 PROXY_TOKEN 이 같은지 확인하세요.")
            if r.status_code in (400, 405, 500, 502) and "json" in r.headers.get("Content-Type", ""):
                msg = r.json().get("error")
                if msg:
                    raise ApiError(f"중계 서버: {msg}")
        else:
            url = DATA_GO_KR + (path or "") if target == "datagokr" else TARGET_URLS[target]
            r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except ApiError:
        raise
    except requests.ConnectionError as e:
        hint = ("중계 서버 주소(PROXY_URL)를 확인하세요." if proxy else
                "해외 서버에서는 브이월드 등 국내 API 가 막힙니다. 서울 중계 서버를 설정하세요 "
                "(docs/DEPLOY.md 5단계).")
        raise ApiError(f"접속 실패 (ConnectionError). {hint}") from e
    except requests.RequestException as e:
        raise ApiError(f"접속 실패: {type(e).__name__}") from e
    except ValueError as e:
        raise ApiError("응답이 JSON 이 아닙니다. 키와 등록 URL 을 확인하세요.") from e
