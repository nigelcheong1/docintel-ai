import type { DocumentEvalCase, DocumentEvalSuiteDetail, DocumentSummary } from "@/lib/types";

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
