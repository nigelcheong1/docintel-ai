import type { SearchHit } from "@/lib/types";

export function SearchResults({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No cited evidence found.</p>;
  }

  return (
    <div className="space-y-3">
      {hits.map((hit) => (
        <article key={hit.chunk_id} className="min-w-0 rounded border border-line bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="break-all text-sm font-semibold">{hit.document_filename}</h2>
              <p className="mt-1 text-xs text-slate-500">Page {hit.page_number}</p>
            </div>
            <span className="rounded border border-line px-2 py-1 text-xs font-medium">{Math.round(hit.score * 100)}%</span>
          </div>
          <p className="mt-3 break-words text-sm leading-6 text-slate-700">{hit.snippet}</p>
        </article>
      ))}
    </div>
  );
}
