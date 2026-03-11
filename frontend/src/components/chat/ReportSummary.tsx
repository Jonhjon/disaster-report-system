import { Link } from "react-router-dom";

function ReportSummary({ result }: { result: Record<string, unknown> }) {
  const isNew = result.status === "created";

  return (
    <div
      className={`mx-4 my-3 rounded-lg border-2 p-4 ${
        isNew ? "border-green-300 bg-green-50" : "border-blue-300 bg-blue-50"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-lg">{isNew ? "✅" : "🔄"}</span>
        <span className="font-semibold">
          {isNew ? "通報成功 - 已建立新事件" : "通報成功 - 已合併至現有事件"}
        </span>
      </div>
      <p className="mb-2 text-sm text-gray-600">
        {result.message as string}
      </p>
      {Boolean(result.event_id) && (
        <Link
          to={`/events/${result.event_id}`}
          className="text-sm text-blue-600 hover:underline"
        >
          查看災情事件詳情
        </Link>
      )}
    </div>
  );
}

export default ReportSummary;
