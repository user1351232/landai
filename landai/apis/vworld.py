"""브이월드 API (주소 → 좌표, 좌표 → 필지).

키는 .env 의 VWORLD_KEY, 키 발급 때 등록한 서비스 URL 은 VWORLD_DOMAIN 에 넣습니다.
"""

from __future__ import annotations

import requests

from landai.config import get_key

BASE = "https://api.vworld.kr/req"
TIMEOUT = 15
PARCEL_LAYER = "LP_PA_CBND_BUBUN"   # 연속지적도

# 필지 속성 이름 → 화면에 보일 한글 이름
PARCEL_LABELS = {
    "pnu": "필지고유번호(PNU)",
    "addr": "지번 주소",
    "jibun": "지번",
    "bonbun": "본번",
    "bubun": "부번",
    "jiga": "개별공시지가(원/㎡)",
    "gosi_year": "공시 연도",
    "gosi_month": "공시 월",
}


class VworldError(RuntimeError):
    pass


def _params(extra: dict) -> dict:
    key = get_key("VWORLD_KEY")
    if not key:
        raise VworldError("VWORLD_KEY 가 비어 있습니다. .env 파일에 브이월드 키를 넣으세요.")
    params = {"key": key, "domain": get_key("VWORLD_DOMAIN") or "http://localhost",
              "format": "json"}
    params.update(extra)
    return params


def _get(url: str, params: dict) -> dict:
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise VworldError(f"브이월드 접속 실패: {type(e).__name__} (인터넷 연결 확인)") from e
    except ValueError as e:
        raise VworldError("브이월드 응답이 JSON이 아닙니다. 키와 등록 URL(VWORLD_DOMAIN)을 확인하세요.") from e


def _error_text(resp: dict) -> str:
    err = resp.get("error") or {}
    return f"브이월드 오류 {err.get('code', '')}: {err.get('text', resp.get('status', ''))}".strip()


def geocode(address: str) -> dict | None:
    """주소를 좌표로. 도로명 주소로 먼저 찾고, 없으면 지번 주소로 찾습니다."""
    for kind in ("road", "parcel"):
        body = _get(f"{BASE}/address", _params({
            "service": "address", "request": "getcoord", "version": "2.0",
            "crs": "epsg:4326", "address": address, "refine": "true",
            "simple": "false", "type": kind,
        }))
        resp = body.get("response", {})
        status = resp.get("status")
        if status == "OK":
            pt = resp["result"]["point"]
            refined = (resp.get("refined") or {}).get("text") or address
            return {"lon": float(pt["x"]), "lat": float(pt["y"]), "address": refined,
                    "type": "도로명" if kind == "road" else "지번"}
        if status == "ERROR":
            raise VworldError(_error_text(resp))
    return None


def parcels_at(lon: float, lat: float) -> list[dict]:
    """좌표가 들어 있는 필지(GeoJSON Feature 목록). 도로·하천 위면 빈 목록."""
    body = _get(f"{BASE}/data", _params({
        "service": "data", "request": "GetFeature", "data": PARCEL_LAYER,
        "geomFilter": f"POINT({lon} {lat})", "crs": "EPSG:4326",
        "geometry": "true", "attribute": "true", "size": "10", "page": "1",
    }))
    resp = body.get("response", {})
    status = resp.get("status")
    if status == "NOT_FOUND":
        return []
    if status != "OK":
        raise VworldError(_error_text(resp))
    return resp["result"]["featureCollection"]["features"]


def tile_url(key: str, layer: str) -> str:
    """브이월드 배경지도 타일 주소. layer: Base | Satellite | Hybrid | gray | midnight"""
    ext = "jpeg" if layer == "Satellite" else "png"
    return f"https://api.vworld.kr/req/wmts/1.0.0/{key}/{layer}/{{z}}/{{y}}/{{x}}.{ext}"
