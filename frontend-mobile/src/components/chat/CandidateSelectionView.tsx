// 相似事件候選清單，使用者可選合併或建立新事件
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { EventCandidate } from '../../types';

interface Props {
  candidates: EventCandidate[];
  onSelect: (eventId: string) => void;
}

export function CandidateSelectionView({ candidates, onSelect }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>系統偵測到附近的相似事件：</Text>
      {candidates.map((c) => (
        <Pressable
          key={c.event_id}
          onPress={() => onSelect(c.event_id)}
          style={({ pressed }) => [
            styles.card,
            pressed && styles.cardPressed,
          ]}
        >
          <Text style={styles.cardTitle}>{c.title}</Text>
          <Text style={styles.meta}>
            地點：{c.location_text}・距離 {Math.round(c.distance_m)} 公尺・通報 {c.report_count} 筆
          </Text>
          <Text numberOfLines={2} style={styles.desc}>{c.description}</Text>
        </Pressable>
      ))}
      <Pressable
        onPress={() => onSelect('new')}
        style={({ pressed }) => [
          styles.card,
          styles.cardNew,
          pressed && styles.cardPressed,
        ]}
      >
        <Text style={styles.cardTitleNew}>建立全新事件（此通報與上述無關）</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 8 },
  title: { fontSize: 14, fontWeight: '600', marginBottom: 8, color: '#374151' },
  card: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#d1d5db',
    backgroundColor: '#fff',
    marginBottom: 8,
  },
  cardPressed: { opacity: 0.7 },
  cardNew: { borderColor: '#10b981', backgroundColor: '#f0fdf4' },
  cardTitle: { fontSize: 14, fontWeight: '600', color: '#111827' },
  cardTitleNew: { fontSize: 14, fontWeight: '600', color: '#047857' },
  meta: { fontSize: 12, color: '#6b7280', marginTop: 4 },
  desc: { fontSize: 13, color: '#374151', marginTop: 4 },
});
