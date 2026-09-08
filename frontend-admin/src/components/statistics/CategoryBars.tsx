import type { CategoryCount } from "../../types";

interface CategoryBarsProps {
  title: string;
  items: CategoryCount[];
  labelFor: (key: string) => string;
  colorFor: (key: string) => string;
}

/**
 * 分類長條圖。
 *
 * 刻意用 Tailwind div 而非 SVG：中文標籤加數字加百分比，用 SVG 手刻文字排版
 * 既麻煩、文字又不能選取，而 div 版本自帶 RWD 與可存取性。
 */
function CategoryBars({ title, items, labelFor, colorFor }: CategoryBarsProps) {
  // 分母護欄：全為 0 或空陣列時不能拿來當除數
  const maxCount = items.reduce((max, item) => Math.max(max, item.count), 0);

  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-gray-700">{title}</h2>
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">此區間沒有資料</p>
      ) : (
        <div className="space-y-1.5">
          {items.map((item) => (
            <div key={item.key} className="flex items-center gap-3">
              <span
                className="w-24 shrink-0 truncate text-sm text-gray-700"
                title={labelFor(item.key)}
              >
                {labelFor(item.key)}
              </span>
              <div className="h-5 flex-1 overflow-hidden rounded bg-gray-100">
                <div
                  className="h-5 rounded"
                  style={{
                    width: `${(item.count / Math.max(maxCount, 1)) * 100}%`,
                    backgroundColor: colorFor(item.key),
                  }}
                  role="meter"
                  aria-valuenow={item.count}
                  aria-valuemin={0}
                  aria-valuemax={maxCount}
                  aria-label={`${labelFor(item.key)} ${item.count} 件`}
                />
              </div>
              <span className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-600">
                {item.count}（{item.percentage}%）
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default CategoryBars;
