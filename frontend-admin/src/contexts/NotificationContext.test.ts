import { describe, expect, it } from "vitest";
import { parseNotification } from "./NotificationContext";

const validRaw = JSON.stringify({
  event_id: "evt-1",
  title: "信義區火警",
  disaster_type: "fire",
  severity: 4,
  location_text: "台北市信義區松壽路1號",
  occurred_at: "2026-05-08T10:00:00+00:00",
});

describe("parseNotification", () => {
  it("解析合法 payload 並補上 received_at + read=false", () => {
    const before = Date.now();
    const result = parseNotification(validRaw);
    const after = Date.now();

    expect(result).not.toBeNull();
    if (!result) return;
    expect(result.event_id).toBe("evt-1");
    expect(result.title).toBe("信義區火警");
    expect(result.disaster_type).toBe("fire");
    expect(result.severity).toBe(4);
    expect(result.location_text).toBe("台北市信義區松壽路1號");
    expect(result.occurred_at).toBe("2026-05-08T10:00:00+00:00");
    expect(result.read).toBe(false);

    const receivedAt = new Date(result.received_at).getTime();
    expect(receivedAt).toBeGreaterThanOrEqual(before);
    expect(receivedAt).toBeLessThanOrEqual(after);
  });

  it("回傳 null when JSON 格式錯誤", () => {
    expect(parseNotification("not json")).toBeNull();
    expect(parseNotification("{")).toBeNull();
  });

  it("拒絕欄位型別不正確的 payload", () => {
    const missingFields = JSON.stringify({ event_id: "x" });
    expect(parseNotification(missingFields)).toBeNull();

    const wrongTypes = JSON.stringify({
      event_id: 123, // should be string
      title: "ok",
      disaster_type: "fire",
      severity: 4,
      location_text: "台北",
      occurred_at: "2026-05-08T10:00:00Z",
    });
    expect(parseNotification(wrongTypes)).toBeNull();

    const severityNotNumber = JSON.stringify({
      event_id: "x",
      title: "ok",
      disaster_type: "fire",
      severity: "4", // string instead of number
      location_text: "台北",
      occurred_at: "2026-05-08T10:00:00Z",
    });
    expect(parseNotification(severityNotNumber)).toBeNull();
  });
});
