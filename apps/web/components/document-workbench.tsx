"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpenCheck,
  Database,
  Gauge,
  Layers3,
  Search,
  Sparkles,
} from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { DocumentChunk, DocumentDetail, DocumentFact, DocumentPage, DocumentProfile } from "@/lib/types";

type WorkbenchTab = "overview" | "evidence" | "quality";

type DocumentWorkbenchProps = {
  document: DocumentDetail;
  profile: DocumentProfile | null;
  pages: DocumentPage[];
  chunks: DocumentChunk[];
  initialPageNumber?: number;
};

function formatDocumentType(value?: string | null) {
  if (!value) {
    return "Document";
  }
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatStatus(value: string) {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatTextSource(value: string) {
  const normalized = value.replace(/_/g, " ").toLowerCase();
  if (normalized === "ocr") {
    return "OCR";
  }
  return normalized.replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "Not available";
  }
  return `${Math.round(value * 10) / 10}%`;
}

function formatOcrConfidence(value: number | null | undefined) {
  return typeof value === "number" ? `${formatPercent(value)} OCR confidence` : "OCR not run";
}

function formatCount(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function selectedPageFrom(pages: DocumentPage[], initialPageNumber?: number) {
  return pages.find((page) => page.page_number === initialPageNumber) ?? pages[0] ?? null;
}

function pageTone(page: DocumentPage) {
  if (page.text_source === "ocr" || page.text_source === "hybrid") {
    return "amber" as const;
  }
  if (page.character_count > 0 && page.chunk_count > 0) {
    return "success" as const;
  }
  return "neutral" as const;
}

function FactList({ title, facts }: { title: string; facts: DocumentFact[] }) {
  if (facts.length === 0) {
    return null;
  }

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {facts.slice(0, 8).map((fact) => (
          <Badge key={`${fact.kind}-${fact.label}-${fact.value}-${fact.page_number}`} tone="neutral">
            {fact.value}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function WorkbenchStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-teal-100 bg-teal-50/50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function WorkflowStep({ label, active }: { label: string; active: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <span className={["h-2.5 w-2.5 rounded-full", active ? "bg-teal-600" : "bg-slate-300"].join(" ")} />
      <span className={active ? "font-medium text-ink" : "text-slate-500"}>{label}</span>
    </li>
  );
}

export function DocumentWorkbench(props: DocumentWorkbenchProps) {
  return <DocumentWorkbenchContent key={`${props.document.id}:${props.initialPageNumber ?? "overview"}`} {...props} />;
}

function DocumentWorkbenchContent({ document, profile, pages, chunks, initialPageNumber }: DocumentWorkbenchProps) {
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(
    selectedPageFrom(pages, initialPageNumber)?.page_number ?? null,
  );
  const [activeTab, setActiveTab] = useState<WorkbenchTab>(initialPageNumber ? "evidence" : "overview");
  const selectedPage = pages.find((page) => page.page_number === selectedPageNumber) ?? pages[0] ?? null;
  const visibleChunks = useMemo(
    () =>
      selectedPage
        ? chunks
            .filter((chunk) => chunk.page_number === selectedPage.page_number)
            .sort((first, second) => first.chunk_index - second.chunk_index)
        : chunks.slice().sort((first, second) => first.chunk_index - second.chunk_index),
    [chunks, selectedPage],
  );
  const ocrConfidence = document.parse_quality?.ocr_confidence_average;
  const warnings = document.parse_quality?.warnings ?? [];

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-teal-100 bg-white/95 p-5 shadow-sm shadow-teal-950/5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-normal text-teal-700">
              <BookOpenCheck className="h-4 w-4" aria-hidden="true" />
              Evidence Workbench
            </p>
            <h1 className="mt-2 break-words text-3xl font-black tracking-normal text-ink">{document.filename}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Review page coverage, source quality, and the exact chunks available for cited answers.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/documents"
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink shadow-sm transition hover:border-teal-600 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Documents
            </Link>
            <Link
              href={`/search?documentId=${document.id}`}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-teal-900/10 transition hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              Ask document
            </Link>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <WorkbenchStat label="Status" value={formatStatus(document.status)} />
          <WorkbenchStat label="Pages" value={formatCount(document.page_count, "page", "pages")} />
          <WorkbenchStat label="Evidence" value={formatCount(document.chunk_count, "chunk", "chunks")} />
          <WorkbenchStat label="Type" value={formatDocumentType(profile?.document_type)} />
          <WorkbenchStat label="OCR" value={formatOcrConfidence(ocrConfidence)} />
        </div>
        {warnings.length > 0 ? (
          <div className="mt-4 space-y-2">
            {warnings.slice(0, 2).map((warning) => (
              <p key={warning} className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                <AlertTriangle className="mt-1 h-4 w-4 flex-none" aria-hidden="true" />
                {warning}
              </p>
            ))}
          </div>
        ) : null}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-5">
          <Panel className="p-4">
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Workbench views">
              {(["overview", "evidence", "quality"] as const).map((tab) => (
                <Button
                  key={tab}
                  type="button"
                  variant={activeTab === tab ? "primary" : "secondary"}
                  className="min-h-9 px-3 py-1.5 text-xs capitalize"
                  onClick={() => setActiveTab(tab)}
                  aria-pressed={activeTab === tab}
                >
                  {tab}
                </Button>
              ))}
            </div>
          </Panel>

          {activeTab === "overview" ? (
            <Panel tone="accent" className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="teal">{formatDocumentType(profile?.document_type)}</Badge>
                <StatusBadge status={document.status} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-ink">{profile?.title ?? "Document intelligence"}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {profile?.overview ?? "No intelligence profile is available yet. Reindex this document after text extraction completes."}
                </p>
              </div>
              {profile ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">Sections</h3>
                    <div className="mt-2 space-y-2">
                      {profile.sections.slice(0, 5).map((section) => (
                        <button
                          key={`${section.heading}-${section.page_number}`}
                          type="button"
                          className="w-full rounded-lg border border-line bg-white p-3 text-left text-sm transition hover:border-teal-300 hover:bg-teal-50/50"
                          onClick={() => {
                            setSelectedPageNumber(section.page_number);
                            setActiveTab("evidence");
                          }}
                        >
                          <span className="font-semibold text-ink">{section.heading}</span>
                          <span className="ml-2 text-xs text-slate-500">p.{section.page_number}</span>
                          <span className="mt-1 block text-xs leading-5 text-slate-500">{section.text_preview}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-4">
                    <FactList title="Numbers" facts={profile.key_numbers} />
                    <FactList title="Entities" facts={profile.key_entities} />
                    <FactList title="Dates" facts={profile.key_dates} />
                  </div>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {activeTab === "evidence" ? (
            <Panel aria-label="Page evidence" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-bold text-ink">
                    {selectedPage ? `Page ${selectedPage.page_number} evidence` : "Evidence chunks"}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {visibleChunks.length === 0
                      ? "No chunks were produced for this page."
                      : formatCount(visibleChunks.length, "chunk available", "chunks available")}
                  </p>
                </div>
                {selectedPage ? <Badge tone={pageTone(selectedPage)}>{formatTextSource(selectedPage.text_source)}</Badge> : null}
              </div>
              <div className="space-y-3">
                {visibleChunks.map((chunk) => (
                  <article key={chunk.id} className="rounded-lg border border-line bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                      <span>Chunk {chunk.chunk_index + 1}</span>
                      <span>{chunk.token_estimate} tokens</span>
                    </div>
                    <p className="mt-2 break-words text-sm leading-6 text-slate-700">{chunk.text}</p>
                  </article>
                ))}
              </div>
            </Panel>
          ) : null}

          {activeTab === "quality" ? (
            <Panel className="space-y-4">
              <div className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-accent" aria-hidden="true" />
                <h2 className="text-lg font-bold text-ink">Indexing quality</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <WorkbenchStat label="Text pages" value={`${document.parse_quality?.text_page_count ?? 0}/${document.page_count}`} />
                <WorkbenchStat label="OCR pages" value={`${document.parse_quality?.ocr_page_count ?? 0}`} />
                <WorkbenchStat label="Empty pages" value={`${document.parse_quality?.empty_page_count ?? 0}`} />
              </div>
              {warnings.length > 0 ? (
                <div className="space-y-2">
                  {warnings.map((warning) => (
                    <p key={warning} className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                      <AlertTriangle className="mt-1 h-4 w-4 flex-none" aria-hidden="true" />
                      {warning}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                  No indexing warnings were reported for this document.
                </p>
              )}
            </Panel>
          ) : null}
        </div>

        <aside className="space-y-5">
          <Panel className="space-y-4">
            <div className="flex items-center gap-2">
              <Layers3 className="h-4 w-4 text-accent" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Processing timeline</h2>
            </div>
            <ol className="space-y-3">
              <WorkflowStep label="Uploaded" active />
              <WorkflowStep label="Text extracted" active={pages.length > 0} />
              <WorkflowStep label="Evidence indexed" active={document.chunk_count > 0} />
              <WorkflowStep label="Ready for QA" active={document.status === "indexed"} />
            </ol>
          </Panel>

          <Panel className="space-y-3">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-accent" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Pages</h2>
            </div>
            {pages.length === 0 ? (
              <p className="text-sm leading-6 text-slate-500">No page diagnostics are available yet.</p>
            ) : (
              <div className="space-y-2">
                {pages.map((page) => {
                  const isSelected = selectedPage?.page_number === page.page_number;
                  return (
                    <button
                      key={page.page_number}
                      type="button"
                      className={[
                        "w-full rounded-lg border p-3 text-left transition",
                        isSelected
                          ? "border-teal-400 bg-teal-50 shadow-sm shadow-teal-900/10"
                          : "border-line bg-white hover:border-teal-300 hover:bg-teal-50/50",
                      ].join(" ")}
                      onClick={() => {
                        setSelectedPageNumber(page.page_number);
                        setActiveTab("evidence");
                      }}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink">Page {page.page_number}</span>
                        <Badge tone={pageTone(page)}>{formatTextSource(page.text_source)}</Badge>
                      </span>
                      <span className="mt-2 line-clamp-2 block text-xs leading-5 text-slate-500">{page.text_preview}</span>
                      <span className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>{formatCount(page.chunk_count, "chunk", "chunks")}</span>
                        <span>{page.character_count} chars</span>
                        {typeof page.ocr_confidence === "number" ? <span>{formatPercent(page.ocr_confidence)} OCR</span> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Suggested questions</h2>
            </div>
            {profile?.suggested_questions.length ? (
              <div className="flex flex-wrap gap-2">
                {profile.suggested_questions.slice(0, 5).map((question) => (
                  <Link
                    key={question}
                    href={`/search?documentId=${document.id}&query=${encodeURIComponent(question)}`}
                    className="inline-flex min-h-8 items-center rounded-md border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-teal-600 hover:text-teal-700"
                  >
                    {question}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-500">Suggested questions will appear after indexing.</p>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  );
}
