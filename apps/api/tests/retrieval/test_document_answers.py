from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.intelligence import build_document_profile
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query


def make_document(filename: str, page_text: str, chunks: list[tuple[str, str | None]]) -> Document:
    document = Document(
        id="doc-1",
        filename=filename,
        stored_filename=filename,
        mime_type="application/pdf",
        file_path=f"/tmp/{filename}",
        status=DocumentStatus.INDEXED,
    )
    page = Page(
        id="page-1",
        document_id=document.id,
        page_number=1,
        text=page_text,
        width=612,
        height=792,
    )
    document.pages = [page]
    document.chunks = [
        Chunk(
            id=f"chunk-{index}",
            document_id=document.id,
            page_id=page.id,
            page=page,
            chunk_index=index,
            text=text,
            token_estimate=len(text.split()),
            layout={"section_heading": heading} if heading else {},
        )
        for index, (text, heading) in enumerate(chunks)
    ]
    return document


def answer_for(query: str, document: Document):
    profile = build_document_profile(document)
    route = route_query(query, profile.document_type)
    return build_document_aware_answer(query, document, profile, route)


def test_builds_research_paper_overview_from_abstract():
    document = make_document(
        "paper.pdf",
        "Title\nAbstract\nThis paper proposes a language-guided transformer for human-robot action recognition.",
        [
            (
                "ABSTRACT This paper proposes a language-guided transformer for human-robot action recognition.",
                "ABSTRACT",
            ),
            ("REFERENCES Smith 2024.", "REFERENCES"),
        ],
    )

    result = answer_for("What is this document about?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.status == "answerable"
    assert result.query_intent == "overview"
    assert "language-guided transformer" in result.answer.summary
    assert result.answer.citations[0].section_heading == "ABSTRACT"


def test_academic_report_overview_strips_compound_overview_heading():
    document = make_document(
        "DRL Final Report.pdf",
        (
            "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
            "Assessment Title : Project Submission Prepared by : Student Name. "
            "1. Overview & Objective dPickleBall is a two-player Unity pickleball game."
        ),
        [
            (
                "1. Overview & Objective dPickleBall is a two-player Unity pickleball game in which each side's "
                "paddle is driven by a Python policy.",
                "OVERVIEW",
            ),
        ],
    )

    result = answer_for("What is this project report about?", document)

    assert result is not None
    assert result.answer is not None
    assert result.answer.summary.startswith("dPickleBall is a two-player Unity pickleball game")
    assert "& Objective" not in result.answer.summary


def test_academic_report_overview_skips_continuation_fragments():
    document = make_document(
        "DRL Final Report.pdf",
        (
            "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
            "Assessment Title : Project Submission Prepared by : Student Name. "
            "Overview & Objective dPickleBall is a two-player Unity pickleball game."
        ),
        [
            (
                "OVERVIEW Overview & Objective dPickleBall is a two-player Unity pickleball game in which each side's "
                "paddle is driven by a Python policy.",
                "OVERVIEW",
            ),
            (
                "OVERVIEW unlike the returns-based objective, does not saturate while the pool stays competitive. "
                "Resuming the fine-tuned model and training against the pool happens at the hardest level.",
                "OVERVIEW",
            ),
        ],
    )

    result = answer_for("What is this project report about?", document)

    assert result is not None
    assert result.answer is not None
    assert "dPickleBall is a two-player Unity pickleball game" in result.answer.summary
    assert "unlike the returns-based objective" not in result.answer.summary
    assert "Resuming the fine-tuned model" not in result.answer.summary


def test_research_overview_answer_cleans_abstract_and_ignores_boilerplate():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Contents lists available at ScienceDirect",
                "Journal of Manufacturing Systems",
                "Technical paper",
                "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception",
                "A B S T R A C T",
                "Human-robot collaboration enhances efficiency by enabling robots to work alongside human operators.",
                "The proposed H2R Bridge transfers vision-language models to few-shot intention meta-perception.",
            ]
        ),
        [
            (
                "Contents lists available at ScienceDirect Journal of Manufacturing Systems Technical paper H2R Bridge: "
                "Transferring vision-language models to few-shot intention meta-perception. A B S T R A C T "
                "Human-robot collaboration enhances efficiency by enabling robots to work alongside human operators. "
                "All rights are reserved, including those for text and data mining, AI training, and similar technologies.",
                "ABSTRACT",
            )
        ],
    )

    result = answer_for("What is this document about?", document)

    assert result is not None
    assert result.answer is not None
    assert "Human-robot collaboration enhances efficiency" in result.answer.summary
    assert "ScienceDirect" not in result.answer.summary
    assert "All rights are reserved" not in result.answer.summary
    assert "D. D." not in result.answer.summary


