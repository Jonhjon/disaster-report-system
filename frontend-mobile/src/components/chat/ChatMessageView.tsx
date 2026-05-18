// 單則對話訊息（user / assistant）
import { StyleSheet, Text, View } from 'react-native';
import type { ChatMessage } from '../../types';

interface ChatMessageViewProps {
  message: ChatMessage;
}

export function ChatMessageView({ message }: ChatMessageViewProps) {
  const isUser = message.role === 'user';
  return (
    <View
      style={[
        styles.row,
        isUser ? styles.rowRight : styles.rowLeft,
      ]}
    >
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAssistant,
        ]}
      >
        <Text
          style={[styles.text, isUser ? styles.textUser : styles.textAssistant]}
        >
          {message.content}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginVertical: 4,
    paddingHorizontal: 8,
  },
  rowLeft: { justifyContent: 'flex-start' },
  rowRight: { justifyContent: 'flex-end' },
  bubble: {
    maxWidth: '80%',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
  },
  bubbleUser: { backgroundColor: '#dc2626' },
  bubbleAssistant: { backgroundColor: '#f3f4f6' },
  text: { fontSize: 14, lineHeight: 20 },
  textUser: { color: '#fff' },
  textAssistant: { color: '#111827' },
});
