import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { api } from '../api';
import { Badge, Card, IconButton, SectionTitle, useToast } from '../components/ui';
import { colors, radius } from '../theme';
import type { DocRow, Overview } from '../types';
import { AdminData } from './AdminData';
import { AdminDocuments } from './AdminDocuments';
import { AdminPipeline } from './AdminPipeline';

type Tab = 'home' | 'docs' | 'pipeline' | 'data';
const TABS: { id: Tab; label: string; icon: React.ComponentProps<typeof Ionicons>['name'] }[] = [
  { id: 'home', label: 'Accueil', icon: 'speedometer-outline' },
  { id: 'docs', label: 'Documents', icon: 'documents-outline' },
  { id: 'pipeline', label: 'Traitements', icon: 'play-circle-outline' },
  { id: 'data', label: 'Données', icon: 'server-outline' },
];

function Stat(props: { label: string; value: number | string; icon: React.ComponentProps<typeof Ionicons>['name'] }) {
  return (
    <View style={styles.stat}>
      <Ionicons name={props.icon} size={20} color={colors.primary} />
      <Text style={styles.statValue}>{props.value}</Text>
      <Text style={styles.statLabel}>{props.label}</Text>
    </View>
  );
}

export function AdminApp(props: { onExit: () => void }) {
  const [tab, setTab] = useState<Tab>('home');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [documents, setDocuments] = useState<DocRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const toast = useToast();

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [o, d] = await Promise.all([api.overview(), api.documents()]);
      setOverview(o);
      setDocuments(d);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <SafeAreaView style={styles.root} edges={['top', 'left', 'right']}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Espace administrateur</Text>
          <Text style={styles.headerSub}>Base de connaissances · {documents.length} document(s)</Text>
        </View>
        <IconButton icon="refresh" color="#fff" onPress={() => void refresh()} />
        <IconButton icon="log-out-outline" color="#fff" onPress={props.onExit} />
      </View>

      <View style={{ flex: 1 }}>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {tab === 'home' ? (
          <ScrollView contentContainerStyle={styles.scroll} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />}>
            <Card>
              <SectionTitle title="Vue d'ensemble" />
              <View style={styles.stats}>
                <Stat label="Documents" value={overview?.documents ?? '–'} icon="documents-outline" />
                <Stat label="Extraits" value={overview?.extracted ?? '–'} icon="document-text-outline" />
                <Stat label="Fragments" value={overview?.chunks ?? '–'} icon="cut-outline" />
                <Stat label="Vecteurs" value={overview?.vectors ?? '–'} icon="git-network-outline" />
              </View>
            </Card>
            <Card>
              <SectionTitle title="Configuration" />
              <View style={styles.cfgRow}><Text style={styles.cfgKey}>Vectorisation</Text><Text style={styles.cfgVal}>{overview?.embedding_model ?? '–'}{overview?.vector_dim ? ` · dim ${overview.vector_dim}` : ''}</Text></View>
              <View style={styles.cfgRow}>
                <Text style={styles.cfgKey}>Agent IA Groq</Text>
                <Badge label={overview?.groq_configured ? 'Configuré' : 'Non configuré'} tone={overview?.groq_configured ? 'success' : 'warn'} />
              </View>
              <View style={styles.cfgRow}><Text style={styles.cfgKey}>Modèle (découpage)</Text><Text style={styles.cfgVal}>{overview?.groq_model ?? '–'}</Text></View>
              <View style={styles.cfgRow}><Text style={styles.cfgKey}>Modèle (métadonnées)</Text><Text style={styles.cfgVal}>{overview?.groq_fast_model ?? '–'}</Text></View>
            </Card>
            <Card>
              <SectionTitle title="Parcours d'un document" />
              {[['T1', 'Envoi et stockage (Champy)'], ['T2', 'Extraction du texte (Nelson)'], ['T3', 'Découpage : code d\'Alex ou agent IA'], ['T4', 'Vecteurs et index (Didier)']].map(([k, v]) => (
                <View key={k} style={styles.flowRow}><View style={styles.flowDot}><Text style={styles.flowDotText}>{k}</Text></View><Text style={styles.cfgVal}>{v}</Text></View>
              ))}
              <Pressable onPress={() => setTab('pipeline')} style={styles.link}><Text style={styles.linkText}>Aller aux traitements →</Text></Pressable>
            </Card>
          </ScrollView>
        ) : null}
        {tab === 'docs' ? <AdminDocuments documents={documents} onChanged={() => void refresh()} toast={toast.show} /> : null}
        {tab === 'pipeline' ? <AdminPipeline documents={documents} onChanged={() => void refresh()} toast={toast.show} /> : null}
        {tab === 'data' ? <AdminData documents={documents} /> : null}
        {toast.node}
      </View>

      <SafeAreaView edges={['bottom']} style={styles.tabBar}>
        <View style={styles.tabRow}>
          {TABS.map((t) => {
            const on = tab === t.id;
            return (
              <Pressable key={t.id} style={styles.tab} onPress={() => setTab(t.id)}>
                <View style={[styles.tabIcon, on && { backgroundColor: colors.primarySoft }]}>
                  <Ionicons name={t.icon} size={22} color={on ? colors.primary : colors.muted} />
                </View>
                <Text style={[styles.tabLabel, on && { color: colors.primary }]}>{t.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </SafeAreaView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.primaryDark, paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { color: '#fff', fontSize: 17, fontWeight: '800' },
  headerSub: { color: '#9FC8BA', fontSize: 12, marginTop: 2 },
  scroll: { padding: 14, gap: 12, paddingBottom: 40 },
  error: { margin: 14, padding: 12, backgroundColor: colors.dangerSoft, color: colors.danger, borderRadius: radius.sm, fontSize: 13.5, fontWeight: '600' },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  stat: { width: '47.5%', backgroundColor: '#F3F8F6', borderRadius: radius.md, padding: 14, gap: 2 },
  statValue: { fontSize: 26, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 12.5, color: colors.muted, fontWeight: '600' },
  cfgRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 7, gap: 10 },
  cfgKey: { color: colors.muted, fontSize: 13.5 },
  cfgVal: { color: colors.text, fontSize: 13.5, fontWeight: '600', flexShrink: 1, textAlign: 'right' },
  flowRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 6 },
  flowDot: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  flowDotText: { fontSize: 12, fontWeight: '800', color: colors.primaryDark },
  link: { marginTop: 8, alignSelf: 'flex-start' },
  linkText: { color: colors.primary, fontWeight: '700', fontSize: 14 },
  tabBar: { backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  tabRow: { flexDirection: 'row', paddingTop: 6, paddingBottom: 4 },
  tab: { flex: 1, alignItems: 'center', gap: 2 },
  tabIcon: { paddingHorizontal: 16, paddingVertical: 4, borderRadius: radius.pill },
  tabLabel: { fontSize: 11.5, fontWeight: '700', color: colors.muted },
});
