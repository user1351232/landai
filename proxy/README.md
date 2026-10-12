# landai 서울 중계 서버

브이월드는 해외 IP 요청을 막기 때문에, 해외에 있는 Streamlit Cloud 대신
서울 지역(icn1)의 Vercel 함수가 요청을 대신 보내고 결과만 돌려줍니다.

- 주소: `https://<프로젝트>.vercel.app/api/relay`
- 점검: `https://<프로젝트>.vercel.app/api/relay?_target=ping`
- 보호: 요청 헤더 `X-Proxy-Token` 이 Vercel 환경변수 `PROXY_TOKEN` 과 같아야 전달합니다.
- 요청은 POST 본문(JSON)으로 받아서, 키가 접속 기록(URL)에 남지 않습니다.
- 전달 대상은 아래로만 제한됩니다 (아무 주소나 대신 부르는 서버가 되지 않게).
  - 브이월드 data, address, search
  - 도로명주소 검색 API
  - 공공데이터포털 apis.data.go.kr (기관코드/서비스 경로만)
- 키는 이 서버에 저장하지 않습니다. 앱이 보낸 키를 그대로 전달만 합니다.
