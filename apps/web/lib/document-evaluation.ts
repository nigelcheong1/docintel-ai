import { API_BASE_URL, parseJsonResponse } from "@/lib/api";
import type { DocumentAssessment, DocumentCaseWrite, DocumentEvalCase, DocumentEvalResult, DocumentEvalRun, DocumentEvalSuite, DocumentEvalSuiteDetail } from "@/lib/types";

const suites = "/eval/document-suites";
async function read<T>(path: string): Promise<T> {
  return parseJsonResponse<T>(await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" }));
}
async function write<T>(path: string, method: string, data: unknown): Promise<T> {
  return parseJsonResponse<T>(await fetch(`${API_BASE_URL}${path}`, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  }));
}
async function remove(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) await parseJsonResponse<unknown>(response);
}
export const listDocumentSuites = () => read<DocumentEvalSuite[]>(suites);
export const createDocumentSuite = (name: string) => write<DocumentEvalSuite>(suites, "POST", { name });
export const getDocumentSuite = (id: string) => read<DocumentEvalSuiteDetail>(`${suites}/${id}`);
export const updateDocumentSuite = (id: string, name: string) => write<DocumentEvalSuite>(`${suites}/${id}`, "PUT", { name });
export const deleteDocumentSuite = (id: string) => remove(`${suites}/${id}`);
export const saveDocumentCase = (suiteId: string, data: DocumentCaseWrite, caseId?: string) =>
  write<DocumentEvalCase>(`${suites}/${suiteId}/cases${caseId ? `/${caseId}` : ""}`, caseId ? "PUT" : "POST", data);
export const deleteDocumentCase = (suiteId: string, caseId: string) => remove(`${suites}/${suiteId}/cases/${caseId}`);
export const reviewDocumentCase = (suiteId: string, caseId: string, version: number) =>
  write<DocumentEvalCase>(`${suites}/${suiteId}/cases/${caseId}/review`, "POST", { content_version: version });
const runs = "/eval/document-runs";
export const createDocumentRun = (suiteId: string) => write<DocumentEvalRun>(runs, "POST", { suite_id: suiteId });
export const listDocumentRuns = (suiteId?: string) => read<DocumentEvalRun[]>(`${runs}${suiteId ? `?suite_id=${encodeURIComponent(suiteId)}` : ""}`);
export const getDocumentRun = (runId: string) => read<DocumentEvalRun>(`${runs}/${runId}`);
export const getDocumentRunResults = (runId: string) => read<DocumentEvalResult[]>(`${runs}/${runId}/results`);
export const cancelDocumentRun = (runId: string) => write<DocumentEvalRun>(`${runs}/${runId}/cancel`, "POST", {});
export const assessDocumentResult = (runId: string, resultId: string, assessment: DocumentAssessment, note: string) =>
  write<DocumentEvalResult>(`${runs}/${runId}/results/${resultId}/assessment`, "PUT", { assessment, note });
