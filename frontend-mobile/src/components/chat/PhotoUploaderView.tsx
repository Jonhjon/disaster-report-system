// 照片附件上傳：相機 / 相簿 -> 上傳到後端 -> 顯示縮圖
import { useState } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { launchCamera, launchImageLibrary, type Asset } from 'react-native-image-picker';
import { MAX_PHOTOS_PER_REPORT, uploadPhoto } from '../../api/uploadClient';
import type { AttachmentOut } from '../../types';

interface Props {
  attachments: AttachmentOut[];
  onAdd: (a: AttachmentOut) => void;
  onRemove: (id: string) => void;
  disabled?: boolean;
}

export function PhotoUploaderView({ attachments, onAdd, onRemove, disabled }: Props) {
  const [busy, setBusy] = useState(false);

  const upload = async (asset: Asset) => {
    if (!asset.uri) return;
    setBusy(true);
    try {
      const result = await uploadPhoto({
        uri: asset.uri,
        fileName: asset.fileName,
        type: asset.type,
        fileSize: asset.fileSize,
      });
      onAdd(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '上傳失敗';
      Alert.alert('上傳失敗', msg);
    } finally {
      setBusy(false);
    }
  };

  const pickFromCamera = async () => {
    if (attachments.length >= MAX_PHOTOS_PER_REPORT) {
      Alert.alert('已達上限', `最多 ${MAX_PHOTOS_PER_REPORT} 張`);
      return;
    }
    const res = await launchCamera({ mediaType: 'photo', quality: 0.8 });
    const asset = res.assets?.[0];
    if (asset) await upload(asset);
  };

  const pickFromLibrary = async () => {
    if (attachments.length >= MAX_PHOTOS_PER_REPORT) {
      Alert.alert('已達上限', `最多 ${MAX_PHOTOS_PER_REPORT} 張`);
      return;
    }
    const res = await launchImageLibrary({
      mediaType: 'photo',
      quality: 0.8,
      selectionLimit: 1,
    });
    const asset = res.assets?.[0];
    if (asset) await upload(asset);
  };

  return (
    <View style={styles.container}>
      <View style={styles.thumbRow}>
        {attachments.map((a) => (
          <View key={a.id} style={styles.thumb}>
            <Image source={{ uri: a.url }} style={styles.thumbImage} />
            <Pressable style={styles.removeBtn} onPress={() => onRemove(a.id)}>
              <Text style={styles.removeText}>×</Text>
            </Pressable>
          </View>
        ))}
        {busy && (
          <View style={styles.thumb}>
            <ActivityIndicator />
          </View>
        )}
      </View>
      <View style={styles.btnRow}>
        <Pressable
          style={({ pressed }) => [styles.btn, (disabled || busy) && styles.btnDisabled, pressed && styles.btnPressed]}
          onPress={pickFromCamera}
          disabled={disabled || busy}
        >
          <Text style={styles.btnText}>📷 拍照</Text>
        </Pressable>
        <Pressable
          style={({ pressed }) => [styles.btn, (disabled || busy) && styles.btnDisabled, pressed && styles.btnPressed]}
          onPress={pickFromLibrary}
          disabled={disabled || busy}
        >
          <Text style={styles.btnText}>🖼 相簿</Text>
        </Pressable>
        <Text style={styles.counter}>
          {attachments.length} / {MAX_PHOTOS_PER_REPORT}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingVertical: 4 },
  thumbRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: 6,
    backgroundColor: '#f3f4f6',
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  thumbImage: { width: '100%', height: '100%' },
  removeBtn: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  removeText: { color: '#fff', fontSize: 12, lineHeight: 14 },
  btnRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6, gap: 6 },
  btn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#d1d5db',
    backgroundColor: '#fff',
  },
  btnDisabled: { opacity: 0.5 },
  btnPressed: { opacity: 0.7 },
  btnText: { fontSize: 13, color: '#374151' },
  counter: { fontSize: 12, color: '#6b7280', marginLeft: 'auto' },
});
