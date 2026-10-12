# 웹에 올리기 (링크로 접속하는 화면 만들기)

순서: GitHub 에 코드 올리기 → Streamlit Cloud 에 연결 → 키 입력 → 링크 완성 → 브이월드 주소 맞추기 → 서울 중계 서버(Vercel) 연결

## 1. GitHub 에 코드 올리기

1. https://github.com 에 로그인합니다.
2. 오른쪽 위 **+** → **New repository** 를 누릅니다.
3. 아래처럼 정하고 **Create repository** 를 누릅니다.
   - Repository name: `landai`
   - **Public** 선택 (코드에 키가 없으니 공개해도 됩니다. 숨기고 싶으면 Private 도 됩니다)
   - "Add a README file" 은 체크하지 않습니다
4. 다음 화면에서 **uploading an existing file** 링크를 누릅니다.
5. 압축을 푼 `landai` 폴더를 열고, **그 안의 파일과 폴더를 모두 선택**(Ctrl + A)해서 브라우저 창으로 끌어다 놓습니다.
   - `landai` 폴더 자체가 아니라 그 **안의 내용물** 을 끌어다 놓습니다
   - `.env` 파일이 있다면 절대 함께 올리지 않습니다
6. 업로드가 끝나면 아래 **Commit changes** 를 누릅니다.
7. 저장소 첫 화면에 `app.py`, `requirements.txt`, `landai` 폴더가 보이면 성공입니다.

## 2. Streamlit Cloud 에 연결

1. https://share.streamlit.io 에 접속해 **Continue with GitHub** 로 로그인하고 권한을 허용합니다.
2. **Create app** → GitHub 저장소에서 배포하는 항목을 고릅니다.
3. 아래처럼 입력합니다.
   - Repository: `user1351232/landai`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: 원하는 이름 (예: `jeonju-land-ai` → `https://jeonju-land-ai.streamlit.app`)
4. **Advanced settings** 를 열어
   - Python version: 3.12 이상 아무거나 (목록의 최신 버전 3.14 권장)
   - Secrets 칸에 아래를 붙여 넣고 키를 채웁니다 (`.streamlit/secrets.toml.example` 과 같은 형식)
     ```
     VWORLD_KEY = "브이월드 키"
     VWORLD_DOMAIN = "http://localhost"
     DATA_GO_KR_KEY = "공공데이터포털 키"
     JUSO_KEY = "도로명주소 키"
     ```
5. **Deploy** 를 누릅니다. 처음에는 몇 분 걸립니다.

## 3. 브이월드 주소 맞추기 (지도와 필지 조회)

브이월드 키는 등록한 서비스 URL 에서만 작동합니다. 링크가 생기면:

1. 브이월드 → 마이포털 → 인증키 관리 → 사용 중인 키의 서비스 URL 을 앱 주소(예: `https://jeonju-land-ai.streamlit.app`)로 바꿉니다. 수정이 안 되면 같은 방법으로 키를 새로 발급합니다.
2. Streamlit Cloud 앱 화면 오른쪽 아래 **Manage app** → **Settings** → **Secrets** 에서 `VWORLD_DOMAIN` 을 같은 주소로 바꾸고 저장합니다. 키를 새로 받았다면 `VWORLD_KEY` 도 바꿉니다.
3. 앱이 자동으로 다시 시작됩니다.

## 4. 코드를 고친 뒤

새 버전 압축 파일을 받으면, GitHub 저장소에서 다시 **Add file → Upload files** 로 내용물을 끌어다 놓고 **Commit changes** 를 누릅니다. 같은 이름의 파일은 새 것으로 덮어쓰이고, 앱은 자동으로 새 버전이 됩니다.

주의: 덮어쓰기는 같은 이름의 파일만 바꿉니다. 새 버전에서 **없어지거나 이름이 바뀐 파일은 GitHub 에 그대로 남습니다.** 그런 파일이 있으면 버전 안내에서 알려 드리니, 저장소에서 그 파일을 열고 휴지통 아이콘으로 지우세요.

## 5. 서울 중계 서버 (Vercel) 연결

브이월드는 해외 IP 요청을 막습니다. Streamlit Cloud 서버는 해외에 있어서 필지 조회가 "접속 실패"로 나옵니다.
그래서 서울 지역(icn1)에서 도는 작은 중계 서버를 Vercel 무료 플랜으로 만듭니다. 코드는 저장소의 `proxy/` 폴더에 있습니다.

1. **중계 비밀번호 만들기**: 영문 대소문자와 숫자를 섞어 30자 이상 아무렇게나 만들어 메모장에 적어 둡니다. (이것이 `PROXY_TOKEN`)
2. https://vercel.com → **Sign Up** → **Hobby** → **Continue with GitHub** 로 가입·로그인합니다.
3. **Add New… → Project** → GitHub 저장소 목록에서 `landai` 옆 **Import** 를 누릅니다.
   - 목록에 없으면 **Adjust GitHub App Permissions** 를 눌러 `landai` 저장소 접근을 허용합니다.
4. 설정 화면에서
   - Project Name: `landai-proxy`
   - Framework Preset: **Other**
   - **Root Directory**: Edit → `proxy` 폴더 선택 (중요)
   - **Environment Variables**: Key `PROXY_TOKEN`, Value 에 1번의 비밀번호 → Add
5. **Deploy** 를 누릅니다. 1분 정도 걸립니다.
6. 완료 화면의 주소(예: `https://landai-proxy.vercel.app`) 뒤에 `/api/relay?_target=ping` 을 붙여 브라우저로 엽니다.
   - `"region": "icn1"`, `"vworld_reachable": true`, `"token_set": true` 가 보이면 성공입니다.
7. Streamlit Cloud → **Manage app → ⋮ → Settings → Secrets** 에 두 줄을 추가하고 Save 합니다.
   ```
   PROXY_URL = "https://landai-proxy.vercel.app"
   PROXY_TOKEN = "1번의 비밀번호"
   ```
8. 앱을 새로고침하면 왼쪽 아래에 "API 호출 경로: 서울 중계 서버" 가 보이고, 필지 조회가 됩니다.

## 알아둘 점

- 12시간 동안 아무도 들어오지 않으면 앱이 잠듭니다. 발표 전날 한 번 열어 두세요. 잠든 화면에서는 깨우기 버튼을 누르면 됩니다.
- 화면에 오류가 나오면 **Manage app** 을 눌러 나오는 기록(로그)을 캡처해서 공유하세요. 키가 보이지 않는지 확인하세요.
