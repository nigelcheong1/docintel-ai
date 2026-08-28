"use client";

import { useState } from "react";
import { RotateCw, Trash2 } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import type { DocumentDetail, DocumentSummary } from "@/lib/types";

type DocumentListProps = {
  documents: Array<DocumentSummary | DocumentDetail>;
  onDelete?: (documentId: string) => Promise<void>;
  onReindex?: (documentId: string) => Promise<void>;
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

function DocumentActions({
  document,
  isPending,
  onDelete,
  onReindex,
}: {
  document: DocumentSummary | DocumentDetail;
  isPending: boolean;
  onDelete?: (documentId: string) => void;
  onReindex?: (documentId: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink hover:bg-panel disabled:cursor-not-allowed disabled:opacity-60"
        aria-label={`Reindex ${document.filename}`}
        onClick={() => onReindex?.(document.id)}
        disabled={isPending || !onReindex}
      >
        <RotateCw className={isPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
        {isPending ? "Reindexing..." : "Reindex"}
      </button>
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
        aria-label={`Delete ${document.filename}`}
        onClick={() => onDelete?.(document.id)}
        disabled={isPending || !onDelete}
      >
        <Trash2 className="h-4 w-4" aria-hidden="true" />
        Delete
      </button>
    </div>
  );
}

export function DocumentList({ documents, onDelete, onReindex }: DocumentListProps) {
  const [pendingDocumentId, setPendingDocumentId] = useState<string | null>(null);
  const hasActions = Boolean(onDelete || onReindex);

  async function runAction(documentId: string, action?: (id: string) => Promise<void>) {
    if (!action || pendingDocumentId) {
      return;
    }

    setPendingDocumentId(documentId);
    try {
      await action(documentId);
    } finally {
      setPendingDocumentId(null);
    }
  }

  if (documents.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No documents uploaded.</p>;
  }

  return (
    <div className="overflow-hidden rounded border border-line bg-white">
      <div className="divide-y divide-line md:hidden">
        {documents.map((document) => (
          <article key={document.id} className="space-y-3 p-4">
            <h2 className="break-words text-sm font-medium text-ink">{document.filename}</h2>
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
              <dt className="text-slate-500">Status</dt>
              <dd><StatusBadge status={document.status} /></dd>
              <dt className="text-slate-500">Type</dt>
              <dd className="break-all text-slate-600">{document.mime_type}</dd>
              <DocumentMetadata document={document} />
            </dl>
            {hasActions ? (
              <DocumentActions
                document={document}
                isPending={pendingDocumentId === document.id}
                onDelete={onDelete ? (documentId) => void runAction(documentId, onDelete) : undefined}
                onReindex={onReindex ? (documentId) => void runAction(documentId, onReindex) : undefined}
              />
            ) : null}
          </article>
        ))}
      </div>
      <div className="hidden md:block">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b border-line bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Filename</th>
              <th className="w-36 px-4 py-3">Status</th>
              <th className="w-20 px-4 py-3">Pages</th>
              <th className="w-20 px-4 py-3">Chunks</th>
              <th className="w-44 px-4 py-3">Updated</th>
              {hasActions ? <th className="w-48 px-4 py-3">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id} className="border-b border-line last:border-b-0">
                <td className="truncate px-4 py-3">{document.filename}</td>
                <td className="px-4 py-3"><StatusBadge status={document.status} /></td>
                <td className="px-4 py-3 text-slate-600">{"page_count" in document ? document.page_count : "Not available"}</td>
                <td className="px-4 py-3 text-slate-600">{"chunk_count" in document ? document.chunk_count : "Not available"}</td>
                <td className="px-4 py-3 text-slate-600">{formatUpdatedAt(document.updated_at)}</td>
                {hasActions ? (
                  <td className="px-4 py-3">
                    <DocumentActions
                      document={document}
                      isPending={pendingDocumentId === document.id}
                      onDelete={onDelete ? (documentId) => void runAction(documentId, onDelete) : undefined}
                      onReindex={onReindex ? (documentId) => void runAction(documentId, onReindex) : undefined}
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
