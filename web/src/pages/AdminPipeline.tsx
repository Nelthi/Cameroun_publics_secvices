import { Cpu, FileText, GitFork, Rocket, Scissors } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Badge, Button, Card, Progress, useToast } from '../components/ui';
import type { DocRow, Job } from '../types';

type Phase = 'extract' | 'chunk' | 'index' | 'all';

export function AdminPipeline({ documents, onChanged }: { documents: DocRow[]; onChanged: () => void }) {
  const toast = useToast();
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'native' | 'ai'>('native');
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const consoleRef = useRef<HTMLDivElement>(null);
  const running = job?.status === 'queued' || job?.status === 'running';

  const stop = () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  useEffect(() => stop, []);
  useEffect(() => { consoleRef.current?.scrollTo({ top: consoleRef.current.scrollHeight }); }, [job?.log.length]);

  const follow = (first: Job) => {
    setJob(first);
    stop();
    timer.current = setInterval(async () => {
      try {
        const next = await api.job(first.id);
        setJob(next);
        if (next.status === 'done' || next.status === 'error') {
          stop();
          onChanged();
          toast(next.status === 'done' ? 'Traitement terminé' : 'Traitement terminé avec erreur');
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
  const allOn = documents.length > 0 && selected.length === documents.length;

  return (
    <div className="page-stack">
      <Card>
        <div className="card-title-row">
          <h3>Documents concernés</h3>
          <span className="muted">{selected.length ? `${selected.length} choisi(s)` : 'Tous les documents'}</span>
        </div>
        {documents.length === 0 ? <p className="muted">Envoyez d'abord un document.</p> : (
          <div className="check-list">
            <label className="check all"><input type="checkbox" checked={allOn} onChange={() => setSelected(allOn ? [] : documents.map((d) => d.document_id))} /> Tout sélectionner</label>
            {documents.map((d) => (
              <label className="check" key={d.document_id}>
                <input type="checkbox" checked={selected.includes(d.document_id)} onChange={() => toggle(d.document_id)} />
                <span>{d.title ?? d.document_id}</span>
                <small>{d.document_id}</small>
              </label>
            ))}
          </div>
        )}
      </Card>

      <div className="steps">
        <Card className="step">
          <span className="step-tag">ÉTAPE 1 · T2 Nelson</span>
          <h3><FileText size={19} /> Extraction du texte</h3>
          <p>Lit chaque fichier (PDF, Word, texte) et produit le texte nettoyé, page par page.</p>
          <Button disabled={running} icon={<FileText size={17} />} onClick={() => void launch('extract')}>Lancer l'extraction</Button>
        </Card>

        <Card className="step">
          <span className="step-tag">ÉTAPE 2 · T3 Alex / agent IA</span>
          <h3><Scissors size={19} /> Découpage en fragments</h3>
          <p>Choisissez la méthode de découpage.</p>
          <div className="mode-pick">
            <label className={mode === 'native' ? 'on' : ''}>
              <input type="radio" name="mode" checked={mode === 'native'} onChange={() => setMode('native')} />
              <span><strong>Code natif (Alex)</strong><small>Règles de taille (800 car.) et de fin de phrase.</small></span>
            </label>
            <label className={mode === 'ai' ? 'on' : ''}>
              <input type="radio" name="mode" checked={mode === 'ai'} onChange={() => setMode('ai')} />
              <span><strong>Agent IA (Groq)</strong><small>Découpage par sens : une idée par fragment.</small></span>
            </label>
          </div>
          <Button disabled={running} icon={<Scissors size={17} />} onClick={() => void launch('chunk')}>{mode === 'ai' ? 'Découper avec l\'IA' : 'Découper avec le code natif'}</Button>
        </Card>

        <Card className="step">
          <span className="step-tag">ÉTAPE 3 · T4 Didier</span>
          <h3><GitFork size={19} /> Vectorisation et index</h3>
          <p>Transforme chaque fragment en vecteur (BAAI/bge-m3) et reconstruit l'index de recherche. Le premier lancement télécharge le modèle.</p>
          <Button disabled={running} icon={<Cpu size={17} />} onClick={() => void launch('index')}>Construire l'index</Button>
        </Card>
      </div>

      <div><Button variant="secondary" disabled={running} icon={<Rocket size={17} />} onClick={() => void launch('all')}>Tout lancer (étapes 1 à 3)</Button></div>
      {error ? <p className="err-text">{error}</p> : null}

      {job ? (
        <Card>
          <div className="card-title-row">
            <h3>Journal d'exécution</h3>
            <Badge tone={job.status === 'done' ? 'success' : job.status === 'error' ? 'danger' : 'info'}>{job.status === 'done' ? 'Terminé' : job.status === 'error' ? 'Erreur' : 'En cours'}</Badge>
          </div>
          <Progress value={job.progress} />
          <div className="console" ref={consoleRef}>
            {job.log.length === 0 ? <div>En attente…</div> : job.log.map((line, i) => <div key={i} className={line.includes('ERREUR') ? 'bad' : ''}>{line}</div>)}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