def test_research_overview_answer_uses_multiple_informative_abstract_sentences():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Title",
                "Abstract",
                "Human-robot collaboration enhances efficiency by enabling shared tasks.",
                "This paper introduces H2R Bridge for few-shot intention meta-perception.",
                "The framework transfers vision-language models to industrial HRC scenarios.",
            ]
        ),
        [
            (
                "ABSTRACT Human-robot collaboration enhances efficiency by enabling shared tasks. "
                "This paper introduces H2R Bridge for few-shot intention meta-perception. "
                "The framework transfers vision-language models to industrial HRC scenarios.",
                "ABSTRACT",
            ),
        ],
    )

    result = answer_for("What is this document about?", document)

    assert result is not None
    assert result.answer is not None
    assert "Human-robot collaboration enhances efficiency" in result.answer.summary
    assert "This paper introduces H2R Bridge" in result.answer.summary
    assert "vision-language models" in result.answer.summary


def test_research_methods_answer_prefers_method_section_over_front_matter():
    document = make_document(
        "paper.pdf",
        "Abstract\nExisting methods heavily rely on case-specific data.\nMethod\nThe H2R Bridge freezes the vision encoder and trains a lightweight temporal transformer.",
        [
            (
                "Contents lists available at ScienceDirect. Existing methods heavily rely on case-specific data and face challenges with unseen categories.",
                None,
            ),
            (
                "METHOD The H2R Bridge freezes the vision encoder and trains a lightweight temporal transformer for few-shot intention recognition.",
                "METHOD",
            ),
        ],
    )

    result = answer_for("What methods are used?", document)

    assert result is not None
    assert result.answer is not None
    assert "freezes the vision encoder" in result.answer.summary
    assert "ScienceDirect" not in result.answer.summary
    assert result.answer.citations[0].section_heading == "METHOD"


def test_research_methods_answer_avoids_method_named_result_tables():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper proposes H2R Bridge.\n3. Multimodal learning framework\nThe proposed framework extracts temporal tokens and uses a visual encoder for spatial-temporal attention.",
        [
            (
                "The proposed framework extracts temporal tokens and uses a visual encoder for spatial-temporal attention.",
                None,
            ),
            ("METHOD Method Pretrain TOP1(%) TOP5(%) TSN 41.06 75.20 I3D 82.06 98.63.", "METHOD"),
            ("RESULTS Table 7 reports TOP1 91.10 and F1 89.58 on HRI30.", "RESULTS"),
        ],
    )

    result = answer_for("What methods are used?", document)

    assert result is not None
    assert result.answer is not None
    assert "visual encoder" in result.answer.summary
    assert "Pretrain TOP1" not in result.answer.summary
    assert result.quality.confidence == "moderate"


