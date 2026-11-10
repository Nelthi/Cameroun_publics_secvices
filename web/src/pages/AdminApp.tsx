import { Database, FileStack, LayoutDashboard, LogOut, Play, RefreshCw, Settings, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Badge, Card, IconButton } from '../components/ui';
import type { DocRow, Overview } from '../types';
import { AdminData } from './AdminData';
import { AdminDocuments } from './AdminDocuments';
import { AdminPipeline } from './AdminPipeline';
import { SettingsDialog } from './RolePage';

type Tab = 'home' | 'docs' | 'pipeline' | 'data';
const NAV = [
  { id: 'home' as Tab, label: 'Tableau de bord', icon: <LayoutDashboard size={19} /> },
  { id: 'docs' as Tab, label: 'Documents', icon: <FileStack size={19} /> },
  { id: 'pipeline' as Tab, label: 'Traitements', icon: <Play size={19} /> },
  { id: 'data' as Tab, label: 'Données', icon: <Database size={19} /> },
];

export function AdminApp({ onExit }: { onExit: () => void }) {
  const [tab, setTab] = useState<Tab>('home');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [documents, setDocuments] = useState<DocRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [o, d] = await Promise.all([api.overview(), api.documents()]);
      setOverview(o);
      setDocuments(d);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const title = NAV.find((n) => n.id === tab)?.label;

  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <div className="brand"><span><ShieldCheck size={22} /></span><div><strong>Assistant Services Publics</strong><small>Espace administrateur</small></div></div>
        <nav>
          {NAV.map((n) => (
            <button key={n.id} className={tab === n.id ? 'on' : ''} onClick={() => setTab(n.id)}>{n.icon}{n.label}</button>
          ))}
        </nav>
        <div className="admin-nav-foot">
          <button onClick={() => setSettings(true)}><Settings size={18} /> Paramètres</button>
          <button onClick={onExit}><LogOut size={18} /> Changer d'espace</button>
        </div>
      </aside>

      <main className="admin-main">
        <header className="admin-head">
          <div><h2>{title}</h2><small>{documents.length} document(s) dans la base de connaissances</small></div>
          <IconButton label="Actualiser" onClick={() => void refresh()}><RefreshCw size={19} /></IconButton>
        </header>
        <div className="admin-content">
          {error ? <div className="chat-error">{error}</div> : null}
          {tab === 'home' ? (
            <div className="page-stack">
              <div className="stats">
                {[
                  ['Documents', overview?.documents], ['Textes extraits', overview?.extracted],
                  ['Fragments', overview?.chunks], ['Vecteurs', overview?.vectors],
                ].map(([label, value]) => (
                  <Card className="stat" key={label as string}><span>{label}</span><strong>{value ?? '–'}</strong></Card>
                ))}
              </div>
              <div className="two-col">
                <Card>
                  <h3>Configuration</h3>
                  <div className="cfg"><span>Vectorisation</span><strong>{overview?.embedding_model ?? '–'}{overview?.vector_dim ? ` · dim ${overview.vector_dim}` : ''}</strong></div>
                  <div className="cfg"><span>Agent IA Groq</span><Badge tone={overview?.groq_configured ? 'success' : 'warn'}>{overview?.groq_configured ? 'Configuré' : 'Non configuré'}</Badge></div>
                  <div className="cfg"><span>Modèle de découpage</span><strong>{overview?.groq_model ?? '–'}</strong></div>
                  <div className="cfg"><span>Modèle des métadonnées</span><strong>{overview?.groq_fast_model ?? '–'}</strong></div>
                </Card>
                <Card>
                  <h3>Parcours d'un document</h3>
                  {[['T1', 'Envoi et stockage (Champy)'], ['T2', 'Extraction du texte (Nelson)'], ['T3', "Découpage : code d'Alex ou agent IA"], ['T4', 'Vecteurs et index (Didier)']].map(([k, v]) => (
                    <div className="flow" key={k}><span>{k}</span>{v}</div>
                  ))}
                  <button className="link" onClick={() => setTab('pipeline')}>Aller aux traitements →</button>
                </Card>
              </div>
            </div>
          ) : null}
          {tab === 'docs' ? <AdminDocuments documents={documents} onChanged={() => void refresh()} /> : null}
          {tab === 'pipeline' ? <AdminPipeline documents={documents} onChanged={() => void refresh()} /> : null}
          {tab === 'data' ? <AdminData documents={documents} /> : null}
        </div>
      </main>
      {settings ? <SettingsDialog onClose={() => setSettings(false)} /> : null}
    </div>
  );
}
