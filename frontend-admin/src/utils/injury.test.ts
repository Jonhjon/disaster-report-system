import { describe, expect, it } from "vitest";
import { clampSevereInjured, formatSevereSuffix } from "./injury";

describe("clampSevereInjured", () => {
  it("keeps severe when within injured", () => {
    expect(clampSevereInjured(2, 5)).toBe(2);
  });

  it("clamps severe down to injured when it exceeds", () => {
    expect(clampSevereInjured(8, 3)).toBe(3);
  });

  it("allows severe equal to injured", () => {
    expect(clampSevereInjured(4, 4)).toBe(4);
  });

  it("forces 0 when injured is 0", () => {
    expect(clampSevereInjured(3, 0)).toBe(0);
  });

  it("never returns negative", () => {
    expect(clampSevereInjured(-2, 5)).toBe(0);
    expect(clampSevereInjured(2, -5)).toBe(0);
  });
});

describe("formatSevereSuffix", () => {
  it("annotates when there are severe injuries", () => {
    expect(formatSevereSuffix(2)).toBe("（其中重傷 2）");
  });

  it("returns empty string when no severe injuries", () => {
    expect(formatSevereSuffix(0)).toBe("");
  });

  it("returns empty string for negative (defensive)", () => {
    expect(formatSevereSuffix(-1)).toBe("");
  });
});
