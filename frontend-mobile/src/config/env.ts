// API base URL 設定。開發階段以模擬器/實機判斷預設值；可由 react-native-config 覆寫。
import { Platform } from 'react-native';

let Config: { API_BASE_URL?: string } = {};
try {
  // 動態載入 react-native-config，避免 jest 環境失敗
  Config = require('react-native-config').default ?? {};
} catch {
  Config = {};
}

// 開發階段 Android 一律走 `localhost:8000`，搭配 `adb reverse tcp:8000 tcp:8000`：
//   - 實機（USB 連線）：reverse 把手機的 8000 透過 USB 轉到電腦的 8000
//   - 模擬器：reverse 也適用；若不想 reverse 可改 `10.0.2.2:8000`
const DEFAULT_DEV_BASE_URL = Platform.select({
  android: 'http://localhost:8000',
  default: 'http://localhost:8000',
});

export const API_BASE_URL: string =
  Config.API_BASE_URL && Config.API_BASE_URL.length > 0
    ? Config.API_BASE_URL
    : DEFAULT_DEV_BASE_URL ?? 'http://localhost:8000';

export const API_PATH_PREFIX = '/api';

export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${API_PATH_PREFIX}${normalized}`;
}
