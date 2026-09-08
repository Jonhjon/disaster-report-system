import { describe, expect, it } from "vitest";
import {
  CHART,
  buildAreaPath,
  buildLinePath,
  niceMax,
  niceTicks,
  pivotCrossTab,
  tickIndices,
  xAt,
  yAt,
} from "./statsChart";
import type { CrossTabCell } from "../types";

describe("xAt", () => {
  it("centers a single point (n=1) without NaN/Infinity from division by zero", () => {
    const x = xAt(0, 1);
    expect(Number.isFinite(x)).toBe(true);
    expect(x).toBeCloseTo((CHART.left + (CHART.w - CHART.right)) / 2);
  });

  it("places the first of n points at the left edge", () => {
    expect(xAt(0, 5)).toBe(CHART.left);
  });

  it("places the last of n points at the right edge", () => {
    expect(xAt(4, 5)).toBe(CHART.w - CHART.right);
  });
});

describe("yAt", () => {
  it("places value 0 at the baseline (chart bottom minus bottom margin)", () => {
    expect(yAt(0, 10)).toBe(CHART.h - CHART.bottom);
  });

  it("places the max value at the top", () => {
    expect(yAt(10, 10)).toBe(CHART.top);
  });

  it("guards against yMax=0 division by zero, returning a finite number", () => {
    expect(Number.isFinite(yAt(0, 0))).toBe(true);
  });
});

describe("buildLinePath", () => {
  it("returns empty string for empty input", () => {
    expect(buildLinePath([], 1)).toBe("");
  });

  it("never emits NaN when yMax is 0 (division-by-zero guard)", () => {
    const path = buildLinePath([0, 0, 0], 0);
    expect(path).not.toContain("NaN");
  });

  it("never emits NaN for a single point", () => {
    const path = buildLinePath([5], 5);
    expect(path).not.toContain("NaN");
  });
});

describe("buildAreaPath", () => {
  it("returns empty string for empty input", () => {
    expect(buildAreaPath([], 1)).toBe("");
  });

  it("produces a closed path without NaN", () => {
    const path = buildAreaPath([1, 2, 3], 3);
    expect(path).not.toContain("NaN");
    expect(path.trim().endsWith("Z")).toBe(true);
  });
});

describe("niceMax", () => {
  it("niceMax(0) === 1", () => {
    expect(niceMax(0)).toBe(1);
  });

  it("niceMax(7) === 8", () => {
    expect(niceMax(7)).toBe(8);
  });

  it("niceMax(23) === 25", () => {
    expect(niceMax(23)).toBe(25);
  });

  it("niceMax(117) === 120", () => {
    expect(niceMax(117)).toBe(120);
  });
});

describe("niceTicks", () => {
  it("starts at 0, ends at yMax, and strictly increases", () => {
    const ticks = niceTicks(100);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBe(100);
    for (let i = 1; i < ticks.length; i++) {
      expect(ticks[i]).toBeGreaterThan(ticks[i - 1]);
    }
  });
});

describe("tickIndices", () => {
  it("caps the number of labels and always includes first and last index", () => {
    const indices = tickIndices(365, 8);
    expect(indices.length).toBeLessThanOrEqual(8);
    expect(indices).toContain(0);
    expect(indices).toContain(364);
  });

  it("returns all indices when point count is below the cap", () => {
    const indices = tickIndices(3);
    expect(indices).toEqual([0, 1, 2]);
  });
});

describe("pivotCrossTab", () => {
  const types = ["fire", "flooding"] as const;
  const severities = [1, 2, 3] as const;

  it("fills missing cells with 0 and computes totals correctly", () => {
    const cells: CrossTabCell[] = [
      { disaster_type: "fire", severity: 1, count: 5 },
      { disaster_type: "fire", severity: 3, count: 2 },
      { disaster_type: "flooding", severity: 2, count: 4 },
    ];

    const result = pivotCrossTab(cells, types, severities);

    // fire row: [5, 0, 2], flooding row: [0, 4, 0]
    expect(result.matrix[0]).toEqual([5, 0, 2]);
    expect(result.matrix[1]).toEqual([0, 4, 0]);
    expect(result.rowTotals).toEqual([7, 4]);
    expect(result.colTotals).toEqual([5, 4, 2]);
    expect(result.grandTotal).toBe(11);
    expect(result.max).toBe(5);
  });

  it("returns an all-zero matrix for empty cells, with grandTotal and max === 0 (not -Infinity)", () => {
    const result = pivotCrossTab([], types, severities);

    expect(result.matrix).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
    expect(result.rowTotals).toEqual([0, 0]);
    expect(result.colTotals).toEqual([0, 0, 0]);
    expect(result.grandTotal).toBe(0);
    expect(result.max).toBe(0);
  });
});
