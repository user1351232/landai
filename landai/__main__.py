"""하나로 묶은 실행 명령.

    python -m landai web                    웹 화면 실행 (브라우저가 열립니다)
    python -m landai doctor                 설치·키·자료 상태 점검
    python -m landai keys                   API 키 점검
    python -m landai ingest --all           수신 검사 (기본 지역: 전주시)
    python -m landai ingest --region wanju --dataset permits
    python -m landai test                   테스트 실행
"""

from __future__ import annotations

import sys

HELP = __doc__


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "web":
        import subprocess
        from pathlib import Path
        from landai.config import ROOT
        # Streamlit 이 처음 실행될 때 이메일을 묻고 멈추는 것을 막습니다
        cred = Path.home() / ".streamlit" / "credentials.toml"
        if not cred.exists():
            cred.parent.mkdir(parents=True, exist_ok=True)
            cred.write_text('[general]\nemail = ""\n', encoding="utf-8")
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"), *rest])
    if cmd == "doctor":
        from landai.doctor import main as run
        return run()
    if cmd == "keys":
        from landai.apis.keycheck import main as run
        return run()
    if cmd == "ingest":
        from landai.ingest.run import main as run
        return run(rest)
    if cmd == "test":
        import unittest
        from landai.config import ROOT
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        ok = unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()
        return 0 if ok else 1
    print(f"알 수 없는 명령: {cmd}\n{HELP}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
