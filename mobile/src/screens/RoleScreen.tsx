import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, shadow } from '../theme';
import type { Role } from '../types';

export function RoleScreen(props: { onPick: (role: Role) => void; onSettings: () => void }) {
  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.top}>
        <Pressable onPress={props.onSettings} hitSlop={10} style={styles.gear}>
          <Ionicons name="settings-outline" size={22} color="#fff" />
        </Pressable>
        <View style={styles.logo}>
          <Ionicons name="shield-checkmark" size={34} color={colors.primaryDark} />
        </View>
        <Text style={styles.title}>Assistant Services Publics</Text>
        <Text style={styles.subtitle}>Des réponses fiables sur vos démarches administratives, tirées des documents officiels.</Text>
      </View>
      <View style={styles.cards}>
        <Text style={styles.choose}>Choisissez votre espace</Text>
        <Pressable style={styles.card} onPress={() => props.onPick('user')}>
          <View style={[styles.iconWrap, { backgroundColor: colors.primarySoft }]}>
            <Ionicons name="chatbubbles" size={26} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Citoyen</Text>
            <Text style={styles.cardText}>Posez vos questions sur une procédure et obtenez une réponse sourcée.</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.muted} />
        </Pressable>
        <Pressable style={styles.card} onPress={() => props.onPick('admin')}>
          <View style={[styles.iconWrap, { backgroundColor: '#FBF1DA' }]}>
            <Ionicons name="construct" size={26} color={colors.warn} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Administrateur</Text>
            <Text style={styles.cardText}>Envoyez des documents, lancez les traitements et consultez les données.</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.muted} />
        </Pressable>
      </View>
      <Text style={styles.footer}>Démonstration · Projet HEMLE</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  top: { backgroundColor: colors.primary, paddingHorizontal: 24, paddingTop: 28, paddingBottom: 56, borderBottomLeftRadius: 32, borderBottomRightRadius: 32 },
  gear: { alignSelf: 'flex-end', padding: 6 },
  logo: { width: 64, height: 64, borderRadius: 20, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center', marginTop: 4 },
  title: { color: '#fff', fontSize: 26, fontWeight: '800', marginTop: 18 },
  subtitle: { color: '#CFE6DE', fontSize: 14.5, lineHeight: 21, marginTop: 8 },
  cards: { paddingHorizontal: 20, marginTop: -30, gap: 14 },
  choose: { fontSize: 13, fontWeight: '700', color: colors.muted, textTransform: 'uppercase', letterSpacing: 0.8, marginTop: 44, marginLeft: 4 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: colors.surface, borderRadius: radius.lg, padding: 16, borderWidth: 1, borderColor: colors.border, ...shadow },
  iconWrap: { width: 52, height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  cardText: { fontSize: 13.5, color: colors.muted, marginTop: 3, lineHeight: 19 },
  footer: { textAlign: 'center', color: colors.muted, fontSize: 12, marginTop: 'auto', paddingBottom: 14 },
});
