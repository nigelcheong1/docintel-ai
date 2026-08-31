import { AlertTriangle, CheckCircle2, Info, Lightbulb } from "lucide-react";

import type { AnswerQuality, SearchAnswer, SearchDiagnostics, SearchHit } from "@/lib/types";

function formatSignalName(signal: string) {
  const label = signal.replace(/_/g, " ");
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

function formatMetadataValue(value: string) {
  const label = value.replace(/_/g, " ").toLowerCase();
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

function formatPercentage(score: number) {
  return `${Math.round(score * 100)}%`;
}

function formatConfidence(confidence: AnswerQuality["confidence"]) {
  return `${confidence.charAt(0).toUpperCase()}${confidence.slice(1)} confidence`;
}

function confidenceClassName(confidence: AnswerQuality["confidence"]) {
  if (confidence === "strong") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (confidence === "moderate") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function ConfidenceBadge({ confidence }: { confidence: AnswerQuality["confidence"] }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium ${confidenceClassName(confidence)}`}>
      {confidence === "strong" ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> : null}
      {confidence === "weak" ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> : null}
      {formatConfidence(confidence)}
    </span>
  );
}

function MetadataBadges({ documentType, queryIntent }: { documentType?: string | null; queryIntent?: string | null }) {
  const items = [documentType, queryIntent].filter((item): item is string => Boolean(item));
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className="rounded border border-line bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600">
          {formatMetadataValue(item)}
        </span>
      ))}
    </div>
  );
}

function formatCount(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function SearchDiagnosticsPanel({ diagnostics }: { diagnostics: SearchDiagnostics }) {
  return (
    <section className="rounded border border-line bg-white p-4" aria-labelledby="search-diagnostics-heading">
      <div className="flex items-center gap-2">
        <Info className="h-4 w-4 text-accent" aria-hidden="true" />
        <h2 id="search-diagnostics-heading" className="text-sm font-semibold">
          Search diagnostics
        </h2>
      </div>
      <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">Status</dt>
          <dd className="mt-1 font-medium text-slate-700">{formatMetadataValue(diagnostics.quality_status)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Intent</dt>
          <dd className="mt-1 font-medium text-slate-700">{formatMetadataValue(diagnostics.query_intent)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Answer evidence</dt>
          <dd className="mt-1 font-medium text-slate-700">
            {formatCount(diagnostics.answer_evidence_count, "answer chunk", "answer chunks")}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Related results</dt>
          <dd className="mt-1 font-medium text-slate-700">
            {formatCount(diagnostics.related_result_count, "related result", "related results")}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs leading-5 text-slate-600">{diagnostics.reason}</p>
      {diagnostics.top_rejected_reasons.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs text-slate-500">
          {diagnostics.top_rejected_reasons.map((reason) => (
            <li key={reason} className="break-words">
              {reason}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function EvidenceCard({ hit }: { hit: SearchHit }) {
  return (
    <article className="min-w-0 rounded border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="break-all text-sm font-semibold">{hit.document_filename}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>Page {hit.page_number}</span>
            {hit.section_heading ? (
              <span className="rounded border border-line px-2 py-0.5 font-medium text-slate-600">
                {hit.section_heading}
              </span>
            ) : null}
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-right text-xs">
          <dt className="text-slate-500">Blended score</dt>
          <dd className="font-medium">{formatPercentage(hit.score)}</dd>
          <dt className="text-slate-500">Source score</dt>
          <dd className="font-medium">{formatPercentage(hit.source_score)}</dd>
        </dl>
      </div>
      <p className="mt-3 break-words text-sm leading-6 text-slate-700">{hit.snippet}</p>
      {Object.keys(hit.ranking_signals).length > 0 ? (
        <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-xs">
          {Object.entries(hit.ranking_signals).map(([signal, value]) => (
            <div key={signal} className="flex items-baseline gap-1.5">
              <dt className="text-slate-500">{formatSignalName(signal)}</dt>
              <dd className="font-medium text-slate-700">{formatPercentage(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </article>
  );
}

function EvidenceGroup({ title, hits }: { title: string; hits: SearchHit[] }) {
  if (hits.length === 0) {
    return null;
  }
  return (
    <section className="space-y-3" aria-labelledby={`${title.toLowerCase().replaceAll(" ", "-")}-heading`}>
      <h2 id={`${title.toLowerCase().replaceAll(" ", "-")}-heading`} className="text-sm font-semibold text-slate-700">
        {title}
      </h2>
      {hits.map((hit) => (
        <EvidenceCard key={hit.chunk_id} hit={hit} />
      ))}
    </section>
  );
}

export function SearchResults({
  hits,
  answer,
  quality,
  documentType,
  queryIntent,
  diagnostics,
  onSuggestionSelect,
}: {
  hits: SearchHit[];
  answer?: SearchAnswer | null;
  quality?: AnswerQuality | null;
  documentType?: string | null;
  queryIntent?: string | null;
  diagnostics?: SearchDiagnostics | null;
  onSuggestionSelect?: (question: string) => void;
}) {
  if (hits.length === 0 && !answer && quality?.status !== "insufficient_evidence") {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No cited evidence found.</p>;
  }

  const answerChunkIds = new Set([
    ...(diagnostics?.answer_chunk_ids ?? []),
    ...(answer?.citations.map((citation) => citation.chunk_id) ?? []),
  ]);
  const answerEvidence = hits.filter((hit) => hit.result_role === "answer_evidence" || answerChunkIds.has(hit.chunk_id));
  const answerEvidenceIds = new Set(answerEvidence.map((hit) => hit.chunk_id));
  const relatedHits = hits.filter((hit) => !answerEvidenceIds.has(hit.chunk_id));

  return (
    <div className="space-y-3">
      {answer ? (
        <section className="border-l-2 border-accent bg-white px-4 py-4" aria-labelledby="answer-heading">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 id="answer-heading" className="text-sm font-semibold">
                Answer
              </h2>
              <MetadataBadges documentType={documentType} queryIntent={queryIntent} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {quality ? <ConfidenceBadge confidence={quality.confidence} /> : null}
              <span className="text-xs font-medium text-slate-500">
                {answer.citations.length} {answer.citations.length === 1 ? "citation" : "citations"}
              </span>
            </div>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{answer.summary}</p>
          {quality?.reason ? <p className="mt-2 text-xs text-slate-500">{quality.reason}</p> : null}
          {answer.citations.length > 0 ? (
            <ul className="mt-3 space-y-1 text-xs text-slate-600">
              {answer.citations.map((citation) => (
                <li key={citation.chunk_id} className="break-words">
                  {citation.document_filename}, page {citation.page_number}
                  {citation.section_heading ? `, ${citation.section_heading}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
      {!answer && quality?.status === "insufficient_evidence" ? (
        <section className="border-l-2 border-amber-500 bg-white px-4 py-4" aria-labelledby="abstention-heading">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
              <div>
                <h2 id="abstention-heading" className="text-sm font-semibold">
                  Not enough evidence
                </h2>
                <MetadataBadges documentType={documentType} queryIntent={queryIntent} />
              </div>
            </div>
            <ConfidenceBadge confidence={quality.confidence} />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{quality.reason}</p>
          {quality.suggested_questions.length > 0 ? (
            <div className="mt-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />
                Suggested questions
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {quality.suggested_questions.map((question) =>
                  onSuggestionSelect ? (
                    <button
                      key={question}
                      type="button"
                      className="rounded border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:border-accent hover:text-accent"
                      onClick={() => onSuggestionSelect(question)}
                    >
                      {question}
                    </button>
                  ) : (
                    <span key={question} className="rounded border border-line px-2.5 py-1.5 text-xs text-slate-600">
                      {question}
                    </span>
                  ),
                )}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
      {diagnostics ? <SearchDiagnosticsPanel diagnostics={diagnostics} /> : null}
      <EvidenceGroup title="Answer evidence" hits={answerEvidence} />
      <EvidenceGroup title={answerEvidence.length > 0 ? "Related evidence" : "Evidence results"} hits={relatedHits} />
    </div>
  );
}
