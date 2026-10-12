"use client";

import { useEffect, useState } from "react";
import { Play, RefreshCw } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { EvaluationSummary } from "@/components/evaluation-summary";
import { DocumentBenchmarks } from "@/components/document-benchmarks";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { createEvalRun, getEvalRuns, getGoldenEval } from "@/lib/api";
import type { EvalRunSummary, GoldenEvalResponse } from "@/lib/types";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function EvaluationPage() {
  const [tab, setTab] = useState<"documents" | "fixtures">("documents");
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [golden, setGolden] = useState<GoldenEvalResponse | null>(null);
  const [message, setMessage] = useState("Loading evaluations...");
  const [isCreating, setIsCreating] = useState(false);
  const [isRefreshingGolden, setIsRefreshingGolden] = useState(false);

  useEffect(() => {
    if (tab !== "fixtures") return;
    let cancelled = false;
    queueMicrotask(async () => {
      const [runsResult, goldenResult] = await Promise.allSettled([getEvalRuns(), getGoldenEval()]);
      if (cancelled) return;
      const loadMessages: string[] = [];

      if (runsResult.status === "fulfilled") {
        setRuns(runsResult.value);
      } else {
        loadMessages.push(errorMessage(runsResult.reason, "Could not load evaluation runs."));
      }

      if (goldenResult.status === "fulfilled") {
        setGolden(goldenResult.value);
      } else {
        loadMessages.push(errorMessage(goldenResult.reason, "Could not load golden QA."));
      }

      setMessage(loadMessages.join(" "));
    });
    return () => { cancelled = true; };
  }, [tab]);

  async function handleCreateRun() {
    setIsCreating(true);
    setMessage("Running local retrieval evaluation...");
    try {
      const run = await createEvalRun();
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setMessage("");
    } catch (error) {
      setMessage(errorMessage(error, "Evaluation failed."));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleRefreshGolden() {
    setIsRefreshingGolden(true);
    setMessage("Running golden document QA...");
    try {
      setGolden(await getGoldenEval());
      setMessage("");
    } catch (error) {
      setMessage(errorMessage(error, "Golden QA failed."));
    } finally {
      setIsRefreshingGolden(false);
    }
  }

  return (
    <AppShell>
      <section className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black tracking-normal">Evaluation Lab</h1>
        </div>
        {tab === "fixtures" ? <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            onClick={() => void handleRefreshGolden()}
            disabled={isRefreshingGolden}
            variant="secondary"
            leftIcon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
            isLoading={isRefreshingGolden}
          >
            {isRefreshingGolden ? "Running..." : "Refresh fixture tests"}
          </Button>
          <Button
            type="button"
            onClick={() => void handleCreateRun()}
            disabled={isCreating}
            leftIcon={<Play className="h-4 w-4" aria-hidden="true" />}
            isLoading={isCreating}
          >
            {isCreating ? "Running..." : "Run evaluation"}
          </Button>
        </div> : null}
      </section>
      <div role="tablist" aria-label="Evaluation scope" className="mb-6 flex gap-4 border-b border-line">
        {(["documents", "fixtures"] as const).map((value) => <button key={value} id={`evaluation-${value}-tab`} role="tab" aria-selected={tab === value} aria-controls={`evaluation-${value}-panel`} tabIndex={tab === value ? 0 : -1}
          className={`min-h-11 border-b-2 px-1 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${tab === value ? "border-teal-600 text-teal-800" : "border-transparent text-slate-600"}`}
          onClick={() => setTab(value)} onKeyDown={(event) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); const next = event.key === "Home" ? "documents" : event.key === "End" ? "fixtures" : value === "documents" ? "fixtures" : "documents"; setTab(next); document.getElementById(`evaluation-${next}-tab`)?.focus(); } }}>
          {value === "documents" ? "Document Benchmarks" : "Fixture Tests"}
        </button>)}
      </div>
      <div role="tabpanel" id={`evaluation-${tab}-panel`} aria-labelledby={`evaluation-${tab}-tab`}>
        {tab === "documents" ? <DocumentBenchmarks /> : <>{message ? <Panel className="mb-4 text-sm text-slate-600">{message}</Panel> : null}<EvaluationSummary runs={runs} golden={golden} /></>}
      </div>
    </AppShell>
  );
}
