import { useEffect, useState, useCallback } from "react";
import EventFilters from "../components/events/EventFilters";
import EventTable from "../components/events/EventTable";
import { getEvents } from "../services/api";
import type { DisasterEvent } from "../types";

function EventListPage() {
  const [events, setEvents] = useState<DisasterEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    search: "",
    disaster_type: "",
    severity_min: "",
    severity_max: "",
    status: "",
    sort_by: "occurred_at",
    sort_order: "desc",
  });
  const [page, setPage] = useState(1);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEvents({
        search: filters.search || undefined,
        disaster_type: filters.disaster_type || undefined,
        severity_min: filters.severity_min
          ? Number(filters.severity_min)
          : undefined,
        severity_max: filters.severity_max
          ? Number(filters.severity_max)
          : undefined,
        status: filters.status || undefined,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
        page,
        page_size: 20,
      });
      setEvents(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">災情列表</h1>
        <span className="text-sm text-gray-500">共 {total} 筆</span>
      </div>
      <EventFilters filters={filters} onChange={setFilters} />
      {loading ? (
        <div className="py-12 text-center text-gray-400">載入中...</div>
      ) : (
        <EventTable
          events={events}
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}

export default EventListPage;
