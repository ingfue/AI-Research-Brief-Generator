import axios from "axios";

const api = axios.create({ baseURL: "/api" });

/* ---------- Types ---------- */

export interface UploadResponse {
  session_id: string;
  filename: string;
  status: string;
  chunk_count: number;
}

export interface SessionInfo {
  session_id: string;
  filename: string;
  created_at: string;
  status: string;
}

export interface SectionContent {
  section: string;
  content: string;
  status: "pending" | "generating" | "review" | "approved";
}

export interface GenerateFullResponse {
  session_id: string;
  sections: SectionContent[];
  document_url: string;
}

export interface ToneAdjustResponse {
  original: string;
  adjusted: string;
  tone: string;
}

/* ---------- Upload ---------- */

export async function uploadJson(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<UploadResponse>("/upload", form);
  return data;
}

/* ---------- Sessions ---------- */

export async function listSessions(): Promise<SessionInfo[]> {
  const { data } = await api.get<SessionInfo[]>("/sessions");
  return data;
}

/* ---------- Generate ---------- */

export async function generateFull(sessionId: string): Promise<GenerateFullResponse> {
  const { data } = await api.post<GenerateFullResponse>("/generate/full", {
    session_id: sessionId,
  });
  return data;
}

export async function generateStep(
  sessionId: string,
  section: string
): Promise<SectionContent> {
  const { data } = await api.post<SectionContent>("/generate/step", {
    session_id: sessionId,
    section,
  });
  return data;
}

/* ---------- Sections ---------- */

export async function getSections(sessionId: string): Promise<SectionContent[]> {
  const { data } = await api.get<SectionContent[]>(`/sections/${sessionId}`);
  return data;
}

export async function updateSection(
  sessionId: string,
  section: string,
  content: string,
  status: string = "approved"
): Promise<SectionContent> {
  const { data } = await api.put<SectionContent>(
    `/sections/${sessionId}/${section}`,
    { content, status }
  );
  return data;
}

/* ---------- Documents ---------- */

export async function assembleDocument(sessionId: string): Promise<{ download_url: string }> {
  const { data } = await api.post(`/documents/${sessionId}/assemble`);
  return data;
}

export function getDownloadUrl(sessionId: string): string {
  return `/api/documents/${sessionId}/download`;
}

/* ---------- Tone ---------- */

export async function adjustTone(
  text: string,
  tone: string,
  customInstruction?: string
): Promise<ToneAdjustResponse> {
  const { data } = await api.post<ToneAdjustResponse>("/tone/adjust", {
    text,
    tone,
    custom_instruction: customInstruction,
  });
  return data;
}

/* ---------- Debug ---------- */

export interface DebugSession {
  session_id: string;
  chunk_count: number;
}

export interface DebugChunk {
  chunk_id: string;
  chunk_type: string;
  chunk_tier: string;
  section_tags: string[];
  subject: string;
  content: string;
  content_length: number;
  parent_chunk_id: string;
  paragraph_index: number;
}

export interface DebugStats {
  session_id: string;
  total_chunks: number;
  by_type: Record<string, number>;
  by_tier: Record<string, number>;
  by_section_tag: Record<string, number>;
  available_tags: string[];
}

export interface DebugAggregate {
  session_id: string;
  section_tag: string;
  found: boolean;
  chunk_id?: string;
  content_length?: number;
  content?: string;
}

export async function debugListSessions(): Promise<DebugSession[]> {
  const { data } = await api.get<{ sessions: DebugSession[] }>("/debug/sessions");
  return data.sessions;
}

export async function debugGetStats(sessionId: string): Promise<DebugStats> {
  const { data } = await api.get<DebugStats>(`/debug/${sessionId}/stats`);
  return data;
}

export async function debugGetChunks(
  sessionId: string,
  tier?: "tier1" | "tier2"
): Promise<{ total_chunks: number; chunks: DebugChunk[] }> {
  const path = tier ? `/debug/${sessionId}/chunks/${tier}` : `/debug/${sessionId}/chunks`;
  const { data } = await api.get(path);
  return data;
}

export async function debugGetSectionChunks(
  sessionId: string,
  tag: string
): Promise<{ total_chunks: number; chunks: DebugChunk[] }> {
  const { data } = await api.get(`/debug/${sessionId}/section/${tag}`);
  return data;
}

export async function debugGetAggregate(
  sessionId: string,
  tag: string
): Promise<DebugAggregate> {
  const { data } = await api.get<DebugAggregate>(`/debug/${sessionId}/section/${tag}/aggregate`);
  return data;
}

export async function debugSearch(
  sessionId: string,
  query: string,
  opts?: { top?: number; chunk_tier?: string; section_tag?: string }
): Promise<{ total_results: number; results: DebugChunk[] }> {
  const params: Record<string, string> = { q: query };
  if (opts?.top) params.top = String(opts.top);
  if (opts?.chunk_tier) params.chunk_tier = opts.chunk_tier;
  if (opts?.section_tag) params.section_tag = opts.section_tag;
  const { data } = await api.get(`/debug/${sessionId}/search`, { params });
  return data;
}
