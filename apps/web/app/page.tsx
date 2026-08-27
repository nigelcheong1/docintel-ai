"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, FileSearch, Gauge, UploadCloud } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { DocumentList } from "@/components/document-list";
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

  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">Upload PDFs, index local embeddings, and search with cited evidence.</p>
      </section>
      <div className="grid gap-4 sm:grid-cols-3">
        <div data-testid="document-count" className="rounded border border-line bg-white p-4">
          <p className="text-sm text-slate-500">Documents</p>
          <p className="mt-3 text-3xl font-semibold">{documents.length}</p>
        </div>
        <div className="rounded border border-line bg-white p-4">
          <p className="text-sm text-slate-500">Indexed documents</p>
          <p className="mt-3 text-3xl font-semibold">{indexedCount}</p>
        </div>
        <div data-testid="evaluation-count" className="rounded border border-line bg-white p-4">
          <p className="text-sm text-slate-500">Evaluation runs</p>
          <p className="mt-3 text-3xl font-semibold">{evaluationCount}</p>
        </div>
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
              className="flex items-center gap-3 border-b border-line bg-white px-4 py-3 text-sm font-medium hover:bg-panel"
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
        {message ? <p className="text-sm text-slate-600">{message}</p> : <DocumentList documents={documents.slice(0, 5)} />}
      </section>
    </AppShell>
  );
}
