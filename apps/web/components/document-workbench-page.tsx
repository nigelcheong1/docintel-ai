"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentWorkbench } from "@/components/document-workbench";
import { Panel } from "@/components/ui/panel";
import { getDocument, getDocumentChunks, getDocumentPages, getDocumentProfile } from "@/lib/api";
import type { DocumentChunk, DocumentDetail, DocumentPage, DocumentProfile } from "@/lib/types";

type DocumentWorkbenchPageProps = {
  documentId: string;
  initialPageNumber?: number;
};

export function DocumentWorkbenchPage({ documentId, initialPageNumber }: DocumentWorkbenchPageProps) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [profile, setProfile] = useState<DocumentProfile | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [message, setMessage] = useState("Loading document workbench...");

  useEffect(() => {
    let isCurrent = true;

    async function loadWorkbench() {
      setMessage("Loading document workbench...");
      try {
        const [documentDetail, pageDiagnostics, documentChunks, profileResult] = await Promise.all([
          getDocument(documentId),
          getDocumentPages(documentId),
          getDocumentChunks(documentId),
          getDocumentProfile(documentId).catch(() => null),
        ]);
        if (!isCurrent) {
          return;
        }
        setDocument(documentDetail);
        setPages(pageDiagnostics);
        setChunks(documentChunks);
        setProfile(profileResult);
        setMessage("");
      } catch (error) {
        if (isCurrent) {
          setMessage(error instanceof Error ? error.message : "Could not load document workbench.");
        }
      }
    }

    void loadWorkbench();

    return () => {
      isCurrent = false;
    };
  }, [documentId]);

  return (
    <AppShell>
      {message ? <Panel className="text-sm text-slate-600">{message}</Panel> : null}
      {document && !message ? (
        <DocumentWorkbench
          document={document}
          profile={profile}
          pages={pages}
          chunks={chunks}
          initialPageNumber={initialPageNumber}
        />
      ) : null}
    </AppShell>
  );
}
