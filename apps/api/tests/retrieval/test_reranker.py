import pytest

from app.retrieval.reranker import (
    infer_query_intents,
    infer_section_intents,
    keyword_overlap_score,
    rerank_hits,
)
from app.retrieval.search import SearchHit


def make_hit(
    *,
    score: float,
    section_heading: str | None,
    text: str = "",
) -> SearchHit:
    return SearchHit(
        chunk_id="chunk",
        document_id="document",
        document_filename="resume.pdf",
        page_number=1,
        chunk_index=0,
        text=text,
        score=score,
        source_score=score,
        section_heading=section_heading,
    )


def test_infer_query_intents_normalizes_section_concepts():
    assert infer_query_intents("Show me skills, projects, and education") == {
        "education",
        "project",
        "skill",
    }


def test_infer_query_intents_understands_programming_language_and_tools_queries():
    assert infer_query_intents("What programming languages does this candidate know?") == {
        "programming_language",
        "skill",
    }
    assert infer_query_intents("Which tools and frameworks are listed?") == {
        "framework",
        "skill",
        "tool",
    }


def test_infer_query_intents_requires_unambiguous_phrases_for_work_and_language():
    assert infer_query_intents("How does invoice payment work?") == set()
    assert infer_query_intents("What language is this contract written in?") == set()
    assert infer_query_intents("Show the work history") == {"experience"}
    assert infer_query_intents("Which programming languages are listed?") == {
        "programming_language",
        "skill",
    }


def test_infer_section_intents_normalizes_resume_section_families():
    assert infer_section_intents("TOOLS & PLATFORMS") == {"skill", "tool"}
    assert infer_section_intents("FRAMEWORKS & LIBRARIES") == {"framework", "skill"}
    assert infer_section_intents("PROGRAMMING LANGUAGES") == {"programming_language", "skill"}
    assert infer_section_intents("KEY PROJECTS") == {"project"}
    assert infer_section_intents("EDUCATION") == {"education"}
    assert infer_section_intents("EXPERIENCE") == {"experience"}
    assert infer_section_intents("WORK EXPERIENCE") == {"experience"}


def test_keyword_overlap_score_measures_query_terms_present_in_text():
    assert keyword_overlap_score("data science", "Data engineering and SCIENCE") == 1.0
    assert keyword_overlap_score("data science", "Product management") == 0.0


def test_rerank_hits_prefers_projects_section_when_vector_scores_are_close():
    hits = [
        make_hit(score=0.91, section_heading="TOOLS & PLATFORMS", text="Python and Docker"),
        make_hit(score=0.90, section_heading="KEY PROJECTS", text="PROJECTS: skin lesion classification"),
    ]

    reranked = rerank_hits("projects", hits)

    assert [hit.section_heading for hit in reranked] == ["KEY PROJECTS", "TOOLS & PLATFORMS"]
    assert reranked[0].source_score == 0.90
    assert reranked[0].ranking_signals == {"keyword_overlap": 1.0, "section_intent": 1.0}
    assert reranked[0].score == pytest.approx(0.925)


def test_rerank_hits_prefers_matching_skill_and_education_sections():
    skill_hits = [
        make_hit(score=0.91, section_heading="WORK EXPERIENCE", text="Built APIs"),
        make_hit(score=0.90, section_heading="TECHNICAL SKILLS", text="SKILLS: Python and SQL"),
    ]
    education_hits = [
        make_hit(score=0.91, section_heading="CERTIFICATIONS", text="Cloud certificate"),
        make_hit(score=0.90, section_heading="EDUCATION", text="EDUCATION: Computer Science"),
    ]

    assert rerank_hits("skills", skill_hits)[0].section_heading == "TECHNICAL SKILLS"
    assert rerank_hits("education", education_hits)[0].section_heading == "EDUCATION"
