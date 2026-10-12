// 좌표 계산. 면적은 반드시 미터 단위 투영좌표계(EPSG:5186)에서 계산합니다.
// EPSG:5186 = GRS80 횡메르카토르, 원점 위도 38°, 중앙 경선 127°, 축척계수 1,
//             가산 동쪽 200,000m, 가산 북쪽 600,000m
// 외부 라이브러리 없이 Snyder(1987) 횡메르카토르 식으로 직접 계산합니다.

const A = 6378137.0;
const F = 1 / 298.257222101;
const E2 = 2 * F - F * F;
const EP2 = E2 / (1 - E2);
const LAT0 = (38 * Math.PI) / 180;
const LON0 = (127 * Math.PI) / 180;
const K0 = 1.0;
const FE = 200000;
const FN = 600000;

function meridianArc(phi) {
  const e4 = E2 * E2, e6 = e4 * E2;
  return A * ((1 - E2 / 4 - (3 * e4) / 64 - (5 * e6) / 256) * phi
    - ((3 * E2) / 8 + (3 * e4) / 32 + (45 * e6) / 1024) * Math.sin(2 * phi)
    + ((15 * e4) / 256 + (45 * e6) / 1024) * Math.sin(4 * phi)
    - ((35 * e6) / 3072) * Math.sin(6 * phi));
}
const M0 = meridianArc(LAT0);

/** 경위도(도) → EPSG:5186 [동쪽 X, 북쪽 Y] (미터) */
export function toEpsg5186(lon, lat) {
  const phi = (lat * Math.PI) / 180;
  const lam = (lon * Math.PI) / 180;
  const sin = Math.sin(phi), cos = Math.cos(phi), tan = Math.tan(phi);
  const N = A / Math.sqrt(1 - E2 * sin * sin);
  const T = tan * tan;
  const C = EP2 * cos * cos;
  const Aa = (lam - LON0) * cos;
  const M = meridianArc(phi);
  const x = K0 * N * (Aa + ((1 - T + C) * Aa ** 3) / 6
    + ((5 - 18 * T + T * T + 72 * C - 58 * EP2) * Aa ** 5) / 120);
  const y = K0 * (M - M0 + N * tan * ((Aa * Aa) / 2
    + ((5 - T + 9 * C + 4 * C * C) * Aa ** 4) / 24
    + ((61 - 58 * T + T * T + 600 * C - 330 * EP2) * Aa ** 6) / 720));
  return [x + FE, y + FN];
}

export function inRegion(lon, lat, region) {
  const [x0, y0, x1, y1] = region.bbox_wgs84;
  return lon >= x0 && lon <= x1 && lat >= y0 && lat <= y1;
}

function polygons(geom) {
  if (!geom) return [];
  if (geom.type === "Polygon") return [geom.coordinates];
  if (geom.type === "MultiPolygon") return geom.coordinates;
  return [];
}

function ringArea(ring) {
  let s = 0;
  for (let i = 0, n = ring.length; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

/** GeoJSON(경위도) 도형의 면적 ㎡ — EPSG:5186 에서 계산, 구멍은 뺌 */
export function areaM2(geom) {
  let total = 0;
  for (const poly of polygons(geom)) {
    poly.forEach((ring, i) => {
      const a = ringArea(ring.map(([lon, lat]) => toEpsg5186(lon, lat)));
      total += i === 0 ? a : -a;
    });
  }
  return total;
}

function inRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** 점이 도형 안에 있는지 (구멍 제외) */
export function contains(geom, lon, lat) {
  return polygons(geom).some((poly) =>
    inRing(lon, lat, poly[0]) && !poly.slice(1).some((hole) => inRing(lon, lat, hole)));
}
