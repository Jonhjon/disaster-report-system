import { describe, expect, it } from "vitest";
import {
  DisasterEventSchema,
  EventListResponseSchema,
  EventMapItemSchema,
} from "./";

const validEvent = {
  id: "abc",
  title: "台北淹水",
  disaster_type: "flooding",
  severity: 3,
  description: null,
  location_text: "台北市",
  latitude: 25.05,
  longitude: 121.53,
  occurred_at: "2026-04-20T10:00:00Z",
  casualties: 0,
  injured: 2,
  trapped: 0,
  status: "reported",
  report_count: 1,
  location_approximate: false,
  created_at: "2026-04-20T10:00:00Z",
  updated_at: "2026-04-20T10:00:00Z",
};

describe("DisasterEventSchema", () => {
  it("accepts valid event", () => {
    expect(() => DisasterEventSchema.parse(validEvent)).not.toThrow();
  });

  it("throws when required field missing", () => {
    const { title: _, ...noTitle } = validEvent;
    expect(() => DisasterEventSchema.parse(noTitle)).toThrow();
  });

  it("throws on invalid disaster_type", () => {
    expect(() =>
      DisasterEventSchema.parse({ ...validEvent, disaster_type: "earthquake" })
    ).toThrow();
  });

  it("throws on invalid status", () => {
    expect(() =>
      DisasterEventSchema.parse({ ...validEvent, status: "unknown_status" })
    ).toThrow();
  });
});

describe("EventMapItemSchema", () => {
  it("accepts valid map item", () => {
    const item = {
      id: "abc",
      title: "淹水",
      disaster_type: "flooding",
      severity: 2,
      latitude: 25.0,
      longitude: 121.5,
      status: "reported",
      report_count: 1,
      occurred_at: "2026-04-20T10:00:00Z",
      location_approximate: false,
    };
    expect(() => EventMapItemSchema.parse(item)).not.toThrow();
  });
});

describe("EventListResponseSchema", () => {
  it("accepts valid list response", () => {
    const resp = {
      items: [validEvent],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    };
    expect(() => EventListResponseSchema.parse(resp)).not.toThrow();
  });

  it("throws when items is missing", () => {
    expect(() => EventListResponseSchema.parse({ total: 0, page: 1 })).toThrow();
  });
});
