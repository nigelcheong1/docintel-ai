import { CalendarDays, FileText, Hash, Lightbulb, ListTree, Tags } from "lucide-react";

import type { DocumentFact, DocumentProfile, DocumentSection } from "@/lib/types";

function formatLabel(value: string) {
  const label = value.replace(/_/g, " ").toLowerCase();
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

function uniqueFacts(facts: DocumentFact[], limit: number) {
  const seen = new Set<string>();
  const items: DocumentFact[] = [];
  for (const fact of facts) {
    const key = `${fact.kind}:${fact.value.toLowerCase()}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    items.push(fact);
    if (items.length >= limit) {
      return items;
    }
  }
  return items;
}

function FactList({ title, icon: Icon, facts }: { title: string; icon: typeof CalendarDays; facts: DocumentFact[] }) {
  const items = uniqueFacts(facts, 4);
  if (items.length === 0) {
    return null;
  }
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {title}
      </div>
      <ul className="mt-2 flex flex-wrap gap-2">
        {items.map((fact) => (
          <li key={`${fact.kind}-${fact.value}`} className="rounded border border-line bg-white px-2 py-1 text-xs text-slate-700">
            {fact.value}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SectionList({ sections }: { sections: DocumentSection[] }) {
  if (sections.length === 0) {
    return null;
  }
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <ListTree className="h-3.5 w-3.5" aria-hidden="true" />
        Sections
      </div>
      <ul className="mt-2 flex flex-wrap gap-2">
        {sections.slice(0, 8).map((section) => (
          <li key={`${section.heading}-${section.page_number}`} className="rounded border border-line bg-white px-2 py-1 text-xs text-slate-700">
            {section.heading}
            <span className="ml-1 text-slate-400">p.{section.page_number}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DocumentProfilePanel({
  profile,
  isLoading = false,
  onSuggestionSelect,
}: {
  profile?: DocumentProfile | null;
  isLoading?: boolean;
  onSuggestionSelect?: (question: string) => void;
}) {
  if (isLoading) {
    return (
      <section className="mb-4 rounded border border-line bg-white p-4 text-sm text-slate-600">
        Loading document profile...
      </section>
    );
  }

  if (!profile) {
    return null;
  }

  return (
    <section className="mb-4 rounded border border-line bg-white p-4" aria-labelledby="document-profile-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded border border-accent/30 bg-accent/10 px-2 py-1 text-xs font-medium text-accent">
              <FileText className="h-3.5 w-3.5" aria-hidden="true" />
              {formatLabel(profile.document_type)}
            </span>
            <h2 id="document-profile-heading" className="break-words text-sm font-semibold">
              {profile.title || profile.filename}
            </h2>
          </div>
          {profile.overview ? <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-700">{profile.overview}</p> : null}
        </div>
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <SectionList sections={profile.sections} />
          <FactList title="Entities" icon={Tags} facts={profile.key_entities} />
        </div>
        <div className="space-y-4">
          <FactList title="Dates" icon={CalendarDays} facts={profile.key_dates} />
          <FactList title="Numbers" icon={Hash} facts={profile.key_numbers} />
        </div>
      </div>

      {profile.suggested_questions.length > 0 ? (
        <div className="mt-4 border-t border-line pt-4">
          <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />
            Suggested questions
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {profile.suggested_questions.slice(0, 5).map((question) =>
              onSuggestionSelect ? (
                <button
                  key={question}
                  type="button"
                  className="rounded border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:border-accent hover:text-accent"
                  onClick={() => onSuggestionSelect(question)}
                >
                  {question}
                </button>
              ) : (
                <span key={question} className="rounded border border-line px-2.5 py-1.5 text-xs text-slate-600">
                  {question}
                </span>
              ),
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
