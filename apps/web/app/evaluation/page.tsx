import { AppShell } from "@/components/app-shell";
import { EvaluationSummary } from "@/components/evaluation-summary";

export default function EvaluationPage() {
  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Evaluation</h1>
        <p className="mt-2 text-sm text-slate-600">Track local retrieval metrics for repeatable project demos.</p>
      </section>
      <EvaluationSummary runs={[]} />
    </AppShell>
  );
}
