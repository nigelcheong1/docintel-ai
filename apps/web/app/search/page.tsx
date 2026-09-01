"use client";

import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { AlertTriangle, Search } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { DocumentProfilePanel } from "@/components/document-profile-panel";
import { SearchResults } from "@/components/search-results";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { getDocumentProfile, getDocuments, searchDocuments } from "@/lib/api";
import type { AnswerQuality, DocumentProfile, DocumentSummary, SearchAnswer, SearchDiagnostics, SearchHit } from "@/lib/types";

const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  processing: "Processing",
  ocr_processing: "OCR running",
  deferred_ocr: "OCR deferred",
  failed: "Failed",
};

const WARNING_STATUSES = new Set(["deferred_ocr", "ocr_processing", "failed"]);

function documentScopeLabel(document: DocumentSummary) {
  const statusLabel = DOCUMENT_STATUS_LABELS[document.status];
  return statusLabel ? `${document.filename} (${statusLabel})` : document.filename;
}

function selectedDocumentGuidance(document: DocumentSummary | undefined) {
  if (!document || !WARNING_STATUSES.has(document.status)) {
    return null;
  }

  if (document.error_message) {
    return document.error_message;
  }
  if (document.status === "ocr_processing") {
    return "OCR is still running for this document. Try again after processing completes.";
  }
  if (document.status === "failed") {
    return "This document failed indexing. Reindex it before searching.";
  }
  return "This document needs OCR before cited search can use its contents.";
}

export default function SearchPage() {
  const latestSearchId = useRef(0);
  const latestProfileId = useRef(0);
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedProfile, setSelectedProfile] = useState<DocumentProfile | null>(null);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [answer, setAnswer] = useState<SearchAnswer | null>(null);
  const [quality, setQuality] = useState<AnswerQuality | null>(null);
  const [documentType, setDocumentType] = useState<string | null>(null);
  const [queryIntent, setQueryIntent] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<SearchDiagnostics | null>(null);
  const [message, setMessage] = useState("Enter a question or search phrase.");
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const selectedDocument = documents.find((document) => document.id === selectedDocumentId);
  const documentGuidance = selectedDocumentGuidance(selectedDocument);

  useEffect(() => {
    getDocuments().then(setDocuments).catch(() => setDocuments([]));
  }, []);

  useEffect(() => {
    const profileId = ++latestProfileId.current;
    if (!selectedDocumentId) {
      return;
    }
    getDocumentProfile(selectedDocumentId)
      .then((profile) => {
        if (profileId === latestProfileId.current) {
          setSelectedProfile(profile);
        }
      })
      .catch(() => {
        if (profileId === latestProfileId.current) {
          setSelectedProfile(null);
        }
      })
      .finally(() => {
        if (profileId === latestProfileId.current) {
          setIsProfileLoading(false);
        }
      });
  }, [selectedDocumentId]);

  function handleScopeChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextDocumentId = event.target.value;
    latestSearchId.current += 1;
    latestProfileId.current += 1;
    setSelectedDocumentId(nextDocumentId);
    setSelectedProfile(null);
    setIsProfileLoading(Boolean(nextDocumentId));
    setHits([]);
    setAnswer(null);
    setQuality(null);
    setDocumentType(null);
    setQueryIntent(null);
    setDiagnostics(null);
    setIsSearching(false);
    setMessage("Enter a question or search phrase.");
  }

  async function runSearch(rawQuery: string) {
    const searchId = ++latestSearchId.current;
    const submittedQuery = rawQuery.trim();
    if (!submittedQuery) {
      setMessage("Enter a question or search phrase.");
      setIsSearching(false);
      return;
    }
    setHits([]);
    setAnswer(null);
    setQuality(null);
    setDocumentType(null);
    setQueryIntent(null);
    setDiagnostics(null);
    setIsSearching(true);
    setMessage("Searching local vector index...");
    try {
      const response = await searchDocuments(submittedQuery, 5, selectedDocumentId || undefined);
      if (searchId !== latestSearchId.current) {
        return;
      }
      setHits(response.hits);
      setAnswer(response.answer);
      setQuality(response.quality);
      setDocumentType(response.document_type ?? null);
      setQueryIntent(response.query_intent ?? null);
      setDiagnostics(response.diagnostics ?? null);
      setMessage(response.hits.length === 0 ? "No cited evidence found." : "");
    } catch (error) {
      if (searchId === latestSearchId.current) {
        setMessage(error instanceof Error ? error.message : "Search failed.");
      }
    } finally {
      if (searchId === latestSearchId.current) {
        setIsSearching(false);
      }
    }
  }

  function handleSuggestionSelect(suggestion: string) {
    setQuery(suggestion);
    void runSearch(suggestion);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runSearch(query);
  }

  return (
    <AppShell>
      <section className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Evidence search</p>
        <h1 className="mt-2 text-3xl font-black tracking-normal">Ask your documents</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Ask natural-language questions and separate cited answer evidence from related context.
        </p>
      </section>
      <Panel className="mb-4 p-4">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="search-scope">
            Search scope
          </label>
          <select
            id="search-scope"
            className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-teal-100 sm:w-64"
            value={selectedDocumentId}
            onChange={handleScopeChange}
          >
            <option value="">All documents</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                {documentScopeLabel(document)}
              </option>
            ))}
          </select>
          <input
            className="min-w-0 flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-teal-100"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search query"
            placeholder="Ask about totals, methods, datasets, results, or limitations"
          />
          <Button leftIcon={<Search className="h-4 w-4" aria-hidden="true" />} disabled={isSearching} isLoading={isSearching}>
            Search
          </Button>
        </form>
      </Panel>
      {documentGuidance ? (
        <Panel className="mb-4 border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
            <p>{documentGuidance}</p>
          </div>
        </Panel>
      ) : null}
      <DocumentProfilePanel
        profile={selectedProfile}
        isLoading={isProfileLoading}
        onSuggestionSelect={handleSuggestionSelect}
      />
      {message ? <p className="mb-4 text-sm text-slate-600">{message}</p> : null}
      <SearchResults
        hits={hits}
        answer={answer}
        quality={quality}
        documentType={documentType}
        queryIntent={queryIntent}
        diagnostics={diagnostics}
        onSuggestionSelect={handleSuggestionSelect}
      />
    </AppShell>
  );
}
