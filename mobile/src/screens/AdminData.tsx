import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { api } from '../api';
import { Badge, Card, Empty, SectionTitle, Segmented, formatDate } from '../components/ui';
import { colors, radius } from '../theme';
import type { AuditRow, ChunkRow, DocRow, GapRow, VectorsInfo } from '../types';

type Tab = 'text' | 'chunks' | 'vectors' | 'rag';

export function AdminData(props: { documents: DocRow[] }) {
  const [tab, setTab] = useState<Tab>('text');
  const [docId, setDocId] = useState<string | null>(props.documents[0]?.document_id ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState<{ status: string; warnings: string[]; character_count: number | null; segments: { page_number: number | null; text: string }[]; truncated: boolean } | null>(null);
  const [chunks, setChunks] = useState<{ total: number; items: ChunkRow[] } | null>(null);
  const [vectors, setVectors] = useState<VectorsInfo | null>(null);
  const [rag, setRag] = useState<{ requests: AuditRow[]; gaps: GapRow[] } | null>(null);

  useEffect(() => {
    if (!docId && props.documents.length) setDocId(props.documents[0].document_id);
  }, [props.documents, docId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === 'text' && docId) setText(await api.documentText(docId));
      if (tab === 'chunks') setChunks(await api.chunks(docId ?? undefined, 40));
      if (tab === 'vectors') setVectors(await api.vectors(15));
      if (tab === 'rag') setRag(await api.audit());
    } catch (e) {
      setError((e as Error).message);
      if (tab === 'text') setText(null);
    } finally {
      setLoading(false);
    }
  }, [tab, docId]);

  useEffect(() => { void load(); }, [load]);

  const needsDoc = tab === 'text' || tab === 'chunks';

  return (
    <ScrollView contentContainerStyle={styles.scroll}>
      <Segmented value={tab} onChange={setTab} options={[
        { value: 'text', label: 'Texte' }, { value: 'chunks', label: 'Fragments' },
        { value: 'vectors', label: 'Vecteurs' }, { value: 'rag', label: 'RAG' },
      ]} />

      {needsDoc ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 4 }}>
          {props.documents.map((d) => (
            <Pressable key={d.document_id} onPress={() => setDocId(d.document_id)} style={[styles.chip, docId === d.document_id && styles.chipOn]}>
              <Text style={[styles.chipText, docId === d.document_id && { color: '#fff' }]} numberOfLines={1}>{d.title ?? d.document_id}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      {loading ? <ActivityIndicator color={colors.primary} style={{ marginVertical: 18 }} /> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {tab === 'text' && !loading && text ? (
        <>
          <Card>
            <View style={styles.rowBetween}>
              <Text style={styles.strong}>{text.character_count ?? 0} caractères extraits</Text>
              <Badge label={text.status} tone={text.status === 'processed' ? 'success' : 'warn'} />
            </View>
            {text.warnings.map((w, i) => <Text key={i} style={styles.warn}>{w}</Text>)}
          </Card>
          {text.segments.map((s, i) => (
            <Card key={i}>
              <Text style={styles.page}>Page {s.page_number ?? '—'}</Text>
              <Text style={styles.body}>{s.text}</Text>
            </Card>
          ))}
          {text.truncated ? <Text style={styles.muted}>Texte tronqué pour l'affichage.</Text> : null}
        </>
      ) : null}

      {tab === 'chunks' && !loading && chunks ? (
        <>
          <Text style={styles.muted}>{chunks.total} fragment(s) · affichage des {chunks.items.length} premiers</Text>
          {chunks.items.length === 0 ? <Card><Empty icon="cut-outline" text="Aucun fragment : lancez le découpage." /></Card> : null}
          {chunks.items.map((c) => (
            <Card key={c.chunk_id}>
              <View style={styles.rowBetween}>
                <Text style={styles.mono}>{c.chunk_id}</Text>
                <Badge label={`p. ${c.source_page} · ${c.text.length} car.`} tone="info" />
              </View>
              <Text style={styles.body}>{c.text}</Text>
            </Card>
          ))}
        </>
      ) : null}

      {tab === 'vectors' && !loading && vectors ? (
        vectors.built ? (
          <>
            <Card>
              <Text style={styles.strong}>{vectors.total} vecteurs · dimension {vectors.dim}</Text>
              <Text style={styles.muted}>Modèle : {vectors.model} · index : {vectors.index_type}</Text>
            </Card>
            {vectors.items.map((v) => (
              <Card key={v.vector_id}>
                <View style={styles.rowBetween}>
                  <Text style={styles.mono}>#{v.vector_id} · {v.chunk_id}</Text>
                  <Badge label={`norme ${v.norm}`} tone="neutral" />
                </View>
                <Text style={styles.mono}>[{v.first_values.join(', ')}, …]</Text>
                <Text style={styles.muted} numberOfLines={2}>{v.text_preview}</Text>
              </Card>
            ))}
          </>
        ) : <Card><Empty icon="git-network-outline" text="Index non construit : lancez la vectorisation." /></Card>
      ) : null}

      {tab === 'rag' && !loading && rag ? (
        <>
          <SectionTitle title="Questions récentes" />
          {rag.requests.length === 0 ? <Card><Empty icon="chatbubbles-outline" text="Aucune question posée." /></Card> : null}
          {rag.requests.map((r) => (
            <Card key={r.request_id}>
              <View style={styles.rowBetween}>
                <Text style={styles.mono}>{r.request_id}</Text>
                <Badge label={r.status} tone={r.status === 'approved' ? 'success' : r.status === 'partial' ? 'warn' : 'danger'} />
              </View>
              <Text style={styles.body}>{r.question}</Text>
              <Text style={styles.muted}>{formatDate(r.timestamp)} · {r.duration_ms ?? '—'} ms{r.error ? ` · ${r.error}` : ''}</Text>
            </Card>
          ))}
          <SectionTitle title="Lacunes (informations manquantes)" />
          {rag.gaps.length === 0 ? <Card><Empty icon="checkmark-circle-outline" text="Aucune lacune enregistrée." /></Card> : null}
          {rag.gaps.map((g, i) => (
            <Card key={i}>
              <Text style={styles.body}>{g.topic}</Text>
              <Text style={styles.muted}>{g.reason} · {g.count}× · {formatDate(g.last_seen)}</Text>
            </Card>
          ))}
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 14, gap: 12, paddingBottom: 40 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, maxWidth: 220 },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.primaryDark },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6 },
  strong: { fontSize: 15, fontWeight: '700', color: colors.text },
  page: { fontSize: 11.5, fontWeight: '800', color: colors.accent, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 },
  body: { fontSize: 14, lineHeight: 21, color: colors.text },
  muted: { fontSize: 12.5, color: colors.muted, lineHeight: 18 },
  warn: { fontSize: 12.5, color: colors.warn, marginTop: 4 },
  error: { color: colors.danger, fontSize: 13.5, fontWeight: '600' },
  mono: { fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 11.5, color: colors.primaryDark, flexShrink: 1 },
});
