import test from "node:test";
import assert from "node:assert/strict";

// 노드에는 localStorage 가 없으므로 흉내 냄 (설정 화면에 키를 저장한 상태)
const mem = new Map();
globalThis.localStorage = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v),
  removeItem: (k) => mem.delete(k) };
mem.set("landai.VWORLD_KEY", "TESTKEY");

const { geocode, parcelsAt, tileUrl, VworldError } = await import("../app/js/vworld.js");
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
  await assert.rejects(parcelsAt(127, 35), (e) => e instanceof VworldError && e.message.includes("INCORRECT_KEY"));
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
