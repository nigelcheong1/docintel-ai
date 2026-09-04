import type {
  DocumentChunk,
  DocumentDetail,
  DocumentPage,
  DocumentProfile,
  DocumentSummary,
  EvalRunSummary,
  GoldenEvalResponse,
  SearchResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function parseErrorDetail(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : undefined;
  } catch {
    return undefined;
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(parseErrorDetail(body) ?? (body || `Request failed with ${response.status}`));
  }
  return response.json() as Promise<T>;
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const response = await fetch(`${API_BASE_URL}/documents`, { cache: "no-store" });
  return parseJsonResponse<DocumentSummary[]>(response);
}

export async function getDocument(documentId: string): Promise<DocumentDetail> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, { cache: "no-store" });
  return parseJsonResponse<DocumentDetail>(response);
}

export async function getDocumentPages(documentId: string): Promise<DocumentPage[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/pages`, { cache: "no-store" });
  return parseJsonResponse<DocumentPage[]>(response);
}

export async function getDocumentChunks(documentId: string): Promise<DocumentChunk[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/chunks`, { cache: "no-store" });
  return parseJsonResponse<DocumentChunk[]>(response);
}

export async function getDocumentProfile(documentId: string): Promise<DocumentProfile> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/profile`, { cache: "no-store" });
  return parseJsonResponse<DocumentProfile>(response);
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, { method: "DELETE" });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(parseErrorDetail(body) ?? (body || `Request failed with ${response.status}`));
  }
}

export async function reindexDocument(documentId: string): Promise<DocumentSummary> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/reindex`, { method: "POST" });
  return parseJsonResponse<DocumentSummary>(response);
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse<DocumentSummary>(response);
}

export async function searchDocuments(query: string, topK = 5, documentId?: string): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK, document_id: documentId }),
  });
  return parseJsonResponse<SearchResponse>(response);
}

export async function getEvalRuns(): Promise<EvalRunSummary[]> {
  const response = await fetch(`${API_BASE_URL}/eval/runs`, { cache: "no-store" });
  return parseJsonResponse<EvalRunSummary[]>(response);
}

export async function getGoldenEval(): Promise<GoldenEvalResponse> {
  const response = await fetch(`${API_BASE_URL}/eval/golden`, { cache: "no-store" });
  return parseJsonResponse<GoldenEvalResponse>(response);
}

export async function createEvalRun(): Promise<EvalRunSummary> {
  const response = await fetch(`${API_BASE_URL}/eval/runs`, { method: "POST" });
  return parseJsonResponse<EvalRunSummary>(response);
}
