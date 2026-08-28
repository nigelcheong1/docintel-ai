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
  const canReindex = document.mime_type === "application/pdf" && onReindex;

  return (
    <div className="flex items-center gap-2">
      {canReindex ? (
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink hover:bg-panel disabled:cursor-not-allowed disabled:opacity-60"
          aria-label={`Reindex ${document.filename}`}
          onClick={() => onReindex(document.id)}
          disabled={isLocked}
        >
          <RotateCw className={isReindexing ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
          {isReindexing ? "Reindexing..." : "Reindex"}
        </button>
      ) : null}
      {onDelete ? (
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
          aria-label={`Delete ${document.filename}`}
          onClick={() => {
            if (window.confirm(`Permanently delete ${document.filename}?`)) {
              onDelete(document.id);
            }
          }}
          disabled={isLocked}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          {isDeleting ? "Deleting..." : "Delete"}
        </button>
      ) : null}
    </div>
  );
}

export function DocumentList({ documents, onDelete, onReindex }: DocumentListProps) {
  const [pendingAction, setPendingAction] = useState<PendingDocumentAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const hasActions = Boolean(onDelete || (onReindex && documents.some((document) => document.mime_type === "application/pdf")));

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
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No documents uploaded.</p>;
  }

  return (
    <div className="overflow-hidden rounded border border-line bg-white">
      {actionError ? <p role="alert" className="border-b border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{actionError}</p> : null}
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
