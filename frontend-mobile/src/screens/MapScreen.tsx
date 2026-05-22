// 災情地圖：抓 /api/events/map 渲染標記
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import { getMapEvents } from '../api/eventsClient';
import {
  DISASTER_TYPE_COLORS,
  DISASTER_TYPE_LABELS,
  type EventMapItem,
} from '../types';
import { useSessionStore } from '../stores/sessionStore';

const TAIWAN_CENTER = {
  latitude: 23.7,
  longitude: 121.0,
  latitudeDelta: 3.0,
  longitudeDelta: 3.0,
};

export function MapScreen() {
  const [events, setEvents] = useState<EventMapItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deviceLocation = useSessionStore(s => s.deviceLocation);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getMapEvents()
      .then(items => {
        if (cancelled) return;
        setEvents(items);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : '載入事件失敗');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const initialRegion = deviceLocation
    ? {
        latitude: deviceLocation.lat,
        longitude: deviceLocation.lng,
        latitudeDelta: 0.05,
        longitudeDelta: 0.05,
      }
    : TAIWAN_CENTER;

  return (
    <View style={styles.container}>
      <MapView
        style={styles.map}
        provider={PROVIDER_GOOGLE}
        initialRegion={initialRegion}
      >
        {deviceLocation && (
          <Marker
            coordinate={{
              latitude: deviceLocation.lat,
              longitude: deviceLocation.lng,
            }}
            title="我的位置"
            pinColor="#2563eb"
          />
        )}
        {events.map(e => (
          <Marker
            key={e.id}
            coordinate={{ latitude: e.latitude, longitude: e.longitude }}
            title={e.title}
            description={`${DISASTER_TYPE_LABELS[e.disaster_type]} ・ 嚴重度 ${
              e.severity
            }`}
            pinColor={DISASTER_TYPE_COLORS[e.disaster_type]}
          />
        ))}
      </MapView>
      {loading && (
        <View style={styles.overlay}>
          <ActivityIndicator size="large" color="#dc2626" />
        </View>
      )}
      {error && (
        <View style={styles.errorBar}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  map: { flex: 1 },
  overlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(255,255,255,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorBar: {
    position: 'absolute',
    bottom: 16,
    left: 16,
    right: 16,
    backgroundColor: '#fef2f2',
    borderRadius: 8,
    padding: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
  },
  errorText: { color: '#991b1b', fontSize: 13 },
});
