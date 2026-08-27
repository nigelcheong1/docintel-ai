import type { EvalRunSummary } from "@/lib/types";

export function EvaluationSummary({ runs }: { runs: EvalRunSummary[] }) {
  if (runs.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No evaluation runs recorded.</p>;
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <article key={run.id} className="rounded border border-line bg-white p-4">
          <h2 className="break-words text-sm font-semibold">{run.name}</h2>
          <p className="mt-1 break-all text-xs text-slate-500">{run.model_name}</p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(run.metrics).map(([key, value]) => (
              <div key={key}>
                <dt className="break-words text-xs uppercase text-slate-500">{key.replaceAll("_", " ")}</dt>
                <dd className="mt-1 text-xl font-semibold">
                  {key === "evaluated_questions" ? value.toFixed(0) : value.toFixed(2)}
                </dd>
              </div>
            ))}
          </dl>
        </article>
      ))}
    </div>
  );
}
