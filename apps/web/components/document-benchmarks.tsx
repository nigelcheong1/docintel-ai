"use client";

import { useEffect, useState } from "react";
import { Pencil, Play, Plus, RefreshCw, Trash2 } from "lucide-react";
import { BenchmarkCaseEditor, benchmarkInputClass, caseStateLabel } from "@/components/benchmark-case-editor";
import { Button } from "@/components/ui/button";
import { getDocuments } from "@/lib/api";
import { createDocumentSuite, deleteDocumentCase, deleteDocumentSuite, getDocumentSuite, listDocumentSuites, updateDocumentSuite } from "@/lib/document-evaluation";
import type { DocumentEvalCase, DocumentEvalSuite, DocumentEvalSuiteDetail, DocumentSummary } from "@/lib/types";

export function DocumentBenchmarks() {
  const [suites, setSuites] = useState<DocumentEvalSuite[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [suite, setSuite] = useState<DocumentEvalSuiteDetail | null>(null);
  const [name, setName] = useState("");
  const [rename, setRename] = useState<string | null>(null);
  const [editing, setEditing] = useState<DocumentEvalCase | "new" | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      setLoading(true);
      try {
        const loadedSuites = await listDocumentSuites();
        const loadedDocs = await getDocuments();
        if (cancelled) return;
        setSuites(loadedSuites); setDocuments(loadedDocs);
        setSelectedId((current) => loadedSuites.some((item) => item.id === current) ? current : loadedSuites[0]?.id ?? "");
        setError("");
      } catch (reason) { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load benchmarks."); }
      finally { if (!cancelled) setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [refresh]);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      setSuite(null); setEditing(null); setConfirm(null); setRename(null);
      if (!selectedId) return;
      try { const detail = await getDocumentSuite(selectedId); if (!cancelled) setSuite(detail); }
      catch (reason) { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load suite."); }
    });
    return () => { cancelled = true; };
  }, [selectedId, refresh]);
  async function action(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed. Try again."); }
    finally { setBusy(false); }
  }
  function saved(item: DocumentEvalCase) {
    setSuite((current) => current ? { ...current, cases: [...current.cases.filter((value) => value.id !== item.id), item] } : current);
  }
  const reviewed = suite?.cases.filter((item) => item.review_state === "reviewed").length ?? 0;
  return <section aria-label="Document benchmarks" className="min-w-0 space-y-5">
    <form className="flex flex-wrap items-end gap-3 border-b border-line pb-5" onSubmit={(event) => {
      event.preventDefault(); void action(async () => {
        const created = await createDocumentSuite(name.trim()); setSuites((current) => [...current, created]); setSelectedId(created.id); setName("");
      });
    }}>
      <label className="min-w-0 flex-1 text-sm font-semibold">Suite name<input className={benchmarkInputClass} required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <Button type="submit" disabled={busy || !name.trim()} leftIcon={<Plus className="h-4 w-4" />}>Create suite</Button>
    </form>
    {error ? <div className="flex flex-wrap items-center gap-3"><p role="alert" className="break-words text-sm text-red-700">{error}</p><Button variant="secondary" onClick={() => setRefresh((value) => value + 1)} leftIcon={<RefreshCw className="h-4 w-4" />}>Retry</Button></div> : null}
    {loading ? <p role="status" className="text-sm text-slate-600">Loading benchmark suites...</p> : !suites.length ? <p className="text-sm text-slate-600">No benchmark suites yet.</p> : <>
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 text-sm font-semibold">Selected suite<select className={benchmarkInputClass} value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{suites.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <Button variant="secondary" aria-label="Rename suite" title="Rename suite" onClick={() => setRename(suite?.name ?? "")} disabled={!suite || busy}><Pencil className="h-4 w-4" /></Button>
        <Button variant="danger" aria-label="Delete suite" title="Delete suite" onClick={() => setConfirm("suite")} disabled={!suite || busy}><Trash2 className="h-4 w-4" /></Button>
        <Button disabled={!reviewed || busy} leftIcon={<Play className="h-4 w-4" />}>Run benchmark</Button>
      </div>
      {rename !== null && suite ? <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => {
        event.preventDefault(); void action(async () => { const updated = await updateDocumentSuite(suite.id, rename); setSuites((items) => items.map((item) => item.id === updated.id ? updated : item)); setSuite((item) => item ? { ...item, name: updated.name } : null); setRename(null); });
      }}><label className="min-w-0 flex-1 text-sm">Rename suite<input className={benchmarkInputClass} required maxLength={120} value={rename} onChange={(event) => setRename(event.target.value)} /></label><Button type="submit" disabled={busy}>Save name</Button><Button variant="ghost" type="button" onClick={() => setRename(null)}>Cancel</Button></form> : null}
      {confirm ? <div className="flex flex-wrap items-center gap-3 border-y border-red-200 py-3 text-sm" role="alert">
        <span>{confirm === "suite" ? "Delete this suite and its cases? Saved run history is retained." : "Delete this case? Saved results are retained."}</span>
        <Button variant="danger" disabled={busy} onClick={() => void action(async () => {
          if (!suite) return;
          if (confirm === "suite") { await deleteDocumentSuite(suite.id); setSuites((items) => items.filter((item) => item.id !== suite.id)); setSelectedId(""); setSuite(null); }
          else { await deleteDocumentCase(suite.id, confirm); setSuite((item) => item ? { ...item, cases: item.cases.filter((value) => value.id !== confirm) } : null); }
          setConfirm(null);
        })}>{confirm === "suite" ? "Confirm delete suite" : "Confirm delete case"}</Button><Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
      </div> : null}
      {suite ? <>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-bold">Cases <span className="ml-2 text-sm font-normal text-slate-600">{reviewed} reviewed / {suite.cases.length} total</span></h2><Button variant="secondary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setEditing("new")}>Add case</Button></div>
        {!suite.cases.length ? <p className="text-sm text-slate-600">No cases in this suite.</p> : <ul className="divide-y divide-line border-y border-line">
          {suite.cases.map((item) => <li key={item.id} className="flex min-w-0 flex-wrap items-start gap-3 py-4">
            <div className="min-w-0 flex-1"><p className="break-words text-sm font-semibold">{item.question}</p><p className="mt-1 break-words text-xs text-slate-600">{item.document_filename} · Version {item.content_version} · {item.expected_outcome === "answerable" ? "Answerable" : "Not enough evidence"}</p>{item.availability_reasons.map((reason) => <p key={reason} className="mt-1 break-words text-xs text-red-700">{reason}</p>)}</div>
            <span className={`text-xs font-semibold ${item.availability === "ready" ? "text-teal-700" : "text-slate-600"}`}>{caseStateLabel(item)}</span>
            <Button variant="ghost" aria-label={`Edit case: ${item.question}`} title="Edit case" onClick={() => setEditing(item)}><Pencil className="h-4 w-4" /></Button><Button variant="ghost" aria-label={`Delete case: ${item.question}`} title="Delete case" onClick={() => setConfirm(item.id)}><Trash2 className="h-4 w-4" /></Button>
          </li>)}
        </ul>}
        {editing ? <BenchmarkCaseEditor key={editing === "new" ? "new" : editing.id} suiteId={suite.id} documents={documents} initialCase={editing === "new" ? undefined : editing} onSaved={saved} onCancel={() => setEditing(null)} /> : null}
      </> : <p role="status" className="text-sm text-slate-600">Loading suite...</p>}
    </>}
  </section>;
}
