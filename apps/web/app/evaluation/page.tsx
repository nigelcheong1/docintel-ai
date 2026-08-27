"use client";

import { useEffect, useState } from "react";
import { Play } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { EvaluationSummary } from "@/components/evaluation-summary";
import { createEvalRun, getEvalRuns } from "@/lib/api";
import type { EvalRunSummary } from "@/lib/types";

export default function EvaluationPage() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [message, setMessage] = useState("Loading evaluation runs...");
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    queueMicrotask(async () => {
      try {
        setRuns(await getEvalRuns());
        setMessage("");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Could not load evaluation runs.");
      }
    });
  }, []);

  async function handleCreateRun() {
    setIsCreating(true);
    setMessage("Running local retrieval evaluation...");
    try {
      const run = await createEvalRun();
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Evaluation failed.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <AppShell>
      <section className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Evaluation</h1>
          <p className="mt-2 text-sm text-slate-600">Track local retrieval metrics for repeatable project demos.</p>
        </div>
        <button
          type="button"
          onClick={() => void handleCreateRun()}
          disabled={isCreating}
          className="inline-flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {isCreating ? "Running..." : "Run evaluation"}
        </button>
      </section>
      {message ? <p className="mb-4 text-sm text-slate-600">{message}</p> : null}
      <EvaluationSummary runs={runs} />
    </AppShell>
  );
}
