import type { DocumentEvalCase, DocumentEvalResult, DocumentEvalRun, DocumentEvalSuiteDetail, DocumentSummary } from "@/lib/types";

export const benchmarkDocument: DocumentSummary = { id: "doc-1", filename: "Research.pdf", mime_type: "application/pdf", status: "indexed" };
export const benchmarkCase: DocumentEvalCase = {
  id: "case-1", suite_id: "suite-1", document_id: "doc-1", document_filename: "Research.pdf",
  question: "How many records were retained?", expected_outcome: "answerable",
  facts: [{ pattern: "2092", alternatives: ["2,092"] }], anchors: [{ page_number: 3, quote: "2092 works retained." }],
  tags: ["multi-part"], review_rationale: "Checked page 3.", review_state: "draft", content_version: 1,
  reviewed_at: null, review_page_hashes: {}, availability: "draft", availability_reasons: [],
  created_at: "2026-10-09T00:00:00Z", updated_at: "2026-10-09T00:00:00Z",
};
export const benchmarkSuite: DocumentEvalSuiteDetail = {
  id: "suite-1", name: "Research checks", case_count: 1, reviewed_count: 0,
  created_at: benchmarkCase.created_at, updated_at: benchmarkCase.updated_at, cases: [benchmarkCase],
};
export const benchmarkRun: DocumentEvalRun = {
  id: "run-1", suite_id: "suite-1", suite_snapshot: { id: "suite-1", name: "Research checks" }, case_snapshots: [benchmarkCase],
  pipeline_config: { embedding_model: "BGE", answer_mode: "verified", revision: "abc123" }, measurements: {
    table_case_pass_rate: { value: null, numerator: 0, denominator: 0, unit: "ratio", scope: "Table-tagged reviewed cases" },
  }, status: "running", cancel_requested: false, total_cases: 2, completed_cases: 1,
  created_at: benchmarkCase.created_at, started_at: benchmarkCase.created_at, finished_at: null, error: null,
  mode_counts: { lexical: 1 }, fallback_count: 1, error_count: 0, unavailable_count: 0, passed_count: 1, failed_count: 0,
};
export const benchmarkResult: DocumentEvalResult = {
  id: "result-1", run_id: "run-1", case_id_snapshot: "case-1", case_version: 1, case_snapshot: benchmarkCase,
  execution_snapshot: { response: {
    query: benchmarkCase.question, hits: [], answer: { summary: "2092 works retained.", citations: [{ chunk_id: "chunk-3", document_filename: "Research.pdf", page_number: 3 }] },
    quality: { status: "answerable", confidence: "strong", reason: "Evidence found", evidence_count: 1, best_score: 0.8, best_source_score: 0.8, best_keyword_overlap: 1, best_section_intent: 1, suggested_questions: [] },
    query_intent: "results", answer_mode: "verified", retrieval_mode: "lexical", retrieval_fallback_reason: "Embedding provider unavailable",
    verification: { status: "verified", sentences: [{ sentence: "2092 works retained.", status: "verified", supporting_chunk_ids: ["chunk-3"], support_score: 1, missing_terms: [], missing_numbers: [] }], removed_sentence_count: 0, unsupported_sentence_count: 0, hallucination_risk: 0, reason: "Supported" },
  }, candidates_by_subquery: { records: [] }, selected_evidence: [] },
  measurements: {}, failure_reasons: [], status: "pass", duration_ms: 125, human_assessment: null, assessment_note: "", assessed_at: null, created_at: benchmarkCase.created_at,
};
