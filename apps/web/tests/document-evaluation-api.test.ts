import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/document-evaluation";
import { benchmarkCase } from "./document-evaluation-fixtures";

describe("document benchmark client", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("uses typed suite and case endpoints with correct payloads", async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify(benchmarkCase), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    await api.listDocumentSuites();
    expect(fetcher).toHaveBeenLastCalledWith("http://localhost:8000/eval/document-suites", { cache: "no-store" });
    await api.createDocumentSuite("Research checks");
    expect(JSON.parse(fetcher.mock.lastCall![1].body)).toEqual({ name: "Research checks" });
    await api.getDocumentSuite("suite-1");
    expect(fetcher.mock.lastCall![0]).toContain("/document-suites/suite-1");
    await api.updateDocumentSuite("suite-1", "Renamed");
    expect(fetcher.mock.lastCall![1].method).toBe("PUT");
    const { document_id, question, expected_outcome, facts, anchors, tags, review_rationale } = benchmarkCase;
    const data = { document_id: document_id!, question, expected_outcome, facts, anchors, tags, review_rationale };
    await api.saveDocumentCase("suite-1", data);
    expect(fetcher.mock.lastCall![1].method).toBe("POST");
    expect(JSON.parse(fetcher.mock.lastCall![1].body)).toEqual(data);
    await api.saveDocumentCase("suite-1", data, "case-1");
    expect(fetcher.mock.lastCall![1].method).toBe("PUT");
    await api.reviewDocumentCase("suite-1", "case-1", 2);
    expect(fetcher.mock.lastCall![0]).toContain("/cases/case-1/review");
    expect(JSON.parse(fetcher.mock.lastCall![1].body)).toEqual({ content_version: 2 });
  });
  it("handles 204 deletes without parsing a body and surfaces server errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api.deleteDocumentSuite("suite-1")).resolves.toBeUndefined();
    await expect(api.deleteDocumentCase("suite-1", "case-1")).resolves.toBeUndefined();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify({ detail: "Case changed; review again." }), { status: 409 })));
    await expect(api.reviewDocumentCase("suite-1", "case-1", 1)).rejects.toThrow("Case changed; review again.");
    await expect(api.deleteDocumentSuite("suite-1")).rejects.toThrow("Case changed; review again.");
  });
  it("creates, loads, cancels and assesses persisted runs without changing expectations", async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    await api.createDocumentRun("suite-1");
    expect(JSON.parse(fetcher.mock.lastCall![1].body)).toEqual({ suite_id: "suite-1" });
    await api.listDocumentRuns("suite-1");
    expect(fetcher.mock.lastCall![0]).toBe("http://localhost:8000/eval/document-runs?suite_id=suite-1");
    await api.listDocumentRuns();
    expect(fetcher.mock.lastCall![0]).toBe("http://localhost:8000/eval/document-runs");
    await api.getDocumentRun("run-1");
    expect(fetcher.mock.lastCall![0]).toContain("/document-runs/run-1");
    await api.getDocumentRunResults("run-1");
    expect(fetcher.mock.lastCall![0]).toContain("/run-1/results");
    await api.cancelDocumentRun("run-1");
    expect(fetcher.mock.lastCall![0]).toContain("/run-1/cancel");
    expect(fetcher.mock.lastCall![1].method).toBe("POST");
    await api.assessDocumentResult("run-1", "result-1", "incorrect", "The source is ambiguous.");
    expect(fetcher.mock.lastCall![1].method).toBe("PUT");
    expect(JSON.parse(fetcher.mock.lastCall![1].body)).toEqual({ assessment: "incorrect", note: "The source is ambiguous." });
  });
});
