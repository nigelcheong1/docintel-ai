"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, FileSearch, Gauge, ShieldCheck, UploadCloud } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { DocumentList } from "@/components/document-list";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { getDocuments, getEvalRuns } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [evaluationCount, setEvaluationCount] = useState(0);
  const [message, setMessage] = useState("Loading workspace summary...");

  useEffect(() => {
    queueMicrotask(async () => {
      try {
        const [documentResults, evaluationRuns] = await Promise.all([getDocuments(), getEvalRuns()]);
        setDocuments(documentResults);
        setEvaluationCount(evaluationRuns.length);
        setMessage("");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Could not load the workspace summary.");
      }
    });
  }, []);

  const indexedCount = documents.filter((document) => document.status === "indexed").length;
  const warningCount = documents.reduce((total, document) => total + (document.parse_quality?.warnings.length ?? 0), 0);

  return (
    <AppShell>
      <section className="mb-6 grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <Badge tone="teal">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Ready for cited search
          </Badge>
          <h1 className="mt-3 text-3xl font-black tracking-normal">Workspace intelligence</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Monitor local indexing, parse quality, and answer evaluation from one focused DocIntel AI workspace.
          </p>
        </div>
        <Link
          href="/search"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-teal-900/10 transition hover:bg-teal-800 active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
        >
          Ask documents
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Panel data-testid="document-count" className="p-4">
          <p className="text-sm text-slate-500">Documents</p>
          <p className="mt-3 text-3xl font-semibold">{documents.length}</p>
        </Panel>
        <Panel className="p-4">
          <p className="text-sm text-slate-500">Indexed documents</p>
          <p className="mt-3 text-3xl font-semibold">{indexedCount}</p>
        </Panel>
        <Panel data-testid="quality-warning-count" className="p-4">
          <p className="text-sm text-slate-500">Quality warnings</p>
          <p className="mt-3 text-3xl font-semibold">{warningCount}</p>
        </Panel>
        <Panel data-testid="evaluation-count" className="p-4">
          <p className="text-sm text-slate-500">Evaluation runs</p>
          <p className="mt-3 text-3xl font-semibold">{evaluationCount}</p>
        </Panel>
      </div>
      <section className="mt-8">
        <h2 className="text-lg font-semibold">Continue working</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {[
            { href: "/documents", label: "Upload documents", icon: UploadCloud },
            { href: "/search", label: "Search evidence", icon: FileSearch },
            { href: "/evaluation", label: "Run evaluation", icon: Gauge },
          ].map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="flex items-center gap-3 rounded-lg border border-line bg-white px-4 py-3 text-sm font-medium shadow-sm shadow-teal-950/5 transition hover:-translate-y-0.5 hover:border-teal-300 hover:bg-teal-50/70"
            >
              <action.icon className="h-4 w-4 text-accent" aria-hidden="true" />
              <span className="min-w-0 flex-1">{action.label}</span>
              <ArrowRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
            </Link>
          ))}
        </div>
      </section>
      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Recent documents</h2>
          <Link href="/documents" className="text-sm font-medium text-accent hover:underline">
            View all
          </Link>
        </div>
        {message ? <Panel className="text-sm text-slate-600">{message}</Panel> : <DocumentList documents={documents.slice(0, 5)} />}
      </section>
    </AppShell>
  );
}
