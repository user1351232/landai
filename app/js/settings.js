// 키 읽기: 앱 설정 화면에 저장한 값 → 빌드 때 넣은 값 순서
import { BUILD_KEYS } from "./keys.js";

const PREFIX = "landai.";

function store() {
  try { return globalThis.localStorage || null; } catch { return null; }
}

export function getSetting(name) {
  const s = store();
  let v = null;
  try { v = s ? s.getItem(PREFIX + name) : null; } catch { v = null; }
  return (v && v.trim()) || String(BUILD_KEYS[name] || "").trim();
}

export function setSetting(name, value) {
  const s = store();
  try { if (s) value ? s.setItem(PREFIX + name, value.trim()) : s.removeItem(PREFIX + name); } catch { /* 무시 */ }
}

// 키가 어디서 왔는지와 가린 모양 (예: "AB12…9Z (36자, 빌드)"). 키 전체는 화면에 보이지 않습니다.
export function describeKey(name) {
  const s = store();
  let local = "";
  try { local = (s && s.getItem(PREFIX + name)) || ""; } catch { local = ""; }
  const raw = local.trim() ? local : String(BUILD_KEYS[name] || "");
  const key = raw.trim();
  if (!key) return "없음";
  const source = local.trim() ? "설정 화면" : "빌드";
  const masked = key.length > 8 ? `${key.slice(0, 4)}…${key.slice(-4)}` : "****";
  return `${masked} (${key.length}자, ${source})`;
}
