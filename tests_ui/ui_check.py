"""앱 화면을 실제 브라우저(Chromium)로 열어, 브이월드 응답을 흉내 내며 흐름을 시험합니다."""
import functools, http.server, json, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
FAKE_L = (Path(__file__).parent / "fake-leaflet.js").read_text(encoding="utf-8")

SQ = {"type": "Polygon", "coordinates": [[[127.1479, 35.8241], [127.1481, 35.8241], [127.1481, 35.8243],
                                         [127.1479, 35.8243], [127.1479, 35.8241]]]}
def feat(addr="전북특별자치도 전주시 완산구 서노송동 568-1", pnu="5211113200105680001"):
    # 2026-10-13 실제 브이월드 응답과 같은 속성 순서·모양
    return {"type": "Feature", "geometry": SQ, "properties": {"gosi_year": "2025", "pnu": pnu, "jibun": "568-1 대",
            "bonbun": "568", "bubun": "1", "addr": addr, "gosi_month": "01", "jiga": "1520000"}}

ZONE_SQ = {"type": "Polygon", "coordinates": [[[127.147, 35.823], [127.149, 35.823], [127.149, 35.825],
                                              [127.147, 35.825], [127.147, 35.823]]]}
PLAN = [{"prposAreaDstrcCodeNm": "일반상업지역", "prposAreaDstrcCode": "UQA220", "cnflcAt": "1", "cnflcAtNm": "포함"},
        {"prposAreaDstrcCodeNm": "방화지구", "cnflcAt": "1", "cnflcAtNm": "포함"},
        {"prposAreaDstrcCodeNm": "대공방어협조구역", "cnflcAt": "1", "cnflcAtNm": "포함"}]
scenario = {"parcels": [feat()], "geocode": {"x": "127.148", "y": "35.8242"}, "error": None, "addr_error": None,
            "plan": PLAN, "plan_error": None, "zone": "일반상업지역"}

