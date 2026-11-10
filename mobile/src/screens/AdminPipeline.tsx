import React, { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../api';
import { Badge, Button, Card, ProgressBar, SectionTitle, Segmented } from '../components/ui';
import { colors, radius } from '../theme';
import type { DocRow, Job } from '../types';

type Phase = 'extract' | 'chunk' | 'index' | 'all';

export function AdminPipeline(props: { documents: DocRow[]; onChanged: () => void; toast: (m: string) => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'native' | 'ai'>('native');
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const running = job?.status === 'queued' || job?.status === 'running';

  const stop = () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  useEffect(() => stop, []);

  const follow = (first: Job) => {
    setJob(first);
    stop();
    timer.current = setInterval(async () => {
      try {
        const next = await api.job(first.id);
        setJob(next);
        if (next.status === 'done' || next.status === 'error') {
          stop();
          props.onChanged();
          props.toast(next.status === 'done' ? 'Traitement terminé' : 'Traitement terminé avec erreur');
        }
      } catch (e) {
        stop();
        setError((e as Error).message);
      }
    }, 900);
  };

  const launch = async (phase: Phase) => {
    setError(null);
    try {
      follow(await api.run(phase, mode, selected.length ? selected : null));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <ScrollView contentContainerStyle={styles.scroll}>
      <Card>
        <SectionTitle title="Documents concernés" right={<Text style={styles.count}>{selected.length ? `${selected.length} choisi(s)` : 'Tous'}</Text>} />
        {props.documents.length === 0 ? <Text style={styles.muted}>Envoyez d'abord un document.</Text> : null}
        {props.documents.map((d) => {
          const on = selected.includes(d.document_id);
          return (
            <Pressable key={d.document_id} style={styles.docRow} onPress={() => toggle(d.document_id)}>
              <Ionicons name={on ? 'checkbox' : 'square-outline'} size={22} color={on ? colors.primary : colors.muted} />
              <Text style={styles.docName} numberOfLines={1}>{d.title ?? d.document_id}</Text>
            </Pressable>
          );
        })}
        {selected.length ? <Button label="Tout désélectionner" variant="ghost" small onPress={() => setSelected([])} style={{ marginTop: 8 }} /> : null}
      </Card>

      <Card>
        <Text style={styles.step}>ÉTAPE 1 · T2 Nelson</Text>
        <Text style={styles.title}>Extraction du texte</Text>
        <Text style={styles.muted}>Lit chaque fichier (PDF, Word, texte) et produit le texte nettoyé, page par page.</Text>
        <Button label="Lancer l'extraction" icon="document-text-outline" disabled={running} onPress={() => void launch('extract')} style={{ marginTop: 12 }} />
      </Card>

      <Card>
        <Text style={styles.step}>ÉTAPE 2 · T3 Alex / agent IA</Text>
        <Text style={styles.title}>Découpage en fragments</Text>
        <Text style={styles.muted}>Choisissez la méthode : le code d'Alex (règles de taille et de phrases) ou l'agent IA Groq (découpage par sens).</Text>
        <View style={{ marginTop: 10 }}>
          <Segmented value={mode} onChange={setMode} options={[{ value: 'native', label: 'Code natif (Alex)' }, { value: 'ai', label: 'Agent IA (Groq)' }]} />
        </View>
        <Button label={mode === 'ai' ? 'Découper avec l\'IA' : 'Découper avec le code natif'} icon="cut-outline" disabled={running} onPress={() => void launch('chunk')} style={{ marginTop: 12 }} />
      </Card>

      <Card>
        <Text style={styles.step}>ÉTAPE 3 · T4 Didier</Text>
        <Text style={styles.title}>Vectorisation et index</Text>
        <Text style={styles.muted}>Transforme chaque fragment en vecteur (BAAI/bge-m3) et reconstruit l'index de recherche. Le premier lancement télécharge le modèle.</Text>
        <Button label="Construire l'index" icon="git-network-outline" disabled={running} onPress={() => void launch('index')} style={{ marginTop: 12 }} />
      </Card>

      <Button label="Tout lancer (étapes 1 à 3)" icon="rocket-outline" variant="secondary" disabled={running} onPress={() => void launch('all')} />
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {job ? (
        <Card>
          <View style={styles.jobHead}>
            <SectionTitle title="Journal d'exécution" />
            <Badge label={job.status === 'done' ? 'Terminé' : job.status === 'error' ? 'Erreur' : 'En cours'} tone={job.status === 'done' ? 'success' : job.status === 'error' ? 'danger' : 'info'} />
          </View>
          <ProgressBar value={job.progress} />
          <View style={styles.console}>
            {job.log.length === 0 ? <Text style={styles.logLine}>En attente…</Text> : job.log.map((line, i) => (
              <Text key={i} style={[styles.logLine, line.includes('ERREUR') && { color: '#FF9B94' }]}>{line}</Text>
            ))}
          </View>
        </Card>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 14, gap: 12, paddingBottom: 40 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  count: { color: colors.muted, fontSize: 13, fontWeight: '600' },
  docRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
  docName: { flex: 1, color: colors.text, fontSize: 14.5 },
  step: { fontSize: 11, fontWeight: '800', color: colors.accent, letterSpacing: 0.8, marginBottom: 2 },
  title: { fontSize: 17, fontWeight: '800', color: colors.text, marginBottom: 4 },
  error: { color: colors.danger, fontSize: 13.5, fontWeight: '600' },
  jobHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  console: { backgroundColor: '#0E1C18', borderRadius: radius.sm, padding: 12, marginTop: 12, gap: 4 },
  logLine: { color: '#BFE5D6', fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 12, lineHeight: 17 },
});
