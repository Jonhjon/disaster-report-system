import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CandidateSelectionCard from "../CandidateSelectionCard";
import type { EventCandidate } from "../../../types";

const mockCandidates: EventCandidate[] = [
  {
    event_id: "event-001",
    title: "台北市信義路淹水",
    description: "信義路二段淹水30公分，交通癱瘓",
    location_text: "台北市信義路二段",
    report_count: 3,
    distance_m: 150,
    score: 0.85,
  },
  {
    event_id: "event-002",
    title: "松仁路淹水災情",
    description: "松仁路一帶積水嚴重",
    location_text: "台北市松仁路100號",
    report_count: 1,
    distance_m: 250,
    score: 0.62,
  },
];

describe("CandidateSelectionCard", () => {
  it("renders a card for each candidate", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText("台北市信義路淹水")).toBeInTheDocument();
    expect(screen.getByText("松仁路淹水災情")).toBeInTheDocument();
  });

  it("always renders a 建立新事件 option", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText(/建立新事件/)).toBeInTheDocument();
  });

  it("renders 建立新事件 even when candidates list is empty", () => {
    render(<CandidateSelectionCard candidates={[]} onSelect={vi.fn()} />);
    expect(screen.getByText(/建立新事件/)).toBeInTheDocument();
  });

  it("shows location_text for each candidate", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText("台北市信義路二段")).toBeInTheDocument();
    expect(screen.getByText("台北市松仁路100號")).toBeInTheDocument();
  });

  it("shows distance in meters for each candidate", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText(/150\s*公尺/)).toBeInTheDocument();
    expect(screen.getByText(/250\s*公尺/)).toBeInTheDocument();
  });

  it("shows similarity score as percentage for each candidate", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText(/85%/)).toBeInTheDocument();
    expect(screen.getByText(/62%/)).toBeInTheDocument();
  });

  it("shows report count for each candidate", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText(/3\s*筆/)).toBeInTheDocument();
  });

  it("shows a header prompting the user to select", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    expect(screen.getByText("系統偵測到相似事件，請選擇：")).toBeInTheDocument();
  });

  it("calls onSelect with event_id when a candidate card is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={onSelect} />);

    const card = screen.getByText("台北市信義路淹水").closest("button");
    await user.click(card!);

    expect(onSelect).toHaveBeenCalledWith("event-001");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("calls onSelect with 'new' when 建立新事件 is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={onSelect} />);

    const newBtn = screen.getByText(/建立新事件/).closest("button");
    await user.click(newBtn!);

    expect(onSelect).toHaveBeenCalledWith("new");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("each candidate card is a button element", () => {
    render(<CandidateSelectionCard candidates={mockCandidates} onSelect={vi.fn()} />);
    const titleEl = screen.getByText("台北市信義路淹水");
    expect(titleEl.closest("button")).not.toBeNull();
  });
});
