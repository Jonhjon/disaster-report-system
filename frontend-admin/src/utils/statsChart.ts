import type { CrossTabCell } from "../types";

/**
 * 手刻 SVG 圖表的座標計算。
 *
 * 這個檔案存在的主要理由是「分母護欄」：除以零會產生 d="MNaN,NaN"，
 * 而 SVG 對非法 path 是靜默不渲染、console 完全沒有錯誤訊息，
 * 是手刻圖表最難 debug 的一類 bug。所有計算集中在此並以純函式測試覆蓋。
 *
 * RWD 策略：固定 viewBox + 外層 overflow-x-auto + min-w。
 * viewBox 等比縮放會連文字一起縮小（手機上 12px 標籤變 6px 不可讀）。
 */
export const CHART = {
  w: 800,
  h: 320,
  top: 16,
  right: 16,
  bottom: 36,
  left: 48,
} as const;

const INNER_W = CHART.w - CHART.left - CHART.right;
const INNER_H = CHART.h - CHART.top - CHART.bottom;

/** 座標四捨五入到小數 2 位，避免 path 字串出現一長串浮點雜訊。 */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** 第 i 個點（共 n 點）的 x 座標。n <= 1 時置中，不可回傳 NaN/Infinity。 */
export function xAt(i: number, n: number): number {
  if (n <= 1) return CHART.left + INNER_W / 2;
  return CHART.left + (i / (n - 1)) * INNER_W;
}

/** 數值 v 在上限 yMax 下的 y 座標。yMax 為 0 時需有護欄。 */
export function yAt(v: number, yMax: number): number {
  return CHART.top + INNER_H - (v / Math.max(yMax, 1)) * INNER_H;
}

/** 把原始最大值進位成好看的軸上限：0→1、7→8、23→25、117→120。 */
export function niceMax(rawMax: number): number {
  if (!Number.isFinite(rawMax) || rawMax <= 0) return 1;

  // 先估一個目標刻度間距（約 4 段），再收斂到最接近的「好看」間距
  const rough = rawMax / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const nice = [1, 2, 3, 5, 10].reduce((best, candidate) =>
    Math.abs(candidate - normalized) < Math.abs(best - normalized) ? candidate : best,
  );
  const step = nice * magnitude;

  return Math.ceil(rawMax / step) * step;
}

/** 產生 y 軸刻度，首項為 0、末項為 yMax、遞增。 */
export function niceTicks(yMax: number, count = 4): number[] {
  const max = Math.max(yMax, 1);
  const target = Math.max(1, Math.round(count));
  // 優先挑能整除的段數，讓刻度標籤都是整數
  const segments =
    [target, 5, 4, 3, 2].find((c) => Number.isInteger(max / c)) ?? target;
  const step = max / segments;
  return Array.from({ length: segments + 1 }, (_, i) => round2(i * step));
}

/** 折線 path 的 d 屬性。空輸入回傳空字串（由元件改渲染空狀態）。 */
export function buildLinePath(counts: number[], yMax: number): string {
  if (counts.length === 0) return "";
  return counts
    .map(
      (count, i) =>
        `${i === 0 ? "M" : "L"}${round2(xAt(i, counts.length))},${round2(yAt(count, yMax))}`,
    )
    .join(" ");
}

/** 面積 path 的 d 屬性（折線 + 沿基線封閉）。空輸入回傳空字串。 */
export function buildAreaPath(counts: number[], yMax: number): string {
  const line = buildLinePath(counts, yMax);
  if (!line) return "";
  const baseline = round2(yAt(0, yMax));
  const lastX = round2(xAt(counts.length - 1, counts.length));
  const firstX = round2(xAt(0, counts.length));
  return `${line} L${lastX},${baseline} L${firstX},${baseline} Z`;
}

/** x 軸標籤抽稀：從 n 個點中挑最多 maxLabels 個索引，必含頭尾。 */
export function tickIndices(n: number, maxLabels = 8): number[] {
  if (n <= 0) return [];
  if (n <= maxLabels) return Array.from({ length: n }, (_, i) => i);

  const step = (n - 1) / (maxLabels - 1);
  const picked = new Set<number>();
  for (let i = 0; i < maxLabels; i++) picked.add(Math.round(i * step));
  return [...picked].sort((a, b) => a - b);
}

export interface CrossTabMatrix {
  matrix: number[][]; // [類型索引][嚴重度索引]
  rowTotals: number[];
  colTotals: number[];
  grandTotal: number;
  max: number; // 單格最大值，供熱度底色計算
}

/** 把稀疏的交叉表格轉成完整矩陣，缺格補 0，並算出行列小計。 */
export function pivotCrossTab(
  cells: readonly CrossTabCell[],
  types: readonly string[],
  severities: readonly number[],
): CrossTabMatrix {
  const typeIndex = new Map(types.map((t, i) => [t, i]));
  const severityIndex = new Map(severities.map((s, i) => [s, i]));

  const matrix = types.map(() => severities.map(() => 0));
  for (const cell of cells) {
    const row = typeIndex.get(cell.disaster_type);
    const col = severityIndex.get(cell.severity);
    // 後端可能回傳不在既定清單內的類型（DB 對 disaster_type 沒有約束），略過而非丟錯
    if (row === undefined || col === undefined) continue;
    matrix[row][col] += cell.count;
  }

  const rowTotals = matrix.map((row) => row.reduce((sum, v) => sum + v, 0));
  const colTotals = severities.map((_, col) =>
    matrix.reduce((sum, row) => sum + row[col], 0),
  );
  const grandTotal = rowTotals.reduce((sum, v) => sum + v, 0);
  // 空矩陣時 Math.max(...[]) 是 -Infinity，會讓熱度底色計算整個壞掉
  const max = matrix.reduce(
    (best, row) => row.reduce((rowBest, v) => Math.max(rowBest, v), best),
    0,
  );

  return { matrix, rowTotals, colTotals, grandTotal, max };
}
