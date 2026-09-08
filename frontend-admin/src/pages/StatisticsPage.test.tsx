import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EventStatistics } from "../types";

const mocks = vi.hoisted(() => ({
  buildSummaryCsv: vi.fn(() => "summary csv"),
  downloadCsv: vi.fn(),
  getEventStatistics: vi.fn(),
  useState: vi.fn(),
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useCallback: <T,>(callback: T) => callback,
    useEffect: vi.fn(),
    useMemo: <T,>(factory: () => T) => factory(),
    useState: mocks.useState,
  };
});

vi.mock("../services/api", () => ({
  downloadEventsCsv: vi.fn(),
  getEventStatistics: mocks.getEventStatistics,
}));

vi.mock("../utils/statsCsv", () => ({
  buildSummaryCsv: mocks.buildSummaryCsv,
  downloadCsv: mocks.downloadCsv,
  withBom: (csv: string) => csv,
}));

import StatisticsPage from "./StatisticsPage";

const stats: EventStatistics = {
  summary: {
    total_events: 0,
    total_report_count: 0,
    total_casualties: 0,
    total_injured: 0,
    total_severe_injured: 0,
    total_trapped: 0,
    avg_severity: null,
    high_severity_count: 0,
    unresolved_count: 0,
  },
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
    method_note: "test",
  },
  bucket: "day",
  timezone: "Asia/Taipei",
  time_field: "occurred_at",
  generated_at: "2026-08-06T16:30:00.000Z",
};

function textContent(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textContent).join("");
  if (node && typeof node === "object" && "props" in node) {
    return textContent((node as ReactElement<{ children?: ReactNode }>).props.children);
  }
  return "";
}

function findButton(node: ReactNode, label: string): ReactElement | undefined {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findButton(child, label);
      if (match) return match;
    }
    return undefined;
  }
  if (!node || typeof node !== "object" || !("props" in node)) return undefined;

  const element = node as ReactElement<{ children?: ReactNode }>;
  if (element.type === "button" && textContent(element).includes(label)) return element;
  return findButton(element.props.children, label);
}

function clickSummaryExport(): void {
  const tree = StatisticsPage();
  const button = findButton(tree, "匯出統計摘要");
  expect(button).toBeDefined();
  (button!.props as { onClick: () => void }).onClick();
}

describe("statistics summary export dates", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-06T16:30:00.000Z"));
    vi.stubEnv("TZ", "America/Los_Angeles");
    mocks.buildSummaryCsv.mockClear();
    mocks.downloadCsv.mockClear();

    let stateCall = 0;
    mocks.useState.mockImplementation((initial: unknown) => {
      const value = stateCall++ === 0 ? stats : initial;
      return [value, vi.fn()];
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("formats the generated-at label in Asia/Taipei", () => {
    clickSummaryExport();

    expect(mocks.buildSummaryCsv).toHaveBeenCalledWith(
      stats,
      expect.objectContaining({
        generatedAtLabel: expect.stringMatching(/^2026\/8\/7.*Asia\/Taipei/),
      })
    );
  });

  it("uses the current Asia/Taipei date in the filename", () => {
    clickSummaryExport();

    expect(mocks.downloadCsv).toHaveBeenCalledWith(
      "災情統計摘要_2026-08-07.csv",
      "summary csv"
    );
  });
});
