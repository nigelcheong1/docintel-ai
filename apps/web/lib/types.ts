export type ParseQuality = {
  page_count: number;
  text_page_count: number;
  empty_page_count: number;
  total_characters: number;
  average_characters_per_page: number;
  low_text_page_ratio: number;
  scanned_likelihood: "low" | "medium" | "high";
  warnings: string[];
  ocr_page_count: number;
  native_text_page_count: number;
  hybrid_page_count: number;
  ocr_confidence_average: number | null;
  ocr_duration_ms: number;
  text_source_summary: Record<string, number>;
};

export type DocumentSummary = {
  id: string;
  filename: string;
  mime_type: string;
  status: string;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
  page_count?: number;
  chunk_count?: number;
  parse_quality?: ParseQuality | null;
  processing_status?: DocumentProcessingStatus | null;
};

export type DocumentDetail = DocumentSummary & {
  page_count: number;
  chunk_count: number;
};

export type DocumentProcessingStage = {
  key: "upload" | "extract" | "ocr" | "chunk" | "embed" | "ready" | "failed";
  label: string;
  status: "pending" | "active" | "complete" | "failed";
  detail?: string | null;
};

export type DocumentProcessingStatus = {
  document_id: string;
  filename: string;
  status: string;
  active_stage: "upload" | "extract" | "ocr" | "chunk" | "embed" | "ready" | "failed";
  progress_percent: number;
  message: string;
  page_count: number;
  chunk_count: number;
  embedded_chunk_count: number;
  ocr_page_count: number;
  stages: DocumentProcessingStage[];
};

export type DocumentPage = {
  document_id: string;
  page_number: number;
  image_url: string;
  text_source: string;
  text_preview: string;
  character_count: number;
  chunk_count: number;
  token_estimate: number;
  text_density: number;
  ocr_quality: "native" | "strong" | "moderate" | "weak" | "missing";
  processing_status: "native_text" | "ocr_strong" | "ocr_moderate" | "ocr_weak" | "missing_text";
  needs_review: boolean;
  ocr_engine?: string | null;
  ocr_confidence?: number | null;
  ocr_duration_ms?: number | null;
};

export type DocumentChunk = {
  id: string;
  document_id: string;
  page_number: number;
  chunk_index: number;
  text: string;
  token_estimate: number;
};

export type DocumentSection = {
  heading: string;
  page_number: number;
  text_preview: string;
  intents: string[];
};

export type DocumentFact = {
  kind: string;
  label: string;
  value: string;
  page_number: number;
  source_text: string;
};

export type DocumentProfile = {
  document_id: string;
  filename: string;
  document_type: string;
  title?: string | null;
  overview?: string | null;
  sections: DocumentSection[];
  key_dates: DocumentFact[];
  key_numbers: DocumentFact[];
  key_entities: DocumentFact[];
  suggested_questions: string[];
};

export type StudyCitation = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  section_heading?: string | null;
  page_image_url?: string | null;
  document_page_url?: string | null;
  snippet?: string | null;
  score?: number | null;
  source_score?: number | null;
  ranking_signals?: Record<string, number>;
};

export type StudyAnswer = {
  id: string;
  question_id: string;
  answer_text: string;
  score: number;
  feedback: string;
  created_at: string;
};

export type StudyQuestion = {
  id: string;
  document_id: string;
  question: string;
  expected_answer: string;
  citations: StudyCitation[];
  created_at: string;
  latest_answer?: StudyAnswer | null;
  answer_count?: number;
  recent_answers?: StudyAnswer[];
};

export type DocumentStudySummary = {
  id: string;
  document_id: string;
  content: string;
  citations: StudyCitation[];
  created_at: string;
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
  page_image_url?: string;
  document_page_url?: string;
  section_heading?: string | null;
  result_role?: "answer_evidence" | "related";
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

export type SearchDiagnostics = {
  document_type?: string | null;
  query_intent: string;
  quality_status: "answerable" | "insufficient_evidence";
  confidence: "strong" | "moderate" | "weak";
  reason: string;
  answer_chunk_ids: string[];
  answer_evidence_count: number;
  related_result_count: number;
  top_rejected_reasons: string[];
};

export type SearchResponse = {
  query: string;
  hits: SearchHit[];
  answer: SearchAnswer | null;
  quality: AnswerQuality;
  document_type?: string | null;
  query_intent: string;
  retrieval_mode?: "hybrid" | "vector" | "lexical";
  retrieval_fallback_reason?: string | null;
  diagnostics?: SearchDiagnostics | null;
};

export type EvalRunSummary = {
  id: string;
  name: string;
  model_name: string;
  metrics: Record<string, number>;
  created_at: string;
};

export type GoldenEvalCaseResult = {
  case_id: string;
  document_name: string;
  document_type: string;
  question: string;
  expected_status: "answerable" | "insufficient_evidence";
  actual_status: "answerable" | "insufficient_evidence";
  expected_terms: string[];
  query_intent: string;
  confidence: "strong" | "moderate" | "weak";
  citation_count: number;
  answer_preview?: string | null;
  quality_reason: string;
  passed: boolean;
  failure_reasons: string[];
};

export type GoldenEvalResponse = {
  name: string;
  summary: {
    total_cases: number;
    passed_cases: number;
    failed_cases: number;
    pass_rate: number;
    answerable_cases: number;
    abstention_cases: number;
    document_types: Record<string, number>;
    quality_dimensions: Record<string, number>;
  };
  cases: GoldenEvalCaseResult[];
};
