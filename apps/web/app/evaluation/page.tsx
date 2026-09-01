"use client";

import { useEffect, useState } from "react";
import { Play, RefreshCw } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { EvaluationSummary } from "@/components/evaluation-summary";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { createEvalRun, getEvalRuns, getGoldenEval } from "@/lib/api";
import type { EvalRunSummary, GoldenEvalResponse } from "@/lib/types";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function EvaluationPage() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [golden, setGolden] = useState<GoldenEvalResponse | null>(null);
  const [message, setMessage] = useState("Loading evaluations...");
  const [isCreating, setIsCreating] = useState(false);
  const [isRefreshingGolden, setIsRefreshingGolden] = useState(false);

  useEffect(() => {
    queueMicrotask(async () => {
      const [runsResult, goldenResult] = await Promise.allSettled([getEvalRuns(), getGoldenEval()]);
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
  }, []);

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
          <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Quality workbench</p>
          <h1 className="mt-2 text-3xl font-black tracking-normal">Evaluation</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Track golden QA safety, parse-quality coverage, and local retrieval metrics before shipping changes.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            onClick={() => void handleRefreshGolden()}
            disabled={isRefreshingGolden}
            variant="secondary"
            leftIcon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
            isLoading={isRefreshingGolden}
          >
            {isRefreshingGolden ? "Running..." : "Refresh golden QA"}
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
        </div>
      </section>
      {message ? <Panel className="mb-4 text-sm text-slate-600">{message}</Panel> : null}
      <EvaluationSummary runs={runs} golden={golden} />
    </AppShell>
  );
}