def test_research_methods_answer_downgrades_term_only_intro_evidence():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper studies human-robot collaboration.\nIntroduction\nExisting methods rely on case-specific data.\nReferences",
        [
            ("ABSTRACT This paper studies human-robot collaboration.", "ABSTRACT"),
            ("INTRODUCTION Existing methods rely on case-specific data and do not generalize well.", "INTRODUCTION"),
            ("REFERENCES Smith 2025.", "REFERENCES"),
        ],
    )

    result = answer_for("What methods are used?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.confidence == "moderate"
    assert result.answer.citations[0].section_heading == "INTRODUCTION"


def test_research_results_answer_uses_results_section_not_intro_or_copyright():
    document = make_document(
        "paper.pdf",
        "Introduction\nAll rights are reserved. Existing studies report limited categories.\nResults\nTable 7 reports zero-shot TOP1 35.240 and two-shot TOP1 42.307 on HRI30.",
        [
            (
                "INTRODUCTION All rights are reserved, including text and data mining. Existing studies report limited categories.",
                "INTRODUCTION",
            ),
            (
                "RESULTS Table 7 reports zero-shot TOP1 35.240 and two-shot TOP1 42.307 on HRI30.",
                "RESULTS",
            ),
        ],
    )

    result = answer_for("What results are reported?", document)

    assert result is not None
    assert result.answer is not None
    assert "Table 7 reports zero-shot TOP1 35.240" in result.answer.summary
    assert "All rights are reserved" not in result.answer.summary
    assert result.answer.citations[0].section_heading == "RESULTS"


def test_research_results_answer_downgrades_term_only_intro_evidence():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper studies human-robot collaboration.\nIntroduction\nPrior work reports limited accuracy.\nReferences",
        [
            ("ABSTRACT This paper studies human-robot collaboration.", "ABSTRACT"),
            ("INTRODUCTION Prior work reports limited accuracy on industrial scenarios.", "INTRODUCTION"),
            ("REFERENCES Smith 2025.", "REFERENCES"),
        ],
    )

    result = answer_for("What results are reported?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.confidence == "moderate"
    assert result.answer.citations[0].section_heading == "INTRODUCTION"


def test_research_results_answer_prefers_result_claims_over_parameter_settings():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper proposes H2R Bridge.\nResults\nThe model improves performance.\nReferences",
        [
            (
                "RESULTS The number of transformer heads H and vision transformer layers are H = [12, 8, 8] and L = [12, 12, 24].",
                "RESULTS",
            ),
            (
                "RESULTS The proposed method consistently demonstrates superior performance across three HRI datasets, achieving the highest positive deviations.",
                "RESULTS",
            ),
            ("REFERENCES Smith 2025.", "REFERENCES"),
        ],
    )

    result = answer_for("What results are reported?", document)

    assert result is not None
    assert result.answer is not None
    assert "superior performance" in result.answer.summary
    assert "transformer heads" not in result.answer.summary


def test_academic_report_results_answer_skips_sentence_fragments():
    document = make_document(
        "DRL Final Report.pdf",
        (
            "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
            "Assessment Title : Project Submission Prepared by : Student Name. "
            "Results & Verification A replay gate validated the result."
        ),
        [
            (
                "RESULTS A replay gate validated the result simulated free flight matched real Unity ball flight "
                "to a mean error of 0.36-0.41 px over 30 frames, well inside the 2 px gate.",
                "RESULTS",
            ),
            (
                "RESULTS and at least 75% on each side, measured over 50 evaluation trials, where a successful "
                "trial means the agent makes five clean returns within an episode: level serve speed angle opponent "
                "domain rand. 1-3 slow to fast narrow to wide ball launcher no 4 mixed wide scripted returner no. "
                "The reward is intentionally lean and event-based.",
                "RESULTS",
            ),
            (
                "RESULTS produced the final agent, which retained balanced, near-ceiling performance across the curriculum.",
                "RESULTS",
            ),
        ],
    )

    result = answer_for("What results are reported?", document)

    assert result is not None
    assert result.answer is not None
    assert "A replay gate validated the result: simulated free flight" in result.answer.summary
    assert "The final agent retained balanced, near-ceiling performance" in result.answer.summary
    assert "and at least 75%" not in result.answer.summary
    assert "1-3 slow to fast" not in result.answer.summary
    assert "The reward is intentionally lean" not in result.answer.summary
    assert "produced the final agent" not in result.answer.summary


def test_research_limitations_answer_prefers_future_work_over_generic_challenges():
    document = make_document(
        "paper.pdf",
        "Related Work\nIndustrial action recognition remains a challenge.\nFuture Work\nFuture work will explore language-conditioned robotic policy learning and virtual-to-real mapping.",
        [
            (
                "RELATED WORK Industrial action recognition remains a challenge for general scenarios.",
                "RELATED WORK",
            ),
            (
                "FUTURE WORK Future work will explore language-conditioned robotic policy learning and virtual-to-real mapping.",
                "FUTURE WORK",
            ),
        ],
    )

    result = answer_for("What limitations or future work are discussed?", document)

    assert result is not None
    assert result.answer is not None
    assert "language-conditioned robotic policy learning" in result.answer.summary
    assert "general scenarios" not in result.answer.summary
    assert result.answer.citations[0].section_heading == "FUTURE WORK"


