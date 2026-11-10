import { FileText, LogOut, Menu, MessageSquare, Mic, Paperclip, Plus, SendHorizontal, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Badge, Button, IconButton, formatDate, useToast } from '../components/ui';
import type { ChatMessage, Conversation } from '../types';

const SUGGESTIONS = [
  'Quelles sont les pièces à fournir pour la CNI ?',
  'Comment faire le pré-enrôlement en ligne ?',
  'Combien de temps pour produire ma carte ?',
];

function StatusBadge({ status }: { status: string | null }) {
  switch (status) {
    case 'approved': return <Badge tone="success">Réponse vérifiée</Badge>;
    case 'partial': return <Badge tone="warn">Réponse partielle</Badge>;
    case 'refused': return <Badge tone="danger">Information introuvable</Badge>;
    case 'needs_clarification': return <Badge tone="info">Précision demandée</Badge>;
    case 'error': return <Badge tone="danger">Service indisponible</Badge>;
    default: return null;
  }
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user';
  return (
    <div className={`msg ${mine ? 'mine' : 'theirs'}`}>
      {!mine ? <div className="avatar"><ShieldCheck size={16} /></div> : null}
      <div className="bubble">
        {!mine ? <div className="bubble-status"><StatusBadge status={message.status} /></div> : null}
        <p>{message.content}</p>
        {!mine && message.sources.length > 0 ? (
          <div className="sources">
            <span>Sources</span>
            <div>
              {message.sources.map((s, i) => (
                <span className="source-chip" key={`${s.document_id}-${s.source_page}-${i}`}>
                  <FileText size={13} /> {s.title ?? s.document_id} · p. {s.source_page}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function UserApp({ onExit }: { onExit: () => void }) {
  const toast = useToast();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [title, setTitle] = useState('Nouvelle discussion');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebar, setSidebar] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const refreshList = useCallback(async () => {
    try {
      setConversations(await api.conversations());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { void refreshList(); }, [refreshList]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, sending]);
  useEffect(() => {
    const el = areaRef.current;
    if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px'; }
  }, [text]);

  const open = async (id: string) => {
    setSidebar(false);
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

  const fresh = () => {
    setSidebar(false);
    setActiveId(null);
    setTitle('Nouvelle discussion');
    setMessages([]);
    setError(null);
    areaRef.current?.focus();
  };

  const remove = async (c: Conversation) => {
    if (!window.confirm(`Supprimer la discussion « ${c.title} » ?`)) return;
    try {
      await api.deleteConversation(c.id);
      if (c.id === activeId) fresh();
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    }
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
        id = (await api.createConversation()).id;
        setActiveId(id);
      }
      await api.sendMessage(id, question);
      const data = await api.conversation(id);
      setTitle(data.title);
      setMessages(data.messages);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-shell">
      {sidebar ? <div className="scrim" onClick={() => setSidebar(false)} /> : null}
      <aside className={`sidebar ${sidebar ? 'open' : ''}`}>
        <div className="sidebar-head"><ShieldCheck size={22} /><strong>Mes discussions</strong></div>
        <div className="sidebar-action"><Button icon={<Plus size={18} />} onClick={fresh}>Nouvelle discussion</Button></div>
        <nav className="conv-list">
          {conversations.length === 0 ? <p className="muted center">Aucune discussion pour l'instant.</p> : null}
          {conversations.map((c) => (
            <div key={c.id} className={`conv ${c.id === activeId ? 'active' : ''}`}>
              <button className="conv-main" onClick={() => void open(c.id)}>
                <MessageSquare size={17} />
                <span><strong>{c.title}</strong><small>{formatDate(c.updated_at)}</small></span>
              </button>
              <IconButton label="Supprimer" onClick={() => void remove(c)}><Trash2 size={16} /></IconButton>
            </div>
          ))}
        </nav>
      </aside>

      <section className="chat-main">
        <header className="chat-head">
          <IconButton label="Discussions" className="only-mobile" onClick={() => setSidebar(true)}><Menu size={22} /></IconButton>
          <div><h2>{title}</h2><small>Réponses issues des documents officiels</small></div>
          <IconButton label="Changer d'espace" onClick={onExit}><LogOut size={20} /></IconButton>
        </header>

        <div className="messages">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon"><MessageSquare size={34} /></div>
              <h3>Comment puis-je vous aider ?</h3>
              <p>Posez une question sur la procédure de votre choix. Chaque réponse cite ses sources.</p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => void send(s)}><Sparkles size={16} />{s}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages-inner">
              {messages.map((m) => <Bubble key={m.id} message={m} />)}
              {sending ? (
                <div className="msg theirs"><div className="avatar"><ShieldCheck size={16} /></div>
                  <div className="bubble typing"><span /><span /><span /> Recherche dans les documents…</div></div>
              ) : null}
              <div ref={endRef} />
            </div>
          )}
        </div>

        {error ? <div className="chat-error">{error}</div> : null}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); void send(); }}>
          <IconButton label="Joindre un fichier" type="button" onClick={() => toast('Pièces jointes : bientôt disponible')}><Paperclip size={20} /></IconButton>
          <textarea
            ref={areaRef}
            rows={1}
            value={text}
            maxLength={2000}
            placeholder="Posez votre question…"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); } }}
          />
          <IconButton label="Saisie vocale" type="button" onClick={() => toast('Saisie vocale : bientôt disponible')}><Mic size={20} /></IconButton>
          <button className="send" type="submit" disabled={!text.trim() || sending} aria-label="Envoyer"><SendHorizontal size={19} /></button>
        </form>
      </section>
    </div>
  );
}
