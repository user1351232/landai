import test from "node:test";
import assert from "node:assert/strict";
import { analyze } from "../app/js/pipeline.js";
import { REGIONS } from "../app/js/regions.js";

const R = REGIONS.jeonju;
const LON = 127.148, LAT = 35.8242;
const SQ = { type: "Polygon", coordinates: [[[127.1479, 35.8241], [127.1481, 35.8241], [127.1481, 35.8243],
  [127.1479, 35.8243], [127.1479, 35.8241]]] };
const feat = (pnu = "5211110100100120003", addr = "예시 필지") =>
  ({ type: "Feature", geometry: SQ, properties: { pnu, addr, jiga: "1234000" } });

test("지역 밖", async () => {
  const r = await analyze(126.5, 37.5, R, { fetchParcels: async () => [feat()] });
  assert.equal(r.status, "outside");
});
test("필지 없음", async () => {
  const r = await analyze(LON, LAT, R, { fetchParcels: async () => [] });
  assert.deepEqual([r.status, r.grade], ["no_parcel", "미연결"]);
});
test("후보 여럿 → 되묻기, 선택하면 분석", async () => {
  const two = [feat(), feat(undefined, "다른 필지")];
  assert.equal((await analyze(LON, LAT, R, { fetchParcels: async () => two })).status, "multiple");
  const r = await analyze(LON, LAT, R, { fetchParcels: async () => two, choice: 1 });
  assert.equal(r.parcel.properties.addr, "다른 필지");
});
test("정상 필지 → 확정, 면적 계산", async () => {
  const r = await analyze(LON, LAT, R, { fetchParcels: async () => [feat()] });
  assert.deepEqual([r.status, r.grade, r.pnu.status], ["ok", "확정", "ok"]);
  assert.ok(r.area_m2 > 300 && r.area_m2 < 500);
  assert.deepEqual(r.log.map((s) => s.단계),
    ["위치 확인", "필지 조회", "필지번호 검사", "위치 교차 확인", "면적 계산", "확신도 판정"]);
});
test("옛 시도코드 필지번호 변환", async () => {
  const r = await analyze(LON, LAT, R, { fetchParcels: async () => [feat("4511110100100120003")] });
  assert.equal(r.pnu.pnu, "5211110100100120003");
});
test("좌표가 필지 밖이면 추정", async () => {
  const r = await analyze(127.149, 35.825, R, { fetchParcels: async () => [feat()] });
  assert.equal(r.grade, "추정");
});
test("조회 오류", async () => {
  const r = await analyze(LON, LAT, R, { fetchParcels: async () => { throw new Error("브이월드 접속 실패"); } });
  assert.equal(r.status, "error");
});
