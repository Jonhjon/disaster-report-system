// 啟動畫面：呼叫 Phone Number Hint 取得電話、請求 GPS 後跳轉
import { useEffect, useRef } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { usePhoneNumberHint } from '../hooks/usePhoneNumberHint';
import { useGeolocation } from '../hooks/useGeolocation';

interface Props {
  onReady: () => void;
}

export function SplashScreen({ onReady }: Props) {
  const { request: requestPhone } = usePhoneNumberHint();
  const { request: requestLocation } = useGeolocation();
  const triggered = useRef(false);

  useEffect(() => {
    if (triggered.current) return;
    triggered.current = true;
    (async () => {
      // 先電話、再 GPS；皆容許失敗
      await requestPhone();
      await requestLocation();
      onReady();
    })();
  }, [onReady, requestPhone, requestLocation]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>智慧災害通報</Text>
      <Text style={styles.subtitle}>正在準備您的裝置...</Text>
      <ActivityIndicator size="large" color="#dc2626" style={styles.spinner} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  title: { fontSize: 28, fontWeight: '700', color: '#111827', marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#6b7280', marginBottom: 32 },
  spinner: { marginTop: 16 },
});
