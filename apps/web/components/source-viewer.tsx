"use client";

import Link from "next/link";
import { useState } from "react";
import { ExternalLink, RotateCcw, X, ZoomIn, ZoomOut } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type SourceViewerSource = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  section_heading?: string | null;
  page_image_url?: string | null;
  document_page_url?: string | null;
  snippet?: string | null;
  score?: number | null;
  source_score?: number | null;
};

function formatPercentage(score?: number | null) {
  return typeof score === "number" ? `${Math.round(score * 100)}%` : "Not available";
}

function SourceViewerControl({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-white text-slate-600 shadow-sm transition hover:border-teal-500 hover:bg-teal-50 hover:text-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function SourceViewer({
  source,
  onClose,
}: {
  source: SourceViewerSource;
  onClose: () => void;
}) {
  const [previewZoom, setPreviewZoom] = useState(100);
  const documentPageUrl = source.document_page_url ?? `/documents/${source.document_id}?page=${source.page_number}`;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/50 px-4 py-8 backdrop-blur-sm">
      <section
        role="dialog"
        aria-label="Source viewer"
        aria-modal="true"
        className="w-full max-w-5xl overflow-hidden rounded-lg border border-teal-100 bg-white shadow-2xl shadow-ink/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-teal-50/70 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Source viewer</p>
            <h2 className="mt-1 break-words text-base font-bold text-ink">{source.document_filename}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span>Page {source.page_number}</span>
              {source.section_heading ? <Badge tone="teal">{source.section_heading}</Badge> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Link
              href={documentPageUrl}
              className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink shadow-sm transition hover:border-teal-600 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              Open in workbench
            </Link>
            <Button
              type="button"
              variant="secondary"
              className="min-h-9 px-3 py-1.5 text-xs"
              leftIcon={<X className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={onClose}
            >
              Close
            </Button>
          </div>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-slate-600">Page preview</p>
              <div className="flex items-center gap-2">
                <span className="min-w-12 text-center text-xs font-semibold text-slate-600">{previewZoom}%</span>
                <SourceViewerControl
                  label="Zoom out source preview"
                  onClick={() => setPreviewZoom((current) => Math.max(50, current - 25))}
                >
                  <ZoomOut className="h-4 w-4" aria-hidden="true" />
                </SourceViewerControl>
                <SourceViewerControl label="Reset source preview zoom" onClick={() => setPreviewZoom(100)}>
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                </SourceViewerControl>
                <SourceViewerControl
                  label="Zoom in source preview"
                  onClick={() => setPreviewZoom((current) => Math.min(200, current + 25))}
                >
                  <ZoomIn className="h-4 w-4" aria-hidden="true" />
                </SourceViewerControl>
              </div>
            </div>
            <div className="mt-3 max-h-[34rem] overflow-auto rounded-md border border-line bg-slate-50 p-2">
              {source.page_image_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- Source previews are served by the local document API.
                <img
                  src={source.page_image_url}
                  alt={`Page ${source.page_number} source preview for ${source.document_filename}`}
                  className="mx-auto block h-auto max-w-none rounded-sm border border-slate-200 bg-white shadow-sm"
                  style={{ width: `${previewZoom}%`, minWidth: `${previewZoom}%` }}
                />
              ) : (
                <p className="rounded-md border border-dashed border-line bg-white p-4 text-sm text-slate-600">
                  No page preview is available for this citation.
                </p>
              )}
            </div>
          </div>

          <aside className="space-y-3">
            <div className="rounded-lg border border-line bg-white p-3">
              <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">Evidence excerpt</h3>
              <p className="mt-2 break-words text-sm leading-6 text-slate-700">
                {source.snippet || "No snippet is available for this citation."}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-2 rounded-lg border border-line bg-white p-3 text-xs">
              <dt className="text-slate-500">Blended</dt>
              <dd className="text-right font-semibold text-ink">{formatPercentage(source.score)}</dd>
              <dt className="text-slate-500">Source</dt>
              <dd className="text-right font-semibold text-ink">{formatPercentage(source.source_score)}</dd>
            </dl>
          </aside>
        </div>
      </section>
    </div>
  );
}
