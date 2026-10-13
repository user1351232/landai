import test from "node:test";
import assert from "node:assert/strict";
import { parseJimok, parcelRows, JIMOK } from "../app/js/parcel.js";

test("지목 28개", () => assert.equal(Object.keys(JIMOK).length, 28));
test("지번에서 지목 꺼내기", () => {
  assert.deepEqual(parseJimok("568-1 대"), { code: "대", name: "대", lot: "568-1" });
  assert.deepEqual(parseJimok("산 12 임"), { code: "임", name: "임야", lot: "산 12" });
  assert.deepEqual(parseJimok("45-3장"), { code: "장", name: "공장용지", lot: "45-3" });
  assert.equal(parseJimok("568-1"), null);
  assert.equal(parseJimok(""), null);
  assert.equal(parseJimok("12 꽥"), null);
});
test("실제 브이월드 응답 모양 → 표 순서", () => {
  // 2026-10-13 윈도우 앱에서 받은 전주시청 필지 응답과 같은 모양
  const rows = parcelRows({ gosi_year: "2025", pnu: "5211114700105680001", jibun: "568-1 대", bonbun: "568",
    bubun: "1", addr: "전북특별자치도 전주시 완산구 서노송동 568-1", gosi_month: "01", jiga: "1676000" });
  assert.deepEqual(rows.map(([k]) => k),
    ["지번 주소", "지번", "지목", "본번", "부번", "개별공시지가", "공시 기준", "필지고유번호(PNU)"]);
  const m = Object.fromEntries(rows);
  assert.equal(m["지번"], "568-1");
  assert.equal(m["지목"], "대");
  assert.equal(m["개별공시지가"], "1,676,000 원/㎡");
  assert.equal(m["공시 기준"], "2025년 1월");
});
test("0 채운 본번·부번, 모르는 속성은 뒤에", () => {
  const m = parcelRows({ bonbun: "0568", bubun: "0000", jibun: "1 임", extra: "x" });
  assert.deepEqual(m.slice(-1), [["extra", "x"]]);
  assert.equal(Object.fromEntries(m)["부번"], "0");
  assert.equal(Object.fromEntries(m)["지목"], "임야 (임)");
});
