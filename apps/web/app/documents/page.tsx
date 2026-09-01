"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentList } from "@/components/document-list";
import { UploadPanel } from "@/components/upload-panel";
import { Panel } from "@/components/ui/panel";
import { deleteDocument, getDocument, getDocuments, reindexDocument } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [message, setMessage] = useState("Loading documents...");

  async function refreshDocuments() {
    try {
      const summaries = await getDocuments();
      const result = await Promise.all(summaries.map((document) => getDocument(document.id)));
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
