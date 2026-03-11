import { useEffect, useState } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import EventMarker from "./EventMarker";
import MapFilters from "./MapFilters";
import { getMapEvents } from "../../services/api";
import type { EventMapItem, DisasterType } from "../../types";

// Fix default marker icon issue with bundlers
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";
const DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow });
L.Marker.prototype.options.icon = DefaultIcon;

function MapEventLoader({
  filters,
  onEventsLoaded,
}: {
  filters: { disaster_type?: string; severity_min?: number; status?: string };
  onEventsLoaded: (items: EventMapItem[]) => void;
}) {
  const map = useMap();

  useEffect(() => {
    const loadEvents = async () => {
      const bounds = map.getBounds();
      const boundsStr = `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`;
      const data = await getMapEvents({ bounds: boundsStr, ...filters });
      onEventsLoaded(data.items);
    };

    loadEvents();
    map.on("moveend", loadEvents);
    return () => {
      map.off("moveend", loadEvents);
    };
  }, [map, filters, onEventsLoaded]);

  return null;
}

function DisasterMap() {
  const [events, setEvents] = useState<EventMapItem[]>([]);
  const [filters, setFilters] = useState<{
    disaster_type?: DisasterType;
    severity_min?: number;
    status: string;
  }>({ status: "active" });

  return (
    <div className="flex h-full flex-col">
      <MapFilters filters={filters} onChange={setFilters} />
      <div className="flex-1">
        <MapContainer
          center={[23.5, 121.0]}
          zoom={7}
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapEventLoader filters={filters} onEventsLoaded={setEvents} />
          {events.map((event) => (
            <EventMarker key={event.id} event={event} />
          ))}
        </MapContainer>
      </div>
    </div>
  );
}

export default DisasterMap;
