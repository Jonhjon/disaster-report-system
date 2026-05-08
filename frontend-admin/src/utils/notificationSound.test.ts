import { describe, expect, it } from "vitest";
import { playNotificationSound } from "./notificationSound";

describe("playNotificationSound", () => {
  it("不會在無 window / 無 AudioContext 環境下拋例外", () => {
    // node 環境本來就沒有 window — 確保我們沉默失敗而非崩潰
    expect(() => playNotificationSound()).not.toThrow();
  });
});
