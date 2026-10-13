"use client";

import { useEffect, useRef, useState } from "react";
import { Eye, RefreshCw, Save, Square } from "lucide-react";
import { benchmarkInputClass } from "@/components/benchmark-case-editor";
import { EvaluationMetric } from "@/components/evaluation-metric";
import { SourceViewer, type SourceViewerSource } from "@/components/source-viewer";
import { Button } from "@/components/ui/button";
import { getDocumentPages } from "@/lib/api";
import { assessDocumentResult, cancelDocumentRun, getDocumentRun, getDocumentRunResults } from "@/lib/document-evaluation";
import type { BenchmarkEvidence, DocumentAssessment, DocumentEvalResult, DocumentEvalRun } from "@/lib/types";

const metricLabels: Record<string, string> = {
  outcome_match: "Outcome match", fact_match: "Expected fact pattern match", retrieval_anchor_recall_at_5: "Reviewed-anchor recall at 5",
  citation_precision: "Citation precision", citation_anchor_coverage: "Citation anchor coverage", pack_anchor_coverage: "Evidence pack anchor coverage",
  abstention_match: "Abstention match", checker_support: "Sentence checker support", latency: "Latency",
  table_case_pass_rate: "Table-tagged case checks", multi_part_case_pass_rate: "Multi-part case checks",
};
const filters = ["All", "Failed", "Unavailable", "Errors", "Needs human review"] as const;
function filterResult(result: DocumentEvalResult, filter: typeof filters[number]) {
  if (filter === "All") return true;
  if (filter === "Needs human review") return !result.human_assessment || result.human_assessment === "needs_review";
  return result.status === ({ Failed: "fail", Unavailable: "unavailable", Errors: "error" } as const)[filter];
}
function EvidenceRows({ hits, onPreview }: { hits: BenchmarkEvidence[]; onPreview: (hit: BenchmarkEvidence) => void }) {
  return hits.length ? <ul className="divide-y divide-line">{hits.map((hit) => <li key={hit.chunk_id} className="min-w-0 py-3 text-xs">
    <div className="flex flex-wrap items-center justify-between gap-2"><span className="break-all">Page {hit.page_number} · Chunk {hit.chunk_id} · Score {hit.score.toFixed(3)}</span>
      <Button variant="ghost" title="Preview evidence" aria-label={`Preview page ${hit.page_number} chunk ${hit.chunk_id}`} onClick={() => onPreview(hit)}><Eye className="h-4 w-4" /></Button>
    </div><p className="mt-2 whitespace-pre-wrap break-words leading-5 text-slate-600">{hit.text}</p>
  </li>)}</ul> : <p className="py-3 text-sm text-slate-600">No evidence recorded.</p>;
}
function CaseResult({ result, onAssessed }: { result: DocumentEvalResult; onAssessed: (item: DocumentEvalResult) => void }) {
  const [assessment, setAssessment] = useState<DocumentAssessment | "">(result.human_assessment ?? "");
  const [note, setNote] = useState(result.assessment_note);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [source, setSource] = useState<SourceViewerSource | null>(null);
  const response = result.execution_snapshot.response;
  const expected = result.case_snapshot;
  async function preview(pageNumber: number, chunkId: string, snippet: string, documentId = expected.document_id) {
    setMessage("");
    try {
      if (!documentId) throw new Error("Source document is no longer available. Saved evidence is retained below.");
      const pages = await getDocumentPages(documentId);
      const page = pages.find((item) => item.page_number === pageNumber);
      if (!page) throw new Error("Source page is no longer available. Saved evidence is retained below.");
      setSource({ document_id: documentId, document_filename: expected.document_filename, chunk_id: chunkId, page_number: pageNumber, page_image_url: page.image_url, snippet });
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Could not preview source."); }
  }
  async function saveAssessment() {
    if (!assessment) return;
    setBusy(true); setMessage("");
    try { onAssessed(await assessDocumentResult(result.run_id, result.id, assessment, note)); setMessage("Assessment saved."); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Assessment could not be saved."); }
    finally { setBusy(false); }
  }
  return <article className="min-w-0 border-b border-line py-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="min-w-0 flex-1 break-words text-base font-bold">{expected.question}</h3>
      <span className={`text-xs font-semibold ${result.status === "pass" ? "text-teal-700" : "text-red-700"}`}>
        {result.status === "pass" ? "Automatic checks passed" : result.status === "fail" ? "Automatic checks failed" : result.status === "error" ? "Execution error" : "Source unavailable"}
      </span>
    </div>
    <p className="mt-2 break-words text-xs text-slate-600">{expected.document_filename} · Reviewed version {result.case_version} · {Math.round(result.duration_ms)} ms · {response?.retrieval_mode === "lexical" ? "Lexical retrieval" : response?.retrieval_mode ?? "Retrieval not executed"}</p>
    {response?.retrieval_fallback_reason ? <p className="mt-2 break-words text-sm text-amber-800">{response.retrieval_fallback_reason}</p> : null}
    {result.failure_reasons.map((reason) => <p key={reason} className="mt-2 break-words text-sm text-red-700">{reason}</p>)}
    <div className="mt-4 grid gap-5 md:grid-cols-2">
      <section className="min-w-0"><h4 className="text-sm font-bold">Expected snapshot</h4><p className="mt-2 text-sm">{expected.expected_outcome === "answerable" ? "Answerable" : "Not enough evidence"}</p>
        <ul className="mt-2 space-y-2 text-sm">{expected.facts.map((fact, index) => <li key={index} className="break-words"><span>{fact.pattern}</span>{fact.alternatives.length ? <span className="ml-2 text-slate-600">Alternatives: {fact.alternatives.map((value) => <span key={value} className="mr-2">{value}</span>)}</span> : null}</li>)}</ul>
        <ul className="mt-3 space-y-2">{expected.anchors.map((anchor, index) => <li key={index} className="min-w-0 text-sm"><button className="text-left text-teal-700 underline underline-offset-2" onClick={() => void preview(anchor.page_number, result.execution_snapshot.resolved_anchors?.[index]?.chunk_ids[0] ?? "", anchor.quote)}>Page {anchor.page_number}</button><p className="mt-1 break-words text-slate-600">{anchor.quote}</p></li>)}</ul>
        {expected.review_rationale ? <p className="mt-3 break-words text-sm text-slate-600">Review rationale: {expected.review_rationale}</p> : null}
      </section>
      <section className="min-w-0"><h4 className="text-sm font-bold">Actual answer</h4><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{response?.answer?.summary ?? "No answer generated."}</p>
        <div className="mt-3 flex flex-wrap gap-3">{response?.answer?.citations.map((citation) => <button key={citation.chunk_id} className="text-xs text-teal-700 underline underline-offset-2" onClick={() => void preview(citation.page_number, citation.chunk_id, result.execution_snapshot.selected_evidence?.find((hit) => hit.chunk_id === citation.chunk_id)?.text ?? "")}>{citation.document_filename}, page {citation.page_number}</button>)}</div>
        {response?.verification ? <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">Sentence checks ({response.verification.sentences.length} checked, {response.verification.removed_sentence_count} removed)</summary><ul className="mt-2 space-y-2">{response.verification.sentences.map((sentence, index) => <li key={index} className="break-words">{sentence.sentence}<span className="ml-2 text-xs text-slate-600">{sentence.status.replaceAll("_", " ")}</span></li>)}</ul></details> : null}
      </section>
    </div>
    <details className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Case measurements</summary><dl className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(result.measurements).map(([key, measurement]) => <EvaluationMetric key={key} label={metricLabels[key] ?? key} measurement={measurement} />)}</dl></details>
    <details className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Candidates before evidence selection</summary>
      {Object.entries(result.execution_snapshot.candidates_by_subquery ?? {}).map(([query, hits]) => <section key={query} className="mt-3 min-w-0"><h4 className="break-words font-semibold">{query}</h4><EvidenceRows hits={hits} onPreview={(hit) => void preview(hit.page_number, hit.chunk_id, hit.text, hit.document_id)} /></section>)}
    </details>
    <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">Selected evidence pack</summary><EvidenceRows hits={result.execution_snapshot.selected_evidence ?? []} onPreview={(hit) => void preview(hit.page_number, hit.chunk_id, hit.text, hit.document_id)} /></details>
    <form className="mt-5 flex flex-wrap items-end gap-3 border-t border-line pt-4" onSubmit={(event) => { event.preventDefault(); void saveAssessment(); }}>
      <label className="min-w-0 text-sm font-semibold">Human assessment<select className={benchmarkInputClass} value={assessment} onChange={(event) => setAssessment(event.target.value as DocumentAssessment | "")}><option value="">Not assessed</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option><option value="needs_review">Needs review</option></select></label>
      <label className="min-w-0 flex-1 text-sm font-semibold">Assessment note<textarea className={benchmarkInputClass} rows={2} maxLength={4000} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      <Button type="submit" variant="secondary" leftIcon={<Save className="h-4 w-4" />} disabled={busy || !assessment}>Save assessment</Button>
    </form>
    {message ? <p role="status" className="mt-2 break-words text-sm text-slate-600">{message}</p> : null}
    {source ? <SourceViewer source={source} onClose={() => setSource(null)} /> : null}
  </article>;
}

export function BenchmarkRunResults({ runId, onRunUpdated }: { runId: string; onRunUpdated?: (run: DocumentEvalRun) => void }) {
  const [run, setRun] = useState<DocumentEvalRun | null>(null);
  const [results, setResults] = useState<DocumentEvalResult[]>([]);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [filter, setFilter] = useState<typeof filters[number]>("All");
  const isCurrentRun = useRef<() => boolean>(() => false);
  useEffect(() => {
    let stopped = false;
    isCurrentRun.current = () => !stopped;
    return () => { stopped = true; };
  }, [runId]);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const current = await getDocumentRun(runId);
        const items = await getDocumentRunResults(runId);
        if (stopped) return;
        setRun(current); setResults(items); setError("");
        onRunUpdated?.(current);
        if (current.status === "queued" || current.status === "running") timer = setTimeout(() => void load(), 2000);
      } catch (reason) { if (!stopped) setError(reason instanceof Error ? reason.message : "Could not refresh run. Saved results are still shown."); }
    }
    void load();
    return () => { stopped = true; clearTimeout(timer); };
  }, [runId, refresh, onRunUpdated]);
  async function cancel() {
    const isCurrent = isCurrentRun.current;
    setCancellingRunId(runId);
    try {
      const current = await cancelDocumentRun(runId);
      if (!isCurrent()) return;
      setRun(current); onRunUpdated?.(current); setError(""); setRefresh((value) => value + 1);
    }
    catch (reason) { if (isCurrent()) setError(reason instanceof Error ? reason.message : "Could not cancel run."); }
    finally { if (isCurrent()) setCancellingRunId(null); }
  }
  const active = run?.status === "queued" || run?.status === "running";
  const shown = results.filter((result) => filterResult(result, filter));
  return <section aria-label="Saved benchmark run" className="mt-6 min-w-0 border-t border-line pt-5">
    {error ? <div className="mb-4 flex flex-wrap items-center gap-3"><p role="alert" className="break-words text-sm text-red-700">{error}</p><Button variant="secondary" onClick={() => setRefresh((value) => value + 1)} leftIcon={<RefreshCw className="h-4 w-4" />}>Retry run refresh</Button></div> : null}
    {!run ? <p role="status">Loading saved run...</p> : <>
      <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h2 className="break-words text-lg font-bold">{run.suite_snapshot.name}</h2><p className="mt-1 text-sm capitalize">{run.status}</p><p role="status" className="mt-2 text-sm font-semibold">{run.completed_cases} / {run.total_cases} cases finished</p></div>
        {active ? <Button variant="secondary" disabled={cancellingRunId === runId || run.cancel_requested} leftIcon={<Square className="h-4 w-4" />} onClick={() => void cancel()}>Cancel run</Button> : null}
      </div>
      {run.cancel_requested ? <p className="mt-2 text-sm text-amber-800">Cancellation requested</p> : null}
      {run.error ? <p className="mt-2 break-words text-sm text-red-700">{run.error}</p> : null}
      <p className="mt-3 text-sm text-slate-600">{run.passed_count} automatic passes · {run.failed_count} failures · {run.unavailable_count} unavailable · {run.error_count} errors</p>
      <p className="mt-1 text-xs text-slate-600">{Object.entries(run.mode_counts).map(([mode, count]) => `${mode === "lexical" ? "Lexical" : mode} ${count}`).join(" · ") || "No retrieval completed"} · {run.fallback_count} fallbacks</p>
      <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">Pipeline snapshot</summary><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-xs text-slate-600">{JSON.stringify(run.pipeline_config, null, 2)}</pre></details>
      <dl className="my-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Object.entries(run.measurements).map(([key, measurement]) => <EvaluationMetric key={key} label={metricLabels[key] ?? key} measurement={measurement} />)}</dl>
      <div className="flex flex-wrap gap-2 border-y border-line py-3" role="group" aria-label="Result filter">{filters.map((value) => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)} className={`min-h-9 rounded-md border px-3 py-1.5 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${filter === value ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-slate-600"}`}>{value}</button>)}</div>
      {shown.map((result) => <CaseResult key={result.id} result={result} onAssessed={(item) => setResults((current) => current.map((value) => value.id === item.id ? item : value))} />)}
      {!shown.length ? <p className="py-5 text-sm text-slate-600">{results.length ? "No results match this filter." : "No cases finished yet."}</p> : null}
    </>}
  </section>;
}
