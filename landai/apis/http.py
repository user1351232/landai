"""국내 공공 API 호출 (파이썬 쪽, 국내 컴퓨터에서 직접 호출).

브이월드 등은 해외 IP 요청을 막고, 지도 데이터의 국외 반출도 법적으로 조심해야 해서
해외 서버를 거치지 않습니다. 앱(윈도우·안드로이드)은 사용자 기기에서 직접 부르고,
이 파이썬 코드는 국내 노트북에서 자료를 정리할 때 씁니다.
"""

from __future__ import annotations

import requests

TARGET_URLS = {
    "vworld_data": "https://api.vworld.kr/req/data",
    "vworld_address": "https://api.vworld.kr/req/address",
    "vworld_search": "https://api.vworld.kr/req/search",
    "juso": "https://business.juso.go.kr/addrlink/addrLinkApi.do",
}
DATA_GO_KR = "https://apis.data.go.kr/"


class ApiError(RuntimeError):
    pass


def fetch_json(target: str, params: dict, *, path: str | None = None, timeout: int = 20) -> dict:
    try:
        url = DATA_GO_KR + (path or "") if target == "datagokr" else TARGET_URLS[target]
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError as e:
        raise ApiError("접속 실패 (ConnectionError). 해외 서버에서는 브이월드 등 국내 API 가 막힙니다. "
                       "국내 컴퓨터에서 실행하세요.") from e
    except requests.RequestException as e:
        raise ApiError(f"접속 실패: {type(e).__name__}") from e
    except ValueError as e:
        raise ApiError("응답이 JSON 이 아닙니다. 키와 등록 URL 을 확인하세요.") from e
