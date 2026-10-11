import unittest

from landai import pnu

DONG = "5211110100"          # 예시 법정동코드 (전주시 완산구, 실제 코드 아님)
OK = DONG + "1" + "0012" + "0003"


class TestPnu(unittest.TestCase):
    def test_ok_19(self):
        r = pnu.standardize(OK)
        self.assertEqual((r.status, r.pnu), ("ok", OK))

    def test_float_text_and_dashes(self):
        self.assertEqual(pnu.standardize(OK + ".0").pnu, OK)
        self.assertEqual(pnu.standardize("52111-10100-1-0012-0003").pnu, OK)

    def test_legacy_sido_recoded(self):
        legacy = "45" + OK[2:]
        r = pnu.standardize(legacy, legacy_sido="45", current_sido="52")
        self.assertEqual((r.status, r.pnu, r.rule), ("recoded", OK, "STD-SIDO-01"))

    def test_18_missing_sangu_with_jibun(self):
        broken = DONG + "0012" + "0003"            # 산구분이 빠진 18자리
        r = pnu.standardize(broken, jibun_text="효자동1가 12-3")
        self.assertEqual((r.status, r.pnu), ("restored", OK))

    def test_18_mountain_with_jibun(self):
        broken = DONG + "0012" + "0003"
        r = pnu.standardize(broken, jibun_text="산 12-3")
        self.assertEqual(r.pnu, DONG + "2" + "0012" + "0003")

    def test_18_ambiguous_without_hint(self):
        r = pnu.standardize(DONG + "0012" + "0003")
        self.assertEqual(r.status, "ambiguous")
        self.assertIn(OK, r.candidates)

    def test_18_resolved_by_cadastral(self):
        r = pnu.standardize(DONG + "0012" + "0003", known_pnus={OK})
        self.assertEqual((r.status, r.pnu), ("restored", OK))

    def test_18_legacy_and_broken(self):
        broken = "45" + DONG[2:] + "0012" + "0003"
        r = pnu.standardize(broken, legacy_sido="45", current_sido="52", known_pnus={OK})
        self.assertEqual(r.pnu, OK)

    def test_sci_notation(self):
        r = pnu.standardize("5.21111E+18")
        self.assertEqual((r.status, r.rule), ("sci_notation", "STD-PNU-03"))

    def test_invalid_and_empty(self):
        self.assertEqual(pnu.standardize("12345").status, "invalid")
        self.assertEqual(pnu.standardize("").status, "empty")
        self.assertEqual(pnu.standardize(None).status, "empty")
        # 산구분 3 은 존재하지 않음
        self.assertEqual(pnu.standardize(DONG + "3" + "0012" + "0003").status, "invalid")

    def test_parse_jibun(self):
        self.assertEqual(pnu.parse_jibun("산 12-3"), ("2", "0012", "0003"))
        self.assertEqual(pnu.parse_jibun("123"), ("1", "0123", "0000"))
        self.assertIsNone(pnu.parse_jibun(None))


if __name__ == "__main__":
    unittest.main()