def test_research_future_work_answer_prefers_future_directions_inside_conclusion_chunk():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper proposes H2R Bridge.\nConclusion\nThis paper presents advancements in human-robot collaboration. To address these challenges, potential future research directions include language-conditioned robotic policy learning and virtual-to-real mapping.",
        [
            ("ABSTRACT This paper proposes H2R Bridge.", "ABSTRACT"),
            (
                "FUTURE WORK This paper presents advancements in human-robot collaboration. "
                "To address these challenges, potential future research directions include language-conditioned robotic policy learning and virtual-to-real mapping.",
                "FUTURE WORK",
            ),
        ],
    )

    result = answer_for("What limitations or future work are discussed?", document)

    assert result is not None
    assert result.answer is not None
    assert "future research directions include language-conditioned robotic policy learning" in result.answer.summary
    assert "This paper presents advancements" not in result.answer.summary


def test_research_future_work_answer_uses_following_unheaded_section_continuation():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper proposes H2R Bridge.\nConclusion\nThis paper presents advancements.\nTo address these challenges, potential future research directions include language-conditioned robotic policy learning.",
        [
            ("ABSTRACT This paper proposes H2R Bridge.", "ABSTRACT"),
            ("FUTURE WORK This paper presents advancements in human-robot collaboration.", "FUTURE WORK"),
            (
                "To address these challenges, potential future research directions include language-conditioned robotic policy learning and virtual-to-real mapping.",
                None,
            ),
        ],
    )

    result = answer_for("What limitations or future work are discussed?", document)

    assert result is not None
    assert result.answer is not None
    assert "future research directions include language-conditioned robotic policy learning" in result.answer.summary
    assert "This paper presents advancements" not in result.answer.summary


def test_academic_report_limitations_question_requires_explicit_future_work_evidence():
    document = make_document(
        "DRL Final Report.pdf",
        (
            "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
            "Lecturer : Goh Sim Kuan Assessment Title : Project Submission Prepared by : Student Name. "
            "Own Work Declaration I/We acknowledge the digital copy of the work may be retained for future comparisons. "
            "Overview & Objective dPickleBall is a two-player Unity pickleball game. "
            "Development Pipeline Phase 0: Measuring the environment Before writing any learning code, "
            "the environment was characterised empirically."
        ),
        [
            (
                "OWN WORK DECLARATION I/We acknowledge the digital copy of the work may be retained for future comparisons.",
                None,
            ),
            (
                "OVERVIEW Overview & Objective dPickleBall is a two-player Unity pickleball game.",
                "OVERVIEW",
            ),
            (
                "METHOD Development Pipeline Phase 0: Measuring the environment Before writing any learning code, "
                "the environment was characterised empirically.",
                "METHOD",
            ),
        ],
    )

    result = answer_for("What limitations or future work are discussed?", document)

    assert result is not None
    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"


def test_research_dataset_answer_lists_multiple_detected_benchmarks():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper evaluates H2R Bridge.\nDataset\nExperiments use MECCANO, InHARD, HRI30, Kinetics-400, UCF-101, and HMDB-51.",
        [
            ("ABSTRACT This paper evaluates H2R Bridge.", "ABSTRACT"),
            (
                "DATASET Experiments use MECCANO, InHARD, HRI30, Kinetics-400, UCF-101, and HMDB-51.",
                "DATASET",
            ),
        ],
    )

    result = answer_for("What datasets are mentioned?", document)

    assert result is not None
    assert result.answer is not None
    for dataset in ["MECCANO", "InHARD", "HRI30", "Kinetics-400", "UCF-101", "HMDB-51"]:
        assert dataset in result.answer.summary


