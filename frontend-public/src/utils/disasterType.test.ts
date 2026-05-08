import { describe, expect, it } from "vitest";
import { isDisasterType } from "./disasterType";

describe("isDisasterType", () => {
  it("accepts all valid disaster types", () => {
    const valid = [
      "trapped", "road_collapse", "flooding", "landslide",
      "small_landslide", "building_damage", "utility_damage", "fire", "other",
    ];
    for (const t of valid) {
      expect(isDisasterType(t), `${t} should be valid`).toBe(true);
    }
  });

  it("rejects unknown strings", () => {
    expect(isDisasterType("earthquake")).toBe(false);
    expect(isDisasterType("tornado")).toBe(false);
    expect(isDisasterType("")).toBe(false);
  });

  it("rejects partial matches", () => {
    expect(isDisasterType("flood")).toBe(false);
    expect(isDisasterType("FLOODING")).toBe(false);
  });
});
