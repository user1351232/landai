import test from "node:test";
import assert from "node:assert/strict";
import { standardize, parseJibun } from "../app/js/pnu.js";

const DONG = "5211110100";
const OK = DONG + "1" + "0012" + "0003";

test("19자리 정상", () => assert.deepEqual([standardize(OK).status, standardize(OK).pnu], ["ok", OK]));
test("실수·하이픈 표기 정리", () => {
  assert.equal(standardize(OK + ".0").pnu, OK);
  assert.equal(standardize("52111-10100-1-0012-0003").pnu, OK);
});
test("옛 시도코드 45 → 52", () => {
  const r = standardize("45" + OK.slice(2), { legacySido: "45", currentSido: "52" });
  assert.deepEqual([r.status, r.pnu, r.rule], ["recoded", OK, "STD-SIDO-01"]);
});
test("18자리 + 지번 주소로 복구", () => {
  const r = standardize(DONG + "0012" + "0003", { jibunText: "효자동1가 12-3" });
  assert.deepEqual([r.status, r.pnu], ["restored", OK]);
});
test("18자리 산 지번", () => {
  assert.equal(standardize(DONG + "0012" + "0003", { jibunText: "산 12-3" }).pnu, DONG + "2" + "0012" + "0003");
});
test("18자리 단서 없으면 후보 여럿", () => {
  const r = standardize(DONG + "0012" + "0003");
  assert.equal(r.status, "ambiguous");
  assert.ok(r.candidates.includes(OK));
});
test("18자리 + 지적도로 확정", () => {
  const r = standardize(DONG + "0012" + "0003", { knownPnus: new Set([OK]) });
  assert.deepEqual([r.status, r.pnu], ["restored", OK]);
});
test("지수 표기", () => assert.equal(standardize("5.21111E+18").status, "sci_notation"));
test("잘못된 값", () => {
  assert.equal(standardize("12345").status, "invalid");
  assert.equal(standardize("").status, "empty");
  assert.equal(standardize(null).status, "empty");
  assert.equal(standardize(DONG + "3" + "0012" + "0003").status, "invalid");
});
test("지번 해석", () => {
  assert.deepEqual(parseJibun("산 12-3"), ["2", "0012", "0003"]);
  assert.deepEqual(parseJibun("123"), ["1", "0123", "0000"]);
  assert.equal(parseJibun(null), null);
});
