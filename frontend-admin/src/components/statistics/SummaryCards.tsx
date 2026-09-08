import type { StatisticsSummary } from "../../types";

interface SummaryCardsProps {
  summary: StatisticsSummary;
}

interface Card {
  label: string;
  value: string;
  hint?: string;
  emphasis?: boolean;
}

function formatNumber(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("zh-TW");
}

function SummaryCards({ summary }: SummaryCardsProps) {
  const cards: Card[] = [
    { label: "事件總數", value: formatNumber(summary.total_events), emphasis: true },
    {
      label: "累計通報次數",
      value: formatNumber(summary.total_report_count),
      // 這個數字不等於通報資料表的筆數：事件合併時通報數是累加的，
      // 且刪除事件會讓其通報變成無所屬。命名上刻意避開「通報總數」。
      hint: "含合併事件的累計次數",
    },
    { label: "未結案事件", value: formatNumber(summary.unresolved_count) },
    {
      label: "平均嚴重度",
      value: summary.avg_severity === null ? "—" : summary.avg_severity.toFixed(2),
      hint: "1 輕微 ~ 5 極嚴重",
    },
    {
      label: "高嚴重度事件",
      value: formatNumber(summary.high_severity_count),
      hint: "嚴重度 4 級以上",
    },
    { label: "死亡人數", value: formatNumber(summary.total_casualties) },
    {
      label: "受傷人數",
      value: formatNumber(summary.total_injured),
      hint: `其中重傷 ${formatNumber(summary.total_severe_injured)} 人`,
    },
    { label: "受困人數", value: formatNumber(summary.total_trapped) },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border bg-white p-4">
          <div className="text-xs text-gray-500">{card.label}</div>
          <div
            className={`mt-1 tabular-nums font-bold ${
              card.emphasis ? "text-3xl text-red-600" : "text-2xl text-gray-800"
            }`}
          >
            {card.value}
          </div>
          {card.hint && (
            <div className="mt-1 text-xs text-gray-400">{card.hint}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export default SummaryCards;
