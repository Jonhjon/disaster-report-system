// GPS 定位 hook：取得使用者當前座標，存入 sessionStore
import { useCallback, useState } from 'react';
import { PermissionsAndroid, Platform } from 'react-native';
import Geolocation from 'react-native-geolocation-service';
import { useSessionStore } from '../stores/sessionStore';
import type { DeviceLocation } from '../types';

interface UseGeolocation {
  loading: boolean;
  error: string | null;
  request: () => Promise<DeviceLocation | null>;
}

async function ensurePermission(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  const granted = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
    {
      title: '取得您的位置',
      message: '需要您的位置以準確標註災情地點',
      buttonPositive: '允許',
      buttonNegative: '拒絕',
    },
  );
  return granted === PermissionsAndroid.RESULTS.GRANTED;
}

export function useGeolocation(): UseGeolocation {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setDeviceLocation = useSessionStore((s) => s.setDeviceLocation);

  const request = useCallback(async (): Promise<DeviceLocation | null> => {
    setLoading(true);
    setError(null);
    try {
      const ok = await ensurePermission();
      if (!ok) {
        setError('未授權位置權限');
        return null;
      }
      const loc = await new Promise<DeviceLocation>((resolve, reject) => {
        Geolocation.getCurrentPosition(
          (pos) => {
            resolve({
              lat: pos.coords.latitude,
              lng: pos.coords.longitude,
              accuracy_m: pos.coords.accuracy ?? undefined,
            });
          },
          (err) => reject(new Error(err.message)),
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
        );
      });
      setDeviceLocation(loc);
      return loc;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '取得 GPS 位置失敗';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [setDeviceLocation]);

  return { loading, error, request };
}
