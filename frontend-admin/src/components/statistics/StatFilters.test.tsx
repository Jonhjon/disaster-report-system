import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import StatFilters, { type StatFilterState } from "./StatFilters";

const filters: StatFilterState = {
  search: "",
  disaster_type: "",
  severity_min: "",
  status: "",
  date_from: "",
  date_to: "",
  bucket: "week",
};

describe("StatFilters accessibility", () => {
  it("gives every filter a meaningful accessible label", () => {
    const html = renderToStaticMarkup(
      <StatFilters filters={filters} onChange={vi.fn()} />
    );

    for (const label of [
      "搜尋災情",
      "災害類型",
      "事件狀態",
      "最低嚴重程度",
      "開始日期",
      "結束日期",
      "趨勢分桶",
    ]) {
      expect(html).toContain(`aria-label="${label}"`);
    }
  });

  it("exposes the selected bucket through aria-pressed", () => {
    const html = renderToStaticMarkup(
      <StatFilters filters={filters} onChange={vi.fn()} />
    );

    expect(html).toMatch(/aria-pressed="true"[^>]*>週<\/button>/);
    expect(html).toMatch(/aria-pressed="false"[^>]*>日<\/button>/);
    expect(html).toMatch(/aria-pressed="false"[^>]*>月<\/button>/);
  });
});
