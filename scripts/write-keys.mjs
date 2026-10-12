// 빌드할 때 GitHub Secrets 의 키를 app/js/keys.js 에 넣습니다. 저장소의 파일에는 키를 쓰지 않습니다.
import { writeFileSync } from "node:fs";

const keys = {
  VWORLD_KEY: process.env.VWORLD_KEY || "",
  VWORLD_DOMAIN: process.env.VWORLD_DOMAIN || "",
};
writeFileSync("app/js/keys.js",
  "// 빌드 때 자동 생성된 파일입니다.\nexport const BUILD_KEYS = " + JSON.stringify(keys, null, 2) + ";\n");
console.log("키 파일 생성:", Object.entries(keys).map(([k, v]) => `${k}=${v ? "있음" : "비어 있음"}`).join(", "));
