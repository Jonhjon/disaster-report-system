import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import EventDetail from "../components/events/EventDetail";
import { getEvent, getEventReports, updateEvent, deleteEvent } from "../services/api";
import type { DisasterEvent, DisasterReport, EventUpdateData } from "../types";

function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<DisasterEvent | null>(null);
  const [reports, setReports] = useState<DisasterReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([getEvent(id), getEventReports(id)])
      .then(([eventData, reportsData]) => {
        setEvent(eventData);
        setReports(reportsData.items);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const navigate = useNavigate();

  const handleUpdate = async (data: Record<string, unknown>) => {
    if (!id) return;
    const updated = await updateEvent(id, data as EventUpdateData);
    setEvent(updated);
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteEvent(id);
      navigate("/events");
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    }
  };

  if (loading) {
    return <div className="py-12 text-center text-gray-400">載入中...</div>;
  }

  if (error || !event) {
    return (
      <div className="py-12 text-center">
        <p className="text-red-500">{error || "找不到此事件"}</p>
        <Link to="/events" className="mt-2 text-sm text-blue-600 hover:underline">
          返回災情列表
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Link
          to="/events"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← 返回災情列表
        </Link>
      </div>
      <EventDetail event={event} reports={reports} onUpdate={handleUpdate} onDelete={handleDelete} />
    </div>
  );
}

export default EventDetailPage;
