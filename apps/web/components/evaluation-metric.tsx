import type { EvaluationMeasurement } from "@/lib/types";

export function EvaluationMetric({ label, measurement }: { label: string; measurement: EvaluationMeasurement }) {
  const numerator = Number(measurement.numerator.toFixed(2));
  return (
    <div className="min-w-0">
      <dt className="break-words text-xs text-slate-600">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums">
        {measurement.value === null ? "Not evaluated" : measurement.unit === "ms" ? `${Math.round(measurement.value)} ms` : `${Math.round(measurement.value * 100)}%`}
      </dd>
      <dd className="mt-1 text-xs tabular-nums text-slate-600">{numerator} / {measurement.denominator}</dd>
      <dd className="mt-1 break-words text-xs leading-5 text-slate-500">{measurement.scope}</dd>
    </div>
  );
}
