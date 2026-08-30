export type DocumentSummary = {
  id: string;
  filename: string;
  mime_type: string;
  status: string;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type DocumentDetail = DocumentSummary & {
  page_count: number;
  chunk_count: number;
};

export type SearchHit = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_index: number;
  score: number;
  source_score: number;
  ranking_signals: Record<string, number>;
  snippet: string;
  section_heading?: string | null;
};

export type AnswerCitation = {
  chunk_id: string;
  document_filename: string;
  page_number: number;
  section_heading?: string | null;
};

export type SearchAnswer = {
  summary: string;
  citations: AnswerCitation[];
};

export type AnswerQuality = {
  status: "answerable" | "insufficient_evidence";
  confidence: "strong" | "moderate" | "weak";
  reason: string;
  evidence_count: number;
  best_score: number;
  best_source_score: number;
  best_keyword_overlap: number;
  best_section_intent: number;
  suggested_questions: string[];
};

export type SearchResponse = {
  query: string;
  hits: SearchHit[];
  answer: SearchAnswer | null;
  quality: AnswerQuality;
};

export type EvalRunSummary = {
  id: string;
  name: string;
  model_name: string;
  metrics: Record<string, number>;
  created_at: string;
};
