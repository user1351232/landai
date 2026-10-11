"""공간 자료 수신 검사 (geopandas, pyproj, rasterio 필요).

- INGEST-CRS-01  선언된 좌표계와 실제 좌표 범위를 둘 다 확인. 어긋나면 맞는 좌표계 후보 제안
- INGEST-GEOM-01 빈 도형·잘못된 도형 검출
- INGEST-RES-01  DEM 해상도가 필지 크기에 비해 거친지 검사 (90m 사례)
"""

from __future__ import annotations

from pathlib import Path

from landai.profile import DataProfile

# 국내 자료에서 자주 쓰이는 좌표계 (좌표계 정보가 틀렸을 때 후보로 시험)
CANDIDATE_CRS = ["EPSG:5186", "EPSG:5174", "EPSG:5181", "EPSG:5185", "EPSG:5187",
                 "EPSG:5179", "EPSG:2097", "EPSG:4326"]


def _bounds_to_wgs84(bounds, crs) -> tuple[float, float, float, float] | None:
    from pyproj import Transformer
    try:
        tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        return tr.transform_bounds(*bounds)
    except Exception:
        return None


def _inside(b, region_bbox, tol=0.0) -> bool:
    """b 가 지역 범위 안에 들어오는지 (경위도)."""
    x0, y0, x1, y1 = region_bbox
    return (b[0] >= x0 - tol and b[1] >= y0 - tol and b[2] <= x1 + tol and b[3] <= y1 + tol)


def _overlaps(b, region_bbox) -> bool:
    x0, y0, x1, y1 = region_bbox
    return not (b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1)


def check_crs(bounds, declared_crs, expected_crs, region: dict, profile: DataProfile) -> str | None:
    """좌표계 이중 확인. 사용할 좌표계를 돌려주고, 확정 못 하면 None."""
    rb = region["bbox_wgs84"]
    detail = {"declared": str(declared_crs) if declared_crs else None,
              "expected": expected_crs, "bounds": list(map(float, bounds))}

    if declared_crs:
        wgs = _bounds_to_wgs84(bounds, declared_crs)
        if wgs and _overlaps(wgs, rb):
            status = "pass"
            msg = f"좌표계 {declared_crs} 와 실제 좌표 범위가 대상 지역과 맞음"
            if expected_crs and str(declared_crs).upper() != str(expected_crs).upper():
                status, msg = "warn", msg + f" (매니페스트 기대값 {expected_crs} 와 다름)"
            profile.add("INGEST-CRS-01", status, msg, **detail, bounds_wgs84=wgs)
            return str(declared_crs)

    # 선언 좌표계가 없거나 틀림 → 후보 시험
    fits = []
    for cand in CANDIDATE_CRS:
        wgs = _bounds_to_wgs84(bounds, cand)
        if wgs and _overlaps(wgs, rb):
            fits.append(cand)
    reason = "좌표계 정보 없음" if not declared_crs else f"선언된 {declared_crs} 로는 대상 지역 밖"
    if len(fits) == 1:
        profile.add("INGEST-CRS-01", "warn", f"{reason}. 좌표 범위로 보면 {fits[0]} 로 추정",
                    **detail, candidates=fits)
        return fits[0]
    profile.add("INGEST-CRS-01", "fail",
                f"{reason}. 맞는 좌표계 후보: {', '.join(fits) or '없음'} (사람 확인 필요)",
                **detail, candidates=fits)
    return None


def check_vector(path: Path, manifest: dict, region: dict, profile: DataProfile):
    import geopandas as gpd

    gdf = gpd.read_file(path)
    profile.stats.update(features=len(gdf), columns=[c for c in gdf.columns if c != "geometry"],
                         geom_types=gdf.geom_type.value_counts().to_dict())

    crs = check_crs(gdf.total_bounds, gdf.crs, manifest.get("expected_crs"), region, profile)

    empty = int(gdf.geometry.is_empty.sum() + gdf.geometry.isna().sum())
    invalid = int((~gdf.geometry.is_valid & ~gdf.geometry.is_empty).sum())
    if empty or invalid:
        profile.add("INGEST-GEOM-01", "warn", f"빈 도형 {empty}개, 잘못된 도형 {invalid}개",
                    empty=empty, invalid=invalid)
    else:
        profile.add("INGEST-GEOM-01", "pass", "도형 이상 없음")

    expected = manifest.get("expected_columns") or []
    missing = [c for c in expected if c not in gdf.columns]
    if missing:
        profile.add("INGEST-COL-01", "fail", f"기대 컬럼 누락: {', '.join(missing)}",
                    missing=missing, actual=list(gdf.columns))
    elif expected:
        profile.add("INGEST-COL-01", "pass", "기대 컬럼 모두 있음")
    return gdf, crs


def check_raster(path: Path, manifest: dict, region: dict, profile: DataProfile,
                 parcels=None):
    """DEM 검사. parcels(GeoDataFrame, 미터 좌표계)가 있으면 필지당 픽셀 수를 계산합니다."""
    import rasterio

    with rasterio.open(path) as src:
        res = src.res
        bounds = tuple(src.bounds)
        crs = src.crs.to_string() if src.crs else None
        profile.stats.update(width=src.width, height=src.height, res=list(res), crs=crs,
                             nodata=src.nodata)

    used = check_crs(bounds, crs, manifest.get("expected_crs"), region, profile)

    # 해상도를 미터로 (경위도 래스터면 대략 환산)
    if used and used.upper() == "EPSG:4326":
        px_m = abs(res[0]) * 111_000 * 0.82   # 위도 35도 부근 경도 1도 ≈ 91km
    else:
        px_m = abs(res[0])
    profile.stats["pixel_size_m"] = round(px_m, 2)

    min_px = manifest.get("min_pixels_per_parcel", 25)
    if parcels is not None and len(parcels):
        median_area = float(parcels.to_crs(region["work_crs"]).area.median())
        per_parcel = median_area / (px_m ** 2)
        status = "pass" if per_parcel >= min_px else "warn"
        profile.add("INGEST-RES-01", status,
                    f"픽셀 {px_m:.1f}m, 필지 중앙값 {median_area:,.0f}m²에 픽셀 약 {per_parcel:.1f}개"
                    + ("" if status == "pass" else " → 필지 단위 경사 분석에 너무 거침"),
                    pixel_size_m=px_m, median_parcel_m2=median_area,
                    pixels_per_parcel=per_parcel, threshold=min_px)
    else:
        status = "pass" if px_m <= 10 else "warn"
        profile.add("INGEST-RES-01", status,
                    f"픽셀 {px_m:.1f}m (지적도와 함께 검사하면 필지당 픽셀 수도 계산)"
                    + ("" if status == "pass" else " → 10m보다 거침, 필지 단위 분석 주의"),
                    pixel_size_m=px_m)
