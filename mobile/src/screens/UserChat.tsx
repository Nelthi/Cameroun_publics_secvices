import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, Animated, Dimensions, FlatList, KeyboardAvoidingView, Platform, Pressable,
  StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { api } from '../api';
import { Badge, Button, IconButton, formatDate, useToast } from '../components/ui';
import { colors, radius, shadow } from '../theme';
import type { ChatMessage, Conversation } from '../types';

const DRAWER_WIDTH = Math.min(320, Dimensions.get('window').width * 0.84);
const SUGGESTIONS = [
  'Quelles sont les pièces à fournir pour la CNI ?',
  'Comment faire le pré-enrôlement en ligne ?',
  'Combien de temps pour produire ma carte ?',
];

function statusBadge(status: string | null) {
  switch (status) {
    case 'approved': return <Badge label="Réponse vérifiée" tone="success" />;
    case 'partial': return <Badge label="Réponse partielle" tone="warn" />;
    case 'refused': return <Badge label="Information introuvable" tone="danger" />;
    case 'needs_clarification': return <Badge label="Précision demandée" tone="info" />;
    case 'error': return <Badge label="Service indisponible" tone="danger" />;
    default: return null;
  }
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user';
  return (
    <View style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}>
      {!mine ? (
        <View style={styles.avatar}><Ionicons name="shield-checkmark" size={16} color="#fff" /></View>
      ) : null}
      <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}>
        {!mine ? <View style={{ marginBottom: 6 }}>{statusBadge(message.status)}</View> : null}
        <Text style={[styles.bubbleText, mine && { color: '#fff' }]}>{message.content}</Text>
        {!mine && message.sources.length > 0 ? (
          <View style={styles.sources}>
            <Text style={styles.sourcesLabel}>Sources</Text>
            {message.sources.map((s, i) => (
              <View key={`${s.document_id}-${s.source_page}-${i}`} style={styles.sourceChip}>
                <Ionicons name="document-text-outline" size={13} color={colors.primaryDark} />
                <Text style={styles.sourceText} numberOfLines={1}>{s.title ?? s.document_id} · p. {s.source_page}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}

export function UserChat(props: { onExit: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [title, setTitle] = useState('Nouvelle discussion');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const slide = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const toast = useToast();

  const refreshList = useCallback(async () => {
    try {
      setConversations(await api.conversations());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { void refreshList(); }, [refreshList]);

  const toggleDrawer = (open: boolean) => {
    setDrawerOpen(open);
    Animated.timing(slide, { toValue: open ? 0 : -DRAWER_WIDTH, duration: 220, useNativeDriver: true }).start();
  };

  const openConversation = async (id: string) => {
    toggleDrawer(false);
    setError(null);
    try {
      const data = await api.conversation(id);
      setActiveId(id);
      setTitle(data.title);
      setMessages(data.messages);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const newConversation = () => {
    toggleDrawer(false);
    setActiveId(null);
    setTitle('Nouvelle discussion');
    setMessages([]);
    setError(null);
  };

  const removeConversation = (c: Conversation) => {
    Alert.alert('Supprimer la discussion', `« ${c.title} » sera supprimée.`, [
      { text: 'Annuler', style: 'cancel' },
      {
        text: 'Supprimer', style: 'destructive',
        onPress: async () => {
          try {
            await api.deleteConversation(c.id);
            if (c.id === activeId) newConversation();
            await refreshList();
          } catch (e) {
            setError((e as Error).message);
          }
        },
      },
    ]);
  };

  const send = async (override?: string) => {
    const question = (override ?? text).trim();
    if (!question || sending) return;
    setText('');
    setError(null);
    setSending(true);
    const optimistic: ChatMessage = { id: -Date.now(), role: 'user', content: question, status: null, sources: [], request_id: null, created_at: new Date().toISOString() };
    setMessages((m) => [...m, optimistic]);
    try {
      let id = activeId;
      if (!id) {
        const created = await api.createConversation();
        id = created.id;
        setActiveId(id);
      }
      const reply = await api.sendMessage(id, question);
      const data = await api.conversation(id);
      setTitle(data.title);
      setMessages(data.messages.length ? data.messages : [optimistic, reply]);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(t);
  }, [messages, sending]);

  return (
    <SafeAreaView style={styles.root} edges={['top', 'left', 'right']}>
      <View style={styles.header}>
        <IconButton icon="menu" color="#fff" onPress={() => toggleDrawer(true)} />
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>{title}</Text>
          <Text style={styles.headerSub}>Réponses issues des documents officiels</Text>
        </View>
        <IconButton icon="log-out-outline" color="#fff" onPress={props.onExit} />
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {messages.length === 0 ? (
          <View style={styles.welcome}>
            <View style={styles.welcomeIcon}><Ionicons name="chatbubbles" size={34} color={colors.primary} /></View>
            <Text style={styles.welcomeTitle}>Comment puis-je vous aider ?</Text>
            <Text style={styles.welcomeText}>Posez une question sur la procédure de votre choix. Chaque réponse cite ses sources.</Text>
            <View style={{ gap: 8, marginTop: 18, alignSelf: 'stretch' }}>
              {SUGGESTIONS.map((s) => (
                <Pressable key={s} style={styles.suggestion} onPress={() => void send(s)}>
                  <Ionicons name="sparkles-outline" size={16} color={colors.primary} />
                  <Text style={styles.suggestionText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(m) => String(m.id)}
            renderItem={({ item }) => <Bubble message={item} />}
            contentContainerStyle={{ padding: 14, gap: 12 }}
            ListFooterComponent={sending ? (
              <View style={[styles.row, styles.rowTheirs]}>
                <View style={styles.avatar}><Ionicons name="shield-checkmark" size={16} color="#fff" /></View>
                <View style={[styles.bubble, styles.bubbleTheirs, { flexDirection: 'row', alignItems: 'center', gap: 8 }]}>
                  <ActivityIndicator size="small" color={colors.primary} />
                  <Text style={{ color: colors.muted, fontSize: 14 }}>Recherche dans les documents…</Text>
                </View>
              </View>
            ) : undefined}
          />
        )}

        {error ? (
          <View style={styles.error}><Ionicons name="alert-circle" size={16} color={colors.danger} /><Text style={styles.errorText}>{error}</Text></View>
        ) : null}

        <View style={styles.composer}>
          <IconButton icon="attach" onPress={() => toast.show('Pièces jointes : bientôt disponible')} color={colors.muted} />
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="Posez votre question…"
            placeholderTextColor="#9AA7A1"
            multiline
            maxLength={2000}
          />
          <IconButton icon="mic-outline" onPress={() => toast.show('Saisie vocale : bientôt disponible')} color={colors.muted} />
          <Pressable
            onPress={() => void send()}
            disabled={!text.trim() || sending}
            style={[styles.send, { opacity: !text.trim() || sending ? 0.45 : 1 }]}
          >
            <Ionicons name="send" size={18} color="#fff" />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
      {toast.node}

      {drawerOpen ? <Pressable style={styles.scrim} onPress={() => toggleDrawer(false)} /> : null}
      <Animated.View pointerEvents={drawerOpen ? 'auto' : 'none'} style={[styles.drawer, { transform: [{ translateX: slide }] }]}>
        <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
          <View style={styles.drawerHead}>
            <Ionicons name="shield-checkmark" size={22} color={colors.primary} />
            <Text style={styles.drawerTitle}>Mes discussions</Text>
          </View>
          <View style={{ paddingHorizontal: 14 }}>
            <Button label="Nouvelle discussion" icon="add" onPress={newConversation} />
          </View>
          <FlatList
            data={conversations}
            keyExtractor={(c) => c.id}
            contentContainerStyle={{ padding: 14, gap: 6 }}
            ListEmptyComponent={<Text style={styles.drawerEmpty}>Aucune discussion pour l'instant.</Text>}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => void openConversation(item.id)}
                onLongPress={() => removeConversation(item)}
                style={[styles.convItem, item.id === activeId && styles.convActive]}
              >
                <Ionicons name="chatbubble-ellipses-outline" size={18} color={colors.primaryDark} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.convTitle} numberOfLines={1}>{item.title}</Text>
                  <Text style={styles.convDate}>{formatDate(item.updated_at)}</Text>
                </View>
                <IconButton icon="trash-outline" size={18} color={colors.muted} onPress={() => removeConversation(item)} />
              </Pressable>
            )}
          />
        </SafeAreaView>
      </Animated.View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.primary, paddingHorizontal: 8, paddingVertical: 10 },
  headerTitle: { color: '#fff', fontSize: 16.5, fontWeight: '700' },
  headerSub: { color: '#BFDCD2', fontSize: 11.5, marginTop: 1 },
  welcome: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  welcomeIcon: { width: 72, height: 72, borderRadius: 24, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  welcomeTitle: { fontSize: 21, fontWeight: '800', color: colors.text, marginTop: 16 },
  welcomeText: { fontSize: 14, color: colors.muted, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  suggestion: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 13 },
  suggestionText: { flex: 1, color: colors.text, fontSize: 14 },
  row: { flexDirection: 'row', alignItems: 'flex-end', gap: 8 },
  rowMine: { justifyContent: 'flex-end' },
  rowTheirs: { justifyContent: 'flex-start' },
  avatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  bubble: { maxWidth: '82%', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10 },
  bubbleMine: { backgroundColor: colors.primary, borderBottomRightRadius: 4 },
  bubbleTheirs: { backgroundColor: colors.surface, borderBottomLeftRadius: 4, borderWidth: 1, borderColor: colors.border },
  bubbleText: { fontSize: 15, lineHeight: 22, color: colors.text },
  sources: { marginTop: 10, gap: 6, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 },
  sourcesLabel: { fontSize: 11, fontWeight: '700', color: colors.muted, textTransform: 'uppercase', letterSpacing: 0.6 },
  sourceChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.primarySoft, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5, alignSelf: 'flex-start', maxWidth: '100%' },
  sourceText: { fontSize: 12, color: colors.primaryDark, fontWeight: '600', flexShrink: 1 },
  error: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: colors.dangerSoft, marginHorizontal: 12, padding: 10, borderRadius: radius.sm },
  errorText: { color: colors.danger, fontSize: 13, flex: 1 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 2, padding: 8, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  input: { flex: 1, maxHeight: 120, minHeight: 42, backgroundColor: '#F1F4F2', borderRadius: 21, paddingHorizontal: 14, paddingTop: 10, paddingBottom: 10, fontSize: 15, color: colors.text },
  send: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', marginLeft: 2 },
  scrim: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(10,30,24,0.45)' },
  drawer: { position: 'absolute', top: 0, bottom: 0, left: 0, width: DRAWER_WIDTH, backgroundColor: colors.surface, ...shadow },
  drawerHead: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 18 },
  drawerTitle: { fontSize: 18, fontWeight: '800', color: colors.text },
  drawerEmpty: { color: colors.muted, textAlign: 'center', marginTop: 24, fontSize: 13.5 },
  convItem: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: radius.md },
  convActive: { backgroundColor: colors.primarySoft },
  convTitle: { fontSize: 14.5, fontWeight: '600', color: colors.text },
  convDate: { fontSize: 11.5, color: colors.muted, marginTop: 2 },
});
