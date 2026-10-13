//! 윈도우 앱 본체.
//! 브이월드 같은 국내 공공 API 는 브라우저(웹뷰)에서 직접 부르면 막힐 수 있어서,
//! 이 컴퓨터의 Rust 코드가 대신 호출하고 결과 글자만 화면에 돌려줍니다.
//! 요청은 사용자 컴퓨터(국내)에서 바로 나가며 해외 서버를 거치지 않습니다.
//! 아무 주소나 부르지 못하도록 허용된 주소만 호출합니다.

use std::collections::HashMap;
use std::time::Duration;

fn base_url(target: &str, path: Option<&str>) -> Result<String, String> {
    match target {
        "vworld_data" => Ok("https://api.vworld.kr/req/data".into()),
        "vworld_address" => Ok("https://api.vworld.kr/req/address".into()),
        "vworld_search" => Ok("https://api.vworld.kr/req/search".into()),
        "juso" => Ok("https://business.juso.go.kr/addrlink/addrLinkApi.do".into()),
        // 브이월드 국가중점 API: 정해진 기능 이름만
        "vworld_ned" => match path {
            Some(op @ ("getLandUseAttr" | "ladfrlList" | "getLandCharacteristics" | "getIndvdLandPriceAttr")) => {
                Ok(format!("https://api.vworld.kr/ned/data/{op}"))
            }
            other => Err(format!("허용되지 않은 국가중점 기능: {}", other.unwrap_or(""))),
        },
        "datagokr" => {
            let p = path.ok_or_else(|| "공공데이터포털 경로가 없습니다".to_string())?;
            let ok = !p.is_empty()
                && p.len() <= 120
                && !p.starts_with('/')
                && !p.contains("//")
                && p.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '/');
            if ok {
                Ok(format!("https://apis.data.go.kr/{p}"))
            } else {
                Err(format!("허용되지 않은 경로: {p}"))
            }
        }
        other => Err(format!("허용되지 않은 대상: {other}")),
    }
}

#[tauri::command]
async fn http_get(
    target: String,
    params: HashMap<String, String>,
    path: Option<String>,
) -> Result<String, String> {
    let url = base_url(&target, path.as_deref())?;
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .user_agent("landai-app/0.7")
        .build()
        .map_err(|e| e.to_string())?;
    let resp = client
        .get(&url)
        .query(&params)
        .send()
        .await
        .map_err(|e| format!("접속 실패: {e}"))?;
    let status = resp.status();
    let text = resp
        .text()
        .await
        .map_err(|e| format!("응답 읽기 실패: {e}"))?;
    if !status.is_success() {
        let head: String = text.chars().take(200).collect();
        return Err(format!("HTTP {}: {}", status.as_u16(), head));
    }
    Ok(text)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![http_get])
        .run(tauri::generate_context!())
        .expect("앱을 시작하지 못했습니다");
}

#[cfg(test)]
mod tests {
    use super::base_url;

    #[test]
    fn allowed_targets_only() {
        assert!(base_url("vworld_data", None).is_ok());
        assert!(base_url("https://evil.example", None).is_err());
        assert!(base_url("datagokr", Some("../etc")).is_err());
        assert!(base_url("datagokr", Some("1613000/arLandUseInfoService/DTarLandUseInfo")).is_ok());
        assert_eq!(
            base_url("vworld_ned", Some("getLandUseAttr")).unwrap(),
            "https://api.vworld.kr/ned/data/getLandUseAttr"
        );
        assert!(base_url("vworld_ned", Some("../req/data")).is_err());
        assert!(base_url("vworld_ned", None).is_err());
    }
}
