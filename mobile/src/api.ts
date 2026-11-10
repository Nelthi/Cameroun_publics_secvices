import type {
  AuditRow, ChatMessage, ChunkRow, Conversation, DocRow, GapRow, Job, Overview, Settings,
  Suggestion, UploadResult, VectorsInfo, Draft,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let current: Settings = { baseUrl: 'http://localhost:8000', adminToken: '', userId: 'demo' };

export function configure(settings: Settings) {
  current = { ...settings, baseUrl: settings.baseUrl.trim().replace(/\/+$/, '') };
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
    body = opts.form; // Content-Type multipart ajouté automatiquement
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 30000);
  try {
    const response = await fetch(current.baseUrl + path, {
      method: opts.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      signal: controller.signal,
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
      const message = typeof detail === 'string' ? detail : `Erreur ${response.status}`;
      throw new ApiError(message, response.status);
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === 'AbortError') throw new ApiError('Délai dépassé : le serveur ne répond pas.', 0);
    throw new ApiError(`Serveur injoignable (${current.baseUrl}). Vérifiez l'adresse dans Paramètres.`, 0);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<{ status: string; llm: string; groq_configured: boolean; admin_protected: boolean }>('/api/health'),

  // ---- utilisateur
  conversations: () => request<Conversation[]>('/api/chat/conversations'),
  createConversation: (title?: string) =>
    request<Conversation>('/api/chat/conversations', { method: 'POST', json: { title: title ?? null } }),
  conversation: (id: string) =>
    request<{ id: string; title: string; messages: ChatMessage[] }>(`/api/chat/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/api/chat/conversations/${id}`, { method: 'DELETE' }),
  sendMessage: (id: string, text: string) =>
    request<ChatMessage>(`/api/chat/conversations/${id}/messages`, { json: { text }, timeoutMs: 180000 }),

  // ---- administrateur
  overview: () => request<Overview>('/api/admin/overview', { admin: true }),
  documents: () => request<DocRow[]>('/api/admin/documents', { admin: true }),
  documentText: (id: string) =>
    request<{ status: string; warnings: string[]; character_count: number | null; segments: { page_number: number | null; text: string }[]; truncated: boolean }>(
      `/api/admin/documents/${id}/text?limit=6000`, { admin: true }),
  chunks: (documentId?: string, limit = 30, offset = 0) =>
    request<{ total: number; items: ChunkRow[] }>(
      `/api/admin/chunks?limit=${limit}&offset=${offset}` + (documentId ? `&document_id=${documentId}` : ''), { admin: true }),
  vectors: (limit = 15) => request<VectorsInfo>(`/api/admin/vectors?limit=${limit}`, { admin: true }),
  audit: () => request<{ requests: AuditRow[]; gaps: GapRow[] }>('/api/admin/audit', { admin: true }),
  run: (phase: 'extract' | 'chunk' | 'index' | 'all', mode: 'native' | 'ai', documentIds: string[] | null) =>
    request<Job>(`/api/admin/run/${phase}`, { admin: true, json: { mode, document_ids: documentIds } }),
  job: (id: string) => request<Job>(`/api/admin/jobs/${id}`, { admin: true }),

  suggest: (file: { uri: string; name: string; mimeType?: string }) => {
    const form = new FormData();
    form.append('file', { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' } as unknown as Blob);
    return request<Suggestion>('/api/admin/suggest-metadata', { admin: true, form, timeoutMs: 60000 });
  },
  upload: (drafts: Draft[]) => {
    const form = new FormData();
    drafts.forEach((d) =>
      form.append('files', { uri: d.file.uri, name: d.file.name, type: d.file.mimeType || 'application/octet-stream' } as unknown as Blob));
    form.append('metadata', JSON.stringify(drafts.map((d) => ({
      title: d.title, institution: d.institution, date: d.date, domain: d.domain, subdomain: d.subdomain,
    }))));
    form.append('auto_metadata', 'true');
    return request<{ results: UploadResult[]; stored: number }>('/api/admin/documents', { admin: true, form, timeoutMs: 120000 });
  },
};
