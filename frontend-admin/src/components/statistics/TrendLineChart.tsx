import type { TrendPoint, TrendBucket } from "../../types";
import { TREND_BUCKET_LABELS } from "../../types";
import {
  CHART,
  buildAreaPath,
  buildLinePath,
  niceMax,
  niceTicks,
  tickIndices,
  xAt,
  yAt,
} from "../../utils/statsChart";

interface TrendLineChartProps {
  points: TrendPoint[];
  bucket: TrendBucket;
}

function TrendLineChart({ points, bucket }: TrendLineChartProps) {
  const counts = points.map((p) => p.count);
  const yMax = niceMax(counts.reduce((max, c) => Math.max(max, c), 0));
  const linePath = buildLinePath(counts, yMax);
  const areaPath = buildAreaPath(counts, yMax);
  const labelIndices = tickIndices(points.length);
  const bucketLabel = TREND_BUCKET_LABELS[bucket];

  return (
    <section className="rounded-lg border bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-gray-700">時間趨勢</h2>
        <span className="text-xs text-gray-400">
          以{bucketLabel}分桶，依事件發生時間計算
        </span>
      </div>

      {points.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-400">此區間沒有資料</p>
      ) : (
        // 固定 viewBox + 橫向捲動：等比縮放會連文字一起縮小，
        // 手機上 12px 的軸標籤會變得無法閱讀。
        <div className="overflow-x-auto">
          <svg
            viewBox={`0 0 ${CHART.w} ${CHART.h}`}
            className="h-auto w-full min-w-[640px]"
            aria-hidden="true"
          >
            {/* y 軸格線與刻度 */}
            {niceTicks(yMax).map((tick) => (
              <g key={tick}>
                <line
                  x1={CHART.left}
                  y1={yAt(tick, yMax)}
                  x2={CHART.w - CHART.right}
                  y2={yAt(tick, yMax)}
                  stroke="#e5e7eb"
                  strokeWidth={1}
                />
                <text
                  x={CHART.left - 8}
                  y={yAt(tick, yMax)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={11}
                  fill="#9ca3af"
                >
                  {tick}
                </text>
              </g>
            ))}

            {areaPath && <path d={areaPath} fill="#dbeafe" />}
            {linePath && (
              <path d={linePath} fill="none" stroke="#2563eb" strokeWidth={2} />
            )}

            {points.map((point, i) => (
              <g key={point.bucket_start}>
                <circle
                  cx={xAt(i, points.length)}
                  cy={yAt(point.count, yMax)}
                  r={3}
                  fill="#2563eb"
                />
                {/* 擴大命中區 + 原生 <title>：零 JS 狀態的 tooltip，螢幕閱讀器也讀得到 */}
                <circle
                  cx={xAt(i, points.length)}
                  cy={yAt(point.count, yMax)}
                  r={10}
                  fill="transparent"
                >
                  <title>{`${point.bucket_start}：${point.count} 件`}</title>
                </circle>
              </g>
            ))}

            {/* x 軸標籤（抽稀，避免分桶過多時重疊） */}
            {labelIndices.map((i) => (
              <text
                key={points[i].bucket_start}
                x={xAt(i, points.length)}
                y={CHART.h - CHART.bottom + 18}
                textAnchor="middle"
                fontSize={11}
                fill="#9ca3af"
              >
                {points[i].bucket_start.slice(5)}
              </text>
            ))}
          </svg>
          <table className="sr-only">
            <caption>災情事件時間趨勢資料</caption>
            <thead>
              <tr>
                <th scope="col">分桶日期</th>
                <th scope="col">事件件數</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.bucket_start}>
                  <th scope="row">{point.bucket_start}</th>
                  <td>{point.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default TrendLineChart;
