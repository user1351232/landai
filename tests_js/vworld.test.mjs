import test from "node:test";
import assert from "node:assert/strict";

// 노드에는 localStorage 가 없으므로 흉내 냄 (설정 화면에 키를 저장한 상태)
const mem = new Map();
globalThis.localStorage = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v),
  removeItem: (k) => mem.delete(k) };
mem.set("landai.VWORLD_KEY", "TESTKEY");

const { geocode, parcelsAt, tileUrl, VworldError, zoneAt, landUse, nedItems } = await import("../app/js/vworld.js");
const { buildUrl, getJson, ApiError } = await import("../app/js/http.js");

function mockFetch(bodies) {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    const body = bodies.shift();
    return { ok: true, status: 200, text: async () => JSON.stringify(body) };
  };
  return calls;
}

test("주소 → 좌표 (도로명)", async () => {
  const calls = mockFetch([{ response: { status: "OK", refined: { text: "정제" }, result: { point: { x: "127.1", y: "35.8" } } } }]);
  const r = await geocode("전주시청");
  assert.deepEqual([r.lon, r.lat, r.type], [127.1, 35.8, "도로명"]);
  assert.ok(calls[0].startsWith("https://api.vworld.kr/req/address?"));
  assert.ok(calls[0].includes("key=TESTKEY") && calls[0].includes("domain=http%3A%2F%2Flocalhost"));
});
test("도로명 실패 → 지번으로 재시도", async () => {
  mockFetch([{ response: { status: "NOT_FOUND" } }, { response: { status: "OK", result: { point: { x: "1", y: "2" } } } }]);
  assert.equal((await geocode("효자동 12")).type, "지번");
});
test("필지 조회 성공·없음·오류", async () => {
  mockFetch([{ response: { status: "OK", result: { featureCollection: { features: [{ id: 1 }] } } } }]);
  assert.equal((await parcelsAt(127, 35)).length, 1);
  mockFetch([{ response: { status: "NOT_FOUND" } }]);
  assert.deepEqual(await parcelsAt(127, 35), []);
  mockFetch([{ response: { status: "ERROR", error: { code: "INCORRECT_KEY", text: "키 오류" } } }]);
  await assert.rejects(parcelsAt(127, 35), (e) => e instanceof VworldError && e.message.includes("INCORRECT_KEY")
    && e.message.includes("앱이 보낸 URL: http://localhost") && e.message.includes("등록 서비스 URL"));
  mockFetch([{ response: { status: "ERROR", error: { code: "INVALID_KEY", text: "등록되지 않은 인증키입니다." } } }]);
  await assert.rejects(geocode("전주시청"), (e) => e.message.includes("INVALID_KEY") && e.message.includes("활용 API"));
  mockFetch([{ response: { status: "ERROR", error: { code: "SYSTEM_ERROR", text: "x" } } }]);
  await assert.rejects(parcelsAt(127, 35), (e) => !e.message.includes("→"));
});
test("키가 없으면 안내", async () => {
  mem.delete("landai.VWORLD_KEY");
  await assert.rejects(parcelsAt(127, 35), /설정/);
  mem.set("landai.VWORLD_KEY", "TESTKEY");
});
test("윈도우 앱에서는 Rust 명령으로 호출", async () => {
  const seen = [];
  globalThis.__TAURI__ = { core: { invoke: async (cmd, args) => { seen.push([cmd, args]); return '{"ok":1}'; } } };
  assert.deepEqual(await getJson("vworld_data", { a: 1 }), { ok: 1 });
  assert.equal(seen[0][0], "http_get");
  assert.deepEqual(seen[0][1].params, { a: "1" });
  delete globalThis.__TAURI__;
});
test("허용 대상만 호출", () => {
  assert.throws(() => buildUrl("https://evil.example", {}), ApiError);
  assert.throws(() => buildUrl("datagokr", {}, "../etc"), ApiError);
  assert.ok(buildUrl("datagokr", { serviceKey: "S" }, "1613000/arLandUseInfoService/DTarLandUseInfo")
    .startsWith("https://apis.data.go.kr/1613000/"));
});
test("브라우저 접속 실패 안내", async () => {
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(getJson("vworld_data", {}), /앱으로 실행/);
});
test("타일 주소", () => assert.ok(tileUrl("K", "Satellite").endsWith("/K/Satellite/{z}/{y}/{x}.jpeg")));

test("용도지역 레이어: 이름 없는 도시지역 도형은 건너뛰고 다음 레이어까지", async () => {
  const calls = mockFetch([
    { response: { status: "OK", result: { featureCollection: { features: [{ properties: { uname: null, ucode: "UQA01X" } }] } } } },
    { response: { status: "NOT_FOUND" } },
    { response: { status: "OK", result: { featureCollection: { features: [{ properties: { uname: "계획관리지역" } }] } } } },
  ]);
  const z = await zoneAt(127.1, 35.8);
  assert.deepEqual([z.layer, z.name], ["LT_C_UQ113", "계획관리지역"]);
  assert.ok(calls[0].includes("data=LT_C_UQ111") && calls[0].includes("geomFilter=POINT"));
  mockFetch([1, 2, 3, 4].map(() => ({ response: { status: "NOT_FOUND" } })));
  assert.equal(await zoneAt(127.1, 35.8), null);
});
test("토지이용계획: 국가중점 API 주소와 두 가지 응답 모양", async () => {
  const calls = mockFetch([{ landUses: { field: [{ prposAreaDstrcCodeNm: "일반상업지역", cnflcAt: "1" }],
    totalCount: "1", resultCode: null, resultMsg: null } }]);
  const items = await landUse("5211114700105680001");
  assert.equal(items[0].prposAreaDstrcCodeNm, "일반상업지역");
  assert.ok(calls[0].startsWith("https://api.vworld.kr/ned/data/getLandUseAttr?"));
  assert.ok(calls[0].includes("pnu=5211114700105680001") && calls[0].includes("domain="));
  // 항목 하나면 배열이 아니라 객체로 오는 경우
  assert.equal(nedItems({ response: { status: "OK", fields: { field: { prposAreaDstrcCodeNm: "준주거지역" } } } }).length, 1);
  assert.deepEqual(nedItems({ landUses: { field: [], totalCount: "0" } }), []);
});
test("토지이용계획 오류는 키 안내와 함께", async () => {
  assert.throws(() => nedItems({ landUses: { resultCode: "INCORRECT_KEY", resultMsg: "인증키 정보가 올바르지 않습니다." } }),
    (e) => e instanceof VworldError && e.message.includes("INCORRECT_KEY") && e.message.includes("등록 서비스 URL"));
  assert.throws(() => nedItems({ response: { status: "ERROR", error: { code: "INVALID_KEY", text: "x" } } }), /INVALID_KEY/);
  assert.deepEqual(nedItems({ response: { status: "NOT_FOUND" } }), []);
});
test("국가중점 API 는 정해진 기능만", () => {
  assert.ok(buildUrl("vworld_ned", { a: 1 }, "getLandUseAttr").startsWith("https://api.vworld.kr/ned/data/getLandUseAttr?"));
  assert.throws(() => buildUrl("vworld_ned", {}, "../req/data"), ApiError);
  assert.throws(() => buildUrl("vworld_ned", {}, null), ApiError);
});
