"use client";

import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { DocumentProfilePanel } from "@/components/document-profile-panel";
import { SearchResults } from "@/components/search-results";
import { getDocumentProfile, getDocuments, searchDocuments } from "@/lib/api";
import type { AnswerQuality, DocumentProfile, DocumentSummary, SearchAnswer, SearchDiagnostics, SearchHit } from "@/lib/types";

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
        <h1 className="text-2xl font-semibold">Search</h1>
        <p className="mt-2 text-sm text-slate-600">Retrieve cited evidence from local document embeddings.</p>
      </section>
      <form className="mb-4 flex flex-col gap-2 sm:flex-row" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="search-scope">
          Search scope
        </label>
        <select
          id="search-scope"
          className="w-full rounded border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent sm:w-56"
          value={selectedDocumentId}
          onChange={handleScopeChange}
        >
          <option value="">All documents</option>
          {documents.filter((document) => document.status === "indexed").map((document) => (
            <option key={document.id} value={document.id}>
              {document.filename}
            </option>
          ))}
        </select>
        <input
          className="min-w-0 flex-1 rounded border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search query"
        />
        <button className="inline-flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60" disabled={isSearching}>
          <Search className="h-4 w-4" aria-hidden="true" />
          Search
        </button>
      </form>
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
