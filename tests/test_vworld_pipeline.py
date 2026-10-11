import importlib.util
import os
import unittest
from unittest import mock

from landai import pipeline
from landai.apis import vworld

REGION = {"id": "jeonju", "name": "전주시", "sido_code": "52", "legacy_sido_code": "45",
          "bbox_wgs84": [126.98, 35.72, 127.25, 35.93]}
LON, LAT = 127.1480, 35.8242
SQUARE = {"type": "Polygon", "coordinates": [[[127.1479, 35.8241], [127.1481, 35.8241],
                                              [127.1481, 35.8243], [127.1479, 35.8243],
                                              [127.1479, 35.8241]]]}
HAS_SHAPELY = importlib.util.find_spec("shapely") and importlib.util.find_spec("pyproj")


def feature(pnu="5211110100100120003", addr="전북특별자치도 전주시 완산구 예시동 12-3"):
    return {"type": "Feature", "geometry": SQUARE,
            "properties": {"pnu": pnu, "addr": addr, "jiga": "1234000"}}


class FakeResp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@mock.patch.dict(os.environ, {"VWORLD_KEY": "test-key", "VWORLD_DOMAIN": "http://localhost"})
class TestVworld(unittest.TestCase):
    def test_geocode_road(self):
        body = {"response": {"status": "OK", "refined": {"text": "정제된 주소"},
                             "result": {"point": {"x": "127.1", "y": "35.8"}}}}
        with mock.patch("requests.get", return_value=FakeResp(body)) as g:
            r = vworld.geocode("전주시청")
        self.assertEqual((r["lon"], r["lat"], r["type"]), (127.1, 35.8, "도로명"))
        self.assertEqual(g.call_args.kwargs["params"]["domain"], "http://localhost")

    def test_geocode_falls_back_to_parcel(self):
        bodies = [{"response": {"status": "NOT_FOUND"}},
                  {"response": {"status": "OK", "result": {"point": {"x": "1", "y": "2"}}}}]
        with mock.patch("requests.get", side_effect=[FakeResp(b) for b in bodies]):
            r = vworld.geocode("완산구 효자동 12")
        self.assertEqual(r["type"], "지번")

    def test_parcels_ok_and_not_found(self):
        ok = {"response": {"status": "OK", "result": {"featureCollection": {
            "features": [feature()]}}}}
        with mock.patch("requests.get", return_value=FakeResp(ok)):
            self.assertEqual(len(vworld.parcels_at(LON, LAT)), 1)
        with mock.patch("requests.get", return_value=FakeResp({"response": {"status": "NOT_FOUND"}})):
            self.assertEqual(vworld.parcels_at(LON, LAT), [])

    def test_error_message(self):
        err = {"response": {"status": "ERROR", "error": {"code": "INCORRECT_KEY", "text": "키 오류"}}}
        with mock.patch("requests.get", return_value=FakeResp(err)):
            with self.assertRaises(vworld.VworldError) as cm:
                vworld.parcels_at(LON, LAT)
        self.assertIn("INCORRECT_KEY", str(cm.exception))

    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"VWORLD_KEY": ""}):
            with mock.patch("landai.config.load_env"):
                with self.assertRaises(vworld.VworldError):
                    vworld.parcels_at(LON, LAT)

    def test_tile_url(self):
        self.assertTrue(vworld.tile_url("K", "Satellite").endswith("/K/Satellite/{z}/{y}/{x}.jpeg"))


class TestPipeline(unittest.TestCase):
    def test_outside_region(self):
        r = pipeline.analyze(126.5, 37.5, REGION, fetch=lambda *_: [feature()])
        self.assertEqual(r["status"], "outside")

    def test_no_parcel(self):
        r = pipeline.analyze(LON, LAT, REGION, fetch=lambda *_: [])
        self.assertEqual((r["status"], r["grade"]), ("no_parcel", "미연결"))

    def test_multiple_needs_choice(self):
        two = [feature(), feature(addr="다른 필지")]
        r = pipeline.analyze(LON, LAT, REGION, fetch=lambda *_: two)
        self.assertEqual(r["status"], "multiple")
        r = pipeline.analyze(LON, LAT, REGION, fetch=lambda *_: two, choice=1)
        self.assertEqual(r["parcel"]["properties"]["addr"], "다른 필지")

    def test_ok_parcel(self):
        r = pipeline.analyze(LON, LAT, REGION, fetch=lambda *_: [feature()])
        self.assertEqual((r["status"], r["grade"]), ("ok", "확정"))
        self.assertEqual(r["pnu"]["status"], "ok")
        self.assertEqual([s["단계"] for s in r["log"]][:3], ["위치 확인", "필지 조회", "필지번호 검사"])
        if HAS_SHAPELY:
            self.assertGreater(r["area_m2"], 0)

    def test_legacy_pnu_recoded(self):
        r = pipeline.analyze(LON, LAT, REGION, fetch=lambda *_: [feature(pnu="4511110100100120003")])
        self.assertEqual(r["pnu"]["pnu"], "5211110100100120003")

    def test_fetch_error(self):
        def boom(*_):
            raise vworld.VworldError("브이월드 접속 실패")
        r = pipeline.analyze(LON, LAT, REGION, fetch=boom)
        self.assertEqual(r["status"], "error")


if __name__ == "__main__":
    unittest.main()
