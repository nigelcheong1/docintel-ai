"use client";

import { type FormEvent, useRef, useState } from "react";
import { Search } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { SearchResults } from "@/components/search-results";
import { searchDocuments } from "@/lib/api";
import type { SearchAnswer, SearchHit } from "@/lib/types";

export default function SearchPage() {
  const latestSearchId = useRef(0);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [answer, setAnswer] = useState<SearchAnswer | null>(null);
  const [message, setMessage] = useState("Enter a question or search phrase.");
  const [isSearching, setIsSearching] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const searchId = ++latestSearchId.current;
    const submittedQuery = query.trim();
    if (!submittedQuery) {
      setMessage("Enter a question or search phrase.");
      setIsSearching(false);
      return;
    }
    setHits([]);
    setAnswer(null);
    setIsSearching(true);
    setMessage("Searching local vector index...");
    try {
      const response = await searchDocuments(submittedQuery, 5);
      if (searchId !== latestSearchId.current) {
        return;
      }
      setHits(response.hits);
      setAnswer(response.answer);
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

  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Search</h1>
        <p className="mt-2 text-sm text-slate-600">Retrieve cited evidence from local document embeddings.</p>
      </section>
      <form className="mb-4 flex gap-2" onSubmit={handleSubmit}>
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
      {message ? <p className="mb-4 text-sm text-slate-600">{message}</p> : null}
      <SearchResults hits={hits} answer={answer} />
    </AppShell>
  );
}
