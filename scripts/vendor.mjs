// node_modules 의 지도 라이브러리(Leaflet)를 app/vendor 로 복사합니다 (앱 빌드 전에 실행)
import { cpSync, mkdirSync, existsSync } from "node:fs";

const src = "node_modules/leaflet/dist";
const dst = "app/vendor/leaflet";
if (!existsSync(src)) {
  console.error("leaflet 이 설치되지 않았습니다. 먼저 npm install 을 실행하세요.");
  process.exit(1);
}
mkdirSync(dst, { recursive: true });
for (const f of ["leaflet.js", "leaflet.css"]) cpSync(`${src}/${f}`, `${dst}/${f}`);
cpSync(`${src}/images`, `${dst}/images`, { recursive: true });
console.log("Leaflet 복사 완료 →", dst);
