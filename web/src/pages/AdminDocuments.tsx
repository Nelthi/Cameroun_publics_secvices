import { CloudUpload, FileText, Send, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Badge, Button, Card, Empty, Field, IconButton, formatSize, useToast } from '../components/ui';
import type { DocRow, Draft, UploadResult } from '../types';

const ALLOWED = ['.pdf', '.docx', '.txt'];
const allowed = (f: File) => ALLOWED.some((ext) => f.name.toLowerCase().endsWith(ext));
const today = () => new Date().toISOString().slice(0, 10);
const keyOf = (f: File) => `${f.name}|${f.size}|${f.lastModified}`;

async function filesFromDrop(dt: DataTransfer): Promise<File[]> {
  // Les entrées doivent être lues de façon synchrone, avant tout « await ».
  const entries = Array.from(dt.items).map((i) => i.webkitGetAsEntry?.()).filter((e): e is FileSystemEntry => !!e);
  if (entries.length === 0) return Array.from(dt.files);
  const out: File[] = [];
  const walk = async (entry: FileSystemEntry): Promise<void> => {
    if (entry.isFile) {
      out.push(await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej)));
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      let batch: FileSystemEntry[];
      do {
        batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
        for (const child of batch) await walk(child);
      } while (batch.length > 0);
    }
  };
  for (const entry of entries) await walk(entry);
  return out;
}

