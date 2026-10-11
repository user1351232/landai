"""위치 하나를 받아 분석 단계를 순서대로 실행하고, 단계마다 이력을 남깁니다.

지금 단계 (v0.3)
  1. 위치 확인        지원 지역 안인지 (PLAN-07)
  2. 필지 조회        브이월드 연속지적도에서 좌표가 들어 있는 필지 (후보가 여럿이면 되묻기, PLAN-04)
  3. 필지번호 검사    19자리 형식, 옛 시도코드 변환 (STD-PNU-01, STD-SIDO-01)
  4. 위치 교차 확인   좌표가 필지 경계 안에 실제로 있는지 (VAL-X)
  5. 면적 계산        투영좌표계 EPSG:5186 에서 계산 (PLAN-02)
  6. 확신도 판정      확정 / 복원 / 추정 / 미연결
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from landai import geo
from landai import pnu as pnu_mod

STATUS_KO = {"pass": "통과", "warn": "경고", "fail": "실패"}


class Run:
    def __init__(self):
        self.log: list[dict] = []

    def step(self, name: str, tool: str, status: str, result: str) -> None:
        self.log.append({"시각": datetime.now().strftime("%H:%M:%S"), "단계": name,
                         "도구": tool, "판정": STATUS_KO[status], "결과": result})


def analyze(lon: float, lat: float, region: dict, *, choice: int | None = None,
            fetch: Callable[[float, float], list[dict]] | None = None) -> dict:
    if fetch is None:
        from landai.apis.vworld import parcels_at as fetch

    run = Run()
    out = {"input": {"lon": lon, "lat": lat}, "region": region["id"], "status": "ok",
           "parcels": [], "parcel": None, "pnu": None, "area_m2": None,
           "grade": "미연결", "log": run.log}

    # 1. 위치 확인
    if not geo.in_region(lon, lat, region):
        run.step("위치 확인", "in_region", "fail",
                 f"({lat:.5f}, {lon:.5f}) 은 {region['name']} 범위 밖. 지원 지역이 아님")
        out["status"] = "outside"
        return out
    run.step("위치 확인", "in_region", "pass", f"{region['name']} 범위 안")

    # 2. 필지 조회
    try:
        feats = fetch(lon, lat)
    except Exception as e:
        run.step("필지 조회", "vworld.parcels_at", "fail", str(e))
        out["status"] = "error"
        return out
    out["parcels"] = feats
    if not feats:
        run.step("필지 조회", "vworld.parcels_at", "warn",
                 "필지 없음. 도로·하천 위이거나 지적도에 없는 위치")
        out["status"] = "no_parcel"
        return out
    if len(feats) > 1 and choice is None:
        run.step("필지 조회", "vworld.parcels_at", "warn",
                 f"후보 필지 {len(feats)}개. 사용자 선택 필요 (되묻기)")
        out["status"] = "multiple"
        return out
    feat = feats[choice or 0]
    out["parcel"] = feat
    props = feat.get("properties", {})
    run.step("필지 조회", "vworld.parcels_at", "pass",
             f"{props.get('addr') or props.get('jibun') or '필지'} 찾음")

    # 3. 필지번호 검사
    r = pnu_mod.standardize(props.get("pnu"), legacy_sido=region.get("legacy_sido_code"),
                            current_sido=region.get("sido_code"))
    out["pnu"] = {"raw": r.raw, "pnu": r.pnu, "status": r.status, "note": r.note}
    pnu_ok = r.status in ("ok", "recoded", "restored")
    run.step("필지번호 검사", "pnu.standardize", "pass" if r.status == "ok" else
             ("warn" if pnu_ok else "fail"), f"{r.status} {r.pnu or r.raw} {r.note}".strip())

    # 4. 위치 교차 확인, 5. 면적
    inside = None
    try:
        inside = geo.contains(feat["geometry"], lon, lat)
        run.step("위치 교차 확인", "geo.contains", "pass" if inside else "warn",
                 "입력 좌표가 필지 경계 안에 있음" if inside else "입력 좌표가 필지 경계 밖")
        out["area_m2"] = round(geo.area_m2(feat["geometry"]), 1)
        run.step("면적 계산", "geo.area_m2 (EPSG:5186)", "pass", f"{out['area_m2']:,} ㎡")
    except ImportError as e:
        run.step("면적 계산", "geo.area_m2", "warn", f"라이브러리 없음({e.name}), 건너뜀")

    # 6. 확신도
    if pnu_ok and inside is not False:
        out["grade"] = {"ok": "확정", "recoded": "확정", "restored": "복원"}[r.status]
    else:
        out["grade"] = "추정"
    run.step("확신도 판정", "rules", "pass" if out["grade"] == "확정" else "warn", out["grade"])
    return out
