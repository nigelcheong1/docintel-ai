"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpenCheck,
  Brain,
  CheckCircle2,
  Database,
  Eye,
  FileText,
  Gauge,
  Layers3,
  RotateCcw,
  Search,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { SourceViewer, type SourceViewerSource } from "@/components/source-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import {
  generateDocumentStudySummary,
  generateStudyQuestions,
  getDocumentStudySummary,
  getStudyQuestions,
  submitStudyAnswer,
} from "@/lib/api";
import { apiAssetUrl } from "@/lib/api-assets";
import type {
  DocumentChunk,
  DocumentDetail,
  DocumentFact,
  DocumentPage,
  DocumentProfile,
  DocumentStudySummary,
  StudyCitation,
  StudyQuestion,
} from "@/lib/types";

type WorkbenchTab = "overview" | "summary" | "study" | "evidence" | "quality";

type DocumentWorkbenchProps = {
  document: DocumentDetail;
  profile: DocumentProfile | null;
  pages: DocumentPage[];
  chunks: DocumentChunk[];
  initialPageNumber?: number;
  initialChunkId?: string;
};

function formatDocumentType(value?: string | null) {
  if (!value) {
    return "Document";
  }
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatStatus(value: string) {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatTextSource(value: string) {
  const normalized = value.replace(/_/g, " ").toLowerCase();
  if (normalized === "ocr") {
    return "OCR";
  }
  return normalized.replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "Not available";
  }
  return `${Math.round(value * 10) / 10}%`;
}

function formatOcrConfidence(value: number | null | undefined) {
  return typeof value === "number" ? `${formatPercent(value)} OCR confidence` : "OCR not run";
}

function formatCount(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function formatScore(value: number) {
  return `${Math.round(value * 100)}%`;
}

const workbenchTabs: Array<{ id: WorkbenchTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "summary", label: "Summary" },
  { id: "study", label: "Study" },
  { id: "evidence", label: "Evidence" },
  { id: "quality", label: "Quality" },
];

function selectedPageFrom(pages: DocumentPage[], initialPageNumber?: number) {
  return pages.find((page) => page.page_number === initialPageNumber) ?? pages[0] ?? null;
}

function pageTone(page: DocumentPage) {
  if (page.needs_review || page.ocr_quality === "weak" || page.ocr_quality === "missing") {
    return "amber" as const;
  }
  if (page.text_source === "ocr" || page.text_source === "hybrid") {
    return "amber" as const;
  }
  if (page.character_count > 0 && page.chunk_count > 0) {
    return "success" as const;
  }
  return "neutral" as const;
}

function formatOcrQuality(value: DocumentPage["ocr_quality"]) {
  if (value === "native") {
    return "Native text";
  }
  return `${value.charAt(0).toUpperCase()}${value.slice(1)} OCR`;
}

function formatProcessingStatus(value?: DocumentPage["processing_status"]) {
  const labels: Record<DocumentPage["processing_status"], string> = {
    native_text: "Native text",
    ocr_strong: "OCR strong",
    ocr_moderate: "OCR moderate",
    ocr_weak: "OCR weak",
    missing_text: "Missing text",
  };
  return value ? labels[value] : "Processing pending";
}

function PreviewControl({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-white text-slate-600 shadow-sm transition hover:border-teal-500 hover:bg-teal-50 hover:text-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function sourceFromCitation(citation: StudyCitation): SourceViewerSource {
  return {
    chunk_id: citation.chunk_id,
    document_id: citation.document_id,
    document_filename: citation.document_filename,
    page_number: citation.page_number,
    section_heading: citation.section_heading,
    page_image_url: citation.page_image_url,
    document_page_url: citation.document_page_url,
    snippet: citation.snippet,
    score: citation.score,
    source_score: citation.source_score,
  };
}

function CitationLinks({
  citations,
  onPreviewCitation,
}: {
  citations: StudyCitation[];
  onPreviewCitation?: (source: SourceViewerSource) => void;
}) {
  if (citations.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citations.map((citation) => {
        const documentPageUrl =
          citation.document_page_url ?? `/documents/${citation.document_id}?page=${citation.page_number}&chunk=${citation.chunk_id}`;
        return (
        <span key={`${citation.chunk_id}-${citation.page_number}`} className="inline-flex flex-wrap items-center gap-1.5">
          <Link
            href={documentPageUrl}
            className="inline-flex min-h-8 items-center rounded-md border border-teal-200 bg-teal-50 px-2.5 py-1.5 text-xs font-semibold text-teal-800 transition hover:border-teal-500 hover:bg-teal-100"
          >
            Page {citation.page_number}
            {citation.section_heading ? ` ${citation.section_heading}` : ""}
          </Link>
          {onPreviewCitation && citation.page_image_url ? (
            <button
              type="button"
              aria-label={`Preview citation ${citation.document_filename} page ${citation.page_number}`}
              className="inline-flex min-h-8 items-center gap-1 rounded-md border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-teal-600 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
              onClick={() => onPreviewCitation(sourceFromCitation(citation))}
            >
              <Eye className="h-3.5 w-3.5" aria-hidden="true" />
              Preview
            </button>
          ) : null}
        </span>
        );
      })}
    </div>
  );
}

function FactList({ title, facts }: { title: string; facts: DocumentFact[] }) {
  if (facts.length === 0) {
    return null;
  }

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {facts.slice(0, 8).map((fact) => (
          <Badge key={`${fact.kind}-${fact.label}-${fact.value}-${fact.page_number}`} tone="neutral">
            {fact.value}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function WorkbenchStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-teal-100 bg-teal-50/50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function WorkflowStep({ label, active }: { label: string; active: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <span className={["h-2.5 w-2.5 rounded-full", active ? "bg-teal-600" : "bg-slate-300"].join(" ")} />
      <span className={active ? "font-medium text-ink" : "text-slate-500"}>{label}</span>
    </li>
  );
}

export function DocumentWorkbench(props: DocumentWorkbenchProps) {
  return (
    <DocumentWorkbenchContent
      key={`${props.document.id}:${props.initialPageNumber ?? "overview"}:${props.initialChunkId ?? "none"}`}
      {...props}
    />
  );
}

function DocumentWorkbenchContent({ document, profile, pages, chunks, initialPageNumber, initialChunkId }: DocumentWorkbenchProps) {
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(
    selectedPageFrom(pages, initialPageNumber)?.page_number ?? null,
  );
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(initialChunkId ?? null);
  const [activeTab, setActiveTab] = useState<WorkbenchTab>(initialPageNumber || initialChunkId ? "evidence" : "overview");
  const [previewZoom, setPreviewZoom] = useState(100);
  const [studySummary, setStudySummary] = useState<DocumentStudySummary | null>(null);
  const [studyQuestions, setStudyQuestions] = useState<StudyQuestion[]>([]);
  const [studyMessage, setStudyMessage] = useState("");
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [checkingQuestionId, setCheckingQuestionId] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<SourceViewerSource | null>(null);
  const selectedPage = pages.find((page) => page.page_number === selectedPageNumber) ?? pages[0] ?? null;
  const visibleChunks = useMemo(
    () =>
      selectedPage
        ? chunks
            .filter((chunk) => chunk.page_number === selectedPage.page_number)
            .sort((first, second) => first.chunk_index - second.chunk_index)
        : chunks.slice().sort((first, second) => first.chunk_index - second.chunk_index),
    [chunks, selectedPage],
  );
  const ocrConfidence = document.parse_quality?.ocr_confidence_average;
  const warnings = document.parse_quality?.warnings ?? [];

  useEffect(() => {
    let isCurrent = true;

    async function loadStudyWorkspace() {
      try {
        const [summaryResult, questionResults] = await Promise.all([
          getDocumentStudySummary(document.id),
          getStudyQuestions(document.id),
        ]);
        if (!isCurrent) {
          return;
        }
        setStudySummary((current) => current ?? summaryResult);
        setStudyQuestions((current) => (current.length > 0 ? current : questionResults));
        setStudyMessage("");
      } catch (error) {
        if (isCurrent) {
          setStudyMessage(error instanceof Error ? error.message : "Could not load study workspace.");
        }
      }
    }

    void loadStudyWorkspace();

    return () => {
      isCurrent = false;
    };
  }, [document.id]);

  async function handleGenerateSummary() {
    setIsGeneratingSummary(true);
    setStudyMessage("");
    try {
      setStudySummary(await generateDocumentStudySummary(document.id));
    } catch (error) {
      setStudyMessage(error instanceof Error ? error.message : "Could not generate summary.");
    } finally {
      setIsGeneratingSummary(false);
    }
  }

  async function handleGenerateQuestions() {
    setIsGeneratingQuestions(true);
    setStudyMessage("");
    try {
      const generated = await generateStudyQuestions(document.id, 5, { replaceExisting: true });
      setStudyQuestions(generated);
      setAnswerDrafts({});
    } catch (error) {
      setStudyMessage(error instanceof Error ? error.message : "Could not generate study questions.");
    } finally {
      setIsGeneratingQuestions(false);
    }
  }

  async function handleSubmitAnswer(questionId: string) {
    const answerText = answerDrafts[questionId]?.trim() ?? "";
    if (!answerText) {
      setStudyMessage("Enter an answer before checking it.");
      return;
    }
    setCheckingQuestionId(questionId);
    setStudyMessage("");
    try {
      const gradedAnswer = await submitStudyAnswer(document.id, questionId, answerText);
      setStudyQuestions((current) =>
        current.map((question) => {
          if (question.id !== questionId) {
            return question;
          }
          const previousAnswers = question.recent_answers?.length
            ? question.recent_answers
            : question.latest_answer
              ? [question.latest_answer]
              : [];
          return {
            ...question,
            latest_answer: gradedAnswer,
            answer_count: (question.answer_count ?? previousAnswers.length) + 1,
            recent_answers: [
              gradedAnswer,
              ...previousAnswers.filter((answer) => answer.id !== gradedAnswer.id),
            ].slice(0, 3),
          };
        }),
      );
    } catch (error) {
      setStudyMessage(error instanceof Error ? error.message : "Could not check answer.");
    } finally {
      setCheckingQuestionId(null);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-teal-100 bg-white/95 p-5 shadow-sm shadow-teal-950/5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-normal text-teal-700">
              <BookOpenCheck className="h-4 w-4" aria-hidden="true" />
              Evidence Workbench
            </p>
            <h1 className="mt-2 break-words text-3xl font-black tracking-normal text-ink">{document.filename}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Review page coverage, source quality, and the exact chunks available for cited answers.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/documents"
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink shadow-sm transition hover:border-teal-600 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Documents
            </Link>
            <Link
              href={`/search?documentId=${document.id}`}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-teal-900/10 transition hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              Ask document
            </Link>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <WorkbenchStat label="Status" value={formatStatus(document.status)} />
          <WorkbenchStat label="Pages" value={formatCount(document.page_count, "page", "pages")} />
          <WorkbenchStat label="Evidence" value={formatCount(document.chunk_count, "chunk", "chunks")} />
          <WorkbenchStat label="Type" value={formatDocumentType(profile?.document_type)} />
          <WorkbenchStat label="OCR" value={formatOcrConfidence(ocrConfidence)} />
        </div>
        {warnings.length > 0 ? (
          <div className="mt-4 space-y-2">
            {warnings.slice(0, 2).map((warning) => (
              <p key={warning} className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                <AlertTriangle className="mt-1 h-4 w-4 flex-none" aria-hidden="true" />
                {warning}
              </p>
            ))}
          </div>
        ) : null}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-5">
          <Panel className="p-4">
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Workbench views">
              {workbenchTabs.map((tab) => (
                <Button
                  key={tab.id}
                  type="button"
                  variant={activeTab === tab.id ? "primary" : "secondary"}
                  className="min-h-9 px-3 py-1.5 text-xs"
                  onClick={() => setActiveTab(tab.id)}
                  aria-pressed={activeTab === tab.id}
                >
                  {tab.label}
                </Button>
              ))}
            </div>
          </Panel>

          {activeTab === "overview" ? (
            <Panel tone="accent" className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="teal">{formatDocumentType(profile?.document_type)}</Badge>
                <StatusBadge status={document.status} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-ink">{profile?.title ?? "Document intelligence"}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {profile?.overview ?? "No intelligence profile is available yet. Reindex this document after text extraction completes."}
                </p>
              </div>
              {profile ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">Sections</h3>
                    <div className="mt-2 space-y-2">
                      {profile.sections.slice(0, 5).map((section) => (
                        <button
                          key={`${section.heading}-${section.page_number}`}
                          type="button"
                          className="w-full rounded-lg border border-line bg-white p-3 text-left text-sm transition hover:border-teal-300 hover:bg-teal-50/50"
                          onClick={() => {
                            setSelectedPageNumber(section.page_number);
                            setSelectedChunkId(null);
                            setActiveTab("evidence");
                          }}
                        >
                          <span className="font-semibold text-ink">{section.heading}</span>
                          <span className="ml-2 text-xs text-slate-500">p.{section.page_number}</span>
                          <span className="mt-1 block text-xs leading-5 text-slate-500">{section.text_preview}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-4">
                    <FactList title="Numbers" facts={profile.key_numbers} />
                    <FactList title="Entities" facts={profile.key_entities} />
                    <FactList title="Dates" facts={profile.key_dates} />
                  </div>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {activeTab === "summary" ? (
            <Panel aria-label="Study summary" className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-accent" aria-hidden="true" />
                    <h2 className="text-lg font-bold text-ink">Cited summary</h2>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Generate a reusable overview from the strongest indexed evidence.
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={handleGenerateSummary}
                  isLoading={isGeneratingSummary}
                  variant={studySummary ? "secondary" : "primary"}
                >
                  {studySummary ? "Regenerate summary" : "Generate summary"}
                </Button>
              </div>
              {studyMessage ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                  {studyMessage}
                </p>
              ) : null}
              {studySummary ? (
                <article className="rounded-lg border border-teal-100 bg-teal-50/40 p-4">
                  <p className="text-sm leading-7 text-ink">{studySummary.content}</p>
                  <CitationLinks citations={studySummary.citations} onPreviewCitation={setSelectedSource} />
                </article>
              ) : (
                <div className="rounded-lg border border-dashed border-line bg-slate-50 p-5 text-sm leading-6 text-slate-600">
                  No generated summary yet. Create one to turn this document into a quick review sheet.
                </div>
              )}
            </Panel>
          ) : null}

          {activeTab === "study" ? (
            <Panel aria-label="Study questions" className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-accent" aria-hidden="true" />
                    <h2 className="text-lg font-bold text-ink">Study mode</h2>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Generate practice questions, answer them, and get feedback grounded in citations.
                  </p>
                </div>
                <Button type="button" onClick={handleGenerateQuestions} isLoading={isGeneratingQuestions}>
                  {studyQuestions.length > 0 ? "Regenerate study set" : "Generate study set"}
                </Button>
              </div>
              {studyMessage ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                  {studyMessage}
                </p>
              ) : null}
              {studyQuestions.length === 0 ? (
                <div className="rounded-lg border border-dashed border-line bg-slate-50 p-5 text-sm leading-6 text-slate-600">
                  No study questions yet. Generate a study set from the current document evidence.
                </div>
              ) : (
                <div className="space-y-3">
                  {studyQuestions.map((question, index) => {
                    const latestAnswer = question.latest_answer;
                    const recentAnswers = question.recent_answers?.length
                      ? question.recent_answers
                      : latestAnswer
                        ? [latestAnswer]
                        : [];
                    const answerCount = question.answer_count ?? recentAnswers.length;
                    return (
                      <article key={question.id} className="rounded-lg border border-line bg-white p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">
                              Question {index + 1}
                            </p>
                            <h3 className="mt-1 break-words text-base font-bold text-ink">{question.question}</h3>
                          </div>
                          <div className="flex flex-wrap justify-end gap-2">
                            {answerCount > 0 ? (
                              <Badge tone="neutral">{formatCount(answerCount, "attempt", "attempts")}</Badge>
                            ) : null}
                            {latestAnswer ? (
                              <Badge tone={latestAnswer.score >= 0.75 ? "success" : latestAnswer.score >= 0.4 ? "amber" : "danger"}>
                                {formatScore(latestAnswer.score)}
                              </Badge>
                            ) : null}
                          </div>
                        </div>
                        <details className="mt-3 rounded-md border border-teal-100 bg-teal-50/40 p-3">
                          <summary className="cursor-pointer text-sm font-semibold text-teal-800">
                            Expected answer
                          </summary>
                          <p className="mt-2 text-sm leading-6 text-slate-700">{question.expected_answer}</p>
                        </details>
                        <CitationLinks citations={question.citations} onPreviewCitation={setSelectedSource} />
                        <div className="mt-4 space-y-2">
                          <label htmlFor={`answer-${question.id}`} className="text-sm font-semibold text-ink">
                            Your answer
                          </label>
                          <textarea
                            id={`answer-${question.id}`}
                            aria-label={`Answer for ${question.question}`}
                            value={answerDrafts[question.id] ?? ""}
                            onChange={(event) =>
                              setAnswerDrafts((current) => ({ ...current, [question.id]: event.target.value }))
                            }
                            className="min-h-24 w-full rounded-md border border-line bg-white px-3 py-2 text-sm leading-6 text-ink shadow-sm transition placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                            placeholder="Write your answer from memory, then check it against the cited evidence."
                          />
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => void handleSubmitAnswer(question.id)}
                            isLoading={checkingQuestionId === question.id}
                          >
                            Check answer
                          </Button>
                        </div>
                        {latestAnswer ? (
                          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
                              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                              Feedback
                            </p>
                            <p className="mt-1 text-sm leading-6 text-emerald-900">{latestAnswer.feedback}</p>
                            {recentAnswers.length > 1 ? (
                              <div className="mt-3 border-t border-emerald-200 pt-3">
                                <p className="text-xs font-semibold uppercase tracking-normal text-emerald-800">
                                  Recent attempts
                                </p>
                                <ul className="mt-2 space-y-2">
                                  {recentAnswers.map((answer) => (
                                    <li
                                      key={answer.id}
                                      className="flex flex-wrap items-start justify-between gap-2 rounded-md bg-white/70 px-3 py-2 text-xs text-emerald-950"
                                    >
                                      <span className="min-w-0 flex-1 break-words">{answer.feedback}</span>
                                      <span className="font-semibold">{formatScore(answer.score)}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              )}
            </Panel>
          ) : null}

          {activeTab === "evidence" ? (
            <Panel aria-label="Page evidence" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-bold text-ink">
                    {selectedPage ? `Page ${selectedPage.page_number} evidence` : "Evidence chunks"}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {visibleChunks.length === 0
                      ? "No chunks were produced for this page."
                      : formatCount(visibleChunks.length, "chunk available", "chunks available")}
                  </p>
                </div>
                {selectedPage ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedPage.needs_review ? <Badge tone="amber">Review needed</Badge> : null}
                    <Badge tone={pageTone(selectedPage)}>{formatTextSource(selectedPage.text_source)}</Badge>
                  </div>
                ) : null}
              </div>
              {selectedPage ? (
                <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
                  <section className="min-w-0 rounded-lg border border-line bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-semibold text-ink">Source page</h3>
                        <p className="mt-1 text-xs text-slate-500">
                          {formatOcrQuality(selectedPage.ocr_quality)} - {selectedPage.text_density} density
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="min-w-12 text-center text-xs font-semibold text-slate-600">{previewZoom}%</span>
                        <PreviewControl
                          label="Zoom out page preview"
                          onClick={() => setPreviewZoom((current) => Math.max(50, current - 25))}
                        >
                          <ZoomOut className="h-4 w-4" aria-hidden="true" />
                        </PreviewControl>
                        <PreviewControl label="Reset page preview zoom" onClick={() => setPreviewZoom(100)}>
                          <RotateCcw className="h-4 w-4" aria-hidden="true" />
                        </PreviewControl>
                        <PreviewControl
                          label="Zoom in page preview"
                          onClick={() => setPreviewZoom((current) => Math.min(200, current + 25))}
                        >
                          <ZoomIn className="h-4 w-4" aria-hidden="true" />
                        </PreviewControl>
                      </div>
                    </div>
                    <div className="mt-3 max-h-[32rem] overflow-auto rounded-md border border-line bg-white p-2">
                      {/* eslint-disable-next-line @next/next/no-img-element -- Source previews come from the local API with document-specific dimensions. */}
                      <img
                        src={apiAssetUrl(selectedPage.image_url)}
                        alt={`Page ${selectedPage.page_number} source preview`}
                        className="mx-auto block h-auto max-w-none rounded-sm border border-slate-200 bg-white shadow-sm"
                        style={{ width: `${previewZoom}%`, minWidth: `${previewZoom}%` }}
                      />
                    </div>
                  </section>
                  <section className="min-w-0 space-y-3">
                    {visibleChunks.map((chunk) => (
                      <article
                        key={chunk.id}
                        className={[
                          "rounded-lg border bg-white p-4 transition",
                          chunk.id === selectedChunkId
                            ? "border-amber-300 bg-amber-50/60 shadow-sm shadow-amber-900/10"
                            : "border-line",
                        ].join(" ")}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                          <span>Chunk {chunk.chunk_index + 1}</span>
                          <span className="flex flex-wrap items-center justify-end gap-2">
                            {chunk.id === selectedChunkId ? <Badge tone="amber">Selected citation</Badge> : null}
                            <span>{chunk.token_estimate} tokens</span>
                          </span>
                        </div>
                        <p className="mt-2 break-words text-sm leading-6 text-slate-700">{chunk.text}</p>
                      </article>
                    ))}
                  </section>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {activeTab === "quality" ? (
            <Panel className="space-y-4">
              <div className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-accent" aria-hidden="true" />
                <h2 className="text-lg font-bold text-ink">Indexing quality</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <WorkbenchStat label="Text pages" value={`${document.parse_quality?.text_page_count ?? 0}/${document.page_count}`} />
                <WorkbenchStat label="OCR pages" value={`${document.parse_quality?.ocr_page_count ?? 0}`} />
                <WorkbenchStat label="Empty pages" value={`${document.parse_quality?.empty_page_count ?? 0}`} />
              </div>
              {warnings.length > 0 ? (
                <div className="space-y-2">
                  {warnings.map((warning) => (
                    <p key={warning} className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                      <AlertTriangle className="mt-1 h-4 w-4 flex-none" aria-hidden="true" />
                      {warning}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                  No indexing warnings were reported for this document.
                </p>
              )}
            </Panel>
          ) : null}
        </div>

        <aside className="space-y-5">
          <Panel className="space-y-4">
            <div className="flex items-center gap-2">
              <Layers3 className="h-4 w-4 text-accent" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Processing timeline</h2>
            </div>
            <ol className="space-y-3">
              <WorkflowStep label="Uploaded" active />
              <WorkflowStep label="Text extracted" active={pages.length > 0} />
              <WorkflowStep label="Evidence indexed" active={document.chunk_count > 0} />
              <WorkflowStep label="Ready for QA" active={document.status === "indexed"} />
            </ol>
          </Panel>

          <Panel className="space-y-3">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-accent" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Pages</h2>
            </div>
            {pages.length === 0 ? (
              <p className="text-sm leading-6 text-slate-500">No page diagnostics are available yet.</p>
            ) : (
              <div className="space-y-2">
                {pages.map((page) => {
                  const isSelected = selectedPage?.page_number === page.page_number;
                  return (
                    <button
                      key={page.page_number}
                      type="button"
                      className={[
                        "w-full rounded-lg border p-3 text-left transition",
                        isSelected
                          ? "border-teal-400 bg-teal-50 shadow-sm shadow-teal-900/10"
                          : "border-line bg-white hover:border-teal-300 hover:bg-teal-50/50",
                      ].join(" ")}
                      onClick={() => {
                        setSelectedPageNumber(page.page_number);
                        setSelectedChunkId(null);
                        setActiveTab("evidence");
                      }}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink">Page {page.page_number}</span>
                        <span className="flex flex-wrap justify-end gap-1.5">
                          {page.needs_review ? <Badge tone="amber">Review needed</Badge> : null}
                          <Badge tone={pageTone(page)}>{formatTextSource(page.text_source)}</Badge>
                        </span>
                      </span>
                      <span className="mt-2 line-clamp-2 block text-xs leading-5 text-slate-500">{page.text_preview}</span>
                      <span className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>{formatCount(page.chunk_count, "chunk", "chunks")}</span>
                        <span>{page.character_count} chars</span>
                        <span>{formatProcessingStatus(page.processing_status)}</span>
                        {typeof page.ocr_confidence === "number" ? <span>{formatPercent(page.ocr_confidence)} OCR</span> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-ink">Suggested questions</h2>
            </div>
            {profile?.suggested_questions.length ? (
              <div className="flex flex-wrap gap-2">
                {profile.suggested_questions.slice(0, 5).map((question) => (
                  <Link
                    key={question}
                    href={`/search?documentId=${document.id}&query=${encodeURIComponent(question)}`}
                    className="inline-flex min-h-8 items-center rounded-md border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-teal-600 hover:text-teal-700"
                  >
                    {question}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-500">Suggested questions will appear after indexing.</p>
            )}
          </Panel>
        </aside>
      </div>
      {selectedSource ? <SourceViewer source={selectedSource} onClose={() => setSelectedSource(null)} /> : null}
    </div>
  );
}