def test_research_overview_fallback_downgrades_when_high_level_sections_are_missing():
    document = make_document(
        "paper.pdf",
        "Background\nThis paper studies industrial action recognition.\nMethod\nThe method uses a temporal encoder.\nReferences",
        [
            ("BACKGROUND This paper studies industrial action recognition.", "BACKGROUND"),
            ("METHOD The method uses a temporal encoder.", "METHOD"),
            ("REFERENCES Smith 2025.", "REFERENCES"),
        ],
    )

    result = answer_for("What is this document about?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.confidence == "moderate"
    assert result.answer.citations[0].section_heading == "BACKGROUND"


def test_builds_invoice_amount_answer_from_total_chunk():
    document = make_document(
        "invoice.pdf",
        "Invoice\nDue Date 2026-08-30\nTotal Due RM 1,272.00",
        [("PAYMENT SUMMARY Due Date 2026-08-30 Total Due RM 1,272.00", "PAYMENT SUMMARY")],
    )

    result = answer_for("What total amount is due?", document)

    assert result is not None
    assert result.answer is not None
    assert "RM 1,272.00" in result.answer.summary
    assert result.quality.confidence == "strong"


def test_builds_resume_skills_answer_from_full_skills_section():
    document = make_document(
        "candidate-resume.pdf",
        "Resume\nTechnical Skills\nPython, SQL, PyTorch, TensorFlow\nProjects\nTraffic dashboard",
        [
            ("TECHNICAL SKILLS Python, SQL, PyTorch, TensorFlow.", "TECHNICAL SKILLS"),
            ("PROJECTS Traffic dashboard using SQL.", "PROJECTS"),
        ],
    )

    result = answer_for("What technical skills are mentioned?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.status == "answerable"
    assert result.quality.confidence == "strong"
    assert "Python, SQL, PyTorch, TensorFlow" in result.answer.summary
    assert "Traffic dashboard" not in result.answer.summary


def test_builds_resume_projects_answer_without_losing_later_project_names():
    document = make_document(
        "candidate-resume.pdf",
        "Resume\nProjects\nSkin Lesion Classification and Traffic Accident Prediction are listed.",
        [
            (
                "PROJECTS Skin Lesion Classification and Traffic Accident Prediction are listed as applied ML projects.",
                "PROJECTS",
            ),
            ("TECHNICAL SKILLS Python and PyTorch.", "TECHNICAL SKILLS"),
        ],
    )

    result = answer_for("What projects are listed in this document?", document)

    assert result is not None
    assert result.answer is not None
    assert "Skin Lesion Classification" in result.answer.summary
    assert "Traffic Accident Prediction" in result.answer.summary
    assert "Python and PyTorch" not in result.answer.summary


def test_amount_answer_prioritizes_total_due_and_cites_only_present_values():
    document = make_document(
        "invoice.pdf",
        "\n".join(
            [
                "Invoice",
                "Subtotal RM 1,200.00",
                "Tax RM 72.00",
                "Total Due RM 1,272.00",
            ]
        ),
        [("PAYMENT SUMMARY Total Due RM 1,272.00", "PAYMENT SUMMARY")],
    )

    result = answer_for("What total amount is due?", document)

    assert result is not None
    assert result.answer is not None
    assert "Total due: RM 1,272.00" in result.answer.summary
    assert "RM 1,200.00" not in result.answer.summary
    assert "RM 72.00" not in result.answer.summary
    assert len(result.answer.citations) == 1


def test_date_answer_prioritizes_due_date_over_issue_date():
    document = make_document(
        "invoice.pdf",
        "Invoice\nIssue Date: 2026-08-01\nDue Date: 2026-08-30",
        [("PAYMENT SUMMARY Issue Date: 2026-08-01 Due Date: 2026-08-30", "PAYMENT SUMMARY")],
    )

    result = answer_for("When is payment due?", document)

    assert result is not None
    assert result.answer is not None
    assert "Due date: 2026-08-30" in result.answer.summary
    assert "Issue date: 2026-08-01" not in result.answer.summary


def test_fact_answer_does_not_fallback_to_uncited_opening_chunks():
    document = make_document(
        "invoice.pdf",
        "Invoice\nTotal Due RM 1,272.00",
        [("This opening chunk does not contain the invoice amount.", None)],
    )

    result = answer_for("What total amount is due?", document)

    assert result is not None
    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"


def test_builds_research_metric_answer_from_table_numbers():
    document = make_document(
        "paper.pdf",
        "Abstract\nThe paper evaluates action recognition.\nResults\nTOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455",
        [
            ("ABSTRACT The paper evaluates action recognition.", "ABSTRACT"),
            ("RESULTS TOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455", "RESULTS"),
        ],
    )

    result = answer_for("What amounts or totals are mentioned?", document)

    assert result is not None
    assert result.answer is not None
    assert "30.650" in result.answer.summary


def test_research_paper_rejects_invoice_total_due_question():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper studies video action recognition.\nResults\nTOP1 89.266 TOP5 99.011.",
        [
            ("ABSTRACT This paper studies video action recognition.", "ABSTRACT"),
            ("RESULTS TOP1 89.266 TOP5 99.011.", "RESULTS"),
        ],
    )

    result = answer_for("What total amount is due?", document)

    assert result is not None
    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert "invoice" in result.quality.reason.lower()


def test_builds_report_recommendation_answer():
    document = make_document(
        "quarterly-report.pdf",
        "Executive Summary\nThe report reviews lab usage.\nRecommendations\nIncrease supervisor office hours.",
        [
            ("EXECUTIVE SUMMARY The report reviews lab usage.", "EXECUTIVE SUMMARY"),
            ("RECOMMENDATIONS Increase supervisor office hours.", "RECOMMENDATIONS"),
        ],
    )

    result = answer_for("What recommendations are listed?", document)

    assert result is not None
    assert result.answer is not None
    assert "Increase supervisor office hours" in result.answer.summary


def test_builds_contract_parties_answer():
    document = make_document(
        "agreement.pdf",
        "Service Agreement\nThis agreement is between Acme Robotics Sdn Bhd and Beta University.",
        [("This agreement is between Acme Robotics Sdn Bhd and Beta University.", "PARTIES")],
    )

    result = answer_for("Who are the parties involved?", document)

    assert result is not None
    assert result.answer is not None
    assert "Acme Robotics Sdn Bhd" in result.answer.summary
    assert "Beta University" in result.answer.summary


def test_abstains_with_type_aware_reason_for_contract_question_on_research_paper():
    document = make_document(
        "paper.pdf",
        "Title\nAbstract\nThis paper studies video action recognition.",
        [("ABSTRACT This paper studies video action recognition.", "ABSTRACT")],
    )

    result = answer_for("Who are the parties involved?", document)

    assert result is not None
    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert "research paper" in result.quality.reason.lower()
    assert "What methods are used?" in result.quality.suggested_questions


def test_academic_report_answers_methods_and_results_despite_feature_contract_phrase():
    document = make_document(
        "DRL Final Report.pdf",
        "\n".join(
            [
                "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning",
                "Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock",
                "Observation: the 16-Dimensional Feature Contract",
                "Design Approach",
                "The project uses Unity ML-Agents with a PPO trainer and a shaped reward function.",
                "Results & Verification",
                "The trained tennis agent keeps rallies alive and reduces the residual side asymmetry.",
            ]
        ),
        [
            (
                "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
                "Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock",
                None,
            ),
            (
                "METHOD Design Approach The project uses Unity ML-Agents with a PPO trainer and a shaped reward function.",
                "METHOD",
            ),
            (
                "RESULTS Results & Verification The trained tennis agent keeps rallies alive and reduces the residual side asymmetry.",
                "RESULTS",
            ),
        ],
    )
    profile = build_document_profile(document)

    methods = build_document_aware_answer("What methods were used?", document, profile, route_query("What methods were used?", profile.document_type))
    results = build_document_aware_answer("What results are reported?", document, profile, route_query("What results are reported?", profile.document_type))
    amounts = build_document_aware_answer("What total amount is due?", document, profile, route_query("What total amount is due?", profile.document_type))

    assert profile.document_type == "academic_report"
    assert methods is not None and methods.answer is not None
    assert "PPO trainer" in methods.answer.summary
    assert results is not None and results.answer is not None
    assert "keeps rallies alive" in results.answer.summary
    assert amounts is not None and amounts.answer is None
    assert amounts.quality.status == "insufficient_evidence"
    assert "academic report" in amounts.quality.reason.lower()


def test_academic_report_parties_query_returns_contributors_not_contract_entities():
    document = make_document(
        "DRL Final Report.pdf",
        "\n".join(
            [
                "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning",
                "Lecturer : Goh Sim Kuan",
                "Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock AIT2309970 Sean Ooi",
                "Observation: the 16-Dimensional Feature Contract",
                "Results & Verification The final policy keeps rallies alive.",
            ]
        ),
        [
            (
                "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
                "Lecturer : Goh Sim Kuan Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock AIT2309970 Sean Ooi",
                None,
            ),
            ("RESULTS Results & Verification The final policy keeps rallies alive.", "RESULTS"),
        ],
    )
    profile = build_document_profile(document)

    result = build_document_aware_answer(
        "Who are the parties involved?",
        document,
        profile,
        route_query("Who are the parties involved?", profile.document_type),
    )

    assert profile.document_type == "academic_report"
    assert result is not None and result.answer is not None
    assert "Prepared by: Student ID Student Name AIT2309628 Nigel Cheong Tze Hock AIT2309970 Sean Ooi" in result.answer.summary
    assert "Lecturer: Goh Sim Kuan" in result.answer.summary
    assert "Deep Reinforcement Learning Lecturer" not in result.answer.summary
