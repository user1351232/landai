"""좌표 계산 도구. 면적·거리는 반드시 미터 단위 투영좌표계(EPSG:5186)에서 계산합니다."""

from __future__ import annotations

WORK_CRS = "EPSG:5186"


def in_region(lon: float, lat: float, region: dict) -> bool:
    """좌표가 지역 설정의 대략적 범위 안에 있는지 (PLAN-07)."""
    x0, y0, x1, y1 = region["bbox_wgs84"]
    return x0 <= lon <= x1 and y0 <= lat <= y1


def to_work_crs(geojson_geom: dict, crs: str = WORK_CRS):
    """경위도 GeoJSON 도형을 작업 좌표계(미터) shapely 도형으로."""
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform

    tr = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return transform(tr.transform, shape(geojson_geom))


def area_m2(geojson_geom: dict, crs: str = WORK_CRS) -> float:
    return float(to_work_crs(geojson_geom, crs).area)


def contains(geojson_geom: dict, lon: float, lat: float) -> bool:
    from shapely.geometry import Point, shape
    return shape(geojson_geom).buffer(1e-9).contains(Point(lon, lat))
