const MISSING_LABELS: Record<string, string> = {
  occurred_at: "發生時間",
  casualties: "死亡人數",
  injured: "受傷人數",
  trapped: "受困人數",
  location_text: "精確地點",
  description: "詳細描述",
};

function ReportSummary({ result }: { result: Record<string, unknown> }) {
  const isNew = result.status === "created";
  const needsClarification = result.needs_clarification === true;
  const sessionToken =
    typeof result.session_token === "string" ? result.session_token : null;
  const missingFields = Array.isArray(result.missing_fields)
    ? (result.missing_fields as string[])
    : [];

  const resumeUrl = sessionToken ? `/chat/resume/${sessionToken}` : null;

  return (
    <div
      className={`mx-4 my-3 rounded-lg border-2 p-4 ${
        needsClarification
          ? "border-yellow-300 bg-yellow-50"
          : isNew
            ? "border-green-300 bg-green-50"
            : "border-blue-300 bg-blue-50"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-lg">
          {needsClarification ? "⚠️" : isNew ? "✅" : "🔄"}
        </span>
        <span className="font-semibold">
          {needsClarification
            ? "通報已收到，部分資訊待補充"
            : isNew
              ? "通報成功 - 已建立新事件"
              : "通報成功 - 已合併至現有事件"}
        </span>
      </div>
      <p className="text-sm text-gray-700">{result.message as string}</p>

      {needsClarification && (
        <div className="mt-3 space-y-2 text-sm">
          {missingFields.length > 0 && (
            <p className="text-gray-800">
              仍待補充：
              {missingFields
                .map((f) => MISSING_LABELS[f] ?? f)
                .join("、")}
            </p>
          )}
          <p className="text-gray-700">
            通報中心將透過您偏好的聯絡方式（SMS／LINE／Email）與您聯繫。
          </p>
          {resumeUrl && (
            <div className="rounded border border-yellow-200 bg-white p-2">
              <p className="mb-1 text-xs text-gray-500">
                您也可保留此連結，稍後回來補充：
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate rounded bg-gray-100 px-2 py-1 text-xs">
                  {window.location.origin}
                  {resumeUrl}
                </code>
                <button
                  onClick={() =>
                    navigator.clipboard?.writeText(
                      `${window.location.origin}${resumeUrl}`
                    )
                  }
                  className="rounded bg-yellow-200 px-2 py-1 text-xs font-semibold hover:bg-yellow-300"
                >
                  複製
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ReportSummary;
