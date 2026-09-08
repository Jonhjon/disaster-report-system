import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadEventsCsv, getEventStatistics } from "./api";
import type { EventStatistics, StatisticsQuery } from "../types";

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
  generated_at: "2026-08-01T00:00:00Z",
};

describe("getEventStatistics cancellation", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
    });
  });

  it("passes the caller's AbortSignal to fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(stats), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const cancellableGetStatistics = getEventStatistics as unknown as (
      params: StatisticsQuery,
      signal?: AbortSignal
    ) => Promise<EventStatistics>;

    await cancellableGetStatistics({ search: "new filter" }, controller.signal);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ signal: controller.signal })
    );
  });
});

describe("getEventStatistics errors", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
    });
  });

  it("surfaces a non-2xx FastAPI JSON detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "日期範圍不可超過 366 天" }), {
          status: 422,
          statusText: "Unprocessable Entity",
          headers: { "Content-Type": "application/json" },
        })
      )
    );

    await expect(getEventStatistics({ bucket: "day" })).rejects.toThrow(
      "日期範圍不可超過 366 天"
    );
  });
});

describe("downloadEventsCsv filename", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-06T16:30:00.000Z"));
    vi.stubEnv("TZ", "America/Los_Angeles");
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("event csv", {
          status: 200,
          headers: { "Content-Type": "text/csv" },
        })
      )
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("uses the current Asia/Taipei date across the UTC date boundary", async () => {
    const result = await downloadEventsCsv({});

    expect(result.filename).toBe("災情事件明細_2026-08-07.csv");
  });
});
