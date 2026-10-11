"""어느 컴퓨터에서든 처음 실행할 때 상태를 한 번에 점검합니다.

    python -m landai doctor
"""

from __future__ import annotations

import importlib
import platform
import sys

from landai.config import ROOT, get_key, load_manifest

REQUIRED = ["pandas", "yaml", "dotenv", "requests"]          # 표 자료 검사
SPATIAL = ["geopandas", "pyogrio", "rasterio"]                     # 원본 자료 검사
WEB = ["streamlit", "folium", "streamlit_folium", "shapely", "pyproj"]  # 웹 화면
KEYS = ["VWORLD_KEY", "DATA_GO_KR_KEY", "JUSO_KEY"]
DATASETS = ["dong_code", "cadastral", "permits", "topo5000", "dem"]


def _has(mod: str) -> str | None:
    try:
        m = importlib.import_module(mod)
        return getattr(m, "__version__", "설치됨")
    except Exception:
        return None


def main() -> int:
    problems = 0
    print(f"운영체제   {platform.system()} {platform.release()}")
    print(f"파이썬     {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 10):
        print("  → 파이썬 3.10 이상이 필요합니다")
        problems += 1
    print(f"프로젝트   {ROOT}\n")

    print("[라이브러리]")
    for group, mods, needed in (("기본", REQUIRED, True), ("웹", WEB, True),
                                ("공간", SPATIAL, False)):
        for mod in mods:
            v = _has(mod)
            note = "" if v or needed else "  (원본 자료 검사할 때만 필요)"
            print(f"  {group}  {mod:<16} {v or '없음'}{note}")
            problems += (v is None) and needed
    print()

    print("[API 키]  (.env 파일)")
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("  .env 파일 없음 → .env.example 을 복사해서 .env 로 만들고 키를 채우세요")
        problems += 1
    for k in KEYS:
        print(f"  {k:<16} {'있음' if get_key(k) else '비어 있음'}")
    print()

    print("[자료]  (raw 폴더)")
    for ds in DATASETS:
        m = load_manifest(ds)
        folder = ROOT / m["folder"]
        n = sum(1 for p in folder.iterdir() if p.is_file() and p.name != ".gitkeep") \
            if folder.exists() else 0
        print(f"  {ds:<10} {m['folder']:<16} 파일 {n}개")
    print()

    if problems:
        print(f"점검 결과: 확인할 항목 {problems}개. 위의 '없음' 항목부터 해결하세요.")
        print("라이브러리가 없으면 설치 스크립트(setup_windows.bat 또는 setup_mac_linux.sh)를 다시 실행하세요.")
        return 1
    print("점검 결과: 준비 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
