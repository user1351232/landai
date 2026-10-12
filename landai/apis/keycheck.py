"""API 키 점검. 학교 서버에서 .env 를 채운 뒤 한 번 실행하세요.

    python -m landai.apis.keycheck

키 값은 화면에 출력하지 않습니다.
"""

from __future__ import annotations

import sys

import requests

from landai.apis.http import ApiError, fetch_json
from landai.config import get_key

TEST_ADDRESS = "전북특별자치도 전주시 완산구 효자로 225"
TIMEOUT = 15


def check_vworld() -> tuple[str, str]:
    key = get_key("VWORLD_KEY")
    if not key:
        return "skip", "VWORLD_KEY 가 비어 있음"
    params = {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "address": TEST_ADDRESS, "refine": "true",
        "simple": "false", "format": "json", "type": "road", "key": key,
        "domain": get_key("VWORLD_DOMAIN") or "http://localhost",
    }
    body = fetch_json("vworld_address", params, timeout=TIMEOUT).get("response", {})
    status = body.get("status")
    if status == "OK":
        p = body["result"]["point"]
        return "ok", f"지오코더 정상 (도청 좌표 {float(p['x']):.5f}, {float(p['y']):.5f})"
    err = body.get("error", {})
    return "fail", f"상태 {status}: {err.get('code', '')} {err.get('text', '')}".strip()


def check_juso() -> tuple[str, str]:
    key = get_key("JUSO_KEY")
    if not key:
        return "skip", "JUSO_KEY 가 비어 있음"
    params = {"confmKey": key, "currentPage": 1, "countPerPage": 1,
              "keyword": "효자로 225", "resultType": "json"}
    common = fetch_json("juso", params, timeout=TIMEOUT).get("results", {}).get("common", {})
    if common.get("errorCode") == "0":
        return "ok", f"주소 검색 정상 (결과 {common.get('totalCount')}건)"
    return "fail", f"{common.get('errorCode')}: {common.get('errorMessage')}"


def check_data_go_kr() -> tuple[str, str]:
    key = get_key("DATA_GO_KR_KEY")
    if not key:
        return "skip", "DATA_GO_KR_KEY 가 비어 있음"
    if len(key) < 20:
        return "fail", "키 길이가 너무 짧음. 일반 인증키 전체를 복사했는지 확인"
    return "ok", ("키 형식 정상. 실제 호출 점검은 각 API의 참고문서(오퍼레이션 이름)를 "
                  "받은 뒤 추가 예정")


def main() -> int:
    checks = {"브이월드": check_vworld, "도로명주소": check_juso, "공공데이터포털": check_data_go_kr}
    mark = {"ok": "정상", "fail": "실패", "skip": "건너뜀"}
    failed = False
    for name, fn in checks.items():
        try:
            status, msg = fn()
        except ApiError as e:
            status, msg = "fail", str(e)
        except requests.RequestException as e:
            status, msg = "fail", f"접속 오류: {type(e).__name__} (서버 인터넷 연결·방화벽 확인)"
        except ValueError:
            status, msg = "fail", "응답이 JSON이 아님 (키 또는 등록 URL 확인)"
        failed |= status == "fail"
        print(f"{name:<8} {mark[status]:<4} {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
