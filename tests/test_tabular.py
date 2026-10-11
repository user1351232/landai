import tempfile
import unittest
from pathlib import Path

from landai.ingest.tabular import check_table, read_table
from landai.profile import DataProfile

REGION = {"id": "test", "sido_code": "52", "legacy_sido_code": "45"}
DONG = "5211110100"


def make_csv(path: Path, broken: int = 13) -> None:
    lines = ["허가번호,PNU,허가일자,면적"]
    years = [2018, 2019, 2021, 2022]           # 2020 년 공백
    for i in range(40):
        y = years[i % len(years)]
        lines.append(f"P{i},{DONG}1{i + 1:04d}0000,{y}-03-0{i % 9 + 1},{100 + i}")
    lines.append(f"P40,{DONG}{41:04d}0000,2022-05-01,100")           # 18자리
    lines.append("P41,5.21111E+18,2022-05-01,100")                     # 지수 표기
    lines.append(f"P42,45{DONG[2:]}1{42:04d}0000,2019-05-01,100")       # 옛 시도코드
    for i in range(broken):
        lines.append(f"B{i},{DONG}1{i + 1:04d}0000,2019-01-01,100,쉼표가,더 있음")
    path.write_text("\n".join(lines) + "\n", encoding="cp949")


class TestTabular(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "permits.csv"
        make_csv(self.csv)

    def test_read_keeps_text_and_quarantines(self):
        t = read_table(self.csv)
        self.assertEqual(t.encoding, "cp949")
        self.assertEqual(len(t.quarantine), 13)
        self.assertEqual(len(t.df), 43)
        self.assertTrue(t.df["PNU"].iloc[0].startswith("52"))

    def test_check_table_rules(self):
        manifest = {"expected_columns": ["허가번호", "PNU", "허가일자"],
                    "pnu_column": "auto", "year_column": "auto"}
        prof = DataProfile("permits", "test")
        check_table(self.csv, manifest, REGION, prof, self.tmp / "q")
        by_rule = {c.rule: c for c in prof.checks}

        self.assertEqual(by_rule["INGEST-ROW-01"].details["count"], 13)
        self.assertEqual(by_rule["INGEST-COL-01"].status, "pass")
        self.assertEqual(by_rule["DATA-01"].details["missing"], [2020])

        counts = by_rule["INGEST-PNU-01"].details["counts"]
        self.assertEqual(counts["ok"], 40)
        self.assertEqual(counts["recoded"], 1)
        self.assertEqual(counts["sci_notation"], 1)
        self.assertEqual(counts["ambiguous"], 1)
        self.assertEqual(by_rule["INGEST-PNU-01"].status, "fail")   # 지수 표기는 복구 불가
        self.assertIn("STD-SIDO-01", by_rule)
        self.assertTrue((self.tmp / "q" / "test_permits_broken_rows.csv").exists())
        self.assertEqual(prof.status, "fail")

    def test_missing_column_fails(self):
        manifest = {"expected_columns": ["없는컬럼"], "pnu_column": None, "year_column": None}
        prof = DataProfile("permits", "test")
        check_table(self.csv, manifest, REGION, prof, self.tmp / "q")
        self.assertEqual(prof.status, "fail")


if __name__ == "__main__":
    unittest.main()
