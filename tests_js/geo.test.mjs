import test from "node:test";
import assert from "node:assert/strict";
import { toEpsg5186, areaM2, contains, inRegion } from "../app/js/geo.js";

const A = 6378137, F = 1 / 298.257222101, E2 = 2 * F - F * F;
const rad = (d) => (d * Math.PI) / 180;

test("원점 (127E, 38N) → (200000, 600000)", () => {
  const [x, y] = toEpsg5186(127, 38);
  assert.ok(Math.abs(x - 200000) < 1e-6 && Math.abs(y - 600000) < 1e-6);
});

test("중앙 경선 위 남북 거리 = 자오선 호 길이 (타원체 식과 비교)", () => {
  // 위도 35.80°~35.81° 자오선 호를 수치 적분으로 독립 계산
  let arc = 0; const n = 2000;
  for (let i = 0; i < n; i++) {
    const phi = rad(35.8 + (0.01 * (i + 0.5)) / n);
    arc += (A * (1 - E2)) / Math.pow(1 - E2 * Math.sin(phi) ** 2, 1.5) * rad(0.01 / n);
  }
  const d = toEpsg5186(127, 35.81)[1] - toEpsg5186(127, 35.8)[1];
  assert.ok(Math.abs(d - arc) < 0.01, `${d} vs ${arc}`);
});

test("전주 부근 작은 사각형 면적이 타원체 면적과 0.01% 안에서 일치", () => {
  const lon0 = 127.148, lat0 = 35.824, dlon = 0.001, dlat = 0.001;
  const sq = { type: "Polygon", coordinates: [[[lon0, lat0], [lon0 + dlon, lat0], [lon0 + dlon, lat0 + dlat],
    [lon0, lat0 + dlat], [lon0, lat0]]] };
  const phi = rad(lat0 + dlat / 2);
  const M = (A * (1 - E2)) / Math.pow(1 - E2 * Math.sin(phi) ** 2, 1.5);
  const N = A / Math.sqrt(1 - E2 * Math.sin(phi) ** 2);
  const ref = M * rad(dlat) * N * Math.cos(phi) * rad(dlon);
  const a = areaM2(sq);
  assert.ok(Math.abs(a - ref) / ref < 1e-4, `${a} vs ${ref}`);
  assert.ok(a > 9500 && a < 10500); // 약 90m × 111m ≈ 10,026㎡
});

test("구멍 있는 도형과 MultiPolygon", () => {
  const outer = [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]].map(([x, y]) => [127 + x, 36 + y]);
  const hole = [[0.0004, 0.0004], [0.0006, 0.0004], [0.0006, 0.0006], [0.0004, 0.0006], [0.0004, 0.0004]]
    .map(([x, y]) => [127 + x, 36 + y]);
  const full = areaM2({ type: "Polygon", coordinates: [outer] });
  const holed = areaM2({ type: "Polygon", coordinates: [outer, hole] });
  assert.ok(Math.abs(holed - full * 0.96) / full < 1e-3);
  const multi = areaM2({ type: "MultiPolygon", coordinates: [[outer], [outer]] });
  assert.ok(Math.abs(multi - 2 * full) < 1e-6);
  const poly = { type: "Polygon", coordinates: [outer, hole] };
  assert.equal(contains(poly, 127.0002, 36.0002), true);
  assert.equal(contains(poly, 127.0005, 36.0005), false); // 구멍 안
  assert.equal(contains(poly, 127.002, 36.002), false);
});

test("지역 범위", () => {
  const r = { bbox_wgs84: [126.98, 35.72, 127.25, 35.93] };
  assert.equal(inRegion(127.148, 35.824, r), true);
  assert.equal(inRegion(126.5, 37.5, r), false);
});
