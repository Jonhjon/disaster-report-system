import { describe, expect, it } from "vitest";
import {
  buildSummaryCsv,
  escapeCsvCell,
  sanitizeForSpreadsheet,
  toCsv,
  withBom,
} from "./statsCsv";
import type { EventStatistics } from "../types";

describe("escapeCsvCell", () => {
  it("quotes a value containing a comma", () => {
    expect(escapeCsvCell("a,b")).toBe('"a,b"');
  });

  it("doubles internal quotes and wraps in quotes", () => {
    expect(escapeCsvCell('say "hi"')).toBe('"say ""hi"""');
  });

  it("quotes a value containing a newline", () => {
    const result = escapeCsvCell("行1\n行2");
    expect(result.startsWith('"')).toBe(true);
    expect(result.endsWith('"')).toBe(true);
  });

  it("converts null to empty string", () => {
    expect(escapeCsvCell(null)).toBe("");
  });

  it("converts undefined to empty string", () => {
    expect(escapeCsvCell(undefined)).toBe("");
  });

  it("converts numeric 0 to the string '0', not an empty string", () => {
    expect(escapeCsvCell(0)).toBe("0");
  });

  it("leaves a plain CJK string unquoted", () => {
    expect(escapeCsvCell("台北市信義區")).toBe("台北市信義區");
  });
});

describe("sanitizeForSpreadsheet", () => {
  it("prefixes a leading = with a single quote", () => {
    expect(sanitizeForSpreadsheet("=1+1")).toBe("'=1+1");
  });

  it("prefixes a leading + with a single quote", () => {
    expect(sanitizeForSpreadsheet("+1+1")).toBe("'+1+1");
  });

  it("prefixes a leading - with a single quote", () => {
    expect(sanitizeForSpreadsheet("-1+1")).toBe("'-1+1");
  });

  it("prefixes a leading @ with a single quote", () => {
    expect(sanitizeForSpreadsheet("@SUM(A1)")).toBe("'@SUM(A1)");
  });

  it("neutralizes formulas after leading spaces", () => {
    expect(sanitizeForSpreadsheet("  =1+1")).toBe("'  =1+1");
  });

  it("prefixes a leading line feed with a single quote", () => {
    expect(sanitizeForSpreadsheet("\n=1+1")).toBe("'\n=1+1");
  });

  it("leaves ordinary text untouched", () => {
    expect(sanitizeForSpreadsheet("正常文字")).toBe("正常文字");
  });
});

describe("toCsv", () => {
  it("joins rows with CRLF", () => {
    const csv = toCsv([
      ["a", "b"],
      ["c", "d"],
    ]);
    expect(csv).toBe("a,b\r\nc,d");
  });
});

describe("withBom", () => {
  it("prefixes the string with a BOM character", () => {
    expect(withBom("x").startsWith("﻿")).toBe(true);
  });

  it("does not stack a second BOM when called twice", () => {
    const once = withBom("x");
    const twice = withBom(once);
    const bomCount = (twice.match(/﻿/g) ?? []).length;
    expect(bomCount).toBe(1);
  });
});

function makeStats(overrides: Partial<EventStatistics> = {}): EventStatistics {
  return {
    summary: {
      total_events: 10,
      total_report_count: 15,
      total_casualties: 1,
      total_injured: 3,
      total_severe_injured: 1,
      total_trapped: 0,
      avg_severity: 2.5,
      high_severity_count: 2,
      unresolved_count: 4,
    },
    by_disaster_type: [{ key: "fire", count: 7, percentage: 70.0 }],
    by_severity: [{ key: "3", count: 10, percentage: 100.0 }],
    by_status: [{ key: "reported", count: 10, percentage: 100.0 }],
    trend: [{ bucket_start: "2026-08-01", count: 3 }],
    cross_tab: [{ disaster_type: "fire", severity: 3, count: 7 }],
    resolution: {
      resolved_count: 5,
      legacy_excluded_count: 1,
      avg_hours: 4.5,
      median_hours: 3.0,
      p90_hours: 10.0,
      method_note: "結案耗時 = 事件建立時間 → 狀態最近一次轉為「已結案」的時間（resolved_at）。",
    },
    bucket: "day",
    timezone: "Asia/Taipei",
    time_field: "occurred_at",
    generated_at: "2026-08-06T12:00:00Z",
    ...overrides,
  };
}

describe("buildSummaryCsv", () => {
  const opts = {
    filterDescription: "災害類型：火警",
    generatedAtLabel: "2026-08-06 14:30 (Asia/Taipei)",
  };

  it("includes all section headers", () => {
    const csv = buildSummaryCsv(makeStats(), opts);

    expect(csv).toContain("總覽");
    expect(csv).toContain("依災害類型");
    expect(csv).toContain("依嚴重度");
    expect(csv).toContain("依狀態");
    expect(csv).toContain("時間趨勢");
    expect(csv).toContain("交叉統計");
    expect(csv).toContain("處理效率");
  });

  it("includes the filter description and generated-at label", () => {
    const csv = buildSummaryCsv(makeStats(), opts);

    expect(csv).toContain(opts.filterDescription);
    expect(csv).toContain(opts.generatedAtLabel);
  });

  it("includes the resolution method note verbatim", () => {
    const stats = makeStats();
    const csv = buildSummaryCsv(stats, opts);

    expect(csv).toContain(stats.resolution.method_note);
  });

  it("uses the API-provided percentage as-is, without recomputing", () => {
    const stats = makeStats({
      by_disaster_type: [{ key: "fire", count: 3, percentage: 33.3 }],
    });

    const csv = buildSummaryCsv(stats, opts);

    expect(csv).toContain("33.3");
  });

  it("does not throw for all-empty data and still emits section headers", () => {
    const emptyStats = makeStats({
      by_disaster_type: [],
      by_severity: [],
      by_status: [],
      trend: [],
      cross_tab: [],
      resolution: {
        resolved_count: 0,
        legacy_excluded_count: 0,
        avg_hours: null,
        median_hours: null,
        p90_hours: null,
        method_note: "結案耗時 = 事件建立時間 → 狀態最近一次轉為「已結案」的時間（resolved_at）。",
      },
    });

    expect(() => buildSummaryCsv(emptyStats, opts)).not.toThrow();
    const csv = buildSummaryCsv(emptyStats, opts);
    expect(csv).toContain("總覽");
    expect(csv).toContain("依災害類型");
    expect(csv).toContain("處理效率");
  });
});
