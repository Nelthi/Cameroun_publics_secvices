import type {
  AuditRow, ChatMessage, ChunkRow, Conversation, DocRow, Draft, GapRow, Job, Overview, Suggestion, UploadResult, VectorsInfo,
} from './types';

export interface Settings {
  baseUrl: string;
  adminToken: string;
  userId: string;
}

const KEY = 'cps.settings.v1';
const DEFAULT_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Settings>;
      return { baseUrl: p.baseUrl || DEFAULT_URL, adminToken: p.adminToken || '', userId: p.userId || newId() };
    }
  } catch {
    /* paramètres illisibles */
  }
  const fresh = { baseUrl: DEFAULT_URL, adminToken: '', userId: newId() };
  saveSettings(fresh);
  return fresh;
}

export function saveSettings(s: Settings) {
  localStorage.setItem(KEY, JSON.stringify(s));
  current = { ...s, baseUrl: s.baseUrl.trim().replace(/\/+$/, '') };
}

function newId() {
  return 'u-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

let current: Settings = loadSettings();

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface Options {
  method?: string;
  json?: unknown;
  form?: FormData;
  admin?: boolean;
  timeoutMs?: number;
}

async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', 'X-User-Id': current.userId };
  if (opts.admin && current.adminToken) headers['X-Admin-Token'] = current.adminToken;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 30000);
  try {
    const response = await fetch(current.baseUrl + path, {
      method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: controller.signal,
    });
    if (response.status === 204) return undefined as T;
    const text = await response.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!response.ok) {
      const detail = (data as { detail?: unknown } | null)?.detail;
      throw new ApiError(typeof detail === 'string' ? detail : `Erreur ${response.status}`, response.status);
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === 'AbortError') throw new ApiError('Délai dépassé : le serveur ne répond pas.', 0);
    throw new ApiError(`Serveur injoignable (${current.baseUrl}). Vérifiez qu'il est lancé et l'adresse dans Paramètres.`, 0);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<{ status: string; llm: string; groq_configured: boolean; admin_protected: boolean }>('/api/health'),

  conversations: () => request<Conversation[]>('/api/chat/conversations'),
  createConversation: () => request<Conversation>('/api/chat/conversations', { json: {} }),
  conversation: (id: string) => request<{ id: string; title: string; messages: ChatMessage[] }>(`/api/chat/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/api/chat/conversations/${id}`, { method: 'DELETE' }),
  sendMessage: (id: string, text: string) =>
    request<ChatMessage>(`/api/chat/conversations/${id}/messages`, { json: { text }, timeoutMs: 180000 }),

  overview: () => request<Overview>('/api/admin/overview', { admin: true }),
  documents: () => request<DocRow[]>('/api/admin/documents', { admin: true }),
  documentText: (id: string) =>
    request<{ status: string; warnings: string[]; character_count: number | null; segments: { page_number: number | null; text: string }[]; truncated: boolean }>(
      `/api/admin/documents/${id}/text?limit=12000`, { admin: true }),
  chunks: (documentId?: string, limit = 60) =>
    request<{ total: number; items: ChunkRow[] }>(`/api/admin/chunks?limit=${limit}` + (documentId ? `&document_id=${documentId}` : ''), { admin: true }),
  vectors: (limit = 25) => request<VectorsInfo>(`/api/admin/vectors?limit=${limit}`, { admin: true }),
  audit: () => request<{ requests: AuditRow[]; gaps: GapRow[] }>('/api/admin/audit', { admin: true }),
  run: (phase: 'extract' | 'chunk' | 'index' | 'all', mode: 'native' | 'ai', documentIds: string[] | null) =>
    request<Job>(`/api/admin/run/${phase}`, { admin: true, json: { mode, document_ids: documentIds } }),
  job: (id: string) => request<Job>(`/api/admin/jobs/${id}`, { admin: true }),
  suggest: (file: File) => {
    const form = new FormData();
    form.append('file', file, file.name);
    return request<Suggestion>('/api/admin/suggest-metadata', { admin: true, form, timeoutMs: 60000 });
  },
  upload: (drafts: Draft[]) => {
    const form = new FormData();
    drafts.forEach((d) => form.append('files', d.file, d.file.name));
    form.append('metadata', JSON.stringify(drafts.map((d) => ({
      title: d.title, institution: d.institution, date: d.date, domain: d.domain, subdomain: d.subdomain,
    }))));
    form.append('auto_metadata', 'true');
    return request<{ results: UploadResult[]; stored: number }>('/api/admin/documents', { admin: true, form, timeoutMs: 120000 });
  },
};
