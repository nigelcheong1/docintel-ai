import { StatusBadge } from "@/components/status-badge";
import type { DocumentSummary } from "@/lib/types";

export function DocumentList({ documents }: { documents: DocumentSummary[] }) {
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
            </dl>
          </article>
        ))}
      </div>
      <div className="hidden md:block">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b border-line bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Filename</th>
              <th className="w-36 px-4 py-3">Status</th>
              <th className="w-44 px-4 py-3">Type</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id} className="border-b border-line last:border-b-0">
                <td className="truncate px-4 py-3">{document.filename}</td>
                <td className="px-4 py-3"><StatusBadge status={document.status} /></td>
                <td className="truncate px-4 py-3 text-slate-600">{document.mime_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
