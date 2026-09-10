import type {
  DocumentChunk,
  DocumentDetail,
  DocumentPage,
  DocumentProcessingStatus,
  DocumentProfile,
  DocumentStudySummary,
  DocumentSummary,
  EvalRunSummary,
  GoldenEvalResponse,
  SearchResponse,
  SummaryGenerationMode,
  StudyAnswer,
  StudyGenerationMode,
  StudyQuestion,
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

export async function getDocumentStatus(documentId: string): Promise<DocumentProcessingStatus> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/status`, { cache: "no-store" });
  return parseJsonResponse<DocumentProcessingStatus>(response);
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

export async function getDocumentStudySummary(documentId: string): Promise<DocumentStudySummary | null> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/summary`, { cache: "no-store" });
  return parseJsonResponse<DocumentStudySummary | null>(response);
}

export type GenerateStudySummaryOptions = {
  mode?: SummaryGenerationMode;
};

export async function generateDocumentStudySummary(
  documentId: string,
  options: GenerateStudySummaryOptions = {},
): Promise<DocumentStudySummary> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preview: false, mode: options.mode ?? "concise" }),
  });
  return parseJsonResponse<DocumentStudySummary>(response);
}

export async function previewDocumentStudySummary(
  documentId: string,
  options: GenerateStudySummaryOptions = {},
): Promise<DocumentStudySummary> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preview: true, mode: options.mode ?? "concise" }),
  });
  return parseJsonResponse<DocumentStudySummary>(response);
}

export async function saveDocumentStudySummary(
  documentId: string,
  summary: DocumentStudySummary,
): Promise<DocumentStudySummary> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: summary.content,
      citations: summary.citations,
      mode: summary.generation_mode ?? "concise",
    }),
  });
  return parseJsonResponse<DocumentStudySummary>(response);
}

export async function getStudyQuestions(documentId: string): Promise<StudyQuestion[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/questions`, { cache: "no-store" });
  return parseJsonResponse<StudyQuestion[]>(response);
}

export type GenerateStudyQuestionsOptions = {
  replaceExisting?: boolean;
  preview?: boolean;
  mode?: StudyGenerationMode;
};

export async function generateStudyQuestions(
  documentId: string,
  count = 5,
  options: GenerateStudyQuestionsOptions = {},
): Promise<StudyQuestion[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      count,
      replace_existing: options.replaceExisting ?? false,
      preview: options.preview ?? false,
      mode: options.mode ?? "balanced",
    }),
  });
  return parseJsonResponse<StudyQuestion[]>(response);
}

export async function previewStudyQuestions(
  documentId: string,
  count = 5,
  options: GenerateStudyQuestionsOptions = {},
): Promise<StudyQuestion[]> {
  return generateStudyQuestions(documentId, count, {
    ...options,
    replaceExisting: options.replaceExisting ?? true,
    preview: true,
  });
}

export async function saveStudyQuestions(
  documentId: string,
  questions: StudyQuestion[],
  options: GenerateStudyQuestionsOptions = {},
): Promise<StudyQuestion[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      count: questions.length,
      replace_existing: options.replaceExisting ?? true,
      mode: options.mode ?? questions[0]?.generation_mode ?? "balanced",
      questions: questions.map((question) => ({
        question: question.question,
        expected_answer: question.expected_answer,
        citations: question.citations,
      })),
    }),
  });
  return parseJsonResponse<StudyQuestion[]>(response);
}

export async function submitStudyAnswer(
  documentId: string,
  questionId: string,
  answerText: string,
): Promise<StudyAnswer> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/study/questions/${questionId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer_text: answerText }),
  });
  return parseJsonResponse<StudyAnswer>(response);
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
