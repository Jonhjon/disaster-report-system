// AI 對話通報主畫面
import { useEffect, useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { CandidateSelectionView } from '../components/chat/CandidateSelectionView';
import { ChatMessageView } from '../components/chat/ChatMessageView';
import { PhotoUploaderView } from '../components/chat/PhotoUploaderView';
import { ReportSummaryView } from '../components/chat/ReportSummaryView';
import { useSSEChat } from '../hooks/useSSEChat';
import { useSessionStore } from '../stores/sessionStore';
import type { ChatMessage } from '../types';

export function ChatScreen() {
  const [input, setInput] = useState('');
  const verifiedPhone = useSessionStore(s => s.verifiedPhone);
  const {
    messages,
    isLoading,
    pendingCandidates,
    reportResult,
    attachments,
    addAttachment,
    removeAttachment,
    sendMessage,
    selectCandidate,
  } = useSSEChat();
  const listRef = useRef<FlatList<ChatMessage>>(null);

  useEffect(() => {
    listRef.current?.scrollToEnd({ animated: true });
  }, [messages, pendingCandidates, reportResult]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    sendMessage(text);
  };

  const hasContent = messages.length > 0 || pendingCandidates || reportResult;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {verifiedPhone && (
        <View style={styles.phoneBanner}>
          <Text style={styles.phoneBannerText}>
            ✓ 已自動帶入電話：{verifiedPhone}
          </Text>
        </View>
      )}

      <FlatList
        ref={listRef}
        style={styles.messageList}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => <ChatMessageView message={item} />}
        ListEmptyComponent={
          !hasContent ? (
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>智慧災害通報助手</Text>
              <Text style={styles.emptyText}>
                請描述您要通報的災情，AI 助手會引導您完成通報
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          <View>
            {pendingCandidates && (
              <CandidateSelectionView
                candidates={pendingCandidates}
                onSelect={selectCandidate}
              />
            )}
            {reportResult && <ReportSummaryView result={reportResult} />}
            {isLoading && (
              <View style={styles.thinking}>
                <Text style={styles.thinkingText}>處理中…</Text>
              </View>
            )}
          </View>
        }
      />

      <View style={styles.inputRow}>
        <PhotoUploaderView
          attachments={attachments}
          onAdd={addAttachment}
          onRemove={removeAttachment}
          disabled={isLoading}
        />
        <View style={styles.sendRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="請描述災情狀況..."
            placeholderTextColor="#9ca3af"
            multiline
            editable={!isLoading}
          />
          <Pressable
            style={({ pressed }) => [
              styles.sendBtn,
              (isLoading || !input.trim()) && styles.sendBtnDisabled,
              pressed && styles.sendBtnPressed,
            ]}
            onPress={handleSend}
            disabled={isLoading || !input.trim()}
          >
            <Text style={styles.sendBtnText}>
              {isLoading ? '處理中' : '送出'}
            </Text>
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  phoneBanner: {
    backgroundColor: '#ecfeff',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#a5f3fc',
  },
  phoneBannerText: { fontSize: 12, color: '#0e7490' },
  messageList: { flex: 1, paddingVertical: 8 },
  empty: { padding: 32, alignItems: 'center' },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 8,
  },
  emptyText: { fontSize: 13, color: '#6b7280', textAlign: 'center' },
  thinking: { padding: 12, alignItems: 'center' },
  thinkingText: { fontSize: 12, color: '#9ca3af' },
  inputRow: {
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
    backgroundColor: '#fff',
    padding: 8,
  },
  sendRow: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 6 },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
    color: '#111827',
    maxHeight: 100,
    backgroundColor: '#fff',
  },
  sendBtn: {
    marginLeft: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#dc2626',
    borderRadius: 8,
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.5 },
  sendBtnPressed: { opacity: 0.7 },
  sendBtnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});
