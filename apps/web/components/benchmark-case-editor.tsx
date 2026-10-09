"use client";

import { useState } from "react";
import { Check, Eye, Plus, Save, Trash2, X } from "lucide-react";
import { SourceViewer, type SourceViewerSource } from "@/components/source-viewer";
import { Button } from "@/components/ui/button";
import { getDocumentChunks, getDocumentPages } from "@/lib/api";
import { reviewDocumentCase, saveDocumentCase } from "@/lib/document-evaluation";
import type { DocumentCaseWrite, DocumentEvalCase, DocumentSummary } from "@/lib/types";

export const benchmarkInputClass = "mt-1 w-full min-w-0 rounded-md border border-line bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-teal-600";
export function caseStateLabel(item: DocumentEvalCase) {
  return item.availability === "ready" ? "Reviewed" : item.availability[0].toUpperCase() + item.availability.slice(1);
}

export function BenchmarkCaseEditor({ suiteId, documents, initialCase, onSaved, onCancel }: {
  suiteId: string; documents: DocumentSummary[]; initialCase?: DocumentEvalCase;
  onSaved: (value: DocumentEvalCase) => void; onCancel: () => void;
}) {
  const [data, setData] = useState<DocumentCaseWrite>(() => ({
    document_id: initialCase?.document_id ?? documents.find((doc) => doc.status === "indexed")?.id ?? "",
    question: initialCase?.question ?? "", expected_outcome: initialCase?.expected_outcome ?? "answerable",
    facts: initialCase?.facts ?? [], anchors: initialCase?.anchors ?? [], tags: initialCase?.tags ?? [],
    review_rationale: initialCase?.review_rationale ?? "",
  }));
  const [saved, setSaved] = useState(initialCase);
  const [caseId, setCaseId] = useState(initialCase?.id);
  const [tagsText, setTagsText] = useState(initialCase?.tags.join(", ") ?? "");
  const [viewed, setViewed] = useState<number[]>([]);
  const [scopeViewed, setScopeViewed] = useState(false);
  const [scopeConfirmed, setScopeConfirmed] = useState(false);
  const [source, setSource] = useState<SourceViewerSource | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function change(next: Partial<DocumentCaseWrite>) {
    setData((current) => ({ ...current, ...next })); setSaved(undefined); setViewed([]); setScopeViewed(false); setScopeConfirmed(false);
  }
  const negative = data.expected_outcome === "insufficient_evidence";
  const readyToReview = Boolean(saved && (negative
    ? data.review_rationale.trim() && scopeViewed && scopeConfirmed
    : data.facts.length && data.anchors.length && data.anchors.every((_, index) => viewed.includes(index))));

  async function preview(index?: number) {
    setBusy(true); setError("");
    try {
      const pages = await getDocumentPages(data.document_id);
      const chunks = await getDocumentChunks(data.document_id);
      const anchor = index === undefined ? undefined : data.anchors[index];
      const page = anchor ? pages.find((item) => item.page_number === anchor.page_number) : pages[0];
      if (!page) throw new Error("Source page is unavailable. Check the document in the workbench.");
      const chunk = chunks.find((item) => item.page_number === page.page_number && (!anchor || item.text.includes(anchor.quote)))
        ?? chunks.find((item) => item.page_number === page.page_number);
      setSource({ chunk_id: chunk?.id ?? "", document_id: data.document_id,
        document_filename: documents.find((doc) => doc.id === data.document_id)?.filename ?? initialCase?.document_filename ?? "Document",
        page_number: page.page_number, page_image_url: page.image_url, snippet: anchor?.quote ?? chunk?.text,
      });
      if (index === undefined) setScopeViewed(true); else setViewed((current) => [...new Set([...current, index])]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not open source."); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError("");
    try {
      const item = await saveDocumentCase(suiteId, { ...data, facts: data.facts.map((fact) => ({ ...fact, alternatives: fact.alternatives.map((value) => value.trim()).filter(Boolean) })) }, caseId);
      setCaseId(item.id);
      setSaved(item); setViewed([]); setScopeViewed(false); setScopeConfirmed(false); onSaved(item);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save case."); }
    finally { setBusy(false); }
  }
  async function review() {
    if (!saved || !readyToReview) return;
    setBusy(true); setError("");
    try { const item = await reviewDocumentCase(suiteId, saved.id, saved.content_version); setSaved(item); onSaved(item); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Review failed. Reload the case and try again."); }
    finally { setBusy(false); }
  }
  return <section className="mt-6 border-t border-line pt-5" aria-label="Benchmark case editor">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-lg font-bold">{initialCase ? "Edit case" : "New case"}</h3>
      <span className="text-sm font-semibold text-slate-600">{saved ? caseStateLabel(saved) : "Unsaved draft"}</span>
    </div>
    {error ? <p role="alert" className="my-3 break-words text-sm text-red-700">{error}</p> : null}
    <form className="mt-4 space-y-5" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <label className="block text-sm font-semibold">Document<select className={benchmarkInputClass} value={data.document_id} required onChange={(event) => change({ document_id: event.target.value })}>
        <option value="">Select document</option>
        {documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.filename} ({doc.status})</option>)}
      </select></label>
      <label className="block text-sm font-semibold">Question<textarea className={benchmarkInputClass} rows={2} required maxLength={2000} value={data.question} onChange={(event) => change({ question: event.target.value })} /></label>
      <fieldset><legend className="text-sm font-semibold">Expected outcome</legend><div className="mt-2 flex flex-wrap gap-2">
        {(["answerable", "insufficient_evidence"] as const).map((outcome) => <label key={outcome} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${data.expected_outcome === outcome ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line"}`}>
          <input type="radio" name="expected-outcome" value={outcome} checked={data.expected_outcome === outcome} onChange={() => change({ expected_outcome: outcome, ...(outcome === "insufficient_evidence" ? { facts: [] } : {}) })} />
          {outcome === "answerable" ? "Answerable" : "Not enough evidence"}
        </label>)}
      </div></fieldset>
      {!negative ? <fieldset><legend className="text-sm font-semibold">Expected facts</legend>
        {data.facts.map((fact, index) => <div key={index} className="mt-3 grid min-w-0 gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <label className="text-sm">Expected fact {index + 1}<input className={benchmarkInputClass} maxLength={1000} required value={fact.pattern} onChange={(event) => change({ facts: data.facts.map((item, at) => at === index ? { ...item, pattern: event.target.value } : item) })} /></label>
          <label className="text-sm">Alternatives {index + 1}<textarea rows={2} className={benchmarkInputClass} value={fact.alternatives.join("\n")} onChange={(event) => change({ facts: data.facts.map((item, at) => at === index ? { ...item, alternatives: event.target.value.split("\n") } : item) })} /></label>
          <Button type="button" variant="ghost" aria-label={`Remove fact ${index + 1}`} title={`Remove fact ${index + 1}`} onClick={() => change({ facts: data.facts.filter((_, at) => at !== index) })}><Trash2 className="h-4 w-4" /></Button>
        </div>)}
        <Button type="button" variant="ghost" disabled={data.facts.length >= 20} leftIcon={<Plus className="h-4 w-4" />} onClick={() => change({ facts: [...data.facts, { pattern: "", alternatives: [] }] })}>Add fact</Button>
      </fieldset> : null}
      <fieldset><legend className="text-sm font-semibold">Evidence anchors</legend>
        {data.anchors.map((anchor, index) => <div key={index} className="mt-3 grid min-w-0 gap-3 sm:grid-cols-[5rem_1fr_auto]">
          <label className="text-sm">Page {index + 1}<input className={benchmarkInputClass} type="number" min={1} required value={anchor.page_number} onChange={(event) => change({ anchors: data.anchors.map((item, at) => at === index ? { ...item, page_number: Number(event.target.value) } : item) })} /></label>
          <label className="text-sm">Quote {index + 1}<textarea className={benchmarkInputClass} rows={3} required maxLength={4000} value={anchor.quote} onChange={(event) => change({ anchors: data.anchors.map((item, at) => at === index ? { ...item, quote: event.target.value } : item) })} /></label>
          <div className="flex items-center gap-1"><Button type="button" variant="secondary" aria-label={`Preview anchor ${index + 1}`} title={`Preview anchor ${index + 1}`} disabled={busy} onClick={() => void preview(index)}><Eye className="h-4 w-4" /></Button>
            <Button type="button" variant="ghost" aria-label={`Remove anchor ${index + 1}`} title={`Remove anchor ${index + 1}`} onClick={() => change({ anchors: data.anchors.filter((_, at) => at !== index) })}><Trash2 className="h-4 w-4" /></Button></div>
        </div>)}
        <Button type="button" variant="ghost" disabled={data.anchors.length >= 20} leftIcon={<Plus className="h-4 w-4" />} onClick={() => change({ anchors: [...data.anchors, { page_number: 1, quote: "" }] })}>Add anchor</Button>
      </fieldset>
      <label className="block text-sm font-semibold">Tags<input className={benchmarkInputClass} value={tagsText} onChange={(event) => { setTagsText(event.target.value); change({ tags: event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean) }); }} /></label>
      <label className="block text-sm font-semibold">Review rationale<textarea className={benchmarkInputClass} maxLength={4000} rows={3} value={data.review_rationale} onChange={(event) => change({ review_rationale: event.target.value })} /></label>
      {negative ? <div className="space-y-3"><Button type="button" variant="secondary" leftIcon={<Eye className="h-4 w-4" />} disabled={busy || !data.document_id} onClick={() => void preview()}>Open document scope</Button>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={scopeConfirmed} disabled={!scopeViewed} onChange={(event) => setScopeConfirmed(event.target.checked)} />I reviewed the whole document scope</label>
      </div> : null}
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <Button type="submit" disabled={busy} leftIcon={<Save className="h-4 w-4" />}>Save draft</Button>
        <Button type="button" variant="secondary" disabled={busy || !readyToReview} leftIcon={<Check className="h-4 w-4" />} onClick={() => void review()}>Mark reviewed</Button>
        <Button type="button" variant="ghost" leftIcon={<X className="h-4 w-4" />} onClick={onCancel}>Close editor</Button>
      </div>
    </form>
    {source ? <SourceViewer source={source} onClose={() => setSource(null)} /> : null}
  </section>;
}
