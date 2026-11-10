import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { api } from '../api';
import { Badge, Button, Card, Empty, Field, IconButton, SectionTitle, formatSize } from '../components/ui';
import { colors } from '../theme';
import type { DocRow, Draft, PickedFile, UploadResult } from '../types';

const today = () => new Date().toISOString().slice(0, 10);

export function AdminDocuments(props: { documents: DocRow[]; onChanged: () => void; toast: (m: string) => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const patch = (uri: string, change: Partial<Draft>) =>
    setDrafts((list) => list.map((d) => (d.file.uri === uri ? { ...d, ...change } : d)));

  const suggest = async (file: PickedFile) => {
    patch(file.uri, { loading: true, note: undefined });
    try {
      const s = await api.suggest(file);
      patch(file.uri, {
        loading: false, title: s.title, institution: s.institution, date: s.date, domain: s.domain, subdomain: s.subdomain,
        note: s.ai ? (s.date_guessed ? 'Proposé par Groq (date à vérifier)' : 'Proposé par Groq') : (s.warning ?? 'Proposition sans IA'),
      });
    } catch (e) {
      patch(file.uri, { loading: false, note: (e as Error).message });
    }
  };

  const pick = async () => {
    setError(null);
    setResults(null);
    const result = await DocumentPicker.getDocumentAsync({
      multiple: true,
      copyToCacheDirectory: true,
      type: ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
    });
    if (result.canceled) return;
    const fresh: Draft[] = result.assets
      .filter((a) => !drafts.some((d) => d.file.uri === a.uri))
      .map((a) => ({
        file: { uri: a.uri, name: a.name, size: a.size, mimeType: a.mimeType },
        title: a.name.replace(/\.[^.]+$/, ''), institution: '', date: today(), domain: 'public_services', subdomain: '', loading: true,
      }));
    setDrafts((d) => [...d, ...fresh]);
    fresh.forEach((d) => void suggest(d.file)); // Groq propose les informations de dépôt
  };

  const send = async () => {
    const missing = drafts.find((d) => !d.title.trim() || !d.institution.trim() || !d.subdomain.trim() || !/^\d{4}-\d{2}-\d{2}/.test(d.date));
    if (missing) {
      setError(`Complétez titre, institution, sous-domaine et date (AAAA-MM-JJ) pour « ${missing.file.name} ».`);
      return;
    }
    setError(null);
    setSending(true);
    try {
      const res = await api.upload(drafts);
      setResults(res.results);
      const failed = new Set(res.results.filter((r) => !r.ok).map((r) => r.filename));
      setDrafts((list) => list.filter((d) => failed.has(d.file.name)));
      props.toast(`${res.stored} document(s) enregistré(s)`);
      props.onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
      <Card>
        <SectionTitle title="Envoyer des documents" />
        <Text style={styles.muted}>PDF, Word ou texte. Plusieurs fichiers à la fois ; Groq propose le titre et les informations de dépôt.</Text>
        <Button label="Choisir des fichiers" icon="cloud-upload-outline" onPress={() => void pick()} style={{ marginTop: 12 }} />
      </Card>

      {drafts.map((d) => (
        <Card key={d.file.uri}>
          <View style={styles.fileHead}>
            <View style={{ flex: 1 }}>
              <Text style={styles.fileName} numberOfLines={1}>{d.file.name}</Text>
              <Text style={styles.muted}>{formatSize(d.file.size)}</Text>
            </View>
            <IconButton icon="close" color={colors.muted} onPress={() => setDrafts((l) => l.filter((x) => x.file.uri !== d.file.uri))} />
          </View>
          {d.note ? <Text style={[styles.note, d.note.includes('Groq') && !d.note.includes('sans') ? { color: colors.success } : { color: colors.warn }]}>{d.note}</Text> : null}
          <Field label="Titre" value={d.title} onChangeText={(v) => patch(d.file.uri, { title: v })} />
          <Field label="Institution" value={d.institution} onChangeText={(v) => patch(d.file.uri, { institution: v })} placeholder="ex. DGSN" />
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 1 }}><Field label="Date" value={d.date} onChangeText={(v) => patch(d.file.uri, { date: v })} placeholder="AAAA-MM-JJ" /></View>
            <View style={{ flex: 1 }}><Field label="Domaine" value={d.domain} onChangeText={(v) => patch(d.file.uri, { domain: v })} autoCapitalize="none" /></View>
          </View>
          <Field label="Sous-domaine" value={d.subdomain} onChangeText={(v) => patch(d.file.uri, { subdomain: v })} autoCapitalize="none" placeholder="ex. national_identity_card" />
          <Button label="Suggérer avec Groq" icon="sparkles-outline" variant="secondary" small loading={d.loading} onPress={() => void suggest(d.file)} />
        </Card>
      ))}

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {drafts.length > 0 ? (
        <Button label={`Envoyer ${drafts.length} document${drafts.length > 1 ? 's' : ''}`} icon="paper-plane" loading={sending} onPress={() => void send()} />
      ) : null}

      {results ? (
        <Card>
          <SectionTitle title="Résultat de l'envoi" />
          {results.map((r, i) => (
            <View key={i} style={styles.resultRow}>
              <Badge label={r.ok ? (r.duplicate ? 'Déjà présent' : 'Enregistré') : 'Échec'} tone={r.ok ? (r.duplicate ? 'warn' : 'success') : 'danger'} />
              <Text style={styles.resultText} numberOfLines={2}>{r.filename}{r.error ? ` — ${r.error}` : r.document_id ? ` → ${r.document_id}` : ''}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      <SectionTitle title={`Documents enregistrés (${props.documents.length})`} />
      {props.documents.length === 0 ? <Card><Empty icon="folder-open-outline" text="Aucun document pour l'instant." /></Card> : null}
      {props.documents.map((doc) => (
        <Card key={doc.document_id}>
          <Text style={styles.fileName}>{doc.title ?? doc.original_filename}</Text>
          <Text style={styles.muted}>{doc.document_id} · {doc.institution} · {doc.subdomain}</Text>
          <View style={styles.badges}>
            <Badge label="Stocké" tone="success" />
            <Badge label="Extrait" tone={doc.extracted ? 'success' : 'neutral'} />
            <Badge label={doc.chunked ? `${doc.chunk_count} fragments${doc.chunk_mode === 'ai' ? ' · IA' : ''}` : 'Non découpé'} tone={doc.chunked ? 'success' : 'neutral'} />
            <Badge label="Indexé" tone={doc.indexed ? 'success' : 'neutral'} />
          </View>
        </Card>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 14, gap: 12, paddingBottom: 40 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  fileHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  fileName: { fontSize: 15, fontWeight: '700', color: colors.text },
  note: { fontSize: 12.5, fontWeight: '600', marginBottom: 8 },
  error: { color: colors.danger, fontSize: 13.5, fontWeight: '600' },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  resultText: { flex: 1, fontSize: 13, color: colors.text },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
});
