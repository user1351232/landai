import test from "node:test";
import assert from "node:assert/strict";
import { ZONES, kindOf, parseLandUse, limitsFor, judge, LAW_SOURCE } from "../app/js/zoning.js";
import { REGIONS } from "../app/js/regions.js";

test("국토계획법 용도지역 21개와 상한 값", () => {
  assert.equal(Object.keys(ZONES).length, 21);
  // 시행령 제84조·제85조 대표 값 대조
  assert.deepEqual([ZONES["제2종일반주거지역"].bcr, ZONES["제2종일반주거지역"].far], [60, 250]);
  assert.deepEqual([ZONES["제3종일반주거지역"].bcr, ZONES["제3종일반주거지역"].far], [50, 300]);
  assert.deepEqual([ZONES["준주거지역"].bcr, ZONES["준주거지역"].far], [70, 500]);
  assert.deepEqual([ZONES["중심상업지역"].bcr, ZONES["중심상업지역"].far], [90, 1500]);
  assert.deepEqual([ZONES["계획관리지역"].bcr, ZONES["계획관리지역"].far], [40, 100]);
  assert.deepEqual([ZONES["자연환경보전지역"].bcr, ZONES["자연환경보전지역"].far], [20, 80]);
});
test("항목 종류 나누기", () => {
  assert.equal(kindOf("제2종 일반주거지역"), "용도지역");
  assert.equal(kindOf("도시지역"), "용도지역");
  assert.equal(kindOf("방화지구"), "지구");
  assert.equal(kindOf("대공방어협조구역"), "구역·기타");
  assert.equal(kindOf("가축사육제한구역"), "구역·기타");
});
test("토지이용계획 항목 정리 (포함·저촉 부호)", () => {
  const r = parseLandUse([
    { prposAreaDstrcCodeNm: "일반상업지역", prposAreaDstrcCode: "UQA220", cnflcAt: "1" },
    { prposAreaDstrcCodeNm: "대공방어협조구역", cnflcAt: "2", cnflcAtNm: "저촉" },
    { prposAreaDstrcCodeNm: "" },
  ]);
  assert.equal(r.length, 2);
  assert.deepEqual([r[0].name, r[0].conflict, r[0].kind], ["일반상업지역", "포함", "용도지역"]);
  assert.equal(r[1].conflict, "저촉");
});
test("전주시 조례 값이 있으면 조례, 없으면 법정 상한", () => {
  const j = REGIONS.jeonju;
  const a = limitsFor("일반상업지역", j);
  assert.deepEqual([a.bcr, a.far, a.lawFar], [80, 900, 1300]);
  assert.match(a.farSource, /전주시/);
  assert.equal(a.bcrSource, LAW_SOURCE);
  const b = limitsFor("자연녹지지역", j);
  assert.deepEqual([b.far, b.farSource], [100, LAW_SOURCE]);
  assert.equal(limitsFor("자연녹지지역", REGIONS.wanju).far, 100);
  assert.equal(limitsFor("없는지역", j), null);
});
test("두 자료 일치 → 건축 한도 계산", () => {
  const plan = parseLandUse([{ prposAreaDstrcCodeNm: "제2종일반주거지역", cnflcAt: "1" },
    { prposAreaDstrcCodeNm: "방화지구", cnflcAt: "1" }]);
  const z = judge(plan, "제2종일반주거지역", 1000, REGIONS.jeonju);
  assert.deepEqual([z.zone, z.group, z.agree, z.split], ["제2종일반주거지역", "주거", "match", false]);
  assert.deepEqual(z.build, { maxFootprint: 600, maxFloorArea: 2500 });
  assert.equal(z.districts.length, 1);
});
test("용도지역 두 개에 걸치면 한도 계산 안 함", () => {
  const plan = parseLandUse([{ prposAreaDstrcCodeNm: "제1종일반주거지역", cnflcAt: "1" },
    { prposAreaDstrcCodeNm: "자연녹지지역", cnflcAt: "2" }]);
  const z = judge(plan, "자연녹지지역", 1000, REGIONS.jeonju);
  assert.deepEqual([z.zone, z.split, z.build, z.agree], ["제1종일반주거지역", true, null, "match"]);
});
test("한쪽 자료만 있을 때", () => {
  assert.equal(judge(null, "계획관리지역", 100, REGIONS.wanju).agree, "layer_only");
  assert.equal(judge(null, "계획관리지역", 100, REGIONS.wanju).build.maxFloorArea, 100);
  assert.equal(judge(parseLandUse([{ prposAreaDstrcCodeNm: "준주거지역", cnflcAt: "1" }]), null, 100).agree, "plan_only");
  assert.equal(judge(null, null, 100).agree, "unknown");
  assert.equal(judge(parseLandUse([{ prposAreaDstrcCodeNm: "준주거지역" }]), "일반상업지역", 100).agree, "differ");
});
