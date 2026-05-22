// 通報送出後的結果摘要
import { StyleSheet, Text, View } from 'react-native';

interface Props {
  result: Record<string, unknown>;
}

export function ReportSummaryView({ result }: Props) {
  const status = String(result.status ?? '');
  const message = String(result.message ?? '');
  const eventId = result.event_id ? String(result.event_id) : null;
  const geocodedAddress = result.geocoded_address
    ? String(result.geocoded_address)
    : null;
  const possibleDup = result.possible_duplicate_event_id
    ? String(result.possible_duplicate_event_id)
    : null;

  const isSuccess = status === 'created' || status === 'merged';

  return (
    <View style={[styles.box, isSuccess ? styles.boxSuccess : styles.boxError]}>
      <Text style={styles.title}>
        {isSuccess ? '✓ 通報已送出' : '⚠ 通報處理'}
      </Text>
      <Text style={styles.message}>{message || status}</Text>
      {geocodedAddress && (
        <Text style={styles.meta}>地點：{geocodedAddress}</Text>
      )}
      {possibleDup && (
        <Text style={styles.warn}>⚠ 偵測到可能與另一筆通報重複</Text>
      )}
      {eventId && <Text style={styles.meta}>事件 ID：{eventId}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    padding: 12,
    borderRadius: 8,
    marginVertical: 8,
    marginHorizontal: 8,
    borderLeftWidth: 4,
  },
  boxSuccess: { backgroundColor: '#ecfdf5', borderLeftColor: '#10b981' },
  boxError: { backgroundColor: '#fef2f2', borderLeftColor: '#ef4444' },
  title: { fontSize: 15, fontWeight: '700', marginBottom: 4, color: '#111827' },
  message: { fontSize: 14, color: '#374151', lineHeight: 20 },
  meta: { fontSize: 12, color: '#6b7280', marginTop: 4 },
  warn: { fontSize: 12, color: '#b45309', marginTop: 4 },
});
