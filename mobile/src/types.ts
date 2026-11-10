export type Role = 'user' | 'admin';

export interface Settings {
  baseUrl: string;
  adminToken: string;
  userId: string;
}

export interface Overview {
  documents: number;
  extracted: number;
  chunked: number;
  indexed: number;
  chunks: number;
  vectors: number;
  vector_dim: number | null;
  embedding_model: string;
  groq_configured: boolean;
  groq_model: string;
  groq_fast_model: string;
}

export interface DocRow {
  document_id: string;
  title: string | null;
  institution: string | null;
  domain: string | null;
  subdomain: string | null;
  date: string | null;
  original_filename: string | null;
  file_format: string | null;
  file_size: number | null;
  upload_date: string | null;
  extracted: boolean;
  chunked: boolean;
  indexed: boolean;
  chunk_count: number;
  chunk_mode: 'native' | 'ai' | null;
}

export interface Suggestion {
  title: string;
  institution: string;
  date: string;
  domain: string;
  subdomain: string;
  summary: string;
  ai: boolean;
  date_guessed: boolean;
  warning?: string;
}

export interface UploadResult {
  filename: string;
  ok: boolean;
  document_id?: string;
  duplicate?: boolean;
  error?: string;
  metadata_source?: string;
}

export interface Job {
  id: string;
  kind: string;
  params: { phase: string; mode: string; document_ids: string[] | null };
  status: 'queued' | 'running' | 'done' | 'error';
  progress: number;
  log: string[];
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Source {
  document_id: string;
  source_page: number;
  title?: string;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  status: string | null;
  sources: Source[];
  request_id: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChunkRow {
  chunk_id: string;
  document_id: string;
  text: string;
  source_page: number;
  position: number;
}

export interface VectorRow {
  vector_id: number;
  chunk_id: string | null;
  document_id: string | null;
  source_page: number | null;
  norm: number;
  first_values: number[];
  text_preview: string;
}

export interface VectorsInfo {
  built: boolean;
  total: number;
  dim: number | null;
  model?: string;
  index_type?: string;
  items: VectorRow[];
}

export interface AuditRow {
  request_id: string;
  timestamp: string;
  question: string;
  status: string;
  duration_ms: number | null;
  error: string | null;
}

export interface GapRow {
  topic: string;
  reason: string | null;
  count: number;
  last_seen: string;
}

export interface PickedFile {
  uri: string;
  name: string;
  size?: number;
  mimeType?: string;
}

export interface Draft {
  file: PickedFile;
  title: string;
  institution: string;
  date: string;
  domain: string;
  subdomain: string;
  loading: boolean;
  note?: string;
}
