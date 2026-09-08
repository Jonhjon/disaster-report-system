import { afterEach, describe, expect, it, vi } from "vitest";
import { dateInputToIsoEnd, dateInputToIsoStart } from "./format";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("dateInputToIsoStart", () => {
  it("uses Asia/Taipei midnight even when the browser timezone is different", () => {
    vi.stubEnv("TZ", "America/Los_Angeles");

    expect(dateInputToIsoStart("2026-08-06")).toBe(
      "2026-08-05T16:00:00.000Z"
    );
  });

  it("returns a valid ISO string", () => {
    const iso = dateInputToIsoStart("2026-08-06");
    expect(Number.isNaN(new Date(iso).getTime())).toBe(false);
  });
});

describe("dateInputToIsoEnd", () => {
  it("uses the next Asia/Taipei midnight as an exclusive boundary", () => {
    vi.stubEnv("TZ", "America/Los_Angeles");

    expect(dateInputToIsoEnd("2026-08-06")).toBe(
      "2026-08-06T16:00:00.000Z"
    );
  });

  it("makes a same-date range exactly one half-open day", () => {
    const start = new Date(dateInputToIsoStart("2026-08-06")).getTime();
    const end = new Date(dateInputToIsoEnd("2026-08-06")).getTime();

    expect(end - start).toBe(24 * 60 * 60 * 1000);
  });
});
