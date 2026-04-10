import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { streamChat } from "../api";
import type { EventCandidate } from "../../types";

// ── 建立 SSE mock 回應 ──────────────────────────────────────────────────────

function createMockSSEStream(events: object[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function mockFetchWithSSE(events: object[]) {
  const stream = createMockSSEStream(events);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
    })
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── candidates_selection 處理 ───────────────────────────────────────────────

describe("streamChat - candidates_selection event handling", () => {
  const mockCandidates: EventCandidate[] = [
    {
      event_id: "event-001",
      title: "台北市信義路淹水",
      description: "信義路淹水30公分",
      location_text: "台北市信義路二段",
      report_count: 3,
      distance_m: 150,
      score: 0.85,
    },
  ];

  it("calls onCandidatesSelection with candidates when event is received", async () => {
    mockFetchWithSSE([
      { type: "text", content: "發現附近有相似事件" },
      { type: "candidates_selection", candidates: mockCandidates },
      { type: "done" },
    ]);

    const onCandidatesSelection = vi.fn();

    await new Promise<void>((resolve) => {
      streamChat(
        "台北市信義路淹水",
        [],
        vi.fn(),
        vi.fn(),
        resolve,
        vi.fn(),
        onCandidatesSelection
      );
    });

    expect(onCandidatesSelection).toHaveBeenCalledOnce();
    expect(onCandidatesSelection).toHaveBeenCalledWith(mockCandidates);
  });

  it("does not call onCandidatesSelection when only text and done events arrive", async () => {
    mockFetchWithSSE([
      { type: "text", content: "通報成功" },
      { type: "report_submitted", status: "created", event_id: "abc", message: "已建立" },
      { type: "done" },
    ]);

    const onCandidatesSelection = vi.fn();

    await new Promise<void>((resolve) => {
      streamChat(
        "通報測試",
        [],
        vi.fn(),
        vi.fn(),
        resolve,
        vi.fn(),
        onCandidatesSelection
      );
    });

    expect(onCandidatesSelection).not.toHaveBeenCalled();
  });

  it("still calls onText for text events even when candidates_selection also arrives", async () => {
    mockFetchWithSSE([
      { type: "text", content: "附近有相似事件，請選擇：" },
      { type: "candidates_selection", candidates: mockCandidates },
      { type: "done" },
    ]);

    const onText = vi.fn();
    const onCandidatesSelection = vi.fn();

    await new Promise<void>((resolve) => {
      streamChat(
        "測試",
        [],
        onText,
        vi.fn(),
        resolve,
        vi.fn(),
        onCandidatesSelection
      );
    });

    expect(onText).toHaveBeenCalledWith("附近有相似事件，請選擇：");
    expect(onCandidatesSelection).toHaveBeenCalledWith(mockCandidates);
  });

  it("calls onCandidatesSelection with all candidates when multiple exist", async () => {
    const multiCandidates: EventCandidate[] = [
      {
        event_id: "id-1",
        title: "事件A",
        description: "描述A",
        location_text: "地點A",
        report_count: 2,
        distance_m: 100,
        score: 0.90,
      },
      {
        event_id: "id-2",
        title: "事件B",
        description: "描述B",
        location_text: "地點B",
        report_count: 1,
        distance_m: 200,
        score: 0.65,
      },
    ];

    mockFetchWithSSE([
      { type: "candidates_selection", candidates: multiCandidates },
      { type: "done" },
    ]);

    const onCandidatesSelection = vi.fn();

    await new Promise<void>((resolve) => {
      streamChat(
        "測試",
        [],
        vi.fn(),
        vi.fn(),
        resolve,
        vi.fn(),
        onCandidatesSelection
      );
    });

    const received = onCandidatesSelection.mock.calls[0][0] as EventCandidate[];
    expect(received).toHaveLength(2);
    expect(received[0].event_id).toBe("id-1");
    expect(received[1].event_id).toBe("id-2");
  });
});
