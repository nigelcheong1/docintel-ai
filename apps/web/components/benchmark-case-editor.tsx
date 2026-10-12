"use client";

import { useId, useRef, useState } from "react";
import { Asterisk, Check, CheckCircle2, Circle, Eye, Plus, Save, Trash2, X } from "lucide-react";
import { SourceViewer, type SourceViewerSource } from "@/components/source-viewer";
import { Button } from "@/components/ui/button";
import { getDocumentChunks, getDocumentPages } from "@/lib/api";
import { reviewDocumentCase, saveDocumentCase } from "@/lib/document-evaluation";
import type { DocumentCaseWrite, DocumentEvalCase, DocumentSummary } from "@/lib/types";

export const benchmarkInputClass = "mt-1 w-full min-w-0 rounded-md border border-line bg-white px-3 py-2 text-sm text-ink aria-[invalid=true]:border-red-500 focus:outline-none focus:ring-2 focus:ring-teal-600";
export function caseStateLabel(item: DocumentEvalCase) {
  return item.availability === "ready" ? "Reviewed" : item.availability[0].toUpperCase() + item.availability.slice(1);
}

function RequiredMark() {
  return <Asterisk aria-hidden="true" className="ml-1 inline h-3 w-3 text-red-700" />;
}

function draftFieldErrors(data: DocumentCaseWrite): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!data.document_id.trim()) errors.document = "Select a document.";
  if (!data.question.trim()) errors.question = "Enter a question.";
  else if (data.question.length > 2000) errors.question = "Keep the question within 2,000 characters.";
  data.facts.forEach((fact, index) => {
    if (!fact.pattern.trim()) errors[`fact-${index}`] = `Enter expected fact ${index + 1}.`;
    else if (fact.pattern.trim().length > 1000) errors[`fact-${index}`] = "Keep each fact within 1,000 characters.";
    const alternatives = fact.alternatives.map((value) => value.trim()).filter(Boolean);
    if (alternatives.length > 10 || alternatives.some((value) => value.length > 1000)) {
      errors[`alternatives-${index}`] = "Use up to 10 alternatives, each within 1,000 characters.";
    }
  });
  data.anchors.forEach((anchor, index) => {
    if (!Number.isInteger(anchor.page_number) || anchor.page_number < 1) errors[`page-${index}`] = "Enter a whole page number of 1 or greater.";
    if (!anchor.quote.trim()) errors[`quote-${index}`] = `Enter evidence quote ${index + 1}.`;
    else if (anchor.quote.trim().length > 4000) errors[`quote-${index}`] = "Keep each quote within 4,000 characters.";
  });
  if (data.tags.length > 10 || data.tags.some((tag) => tag.length > 40)) errors.tags = "Use up to 10 tags, each within 40 characters.";
  if (data.review_rationale.length > 4000) errors.rationale = "Keep the rationale within 4,000 characters.";
  return errors;
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
  const [touched, setTouched] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const formId = useId();
  const editRevision = useRef(0);
  function change(next: Partial<DocumentCaseWrite>) {
    editRevision.current += 1;
    setData((current) => ({ ...current, ...next })); setSaved(undefined); setViewed([]); setScopeViewed(false); setScopeConfirmed(false);
  }
  const negative = data.expected_outcome === "insufficient_evidence";
  const draftErrors = draftFieldErrors(data);
  const fieldErrors: Record<string, string> = { ...draftErrors, ...(negative && !data.review_rationale.trim() ? { rationale: "Add a scope-review rationale." } : {}) };
  const selectedDocument = documents.find((item) => item.id === data.document_id);
  const firstFactError = Object.keys(draftErrors).find((key) => key.startsWith("fact-") || key.startsWith("alternatives-"));
  const checks = [
    { label: "Indexed source", complete: Boolean(selectedDocument?.status === "indexed" && saved?.availability !== "unavailable"), reason: !data.document_id ? "Select a document." : selectedDocument?.status !== "indexed" ? "Document must be indexed." : "Document source is unavailable." },
    { label: "Question", complete: !draftErrors.question, reason: draftErrors.question ?? "Enter a question." },
    ...(!negative ? [
      { label: "Expected facts", complete: Boolean(data.facts.length && !firstFactError), reason: !data.facts.length ? "Add at least one expected fact." : firstFactError ? draftErrors[firstFactError] : "Complete every expected fact." },
      { label: "Evidence anchors", complete: Boolean(data.anchors.length && !Object.keys(draftErrors).some((key) => key.startsWith("page-") || key.startsWith("quote-"))), reason: data.anchors.length ? "Complete every anchor page and evidence quote." : "Add at least one evidence anchor." },
    ] : [
      { label: "Scope-review rationale", complete: Boolean(data.review_rationale.trim() && !draftErrors.rationale), reason: fieldErrors.rationale ?? "Add a scope-review rationale." },
      ...(data.facts.length ? [{ label: "Negative case facts", complete: false, reason: "Clear expected facts for this negative case." }] : []),
      ...(data.anchors.length ? [{ label: "Optional evidence anchors", complete: !Object.keys(draftErrors).some((key) => key.startsWith("page-") || key.startsWith("quote-")), reason: "Complete or remove the optional evidence anchors." }] : []),
    ]),
    ...(draftErrors.tags || (!negative && draftErrors.rationale) ? [{ label: "Optional field formats", complete: false, reason: draftErrors.tags ?? draftErrors.rationale }] : []),
    { label: "Current version saved", complete: Boolean(saved), reason: "Save the current draft." },
    ...(negative ? [
      { label: "Document scope inspected", complete: scopeViewed, reason: "Inspect the document scope." },
      { label: "Scope review confirmed", complete: scopeViewed && scopeConfirmed, reason: "Confirm the document scope review." },
    ] : [{ label: "Evidence anchors previewed", complete: Boolean(data.anchors.length && data.anchors.every((_, index) => viewed.includes(index))), reason: "Preview every evidence anchor." }]),
  ];
  const missingChecks = checks.filter((item) => !item.complete);
  const readyToReview = !missingChecks.length;
  const visibleError = (key: string) => submitted || touched.includes(key) ? fieldErrors[key] : undefined;
  function fieldProps(key: string) {
    return { name: key, "aria-invalid": visibleError(key) ? true : undefined, "aria-describedby": visibleError(key) ? `${formId}-${key}-error` : undefined,
      onBlur: () => setTouched((current) => current.includes(key) ? current : [...current, key]) };
  }
  function fieldError(key: string) {
    const message = visibleError(key);
    return message ? <p id={`${formId}-${key}-error`} role="alert" className="mt-1 text-xs font-normal text-red-700">{message}</p> : null;
  }

  async function preview(index?: number) {
    if (!data.document_id || (index !== undefined && (draftErrors[`page-${index}`] || draftErrors[`quote-${index}`]))) return;
    const revision = editRevision.current;
    setBusy(true); setError("");
    try {
      const pages = await getDocumentPages(data.document_id);
      const chunks = await getDocumentChunks(data.document_id);
      if (revision !== editRevision.current) return;
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
    setSubmitted(true); setError("");
    const firstError = Object.keys(draftErrors)[0];
    if (firstError) {
      const control = formRef.current?.elements.namedItem(firstError);
      if (control instanceof HTMLElement) control.focus();
      return;
    }
    const revision = editRevision.current;
    setBusy(true); setError("");
    try {
      const item = await saveDocumentCase(suiteId, { ...data, facts: data.facts.map((fact) => ({ ...fact, alternatives: fact.alternatives.map((value) => value.trim()).filter(Boolean) })) }, caseId);
      setCaseId(item.id);
      if (revision === editRevision.current) setSaved(item);
      else setError("Current edits are not saved. Save again before source review.");
      setViewed([]); setScopeViewed(false); setScopeConfirmed(false); onSaved(item);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save case."); }
    finally { setBusy(false); }
  }
  async function review() {
    if (!saved || !readyToReview) return;
    const revision = editRevision.current;
    setBusy(true); setError("");
    try {
      const item = await reviewDocumentCase(suiteId, saved.id, saved.content_version);
      if (revision === editRevision.current) setSaved(item);
      else setError("Current edits are not saved. Save again before source review.");
      onSaved(item);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Review failed. Reload the case and try again."); }
    finally { setBusy(false); }
  }
  return <section className="mt-6 border-t border-line pt-5" aria-label="Benchmark case editor">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-lg font-bold">{initialCase ? "Edit case" : "New case"}</h3>
      <span className="text-sm font-semibold text-slate-600">{saved ? caseStateLabel(saved) : "Unsaved draft"}</span>
    </div>
    {error ? <p role="alert" className="my-3 break-words text-sm text-red-700">{error}</p> : null}
    <p className="mt-2 flex items-center text-xs text-slate-600"><RequiredMark /><span className="ml-1">Required for review</span></p>
    <form ref={formRef} noValidate className="mt-4 space-y-5" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <div><label className="block text-sm font-semibold">Document<RequiredMark /><select {...fieldProps("document")} className={benchmarkInputClass} value={data.document_id} required onChange={(event) => change({ document_id: event.target.value })}>
        <option value="">Select document</option>
        {documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.filename} ({doc.status})</option>)}
      </select></label>{fieldError("document")}</div>
      <div><label className="block text-sm font-semibold">Question<RequiredMark /><textarea {...fieldProps("question")} className={benchmarkInputClass} rows={2} required maxLength={2000} value={data.question} onChange={(event) => change({ question: event.target.value })} /></label>{fieldError("question")}</div>
      <fieldset><legend className="text-sm font-semibold">Expected outcome<RequiredMark /></legend><div className="mt-2 flex flex-wrap gap-2">
        {(["answerable", "insufficient_evidence"] as const).map((outcome) => <label key={outcome} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${data.expected_outcome === outcome ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line"}`}>
          <input type="radio" name="expected-outcome" value={outcome} checked={data.expected_outcome === outcome} onChange={() => change({ expected_outcome: outcome, ...(outcome === "insufficient_evidence" ? { facts: [] } : {}) })} />
          {outcome === "answerable" ? "Answerable" : "Not enough evidence"}
        </label>)}
      </div></fieldset>
      {!negative ? <fieldset><legend className="text-sm font-semibold">Expected facts<RequiredMark /></legend>
        {data.facts.map((fact, index) => <div key={index} className="mt-3 grid min-w-0 gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <div><label className="block text-sm">Expected fact {index + 1}<RequiredMark /><input {...fieldProps(`fact-${index}`)} className={benchmarkInputClass} maxLength={1000} required value={fact.pattern} onChange={(event) => change({ facts: data.facts.map((item, at) => at === index ? { ...item, pattern: event.target.value } : item) })} /></label>{fieldError(`fact-${index}`)}</div>
          <div><label className="block text-sm">Alternatives {index + 1}<textarea {...fieldProps(`alternatives-${index}`)} rows={2} className={benchmarkInputClass} value={fact.alternatives.join("\n")} onChange={(event) => change({ facts: data.facts.map((item, at) => at === index ? { ...item, alternatives: event.target.value.split("\n") } : item) })} /></label>{fieldError(`alternatives-${index}`)}</div>
          <Button type="button" variant="ghost" aria-label={`Remove fact ${index + 1}`} title={`Remove fact ${index + 1}`} onClick={() => change({ facts: data.facts.filter((_, at) => at !== index) })}><Trash2 className="h-4 w-4" /></Button>
        </div>)}
        <Button type="button" variant="ghost" disabled={data.facts.length >= 20} leftIcon={<Plus className="h-4 w-4" />} onClick={() => change({ facts: [...data.facts, { pattern: "", alternatives: [] }] })}>Add fact</Button>
      </fieldset> : null}
      <fieldset><legend className="text-sm font-semibold">Evidence anchors{!negative ? <RequiredMark /> : null}</legend>
        {data.anchors.map((anchor, index) => <div key={index} className="mt-3 grid min-w-0 gap-3 sm:grid-cols-[5rem_1fr_auto]">
          <div><label className="block text-sm">Page {index + 1}<RequiredMark /><input {...fieldProps(`page-${index}`)} className={benchmarkInputClass} type="number" min={1} step={1} required value={anchor.page_number} onChange={(event) => change({ anchors: data.anchors.map((item, at) => at === index ? { ...item, page_number: Number(event.target.value) } : item) })} /></label>{fieldError(`page-${index}`)}</div>
          <div><label className="block text-sm">Quote {index + 1}<RequiredMark /><textarea {...fieldProps(`quote-${index}`)} className={benchmarkInputClass} rows={3} required maxLength={4000} value={anchor.quote} onChange={(event) => change({ anchors: data.anchors.map((item, at) => at === index ? { ...item, quote: event.target.value } : item) })} /></label>{fieldError(`quote-${index}`)}</div>
          <div className="flex items-center gap-1"><Button type="button" variant="secondary" aria-label={`Preview anchor ${index + 1}`} title={`Preview anchor ${index + 1}`} disabled={busy || !data.document_id || Boolean(draftErrors[`page-${index}`] || draftErrors[`quote-${index}`])} onClick={() => void preview(index)}><Eye className="h-4 w-4" /></Button>
            <Button type="button" variant="ghost" aria-label={`Remove anchor ${index + 1}`} title={`Remove anchor ${index + 1}`} onClick={() => change({ anchors: data.anchors.filter((_, at) => at !== index) })}><Trash2 className="h-4 w-4" /></Button></div>
        </div>)}
        <Button type="button" variant="ghost" disabled={data.anchors.length >= 20} leftIcon={<Plus className="h-4 w-4" />} onClick={() => change({ anchors: [...data.anchors, { page_number: 1, quote: "" }] })}>Add anchor</Button>
      </fieldset>
      <div><label className="block text-sm font-semibold">Tags<input {...fieldProps("tags")} className={benchmarkInputClass} value={tagsText} onChange={(event) => { setTagsText(event.target.value); change({ tags: event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean) }); }} /></label>{fieldError("tags")}</div>
      <div><label className="block text-sm font-semibold">Review rationale{negative ? <RequiredMark /> : null}<textarea {...fieldProps("rationale")} className={benchmarkInputClass} required={negative} maxLength={4000} rows={3} value={data.review_rationale} onChange={(event) => change({ review_rationale: event.target.value })} /></label>{fieldError("rationale")}</div>
      {negative ? <div className="space-y-3"><Button type="button" variant="secondary" leftIcon={<Eye className="h-4 w-4" />} disabled={busy || !data.document_id} onClick={() => void preview()}>Open document scope</Button>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" required checked={scopeConfirmed} disabled={!scopeViewed} onChange={(event) => setScopeConfirmed(event.target.checked)} /><span>I reviewed the whole document scope<RequiredMark /></span></label>
      </div> : null}
      <section aria-label="Review prerequisites" id={`${formId}-review-checks`} className="border-t border-line pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-bold">Review prerequisites</h4><p role="status" className={`text-xs font-semibold ${readyToReview ? "text-teal-700" : "text-slate-600"}`}>{readyToReview ? "Ready for review" : `${missingChecks.length} remaining`}</p></div>
        <ul className="mt-3 grid gap-x-5 gap-y-2 sm:grid-cols-2">{checks.map((item) => <li key={item.label} className="flex items-start gap-2 text-xs leading-5">
          {item.complete ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" aria-hidden="true" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />}
          <span className="min-w-0 break-words">{item.complete ? item.label : item.reason}<span className="ml-2 font-semibold text-slate-600">{item.complete ? "Complete" : "Pending"}</span></span>
        </li>)}</ul>
      </section>
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <Button type="submit" disabled={busy} leftIcon={<Save className="h-4 w-4" />}>Save draft</Button>
        <Button type="button" variant="secondary" disabled={busy || !readyToReview} aria-describedby={`${formId}-review-checks`} leftIcon={<Check className="h-4 w-4" />} onClick={() => void review()}>Mark reviewed</Button>
        <Button type="button" variant="ghost" leftIcon={<X className="h-4 w-4" />} onClick={onCancel}>Close editor</Button>
      </div>
    </form>
    {source ? <SourceViewer source={source} onClose={() => setSource(null)} /> : null}
  </section>;
}
