import { ChevronRight, MessagesSquare, Settings, ShieldCheck, Wrench } from 'lucide-react';
import { useState } from 'react';
import { api, loadSettings, saveSettings } from '../api';
import { Button, Card, Field, Modal } from '../components/ui';
import type { Role } from '../types';

export function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState(loadSettings());
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const test = async () => {
    setTesting(true);
    setStatus(null);
    saveSettings(settings);
    try {
      const h = await api.health();
      setStatus({ ok: true, text: `Connecté. LLM : ${h.llm}. Groq : ${h.groq_configured ? 'configuré' : 'non configuré'}.` });
    } catch (e) {
      setStatus({ ok: false, text: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Modal title="Paramètres" onClose={onClose}>
      <div className="modal-body">
        <Field label="Adresse de l'API" value={settings.baseUrl} placeholder="http://localhost:8000"
          onChange={(e) => setSettings({ ...settings, baseUrl: e.target.value })} />
        <Field label="Jeton administrateur (facultatif)" type="password" value={settings.adminToken}
          placeholder="Seulement si ADMIN_TOKEN est défini sur le serveur"
          onChange={(e) => setSettings({ ...settings, adminToken: e.target.value })} />
        {status ? <p className={status.ok ? 'ok-text' : 'err-text'}>{status.text}</p> : null}
        <div className="row-gap">
          <Button variant="secondary" loading={testing} onClick={() => void test()}>Tester la connexion</Button>
          <Button onClick={() => { saveSettings(settings); onClose(); }}>Enregistrer</Button>
        </div>
      </div>
    </Modal>
  );
}

export function RolePage({ onPick }: { onPick: (role: Role) => void }) {
  const [showSettings, setShowSettings] = useState(false);
  return (
    <div className="role-page">
      <header className="role-hero">
        <button className="role-gear" onClick={() => setShowSettings(true)} aria-label="Paramètres"><Settings size={20} /></button>
        <div className="role-logo"><ShieldCheck size={34} /></div>
        <h1>Assistant Services Publics</h1>
        <p>Des réponses fiables sur vos démarches administratives, tirées des documents officiels.</p>
      </header>
      <main className="role-cards">
        <h2>Choisissez votre espace</h2>
        <div className="role-grid">
          <button className="role-card" onClick={() => onPick('user')}>
            <span className="role-icon green"><MessagesSquare size={26} /></span>
            <span className="role-text"><strong>Citoyen</strong><small>Posez vos questions sur une procédure et obtenez une réponse sourcée.</small></span>
            <ChevronRight size={20} />
          </button>
          <button className="role-card" onClick={() => onPick('admin')}>
            <span className="role-icon gold"><Wrench size={26} /></span>
            <span className="role-text"><strong>Administrateur</strong><small>Envoyez des documents, lancez les traitements et consultez les données.</small></span>
            <ChevronRight size={20} />
          </button>
        </div>
        <Card className="role-note">Démonstration · Projet HEMLE</Card>
      </main>
      {showSettings ? <SettingsDialog onClose={() => setShowSettings(false)} /> : null}
    </div>
  );
}
