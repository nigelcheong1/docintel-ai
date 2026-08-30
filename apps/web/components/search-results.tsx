import { AlertTriangle, CheckCircle2, Lightbulb } from "lucide-react";

import type { AnswerQuality, SearchAnswer, SearchHit } from "@/lib/types";

function formatSignalName(signal: string) {
  const label = signal.replace(/_/g, " ");
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

export function SearchResults({
  hits,
  answer,
  quality,
  onSuggestionSelect,
}: {
  hits: SearchHit[];
  answer?: SearchAnswer | null;
  quality?: AnswerQuality | null;
  onSuggestionSelect?: (question: string) => void;
}) {
  if (hits.length === 0 && !answer && quality?.status !== "insufficient_evidence") {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No cited evidence found.</p>;
  }

  return (
    <div className="space-y-3">
      {answer ? (
        <section className="border-l-2 border-accent bg-white px-4 py-4" aria-labelledby="answer-heading">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="answer-heading" className="text-sm font-semibold">
              Answer
            </h2>
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
              <h2 id="abstention-heading" className="text-sm font-semibold">
                Not enough evidence
              </h2>
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
      {hits.map((hit) => (
        <article key={hit.chunk_id} className="min-w-0 rounded border border-line bg-white p-4">
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
      ))}
    </div>
  );
}
