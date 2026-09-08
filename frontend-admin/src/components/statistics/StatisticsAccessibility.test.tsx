import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CrossTabTable from "./CrossTabTable";
import TrendLineChart from "./TrendLineChart";

describe("statistics chart accessibility", () => {
  it("exposes every non-empty trend bucket and count in a screen-reader-readable table", () => {
    const points = [
      { bucket_start: "2026-09-01", count: 2 },
      { bucket_start: "2026-09-02", count: 17 },
      { bucket_start: "2026-09-03", count: 0 },
    ];

    const html = renderToStaticMarkup(
      <TrendLineChart points={points} bucket="day" />
    );

    expect(html).toMatch(/<table\b[^>]*>[\s\S]*<\/table>/);
    for (const point of points) {
      expect(html).toMatch(
        new RegExp(
          `<tr\\b[^>]*>[\\s\\S]*?<th\\b[^>]*scope="row"[^>]*>${point.bucket_start}</th>[\\s\\S]*?<td\\b[^>]*>${point.count}</td>[\\s\\S]*?</tr>`
        )
      );
    }
  });

  it("marks every cross-tab disaster type and subtotal label as a row header", () => {
    const html = renderToStaticMarkup(
      <CrossTabTable
        cells={[
          { disaster_type: "fire", severity: 1, count: 2 },
          { disaster_type: "earthquake", severity: 5, count: 1 },
        ]}
      />
    );

    const bodyRowLabels = Array.from(
      html.matchAll(/<tr\b[^>]*>[\s\S]*?<t[hd]\b([^>]*)>([^<]+)<\/t[hd]>/g),
      (match) => ({ attributes: match[1], label: match[2] })
    ).filter(({ label }) => label !== "災害類型");

    expect(bodyRowLabels.map(({ label }) => label)).toEqual([
      "火警",
      "earthquake",
      "小計",
    ]);
    for (const { attributes } of bodyRowLabels) {
      expect(attributes).toContain('scope="row"');
    }
  });
});
