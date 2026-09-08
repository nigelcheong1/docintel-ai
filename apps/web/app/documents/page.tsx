"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentList } from "@/components/document-list";
import { UploadPanel } from "@/components/upload-panel";
import { Panel } from "@/components/ui/panel";
import { deleteDocument, getDocument, getDocuments, getDocumentStatus, reindexDocument } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";

const ACTIVE_DOCUMENT_STATUSES = new Set(["uploaded", "processing", "ocr_processing", "embedding"]);

function isActivelyProcessing(document: DocumentDetail): boolean {
  return ACTIVE_DOCUMENT_STATUSES.has(document.status);
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [message, setMessage] = useState("Loading documents...");

  async function refreshDocuments() {
    try {
      const summaries = await getDocuments();
      const result = await Promise.all(
        summaries.map(async (document) => {
          const detail = await getDocument(document.id);
          if (!isActivelyProcessing(detail)) {
            return detail;
          }

          try {
            const processingStatus = await getDocumentStatus(document.id);
            return { ...detail, processing_status: processingStatus };
          } catch {
            return detail;
          }
        }),
      );
      setDocuments(result);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load documents.");
    }
  }

  useEffect(() => {
    queueMicrotask(() => {
      void refreshDocuments();
    });
  }, []);

  const hasActiveProcessing = documents.some(isActivelyProcessing);

  useEffect(() => {
    if (!hasActiveProcessing) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshDocuments();
    }, 1500);
    return () => window.clearInterval(intervalId);
  }, [hasActiveProcessing]);

  async function handleDelete(documentId: string) {
    await deleteDocument(documentId);
    await refreshDocuments();
  }

  async function handleReindex(documentId: string) {
    await reindexDocument(documentId);
    await refreshDocuments();
  }

  return (
    <AppShell>
      <section className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Document intake</p>
        <h1 className="mt-2 text-3xl font-black tracking-normal">Documents</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Upload PDFs and images, inspect indexing health, and retry OCR when documents need another pass.
        </p>
      </section>
      <div className="space-y-4">
        <UploadPanel onUploaded={() => void refreshDocuments()} />
        {message ? (
          <Panel className="text-sm text-slate-600">{message}</Panel>
        ) : (
          <DocumentList documents={documents} onDelete={handleDelete} onReindex={handleReindex} />
        )}
      </div>
    </AppShell>
  );
}
