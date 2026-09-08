import type { EventStatistics } from "../types";
import {
  DISASTER_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  type DisasterType,
  type EventStatus,
} from "../types";

/**
 * 統計摘要的 CSV 產生。
 *
 * 除了 downloadCsv 之外全是純函式，可用 vitest 覆蓋
 * （本專案的 vitest 沒有 jsdom，Blob / URL / document 都不存在）。
 */

const BOM = "﻿";

/** RFC 4180 單格編碼：含逗號、引號、換行或前後空白時加引號，內部引號 double 化。 */
export function escapeCsvCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  const needsQuoting = /[",\r\n]/.test(text) || text !== text.trim();
  return needsQuoting ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * 防試算表公式注入：以 = + - @ 或 tab/CR 開頭的值前綴單引號。
 *
 * 事件標題來自 LLM 對民眾訊息的萃取，可能以這些字元開頭，
 * Excel 會直接當公式執行。刻意與 escapeCsvCell 分離，兩者可獨立測試。
 */
export function sanitizeForSpreadsheet(value: string): string {
  const candidate = value.replace(/^ +/, "");
  return /^[=+\-@\t\r\n]/.test(candidate) ? `'${value}` : value;
}

/** 二維陣列 → CSV 文字。行尾用 CRLF（Excel 相容）。 */
export function toCsv(rows: readonly (string | number | null)[][]): string {
  return rows.map((row) => row.map(escapeCsvCell).join(",")).join("\r\n");
}

export interface SummaryCsvOptions {
  /** 人類可讀的篩選條件描述，寫進註記區 */
  filterDescription: string;
  /** 匯出時間標籤，例如 "2026-08-06 14:30 (Asia/Taipei)" */
  generatedAtLabel: string;
}

type CsvRow = (string | number | null)[];

function disasterTypeLabel(key: string): string {
  return DISASTER_TYPE_LABELS[key as DisasterType] ?? key;
}

function statusLabel(key: string): string {
  return STATUS_LABELS[key as EventStatus] ?? key;
}

function severityLabel(key: string | number): string {
  return SEVERITY_LABELS[Number(key)] ?? String(key);
}

/** 數值指標為 null 時輸出破折號，不可寫成 0（語意完全不同）。 */
function orDash(value: number | null): string {
  return value === null ? "—" : String(value);
}

/**
 * 組出統計摘要 CSV（單檔多區段，區段間空一列）。
 *
 * 百分比一律直接採用 API 給的值、前端不重算，否則 CSV 與畫面上的數字
 * 會因捨入策略不同而互相矛盾。
 */
export function buildSummaryCsv(
  stats: EventStatistics,
  options: SummaryCsvOptions,
): string {
  const { summary, resolution } = stats;
  const rows: CsvRow[] = [
    ["# 匯出時間", options.generatedAtLabel],
    ["# 篩選條件", options.filterDescription],
    ["# 時間分桶", `${stats.bucket}（依發生時間 ${stats.time_field}，時區 ${stats.timezone}）`],
    ["# 註記", resolution.method_note],
    [],

    ["總覽"],
    ["指標", "數值"],
    ["事件總數", summary.total_events],
    ["累計通報次數", summary.total_report_count],
    ["死亡人數", summary.total_casualties],
    ["受傷人數", summary.total_injured],
    ["其中重傷", summary.total_severe_injured],
    ["受困人數", summary.total_trapped],
    ["平均嚴重度", orDash(summary.avg_severity)],
    ["高嚴重度事件數（4 級以上）", summary.high_severity_count],
    ["未結案事件數", summary.unresolved_count],
    [],

    ["依災害類型"],
    ["災害類型", "件數", "佔比(%)"],
    ...stats.by_disaster_type.map<CsvRow>((item) => [
      sanitizeForSpreadsheet(disasterTypeLabel(item.key)),
      item.count,
      item.percentage,
    ]),
    [],

    ["依嚴重度"],
    ["嚴重度", "件數", "佔比(%)"],
    ...stats.by_severity.map<CsvRow>((item) => [
      `${item.key} - ${severityLabel(item.key)}`,
      item.count,
      item.percentage,
    ]),
    [],

    ["依狀態"],
    ["狀態", "件數", "佔比(%)"],
    ...stats.by_status.map<CsvRow>((item) => [
      sanitizeForSpreadsheet(statusLabel(item.key)),
      item.count,
      item.percentage,
    ]),
    [],

    ["時間趨勢"],
    ["分桶起始", "件數"],
    ...stats.trend.map<CsvRow>((point) => [point.bucket_start, point.count]),
    [],

    ["交叉統計（災害類型 × 嚴重度）"],
    ["災害類型", "嚴重度", "件數"],
    ...stats.cross_tab.map<CsvRow>((cell) => [
      sanitizeForSpreadsheet(disasterTypeLabel(cell.disaster_type)),
      cell.severity,
      cell.count,
    ]),
    [],

    ["處理效率"],
    ["指標", "數值"],
    ["納入計算的已結案事件數", resolution.resolved_count],
    ["無結案時戳而未納入的事件數", resolution.legacy_excluded_count],
    ["結案耗時中位數(小時)", orDash(resolution.median_hours)],
    ["結案耗時平均(小時)", orDash(resolution.avg_hours)],
    ["結案耗時 P90(小時)", orDash(resolution.p90_hours)],
  ];

  return toCsv(rows);
}

/** 加上 UTF-8 BOM，Excel 開啟中文才不會亂碼。重複呼叫不應疊加。 */
export function withBom(csv: string): string {
  return csv.startsWith(BOM) ? csv : BOM + csv;
}

/** 觸發瀏覽器下載。唯一的不純函式，刻意隔離且不寫測試。 */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
