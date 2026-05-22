# 智慧災害通報 — Android App（民眾端）

行動裝置原生 App，與 `frontend-public/`（網頁版）並存。差異點：
- 啟動時透過 **Google Phone Number Hint API** 自動帶入電話號碼，不再依賴 LLM 從對話中擷取
- 啟動時請求 GPS 位置權限，把座標傳給後端輔助地點推測
- 原生相機 / 相簿選擇器、Google Maps 顯示災情標記

## 技術棧

- React Native 0.85.3（CLI bare workflow）
- TypeScript 5.8
- React Navigation 7（Bottom Tabs）
- react-native-sse（後端 SSE 對話串流）
- react-native-maps（Google Maps）
- react-native-image-picker / -geolocation-service
- zustand（全域狀態 sessionStore）
- 自寫 Kotlin 原生模組整合 `play-services-auth:21.2.0` 的 Phone Number Hint API

## 必備開發環境

> ⚠️ 本資料夾 **僅支援 Android**。iOS 因 Apple 平台不允許 App 讀取使用者電話，未納入支援。

| 工具 | 版本 |
|---|---|
| Node.js | ≥ 22.11 |
| Java JDK | 17 (Temurin 建議) |
| Android Studio | 最新穩定版（內含 Android SDK 35+） |
| Android SDK Platform | 35+ |
| Android Emulator | 帶 Google APIs 的鏡像（如 Pixel API 33+） |

設定環境變數：
- `ANDROID_HOME` 指向 Android SDK 路徑
- `JAVA_HOME` 指向 JDK 17

## 安裝

```bash
cd frontend-mobile
npm install
```

## 設定 Google Maps API Key

於 `frontend-mobile/android/local.properties` 加入（**不要 commit 此檔**）：

```properties
GOOGLE_MAPS_API_KEY=AIza...
```

可重用根目錄 `.env` 內既有的 `GOOGLE_MAPS_API_KEY`。

## 設定 API Base URL（連後端）

預設情境（Android 模擬器連本機 8000）已內建，無需設定。
若連實機或遠端後端，建立 `frontend-mobile/.env`：

```
API_BASE_URL=http://192.168.1.x:8000
```

並重新啟動 Metro。

## 開發執行

```bash
# Terminal 1：啟動 Metro
npm start

# Terminal 2：啟動模擬器或連接實機後 build & install debug APK
npm run android
```

## 測試

```bash
npm test                # Jest 單元 / 整合測試
npm run test:coverage   # 含覆蓋率報告
npm run typecheck       # tsc --noEmit
```

目前覆蓋：
- Phone Number Hint TS 橋接（4 案例）
- sessionStore zustand 全域狀態（4 案例）
- env / apiUrl URL 組裝（2 案例）
- chatClient SSE 訊息分派與 verified_phone 注入（5 案例）
- App.tsx 根元件可渲染（1 案例）

## Release APK 打包

### 1. 產生 keystore（首次）

```bash
keytool -genkeypair -v \
  -storetype PKCS12 \
  -keystore frontend-mobile/android/app/release.keystore \
  -alias disaster-report-key \
  -keyalg RSA -keysize 2048 -validity 10000
```

> 妥善保管產出的 `release.keystore` 與密碼；遺失即無法簽署同一 App 的後續版本。

### 2. 配置簽署資訊

於 `frontend-mobile/android/gradle.properties` 加入（或放在 `~/.gradle/gradle.properties` 全域）：

```properties
MYAPP_RELEASE_STORE_FILE=release.keystore
MYAPP_RELEASE_KEY_ALIAS=disaster-report-key
MYAPP_RELEASE_STORE_PASSWORD=********
MYAPP_RELEASE_KEY_PASSWORD=********
```

於 `android/app/build.gradle` 的 `signingConfigs` 內新增 `release { ... }`，並把 `buildTypes.release.signingConfig` 改為它。範例：

```gradle
signingConfigs {
    debug { /* 略 */ }
    release {
        if (project.hasProperty('MYAPP_RELEASE_STORE_FILE')) {
            storeFile file(MYAPP_RELEASE_STORE_FILE)
            storePassword MYAPP_RELEASE_STORE_PASSWORD
            keyAlias MYAPP_RELEASE_KEY_ALIAS
            keyPassword MYAPP_RELEASE_KEY_PASSWORD
        }
    }
}
buildTypes {
    release {
        signingConfig signingConfigs.release
        minifyEnabled enableProguardInReleaseBuilds
        proguardFiles getDefaultProguardFile("proguard-android.txt"), "proguard-rules.pro"
    }
}
```

### 3. Build APK

```bash
cd frontend-mobile/android
./gradlew assembleRelease
```

產出檔：`frontend-mobile/android/app/build/outputs/apk/release/app-release.apk`。

### 4. Sideload 安裝

連接實機並啟用 USB 偵錯後：

```bash
adb install -r app-release.apk
```

或直接把 APK 傳給使用者，於 Android 設定中允許「未知來源安裝」後點擊安裝。

## 與後端 / 網頁端的協作

- 後端 `POST /api/chat` 已支援 `verified_phone` 與 `device_location` 兩個選填欄位；App 在每次送出對話時自動帶入
- LLM system prompt 收到 `verified_phone` 時會被指示「不要再向使用者詢問電話」並直接使用該號碼
- 後端在處理 `submit_disaster_report` tool call 時，若 App 提供了 `verified_phone`，會 **覆寫 LLM 填入的 reporter_phone**，確保最終存進 `disaster_reports.reporter_phone` 的是裝置驗證的電話
- `frontend-public/`（網頁版）完全保持原樣，繼續以 LLM 對話擷取電話

## 目錄結構

```
frontend-mobile/
├── android/                              # 原生 Android 工程
│   └── app/src/main/
│       ├── java/com/disasterreportmobile/
│       │   ├── MainApplication.kt        # 已註冊 PhoneNumberHintPackage
│       │   └── phonehint/
│       │       ├── PhoneNumberHintModule.kt
│       │       └── PhoneNumberHintPackage.kt
│       ├── res/xml/network_security_config.xml
│       └── AndroidManifest.xml           # INTERNET / FINE_LOCATION / CAMERA 權限
├── src/
│   ├── api/                              # chatClient / eventsClient / uploadClient
│   ├── components/chat/                  # RN 版本對話 UI
│   ├── config/env.ts                     # API_BASE_URL 切換
│   ├── hooks/                            # usePhoneNumberHint / useGeolocation / useSSEChat
│   ├── native/PhoneNumberHint.ts         # 原生模組 TS 橋接
│   ├── screens/                          # SplashScreen / ChatScreen / MapScreen
│   ├── stores/sessionStore.ts            # zustand 全域狀態
│   └── types/                            # 與 frontend-public 對齊的型別
├── __tests__/                            # Jest 單元測試
└── App.tsx                               # 入口（Splash → Bottom Tabs）
```

## 已知限制 / 後續

- **iOS 不支援**：Apple 不允許 App 讀取本機電話號碼，未來若需 iOS 版可考慮 SMS OTP 驗證流程
- 模擬器無法測 Phone Hint：需用 Google APIs 鏡像的模擬器（如 Pixel API 33）並先在系統設定中加一支 SIM 號碼
- Release build 預設仍允許 cleartext HTTP（為了開發階段連本機）。正式上架前應改 `network_security_config.xml` 為僅允許 HTTPS
