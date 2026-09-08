"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, FileText, RotateCw, Trash2 } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentDetail, DocumentSummary } from "@/lib/types";

type DocumentListProps = {
  documents: Array<DocumentSummary | DocumentDetail>;
  onDelete?: (documentId: string) => Promise<void>;
  onReindex?: (documentId: string) => Promise<void>;
};

type DocumentActionType = "delete" | "reindex";

type PendingDocumentAction = {
  documentId: string;
  type: DocumentActionType;
};

function formatUpdatedAt(updatedAt?: string): string {
  if (!updatedAt) {
    return "Not available";
  }

  const date = new Date(updatedAt);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function DocumentMetadata({ document }: { document: DocumentSummary | DocumentDetail }) {
  const detail = document as Partial<DocumentDetail>;

  return (
    <>
      <dt className="text-slate-500">Pages</dt>
      <dd className="text-slate-600">{detail.page_count ?? "Not available"}</dd>
      <dt className="text-slate-500">Chunks</dt>
      <dd className="text-slate-600">{detail.chunk_count ?? "Not available"}</dd>
      <dt className="text-slate-500">Updated</dt>
      <dd className="text-slate-600">{formatUpdatedAt(document.updated_at)}</dd>
    </>
  );
}

const ACTIVE_DOCUMENT_STATUSES = new Set(["uploaded", "processing", "ocr_processing", "embedding"]);

function fallbackProcessingMessage(status: string): string {
  const messages: Record<string, string> = {
    uploaded: "Upload saved. Waiting to start document processing.",
    processing: "Extracting readable text and page structure.",
    ocr_processing: "Running OCR for scanned or image-only pages.",
    embedding: "Embedding evidence chunks for semantic search.",
  };
  return messages[status] ?? "Processing document.";
}

function fallbackProgressPercent(status: string): number {
  const progress: Record<string, number> = {
    uploaded: 10,
    processing: 35,
    ocr_processing: 45,
    embedding: 80,
  };
  return progress[status] ?? 25;
}

function ProcessingProgress({ document }: { document: DocumentSummary | DocumentDetail }) {
  const status = document.processing_status;
  if (!status && !ACTIVE_DOCUMENT_STATUSES.has(document.status)) {
    return null;
  }

  const progress = Math.max(0, Math.min(100, status?.progress_percent ?? fallbackProgressPercent(document.status)));
  const message = status?.message ?? fallbackProcessingMessage(document.status);

  return (
    <div className="mt-2 w-full min-w-32 space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
        <span className="min-w-0 truncate">{message}</span>
        <span className="font-semibold text-teal-800">{progress}%</span>
      </div>
      <div
        role="progressbar"
        aria-label={`${document.filename} processing progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        className="h-2 overflow-hidden rounded-full bg-teal-50 ring-1 ring-inset ring-teal-100"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-teal-700 via-teal-600 to-amber-400 transition-[width] duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function DocumentStatusDisplay({ document }: { document: DocumentSummary | DocumentDetail }) {
  return (
    <div className="min-w-0">
      <StatusBadge status={document.status} />
      <ProcessingProgress document={document} />
    </div>
  );
}

function qualityBadgeFor(document: DocumentSummary | DocumentDetail) {
  const quality = document.parse_quality;

  if (!quality) {
    return { label: "Quality pending", tone: "neutral" as const };
  }

  if (quality.scanned_likelihood === "high") {
    return { label: "OCR recommended", tone: "amber" as const };
  }

  if (quality.scanned_likelihood === "medium") {
    return { label: "Review text quality", tone: "amber" as const };
  }

  return { label: "Text ready", tone: "success" as const };
}

function formatTextSourceSummary(summary?: Record<string, number> | null) {
  if (!summary) {
    return "";
  }

  return Object.entries(summary)
    .filter(([, count]) => count > 0)
    .map(([source, count]) => `${source} ${count}`)
    .join(", ");
}

function DocumentQuality({ document }: { document: DocumentSummary | DocumentDetail }) {
  const quality = document.parse_quality;
  const badge = qualityBadgeFor(document);
  const textSourceSummary = quality ? formatTextSourceSummary(quality.text_source_summary) : "";
  const ocrPageCount = quality ? (quality.ocr_page_count ?? 0) + (quality.hybrid_page_count ?? 0) : 0;

  return (
    <div className="space-y-2">
      <Badge tone={badge.tone}>{badge.label}</Badge>
      {quality ? (
        <p className="text-xs text-slate-500">
          {quality.text_page_count}/{quality.page_count} text pages
        </p>
      ) : null}
      {quality ? (
        <div className="space-y-1 text-xs text-slate-500">
          <p>OCR pages {ocrPageCount}/{quality.page_count}</p>
          {textSourceSummary ? <p>Text source {textSourceSummary}</p> : null}
          {typeof quality.ocr_confidence_average === "number" ? (
            <p>OCR confidence {quality.ocr_confidence_average}%</p>
          ) : null}
        </div>
      ) : null}
      {quality?.warnings.length ? (
        <div className="space-y-1">
          {quality.warnings.map((warning) => (
            <p key={warning} className="flex items-start gap-1.5 text-xs leading-5 text-amber-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-none" aria-hidden="true" />
              <span>{warning}</span>
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DocumentNameLink({
  document,
  className,
}: {
  document: DocumentSummary | DocumentDetail;
  className?: string;
}) {
  return (
    <Link
      href={`/documents/${document.id}`}
      className={[
        "min-w-0 text-ink underline-offset-4 transition hover:text-teal-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {document.filename}
    </Link>
  );
}

function DocumentActions({
  document,
  pendingAction,
  onDelete,
  onReindex,
}: {
  document: DocumentSummary | DocumentDetail;
  pendingAction: PendingDocumentAction | null;
  onDelete?: (documentId: string) => void;
  onReindex?: (documentId: string) => void;
}) {
  const isLocked = pendingAction !== null;
  const isReindexing = pendingAction?.documentId === document.id && pendingAction.type === "reindex";
  const isDeleting = pendingAction?.documentId === document.id && pendingAction.type === "delete";
  const isImage = document.mime_type.startsWith("image/");
  const reindexLabel = isImage || document.status === "deferred_ocr" ? "Retry OCR" : "Reindex";
  const isRetryingOcr = reindexLabel === "Retry OCR";
  const canReindex = Boolean(onReindex) && (document.mime_type === "application/pdf" || isImage);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {canReindex ? (
        <Button
          type="button"
          variant="secondary"
          className="min-h-9 px-3 py-1.5"
          aria-label={`${reindexLabel} ${document.filename}`}
          leftIcon={<RotateCw className="h-4 w-4" aria-hidden="true" />}
          onClick={() => onReindex?.(document.id)}
          disabled={isLocked}
          isLoading={isReindexing}
        >
          {isReindexing ? (isRetryingOcr ? "Retrying OCR..." : "Reindexing...") : reindexLabel}
        </Button>
      ) : null}
      {onDelete ? (
        <Button
          type="button"
          variant="danger"
          className="min-h-9 px-3 py-1.5"
          aria-label={`Delete ${document.filename}`}
          leftIcon={<Trash2 className="h-4 w-4" aria-hidden="true" />}
          onClick={() => {
            if (window.confirm(`Permanently delete ${document.filename}?`)) {
              onDelete(document.id);
            }
          }}
          disabled={isLocked}
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </Button>
      ) : null}
    </div>
  );
}

export function DocumentList({ documents, onDelete, onReindex }: DocumentListProps) {
  const [pendingAction, setPendingAction] = useState<PendingDocumentAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const hasActions = Boolean(
    onDelete ||
      (onReindex &&
        documents.some((document) => document.mime_type === "application/pdf" || document.mime_type.startsWith("image/"))),
  );

  async function runAction(
    documentId: string,
    type: DocumentActionType,
    action?: (id: string) => Promise<void>,
  ) {
    if (!action || pendingAction) {
      return;
    }

    setPendingAction({ documentId, type });
    setActionError(null);
    try {
      await action(documentId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not update the document. Try again.");
    } finally {
      setPendingAction(null);
    }
  }

  if (documents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-line bg-white/80 p-8 text-center text-sm text-slate-600">
        No documents uploaded.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-white shadow-sm shadow-teal-950/5">
      {actionError ? (
        <p role="alert" className="border-b border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </p>
      ) : null}
      <div className="divide-y divide-line md:hidden">
        {documents.map((document) => (
          <article key={document.id} className="space-y-3 p-4">
            <div className="flex items-start gap-3">
              <div className="grid h-9 w-9 flex-none place-items-center rounded-md bg-teal-50 text-teal-700">
                <FileText className="h-4 w-4" aria-hidden="true" />
              </div>
              <h2 className="min-w-0 break-words text-sm font-semibold">
                <DocumentNameLink document={document} className="break-words" />
              </h2>
            </div>
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
              <dt className="text-slate-500">Status</dt>
              <dd>
                <DocumentStatusDisplay document={document} />
              </dd>
              <dt className="text-slate-500">Type</dt>
              <dd className="break-all text-slate-600">{document.mime_type}</dd>
              <DocumentMetadata document={document} />
              <dt className="text-slate-500">Quality</dt>
              <dd>
                <DocumentQuality document={document} />
              </dd>
            </dl>
            {hasActions ? (
              <DocumentActions
                document={document}
                pendingAction={pendingAction}
                onDelete={onDelete ? (documentId) => void runAction(documentId, "delete", onDelete) : undefined}
                onReindex={onReindex ? (documentId) => void runAction(documentId, "reindex", onReindex) : undefined}
              />
            ) : null}
          </article>
        ))}
      </div>
      <div className="hidden md:block">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b border-line bg-teal-50/70 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Filename</th>
              <th className="w-36 px-4 py-3">Status</th>
              <th className="w-20 px-4 py-3">Pages</th>
              <th className="w-20 px-4 py-3">Chunks</th>
              <th className="w-64 px-4 py-3">Quality</th>
              <th className="w-44 px-4 py-3">Updated</th>
              {hasActions ? <th className="w-48 px-4 py-3">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id} className="border-b border-line transition hover:bg-teal-50/40 last:border-b-0">
                <td className="px-4 py-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="grid h-9 w-9 flex-none place-items-center rounded-md bg-teal-50 text-teal-700">
                      <FileText className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <DocumentNameLink document={document} className="truncate font-semibold" />
                  </div>
                </td>
                <td className="px-4 py-4">
                  <DocumentStatusDisplay document={document} />
                </td>
                <td className="px-4 py-3 text-slate-600">{"page_count" in document ? document.page_count : "Not available"}</td>
                <td className="px-4 py-3 text-slate-600">{"chunk_count" in document ? document.chunk_count : "Not available"}</td>
                <td className="px-4 py-4">
                  <DocumentQuality document={document} />
                </td>
                <td className="px-4 py-3 text-slate-600">{formatUpdatedAt(document.updated_at)}</td>
                {hasActions ? (
                  <td className="px-4 py-3">
                    <DocumentActions
                      document={document}
                      pendingAction={pendingAction}
                      onDelete={onDelete ? (documentId) => void runAction(documentId, "delete", onDelete) : undefined}
                      onReindex={onReindex ? (documentId) => void runAction(documentId, "reindex", onReindex) : undefined}
                    />
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
