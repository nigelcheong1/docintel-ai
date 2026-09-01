import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import type { EvalRunSummary, GoldenEvalCaseResult, GoldenEvalResponse } from "@/lib/types";

function formatMetricName(name: string) {
  return name.replaceAll("_", " ");
}

function formatDocumentType(type: string) {
  const label = type.replaceAll("_", " ").toLowerCase();
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function statusClassName(passed: boolean) {
  return passed ? "success" : "amber";
}

function formatQualityDimension(name: string) {
  const labels: Record<string, string> = {
    answer_quality: "Answer quality",
    abstention_safety: "Abstention safety",
    parse_quality: "Parse quality",
  };

  return labels[name] ?? formatMetricName(name);
}

function GoldenCaseRow({ result }: { result: GoldenEvalCaseResult }) {
  return (
    <tr className="align-top">
      <td className="border-t border-line py-3 pr-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="break-all text-xs font-semibold text-slate-700">{result.case_id}</span>
          <span className="break-words text-xs text-slate-500">{result.question}</span>
        </div>
      </td>
      <td className="border-t border-line px-3 py-3 text-xs text-slate-600">{formatDocumentType(result.document_type)}</td>
      <td className="border-t border-line px-3 py-3 text-xs text-slate-600">{formatDocumentType(result.query_intent)}</td>
      <td className="border-t border-line px-3 py-3 text-xs text-slate-600">{result.citation_count}</td>
      <td className="border-t border-line px-3 py-3">
        <Badge tone={statusClassName(result.passed)}>
          {result.passed ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> : <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />}
          {result.passed ? "Pass" : "Review"}
        </Badge>
      </td>
      <td className="border-t border-line py-3 pl-3 text-xs leading-5 text-slate-600">
        {result.answer_preview ?? result.quality_reason}
        {result.failure_reasons.length > 0 ? (
          <ul className="mt-1 space-y-1 text-amber-700">
            {result.failure_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
      </td>
    </tr>
  );
}

function GoldenEvaluationPanel({ golden }: { golden: GoldenEvalResponse }) {
  const qualityDimensions = golden.summary.quality_dimensions ?? {};

  return (
    <Panel tone="accent" className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Universal document QA</h2>
          <p className="mt-1 break-words text-xs text-slate-500">{golden.name}</p>
        </div>
        <Badge tone={statusClassName(golden.summary.failed_cases === 0)}>
          {golden.summary.failed_cases === 0 ? (
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {golden.summary.failed_cases === 0 ? "All passing" : `${golden.summary.failed_cases} failing`}
        </Badge>
      </div>

      <dl className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-line bg-teal-50/40 p-3">
          <dt className="text-xs uppercase text-slate-500">Pass rate</dt>
          <dd className="mt-1 text-xl font-semibold">{formatPercent(golden.summary.pass_rate)}</dd>
        </div>
        <div className="rounded-lg border border-line bg-white p-3">
          <dt className="text-xs uppercase text-slate-500">Cases</dt>
          <dd className="mt-1 text-xl font-semibold">{golden.summary.total_cases} cases</dd>
        </div>
        <div className="rounded-lg border border-line bg-white p-3">
          <dt className="text-xs uppercase text-slate-500">Answerable</dt>
          <dd className="mt-1 text-xl font-semibold">{golden.summary.answerable_cases}</dd>
        </div>
        <div className="rounded-lg border border-line bg-white p-3">
          <dt className="text-xs uppercase text-slate-500">Abstentions</dt>
          <dd className="mt-1 text-xl font-semibold">{golden.summary.abstention_cases}</dd>
        </div>
      </dl>

      {Object.keys(qualityDimensions).length > 0 ? (
        <section className="mt-5" aria-labelledby="quality-coverage-heading">
          <h3 id="quality-coverage-heading" className="text-sm font-semibold">
            Quality coverage
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(qualityDimensions).map(([dimension, count]) => (
              <Badge key={dimension} tone={dimension === "abstention_safety" ? "amber" : "teal"}>
                <span>{formatQualityDimension(dimension)}</span>
                <span>{count}</span>
              </Badge>
            ))}
          </div>
        </section>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {Object.entries(golden.summary.document_types).map(([type, count]) => (
          <Badge key={type} tone="neutral">{formatDocumentType(type)} {count}</Badge>
        ))}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="pb-2 pr-3 font-medium">Case</th>
              <th className="px-3 pb-2 font-medium">Document</th>
              <th className="px-3 pb-2 font-medium">Intent</th>
              <th className="px-3 pb-2 font-medium">Citations</th>
              <th className="px-3 pb-2 font-medium">Status</th>
              <th className="pb-2 pl-3 font-medium">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {golden.cases.map((result) => (
              <GoldenCaseRow key={result.case_id} result={result} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export function EvaluationSummary({ runs, golden }: { runs: EvalRunSummary[]; golden?: GoldenEvalResponse | null }) {
  if (runs.length === 0 && !golden) {
    return <Panel className="text-sm text-slate-600">No evaluation runs recorded.</Panel>;
  }

  return (
    <div className="space-y-3">
      {golden ? <GoldenEvaluationPanel golden={golden} /> : null}
      {runs.map((run) => (
        <Panel key={run.id} className="p-5">
          <h2 className="break-words text-sm font-semibold">{run.name}</h2>
          <p className="mt-1 break-all text-xs text-slate-500">{run.model_name}</p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(run.metrics).map(([key, value]) => (
              <div key={key}>
                <dt className="break-words text-xs uppercase text-slate-500">{formatMetricName(key)}</dt>
                <dd className="mt-1 text-xl font-semibold">
                  {key === "evaluated_questions" ? value.toFixed(0) : value.toFixed(2)}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>
      ))}
    </div>
  );
}
