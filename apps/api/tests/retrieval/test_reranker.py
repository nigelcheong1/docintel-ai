from app.retrieval.reranker import infer_query_intents, keyword_overlap_score, rerank_hits
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
