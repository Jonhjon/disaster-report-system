/**
 * 傷亡人數相關的純函式邏輯，抽出以便單元測試。
 *
 * 不變式：重傷是受傷的子集，severe_injured 恆 <= injured 且 >= 0。
 */

/**
 * 將重傷人數夾擠在 [0, injured] 範圍內。
 * 供編輯表單即時修正輸入，維持「重傷 <= 受傷」不變式。
 */
export function clampSevereInjured(severe: number, injured: number): number {
  const upper = Math.max(0, injured);
  return Math.max(0, Math.min(severe, upper));
}

/**
 * 重傷附註文字，供事件詳情在受傷數後方顯示。
 * severe <= 0 時回傳空字串（不顯示附註）。
 */
export function formatSevereSuffix(severeInjured: number): string {
  return severeInjured > 0 ? `（其中重傷 ${severeInjured}）` : "";
}
