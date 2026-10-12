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
  return (v && v.trim()) || BUILD_KEYS[name] || "";
}

export function setSetting(name, value) {
  const s = store();
  try { if (s) value ? s.setItem(PREFIX + name, value.trim()) : s.removeItem(PREFIX + name); } catch { /* 무시 */ }
}