def vworld(route):
    url = route.request.url
    h = {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
    if scenario["addr_error"] and "/req/address" in url:
        body = {"response": {"status": "ERROR", "error": {"code": scenario["addr_error"], "text": "등록되지 않은 인증키입니다."}}}
    elif scenario["error"]:
        body = {"response": {"status": "ERROR", "error": {"code": scenario["error"], "text": "시험용 오류"}}}
    elif "/req/address" in url:
        body = {"response": {"status": "OK", "refined": {"text": "정제된 주소"}, "result": {"point": scenario["geocode"]}}}
    elif "/ned/data/getLandUseAttr" in url:
        if scenario["plan_error"]:
            body = {"landUses": {"resultCode": scenario["plan_error"], "resultMsg": "인증키 정보가 올바르지 않습니다."}}
        else:
            body = {"landUses": {"field": scenario["plan"], "totalCount": str(len(scenario["plan"])),
                                 "resultCode": None, "resultMsg": None}}
    elif "/req/data" in url and "LT_C_UQ" in url:
        hit = scenario["zone"] and "LT_C_UQ111" in url
        body = {"response": {"status": "OK", "result": {"featureCollection": {"features": [
            {"type": "Feature", "geometry": ZONE_SQ, "properties": {"uname": scenario["zone"], "ucode": "UQA220"}}]}}}} \
            if hit else {"response": {"status": "NOT_FOUND"}}
    elif "/req/data" in url:
        fs = scenario["parcels"]
        body = {"response": {"status": "OK", "result": {"featureCollection": {"features": fs}}}} if fs \
            else {"response": {"status": "NOT_FOUND"}}
    else:
        return route.fulfill(status=204, headers=h)
    route.fulfill(status=200, headers=h, body=json.dumps(body))

def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(APP))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/index.html"
    results = []
    def check(name, cond):
        results.append((name, bool(cond)))

    with sync_playwright() as p:
        b = p.chromium.launch()
        for width, height, tag in [(1280, 820, "desktop"), (390, 844, "mobile")]:
            ctx = b.new_context(viewport={"width": width, "height": height}, locale="ko-KR")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("**/vendor/leaflet/leaflet.js", lambda r: r.fulfill(body=FAKE_L, content_type="text/javascript"))
            page.route("**/vendor/leaflet/leaflet.css", lambda r: r.fulfill(body="", content_type="text/css"))
            page.route("https://api.vworld.kr/**", vworld)

            # 키 없는 상태
            page.goto(base); page.wait_for_timeout(400)
            check(f"{tag}: 키 없으면 설정 안내", "설정" in page.inner_text("#panel"))
            check(f"{tag}: 키 없으면 OSM 지도", any("openstreetmap" in t for t in page.evaluate("window.__drawn.tiles")))

            # 설정 화면에서 키 저장
            page.click("#open-settings")
            page.fill("#set-vworld-key", "  TESTKEY-ABCD-1234 ")
            page.click("#save-settings"); page.wait_for_timeout(200)
            check(f"{tag}: 키 저장 후 브이월드 위성지도 (앞뒤 공백 제거)",
                  any("/TESTKEY-ABCD-1234/Satellite" in t for t in page.evaluate("window.__drawn.tiles")))

            # 키 점검: 주소 검색만 막힌 경우
            page.click("#open-settings")
            info = page.inner_text("#platform-info")
            check(f"{tag}: 설정에 가린 키 표시", "TEST…1234 (17자, 설정 화면)" in info and "ABCD" not in info)
            scenario.update(addr_error="INVALID_KEY")
            page.click("#check-keys"); page.wait_for_function("!document.querySelector('#check-keys').disabled", timeout=5000)
            items = page.locator("#key-check li")
            check(f"{tag}: 키 점검 - 주소 검색 실패 표시",
                  items.count() == 4 and "INVALID_KEY" in items.nth(0).inner_text() and "fail" in items.nth(0).get_attribute("class"))
            check(f"{tag}: 키 점검 - 필지 조회 정상 표시", "정상 (필지 1개)" in items.nth(1).inner_text())
            page.screenshot(path=str(OUT / f"ui_{tag}_keycheck.png"))
            scenario.update(addr_error=None)
            page.click("#check-keys"); page.wait_for_function("!document.querySelector('#check-keys').disabled", timeout=5000)
            check(f"{tag}: 키 점검 - 넷 다 정상", page.locator("#key-check li.ok").count() == 4)
            check(f"{tag}: 키 점검 - 용도지역·토지이용계획", "정상 (일반상업지역)" in page.inner_text("#key-check")
                  and "정상 (항목 3개)" in page.inner_text("#key-check"))
            page.click("#settings button[value=cancel]"); page.wait_for_timeout(100)

            # 위경도 분석
            scenario.update(parcels=[feat()], error=None)
            page.click("#run"); page.wait_for_selector(".badge", timeout=5000)
            txt = page.inner_text("#panel")
            check(f"{tag}: 위경도 → 확정", "연결 확신도: 확정" in txt)
            check(f"{tag}: 주소·면적·공시지가 표시", "서노송동" in txt and "㎡" in txt and "1,520,000 원/㎡" in txt)
            heads = page.locator("#panel table.props th").all_inner_texts()
            check(f"{tag}: 속성표 순서 (주소 → 지번 → 지목 … PNU)",
                  heads[:3] == ["지번 주소", "지번", "지목"] and heads[-1] == "필지고유번호(PNU)")
            check(f"{tag}: 지목·공시 기준 표시", "대" in txt and "2025년 1월" in txt and "(지목: 대)" in txt)
            check(f"{tag}: 이력서 9단계", page.locator("#panel table.log tbody tr").count() == 9)
            check(f"{tag}: 용도지역 표시 (두 자료 일치)", "일반상업지역" in page.inner_text(".zone-chip")
                  and "일치" in page.inner_text(".zone-head"))
            lim = page.inner_text("table.limits")
            check(f"{tag}: 전주시 조례 용적률 900% · 법정 1300% · 건폐율 80%",
                  "900% (법정 상한 1300%)" in lim and "80%" in lim and "전주시 도시계획 조례" in lim)
            check(f"{tag}: 최대 건축면적·연면적", "최대 건축면적" in lim and "최대 연면적" in lim)
            check(f"{tag}: 지구·구역 목록", "방화지구" in txt and "대공방어협조구역" in txt)
            check(f"{tag}: 지도에 필지 경계 + 용도지역 경계", len(page.evaluate("window.__drawn.geojson")) == 2)
            page.screenshot(path=str(OUT / f"ui_{tag}_result.png"), full_page=True)

            # 토지이용계획 실패 → 레이어 값만으로 계속
            scenario.update(plan_error="INCORRECT_KEY")
            page.click("#run"); page.wait_for_timeout(600)
            t2 = page.inner_text("#panel")
            check(f"{tag}: 토지이용계획 실패해도 용도지역 표시", "용도지역도 값만 확인" in t2 and "확신도: 확정" in t2)
            check(f"{tag}: 실패 이유는 이력서에", "INCORRECT_KEY" in page.inner_text("table.log"))
            scenario.update(plan_error=None, zone=None)
            page.click("#run"); page.wait_for_timeout(500)
            check(f"{tag}: 레이어 없으면 토지이용계획 값", "토지이용계획 값만 확인" in page.inner_text("#panel"))
            scenario.update(zone="일반상업지역")

            # 주소 분석
            page.click("[data-mode=address].tab")
            page.fill("#address", "전주시 완산구 노송광장로 10")
            page.click("#run"); page.wait_for_timeout(500)
            check(f"{tag}: 주소 → 결과", "연결 확신도" in page.inner_text("#panel"))

            # 후보 여럿 → 선택
            scenario.update(parcels=[feat(), feat(addr="다른 후보 필지", pnu="5211113200105690000")])
            page.click("[data-mode=coord].tab"); page.click("#run"); page.wait_for_timeout(500)
            check(f"{tag}: 후보 여럿 안내", "후보 필지가 여러 개" in page.inner_text("#panel"))
            page.click("text=다른 후보 필지"); page.wait_for_timeout(500)
            check(f"{tag}: 선택한 후보로 분석", "다른 후보 필지" in page.inner_text("#panel h2"))

            # 필지 없음, 오류, 지역 밖
            scenario.update(parcels=[])
            page.click("#run"); page.wait_for_timeout(400)
            check(f"{tag}: 필지 없음 안내", "찾지 못했습니다" in page.inner_text("#panel"))
            scenario.update(error="INCORRECT_KEY")
            page.click("#run"); page.wait_for_timeout(400)
            check(f"{tag}: 브이월드 오류 표시", "INCORRECT_KEY" in page.inner_text("#panel"))
            check(f"{tag}: 키 오류 해결 안내", "등록 서비스 URL" in page.inner_text("#panel"))
            page.screenshot(path=str(OUT / f"ui_{tag}_keyerror.png"))
            scenario.update(error=None, parcels=[feat()])
            page.fill("#lat", "37.5665"); page.fill("#lon", "126.978")
            page.click("#run"); page.wait_for_timeout(400)
            check(f"{tag}: 지역 밖 안내", "범위 밖" in page.inner_text("#panel"))

            # 지도 클릭
            page.click("[data-mode=click].tab")
            check(f"{tag}: 지도 클릭 모드에서 분석 버튼 숨김", not page.is_visible("#run"))
            page.evaluate("window.__mapClick(35.8242, 127.148)"); page.wait_for_timeout(500)
            check(f"{tag}: 지도 클릭 → 결과", "연결 확신도" in page.inner_text("#panel"))

            # 잘못된 숫자
            page.click("[data-mode=coord].tab"); page.fill("#lat", "abc"); page.click("#run"); page.wait_for_timeout(200)
            check(f"{tag}: 숫자 아닌 입력 안내", "숫자로" in page.inner_text("#panel"))

            check(f"{tag}: 가로로 넘치지 않음", page.evaluate("document.documentElement.scrollWidth") <= width)
            check(f"{tag}: 자바스크립트 오류 없음", not errors)
            if errors:
                print("JS 오류:", errors)
            ctx.close()
        b.close()
    srv.shutdown()
    for name, ok in results:
        print(("통과 " if ok else "실패 ") + name)
    print(f"\n{sum(ok for _, ok in results)}/{len(results)} 통과")
    return 0 if all(ok for _, ok in results) else 1

if __name__ == "__main__":
    sys.exit(main())
