import { CheckCircle2, MessagesSquare, Network, Scissors } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Badge, Card, Empty, formatDate } from '../components/ui';
import type { AuditRow, ChunkRow, DocRow, GapRow, VectorsInfo } from '../types';

type Tab = 'text' | 'chunks' | 'vectors' | 'rag';
const TABS: { id: Tab; label: string }[] = [
  { id: 'text', label: 'Texte extrait' }, { id: 'chunks', label: 'Fragments' },
  { id: 'vectors', label: 'Vecteurs' }, { id: 'rag', label: 'Journal RAG' },
];

export function AdminData({ documents }: { documents: DocRow[] }) {
  const [tab, setTab] = useState<Tab>('text');
  const [docId, setDocId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState<Awaited<ReturnType<typeof api.documentText>> | null>(null);
  const [chunks, setChunks] = useState<{ total: number; items: ChunkRow[] } | null>(null);
  const [vectors, setVectors] = useState<VectorsInfo | null>(null);
  const [rag, setRag] = useState<{ requests: AuditRow[]; gaps: GapRow[] } | null>(null);

  useEffect(() => { if (!docId && documents.length) setDocId(documents[0].document_id); }, [documents, docId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === 'text') setText(docId ? await api.documentText(docId) : null);
      if (tab === 'chunks') setChunks(await api.chunks(docId || undefined));
      if (tab === 'vectors') setVectors(await api.vectors());
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
    <div className="page-stack">
      <div className="tabs">
        {TABS.map((t) => <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => setTab(t.id)}>{t.label}</button>)}
        {needsDoc ? (
          <select value={docId} onChange={(e) => setDocId(e.target.value)} aria-label="Document">
            {tab === 'chunks' ? <option value="">Tous les documents</option> : null}
            {documents.map((d) => <option key={d.document_id} value={d.document_id}>{d.title ?? d.document_id}</option>)}
          </select>
        ) : null}
      </div>

      {loading ? <p className="muted">Chargement…</p> : null}
      {error ? <p className="err-text">{error}</p> : null}

      {tab === 'text' && !loading && text ? (
        <>
          <Card>
            <div className="card-title-row"><strong>{text.character_count ?? 0} caractères extraits</strong><Badge tone={text.status === 'processed' ? 'success' : 'warn'}>{text.status}</Badge></div>
            {text.warnings.map((w, i) => <p className="warn-text small" key={i}>{w}</p>)}
          </Card>
          {text.segments.map((s, i) => (
            <Card key={i}><span className="page-tag">Page {s.page_number ?? '—'}</span><p className="prose">{s.text}</p></Card>
          ))}
          {text.truncated ? <p className="muted">Texte tronqué pour l'affichage.</p> : null}
        </>
      ) : null}

      {tab === 'chunks' && !loading && chunks ? (
        <>
          <p className="muted">{chunks.total} fragment(s) · {chunks.items.length} affiché(s)</p>
          {chunks.items.length === 0 ? <Card><Empty icon={<Scissors size={34} />}>Aucun fragment : lancez le découpage.</Empty></Card> : null}
          <div className="chunk-grid">
            {chunks.items.map((c) => (
              <Card key={c.chunk_id} className="chunk">
                <div className="card-title-row"><code>{c.chunk_id}</code><Badge tone="info">p. {c.source_page} · {c.text.length} car.</Badge></div>
                <p className="prose">{c.text}</p>
              </Card>
            ))}
          </div>
        </>
      ) : null}

      {tab === 'vectors' && !loading && vectors ? (
        vectors.built ? (
          <>
            <Card><strong>{vectors.total} vecteurs · dimension {vectors.dim}</strong><p className="muted">Modèle : {vectors.model} · index : {vectors.index_type}</p></Card>
            <Card>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>#</th><th>Fragment</th><th>Page</th><th>Norme</th><th>8 premières valeurs</th></tr></thead>
                  <tbody>
                    {vectors.items.map((v) => (
                      <tr key={v.vector_id}>
                        <td>{v.vector_id}</td>
                        <td><code>{v.chunk_id}</code><small>{v.text_preview}</small></td>
                        <td>{v.source_page}</td>
                        <td>{v.norm}</td>
                        <td><code>[{v.first_values.join(', ')}, …]</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        ) : <Card><Empty icon={<Network size={34} />}>Index non construit : lancez la vectorisation.</Empty></Card>
      ) : null}

      {tab === 'rag' && !loading && rag ? (
        <div className="two-col">
          <Card>
            <h3>Questions récentes</h3>
            {rag.requests.length === 0 ? <Empty icon={<MessagesSquare size={34} />}>Aucune question posée.</Empty> : rag.requests.map((r) => (
              <div className="audit" key={r.request_id}>
                <div className="card-title-row"><code>{r.request_id}</code><Badge tone={r.status === 'approved' ? 'success' : r.status === 'partial' ? 'warn' : 'danger'}>{r.status}</Badge></div>
                <p>{r.question}</p>
                <small>{formatDate(r.timestamp)} · {r.duration_ms ?? '—'} ms{r.error ? ` · ${r.error}` : ''}</small>
              </div>
            ))}
          </Card>
          <Card>
            <h3>Lacunes (informations manquantes)</h3>
            {rag.gaps.length === 0 ? <Empty icon={<CheckCircle2 size={34} />}>Aucune lacune enregistrée.</Empty> : rag.gaps.map((g, i) => (
              <div className="audit" key={i}><p>{g.topic}</p><small>{g.reason} · {g.count}× · {formatDate(g.last_seen)}</small></div>
            ))}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
