import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentProfilePanel } from "@/components/document-profile-panel";
import type { DocumentProfile } from "@/lib/types";

const profile: DocumentProfile = {
  document_id: "doc-1",
  filename: "paper.pdf",
  document_type: "research_paper",
  title: "Language Guided Human-to-Robot Action Recognition",
  overview: "ABSTRACT This paper studies human robot interaction with vision-language models.",
  sections: [
    {
      heading: "ABSTRACT",
      page_number: 1,
      text_preview: "ABSTRACT This paper studies human robot interaction.",
      intents: ["overview"],
    },
    {
      heading: "RESULTS",
      page_number: 6,
      text_preview: "RESULTS Accuracy improves on Kinetics-400.",
      intents: ["result"],
    },
  ],
  key_dates: [{ kind: "date", label: "Date", value: "2026", page_number: 1, source_text: "Published in 2026." }],
  key_numbers: [
    { kind: "percentage", label: "Percentage", value: "92.5%", page_number: 6, source_text: "Accuracy 92.5%." },
  ],
  key_entities: [
    { kind: "dataset", label: "Dataset", value: "Kinetics-400", page_number: 6, source_text: "Kinetics-400." },
  ],
  suggested_questions: ["What is this document about?", "What methods are used?"],
};

describe("DocumentProfilePanel", () => {
  it("renders document type, overview, facts, sections, and suggested questions", () => {
    const handleSuggestionSelect = vi.fn();

    render(<DocumentProfilePanel profile={profile} onSuggestionSelect={handleSuggestionSelect} />);

    expect(screen.getByText("Research paper")).toBeInTheDocument();
    expect(screen.getByText("Language Guided Human-to-Robot Action Recognition")).toBeInTheDocument();
    expect(screen.getByText(/vision-language models/)).toBeInTheDocument();
    expect(screen.getByText("Kinetics-400")).toBeInTheDocument();
    expect(screen.getByText("92.5%")).toBeInTheDocument();
    expect(screen.getByText("ABSTRACT")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "What methods are used?" }));

    expect(handleSuggestionSelect).toHaveBeenCalledWith("What methods are used?");
  });

  it("renders a loading state while a selected profile is being fetched", () => {
    render(<DocumentProfilePanel isLoading />);

    expect(screen.getByText("Loading document profile...")).toBeInTheDocument();
  });
});