export function AdminDocuments({ documents, onChanged }: { documents: DocRow[]; onChanged: () => void }) {
  const toast = useToast();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [over, setOver] = useState(false);
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const input = useRef<HTMLInputElement>(null);
  const known = useRef(new Set<string>());

  const patch = (key: string, change: Partial<Draft>) => setDrafts((l) => l.map((d) => (d.key === key ? { ...d, ...change } : d)));

  const suggest = useCallback(async (draft: Draft) => {
    patch(draft.key, { loading: true });
    try {
      const s = await api.suggest(draft.file);
      patch(draft.key, { loading: false, title: s.title, institution: s.institution, date: s.date, domain: s.domain, subdomain: s.subdomain });
      setNotes((n) => ({ ...n, [draft.key]: s.ai ? (s.date_guessed ? 'Proposé par Groq — date à vérifier' : 'Proposé par Groq') : (s.warning ?? 'Proposition sans IA') }));
    } catch (e) {
      patch(draft.key, { loading: false });
      setNotes((n) => ({ ...n, [draft.key]: (e as Error).message }));
    }
  }, []);

  const addFiles = useCallback((files: File[]) => {
    setResults(null);
    setError(null);
    const fresh: Draft[] = files.filter(allowed).filter((f) => !known.current.has(keyOf(f))).map((f) => {
      known.current.add(keyOf(f));
      return { key: keyOf(f), file: f, title: f.name.replace(/\.[^.]+$/, ''), institution: '', date: today(), domain: 'public_services', subdomain: '', loading: true };
    });
    const rejected = files.length - files.filter(allowed).length;
    if (rejected > 0) toast(`${rejected} fichier(s) ignoré(s) : seuls PDF, DOCX et TXT sont acceptés`);
    if (fresh.length === 0) return;
    setDrafts((d) => [...d, ...fresh]);
    fresh.forEach((d) => void suggest(d)); // Groq propose les informations de dépôt
  }, [suggest, toast]);

  // Copier des fichiers dans l'explorateur puis Ctrl+V sur la page
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = Array.from(e.clipboardData?.files ?? []);
      if (files.length) { e.preventDefault(); addFiles(files); }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [addFiles]);

  const send = async () => {
    const bad = drafts.find((d) => !d.title.trim() || !d.institution.trim() || !d.subdomain.trim() || !/^\d{4}-\d{2}-\d{2}/.test(d.date));
    if (bad) { setError(`Complétez titre, institution, sous-domaine et date (AAAA-MM-JJ) pour « ${bad.file.name} ».`); return; }
    setError(null);
    setSending(true);
    try {
      const res = await api.upload(drafts);
      setResults(res.results);
      const failed = new Set(res.results.filter((r) => !r.ok).map((r) => r.filename));
      drafts.filter((d) => !failed.has(d.file.name)).forEach((d) => known.current.delete(d.key));
      setDrafts((l) => l.filter((d) => failed.has(d.file.name)));
      toast(`${res.stored} document(s) enregistré(s)`);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-stack">
      <div
        className={`dropzone ${over ? 'over' : ''}`}
        tabIndex={0}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={async (e) => { e.preventDefault(); setOver(false); addFiles(await filesFromDrop(e.dataTransfer)); }}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
      >
        <CloudUpload size={38} />
        <h3>Déposez vos documents ici</h3>
        <p>Glissez des fichiers ou un dossier, collez-les avec <kbd>Ctrl</kbd> + <kbd>V</kbd>, ou cliquez pour parcourir.</p>
        <small>PDF, DOCX, TXT · plusieurs fichiers à la fois · Groq propose automatiquement le titre et les informations de dépôt</small>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt"
          onChange={(e) => { addFiles(Array.from(e.target.files ?? [])); e.target.value = ''; }} />
      </div>

      {drafts.length > 0 ? (
        <div className="draft-grid">
          {drafts.map((d) => (
            <Card key={d.key} className="draft">
              <div className="draft-head">
                <FileText size={20} />
                <div><strong>{d.file.name}</strong><small>{formatSize(d.file.size)}</small></div>
                <IconButton label="Retirer" onClick={() => { known.current.delete(d.key); setDrafts((l) => l.filter((x) => x.key !== d.key)); }}><X size={18} /></IconButton>
              </div>
              {notes[d.key] ? <p className={notes[d.key].includes('Groq') && !notes[d.key].includes('sans') ? 'ok-text small' : 'warn-text small'}>{notes[d.key]}</p> : null}
              <Field label="Titre" value={d.title} onChange={(e) => patch(d.key, { title: e.target.value })} />
              <div className="two">
                <Field label="Institution" value={d.institution} placeholder="ex. DGSN" onChange={(e) => patch(d.key, { institution: e.target.value })} />
                <Field label="Date" value={d.date} placeholder="AAAA-MM-JJ" onChange={(e) => patch(d.key, { date: e.target.value })} />
              </div>
              <div className="two">
                <Field label="Domaine" value={d.domain} onChange={(e) => patch(d.key, { domain: e.target.value })} />
                <Field label="Sous-domaine" value={d.subdomain} placeholder="ex. national_identity_card" onChange={(e) => patch(d.key, { subdomain: e.target.value })} />
              </div>
              <Button variant="secondary" loading={d.loading} icon={<Sparkles size={16} />} onClick={() => void suggest(d)}>Suggérer avec Groq</Button>
            </Card>
          ))}
        </div>
      ) : null}

      {error ? <p className="err-text">{error}</p> : null}
      {drafts.length > 0 ? (
        <div><Button loading={sending} icon={<Send size={17} />} onClick={() => void send()}>Envoyer {drafts.length} document{drafts.length > 1 ? 's' : ''}</Button></div>
      ) : null}

      {results ? (
        <Card>
          <h3>Résultat de l'envoi</h3>
          {results.map((r, i) => (
            <div className="result-row" key={i}>
              <Badge tone={r.ok ? (r.duplicate ? 'warn' : 'success') : 'danger'}>{r.ok ? (r.duplicate ? 'Déjà présent' : 'Enregistré') : 'Échec'}</Badge>
              <span>{r.filename}{r.error ? ` — ${r.error}` : r.document_id ? ` → ${r.document_id}` : ''}</span>
            </div>
          ))}
        </Card>
      ) : null}

      <Card>
        <h3>Documents enregistrés ({documents.length})</h3>
        {documents.length === 0 ? <Empty icon={<FileText size={34} />}>Aucun document pour l'instant.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Document</th><th>Institution</th><th>Sous-domaine</th><th>Stocké</th><th>Extrait</th><th>Fragments</th><th>Indexé</th></tr></thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.document_id}>
                    <td><strong>{d.title ?? d.original_filename}</strong><small>{d.document_id}</small></td>
                    <td>{d.institution}</td>
                    <td>{d.subdomain}</td>
                    <td><Badge tone="success">Oui</Badge></td>
                    <td><Badge tone={d.extracted ? 'success' : 'neutral'}>{d.extracted ? 'Oui' : 'Non'}</Badge></td>
                    <td><Badge tone={d.chunked ? 'success' : 'neutral'}>{d.chunked ? `${d.chunk_count}${d.chunk_mode === 'ai' ? ' · IA' : ''}` : 'Non'}</Badge></td>
                    <td><Badge tone={d.indexed ? 'success' : 'neutral'}>{d.indexed ? 'Oui' : 'Non'}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
