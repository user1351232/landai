"""수신 검사 실행기.

사용법 (프로젝트 폴더에서)
    python -m landai.ingest.run --region jeonju --dataset permits
    python -m landai.ingest.run --region jeonju --all

결과
    profiles/<지역>_<자료>.json      자료 프로필 (이후 단계가 참조)
    staging/quarantine/*.csv          격리된 깨진 줄, 문제 있는 필지번호
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from landai.config import ROOT, load_manifest, load_region
from landai.profile import DataProfile, sha256

DATASETS = ["dong_code", "cadastral", "permits", "dem", "topo5000"]


def find_files(manifest: dict) -> list[Path]:
    folder = ROOT / manifest["folder"]
    files: list[Path] = []
    for pat in manifest.get("patterns", ["*"]):
        files += sorted(folder.glob(pat))
    return [f for f in dict.fromkeys(files) if f.is_file() and f.name != ".gitkeep"]


def load_dong_codes() -> set[str] | None:
    """raw/dong_code 의 법정동 대조표에서 10자리 코드 집합을 만듭니다."""
    from landai.ingest.tabular import read_table
    files = find_files(load_manifest("dong_code"))
    if not files:
        return None
    t = read_table(files[0])
    for col in t.df.columns:
        vals = t.df[col].dropna().astype(str).str.strip()
        if len(vals) and vals.str.fullmatch(r"\d{10}").mean() > 0.9:
            return set(vals)
    return None


def run_dataset(dataset: str, region: dict, files_override: list[Path] | None = None) -> list[DataProfile]:
    manifest = load_manifest(dataset)
    files = files_override or find_files(manifest)
    profiles_dir = ROOT / "profiles"
    qdir = ROOT / "staging" / "quarantine"
    if not files:
        print(f"[{dataset}] 파일 없음: {manifest['folder']} 에 {manifest.get('patterns')} 형식 파일을 넣으세요")
        return []

    out = []
    for f in files:
        name = dataset if len(files) == 1 else f"{dataset}__{re.sub(r'\W+', '_', f.stem)}"
        profile = DataProfile(dataset=name, region=region["id"])
        profile.files.append({"path": str(f.relative_to(ROOT)), "sha256": sha256(f),
                              "bytes": f.stat().st_size})
        kind = manifest["kind"]
        try:
            if kind == "table":
                from landai.ingest.tabular import check_table
                dong = load_dong_codes() if dataset != "dong_code" else None
                check_table(f, manifest, region, profile, qdir, dong_codes=dong)
            elif kind == "vector":
                from landai.ingest.spatial import check_vector
                from landai.ingest.tabular import PNU_NAME_RE, check_pnu_series, find_column
                gdf, _ = check_vector(f, manifest, region, profile)
                col = find_column(list(gdf.columns), manifest.get("pnu_column"), PNU_NAME_RE)
                if col:
                    check_pnu_series(gdf[col], region, profile, qdir,
                                     dong_codes=load_dong_codes())
            elif kind == "raster":
                from landai.ingest.spatial import check_raster
                check_raster(f, manifest, region, profile)
            elif kind == "topo":
                profile.add("INGEST-TOPO-00", "pass",
                            "도엽 파일 수신 확인 (등고선 추출과 DEM 생성은 3-1단계에서)")
            else:
                profile.add("INGEST-KIND", "fail", f"알 수 없는 자료 종류: {kind}")
        except ImportError as e:
            profile.add("ENV-01", "fail", f"필요한 라이브러리 없음: {e.name}. "
                        "pip install -r requirements.txt 를 실행하세요")
        except Exception as e:  # 검사 자체가 실패해도 프로필은 남김
            profile.add("INGEST-ERR", "fail", f"검사 중 오류: {type(e).__name__}: {e}")

        path = profile.save(profiles_dir)
        print(profile.summary())
        print(f"  → 프로필 저장: {path.relative_to(ROOT)}\n")
        out.append(profile)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="자료 수신 검사")
    ap.add_argument("--region", default="jeonju")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dataset", choices=DATASETS)
    g.add_argument("--all", action="store_true")
    ap.add_argument("--file", type=Path, help="특정 파일만 검사")
    args = ap.parse_args(argv)

    region = load_region(args.region)
    targets = DATASETS if args.all else [args.dataset]
    results = []
    for ds in targets:
        results += run_dataset(ds, region, [args.file.resolve()] if args.file else None)
    return 1 if any(p.status == "fail" for p in results) else 0


if __name__ == "__main__":
    sys.exit(main())
