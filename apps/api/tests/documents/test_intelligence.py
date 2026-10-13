import pytest

from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.intelligence import build_document_profile


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


def test_profile_detects_research_paper_sections_and_questions():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Human-to-Robot Action Recognition with Language Guidance",
                "Abstract",
                "We propose a multimodal transformer for human robot interaction.",
                "Introduction",
                "Human action recognition has advanced with vision-language models.",
                "Results",
                "The method improves TOP1 accuracy on Kinetics-400 and UCF-101.",
                "References",
            ]
        ),
        [
            ("ABSTRACT We propose a multimodal transformer for human robot interaction.", "ABSTRACT"),
            ("RESULTS The method improves TOP1 accuracy on Kinetics-400 and UCF-101.", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert profile.title == "Human-to-Robot Action Recognition with Language Guidance"
    assert [section.heading for section in profile.sections] == [
        "ABSTRACT",
        "INTRODUCTION",
        "RESULTS",
        "REFERENCES",
    ]
    assert any(fact.value == "Kinetics-400" for fact in profile.key_entities)
    assert "What is this document about?" in profile.suggested_questions
    assert "What results are reported?" in profile.suggested_questions


def test_profile_detects_invoice_amounts_and_dates():
    document = make_document(
        "invoice.pdf",
        "\n".join(
            [
                "Invoice INV-1001",
                "Bill To: Xiamen University Malaysia",
                "Issue Date: 2026-08-01",
                "Due Date: 2026-08-30",
                "Subtotal RM 1,200.00",
                "Tax RM 72.00",
                "Total Due RM 1,272.00",
            ]
        ),
        [
            ("Invoice INV-1001 Bill To: Xiamen University Malaysia", "INVOICE DETAILS"),
            ("Issue Date: 2026-08-01 Due Date: 2026-08-30 Total Due RM 1,272.00", "PAYMENT SUMMARY"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "invoice"
    assert any(fact.value == "2026-08-30" for fact in profile.key_dates)
    assert any(fact.value == "RM 1,272.00" for fact in profile.key_numbers)
    assert "What total amount is due?" in profile.suggested_questions


def test_profile_extracts_research_table_metrics_without_percent_symbols():
    document = make_document(
        "paper.pdf",
        "Abstract\nThe paper evaluates action recognition.\nResults\nTOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455",
        [
            ("ABSTRACT The paper evaluates action recognition.", "ABSTRACT"),
            ("RESULTS TOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert any(fact.value == "30.650" for fact in profile.key_numbers)


def test_research_profile_ignores_publisher_boilerplate_for_title_and_overview():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Contents lists available at ScienceDirect",
                "Journal of Manufacturing Systems",
                "journal homepage: www.elsevier.com/locate/jmansys",
                "Technical paper",
                "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception in human robot collaboration",
                "Duidi Wu a,b, Qianyou Zhao a,b, Junming Fan c",
                "School of Mechanical Engineering, Shanghai Jiao Tong University, Shanghai 200240, China",
                "A B S T R A C T",
                "Human-robot collaboration enhances efficiency by enabling robots to work alongside human operators.",
                "The proposed H2R Bridge transfers vision-language models to few-shot intention meta-perception.",
                "Keywords",
                "Human-robot collaboration",
                "Intent recognition",
                "Received 10 December 2024",
                "Accepted 20 March 2025",
            ]
        ),
        [
            (
                "Contents lists available at ScienceDirect Journal of Manufacturing Systems journal homepage: www.elsevier.com/locate/jmansys",
                None,
            ),
            (
                "A B S T R A C T Human-robot collaboration enhances efficiency by enabling robots to work alongside human operators. "
                "The proposed H2R Bridge transfers vision-language models to few-shot intention meta-perception.",
                "ABSTRACT",
            ),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert profile.title == (
        "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception in human robot collaboration"
    )
    assert profile.overview is not None
    assert profile.overview.startswith("Human-robot collaboration enhances efficiency")
    assert "ScienceDirect" not in profile.overview
    assert "Journal of Manufacturing Systems" not in profile.overview


def test_research_profile_reconstructs_split_paper_title():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Contents lists available at ScienceDirect",
                "Technical paper",
                "H2R Bridge: Transferring vision-language models to few-shot intention",
                "meta-perception in human robot collaboration",
                "Duidi Wu a,b, Qianyou Zhao a,b",
                "A B S T R A C T",
                "Human-robot collaboration enhances efficiency.",
            ]
        ),
        [
            (
                "ABSTRACT Human-robot collaboration enhances efficiency.",
                "ABSTRACT",
            )
        ],
    )

    profile = build_document_profile(document)

    assert profile.title == (
        "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception in human robot collaboration"
    )


def test_research_profile_keeps_industry_and_country_terms_in_legitimate_title():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Contents lists available at ScienceDirect",
                "A Framework for Human-Robot Collaboration in Industry 4.0 in China",
                "Duidi Wu a,b, Qianyou Zhao a,b",
                "Abstract",
                "This paper proposes a framework for industrial human-robot collaboration.",
                "References",
            ]
        ),
        [
            (
                "ABSTRACT This paper proposes a framework for industrial human-robot collaboration.",
                "ABSTRACT",
            ),
            ("REFERENCES Smith 2025.", "REFERENCES"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.title == "A Framework for Human-Robot Collaboration in Industry 4.0 in China"


def test_research_profile_filters_noisy_metadata_numbers_and_extracts_research_facts():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception",
                "Abstract",
                "This paper proposes H2R Bridge for few-shot human-robot intention recognition.",
                "Method",
                "The H2R Bridge uses a two-stream transformer and multimodal self-attention.",
                "Dataset",
                "Experiments use MECCANO, InHARD, HRI30, Kinetics-400, UCF-101, and HMDB-51.",
                "Results",
                "H2R Bridge achieves TOP1 91.10 and F1 89.58 on HRI30.",
                "Shanghai 200240 China Industry 4.0 Industry 5.0",
            ]
        ),
        [
            (
                "ABSTRACT This paper proposes H2R Bridge for few-shot human-robot intention recognition.",
                "ABSTRACT",
            ),
            (
                "METHOD The H2R Bridge uses a two-stream transformer and multimodal self-attention.",
                "METHOD",
            ),
            (
                "DATASET Experiments use MECCANO, InHARD, HRI30, Kinetics-400, UCF-101, and HMDB-51.",
                "DATASET",
            ),
            (
                "RESULTS H2R Bridge achieves TOP1 91.10 and F1 89.58 on HRI30.",
                "RESULTS",
            ),
        ],
    )

    profile = build_document_profile(document)
    fact_values = {fact.value for fact in profile.key_entities}
    number_values = {fact.value for fact in profile.key_numbers}

    assert {"MECCANO", "InHARD", "HRI30", "Kinetics-400", "UCF-101", "HMDB-51"}.issubset(fact_values)
    assert any(fact.label == "Method" and "two-stream transformer" in fact.value for fact in profile.key_entities)
    assert any(fact.label == "Contribution" and "proposes H2R Bridge" in fact.value for fact in profile.key_entities)
    assert "200240" not in number_values
    assert "4.0" not in number_values
    assert "5.0" not in number_values
    assert any(value.startswith("TOP1") or value == "91.10" for value in number_values)


def test_research_profile_uses_method_body_not_result_table_for_method_fact():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "H2R Bridge: Transferring vision-language models to few-shot intention meta-perception",
                "Abstract",
                "This paper proposes H2R Bridge for few-shot human-robot intention recognition.",
                "3. Multimodal learning framework",
                "The proposed framework extracts temporal tokens and uses a visual encoder for spatial-temporal attention.",
                "Method",
                "Method Pretrain TOP1(%) TOP5(%) TSN 41.06 75.20 I3D 82.06 98.63.",
                "Results",
                "Table 7 reports TOP1 91.10 and F1 89.58 on HRI30.",
            ]
        ),
        [
            (
                "ABSTRACT This paper proposes H2R Bridge for few-shot human-robot intention recognition.",
                "ABSTRACT",
            ),
            (
                "The proposed framework extracts temporal tokens and uses a visual encoder for spatial-temporal attention.",
                None,
            ),
            ("METHOD Method Pretrain TOP1(%) TOP5(%) TSN 41.06 75.20 I3D 82.06 98.63.", "METHOD"),
            ("RESULTS Table 7 reports TOP1 91.10 and F1 89.58 on HRI30.", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)
    method_facts = [fact.value for fact in profile.key_entities if fact.label == "Method"]

    assert any("visual encoder" in value for value in method_facts)
    assert all("Pretrain TOP1" not in value for value in method_facts)


def test_research_profile_does_not_list_method_table_header_as_method_section():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Abstract",
                "This paper evaluates human-robot collaboration.",
                "Method",
                "Method Pretrain TOP1(%) TOP5(%)",
                "TSN 41.06 75.20",
                "Results",
                "The proposed model achieves TOP1 91.10.",
            ]
        ),
        [
            ("ABSTRACT This paper evaluates human-robot collaboration.", "ABSTRACT"),
            ("METHOD Method Pretrain TOP1(%) TOP5(%) TSN 41.06 75.20.", "METHOD"),
            ("RESULTS The proposed model achieves TOP1 91.10.", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)

    assert not any(section.heading == "METHOD" and "TOP1" in section.text_preview for section in profile.sections)


def test_research_profile_filters_doi_and_section_numbers_from_metrics():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "H2R Bridge",
                "Abstract",
                "This paper evaluates human-robot collaboration.",
                "Results",
                "https://doi.org/10.1016/j.jmsy.2025.03.016",
                "4.2 Comparison with SOTA methods",
                "Table 7 reports TOP1 91.10 and F1 89.58 on HRI30.",
            ]
        ),
        [
            (
                "RESULTS https://doi.org/10.1016/j.jmsy.2025.03.016 4.2 Comparison with SOTA methods Table 7 reports TOP1 91.10 and F1 89.58 on HRI30.",
                "RESULTS",
            )
        ],
    )

    profile = build_document_profile(document)
    values = {fact.value for fact in profile.key_numbers}

    assert "10.1016" not in values
    assert "2025.03" not in values
    assert "4.2" not in values
    assert "TOP1 91.10" in values
    assert "F1 89.58" in values


def test_profile_merges_chunk_sections_with_numbered_page_headings():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Language Guided Human-to-Robot Action Recognition",
                "Abstract",
                "This paper studies human robot interaction.",
                "1. Introduction",
                "Human action recognition is important for robotics.",
                "2. Method",
                "The method fuses video and language features.",
            ]
        ),
        [
            ("ABSTRACT This paper studies human robot interaction.", "ABSTRACT"),
        ],
    )

    profile = build_document_profile(document)

    assert [section.heading for section in profile.sections] == ["ABSTRACT", "INTRODUCTION", "METHOD"]


def test_profile_detects_contract_parties_and_obligation_sections():
    document = make_document(
        "service-agreement.pdf",
        "\n".join(
            [
                "Service Agreement",
                "This agreement is between Acme Robotics Sdn Bhd and Beta University.",
                "Effective Date: January 1, 2026",
                "Obligations",
                "Acme Robotics shall provide maintenance support.",
                "Termination",
                "Either party may terminate with thirty days notice.",
            ]
        ),
        [
            ("This agreement is between Acme Robotics Sdn Bhd and Beta University.", "PARTIES"),
            ("Obligations Acme Robotics shall provide maintenance support.", "OBLIGATIONS"),
            ("Termination Either party may terminate with thirty days notice.", "TERMINATION"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "contract"
    assert any(section.heading == "OBLIGATIONS" for section in profile.sections)
    assert any(fact.value == "Acme Robotics Sdn Bhd" for fact in profile.key_entities)
    assert "Who are the parties involved?" in profile.suggested_questions


def test_profile_detects_reports_with_findings_recommendations_and_risks():
    document = make_document(
        "quarterly-report.pdf",
        "\n".join(
            [
                "Q3 Student Research Operations Report",
                "Executive Summary",
                "The report reviews lab usage and thesis milestones.",
                "Findings",
                "Students submitted 24 draft proposals.",
                "Recommendations",
                "Increase supervisor office hours before proposal week.",
                "Risks",
                "Delayed ethics approval may affect data collection.",
            ]
        ),
        [
            ("EXECUTIVE SUMMARY The report reviews lab usage and thesis milestones.", "EXECUTIVE SUMMARY"),
            ("FINDINGS Students submitted 24 draft proposals.", "FINDINGS"),
            ("RECOMMENDATIONS Increase supervisor office hours before proposal week.", "RECOMMENDATIONS"),
            ("RISKS Delayed ethics approval may affect data collection.", "RISKS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "report"
    assert "What recommendations are listed?" in profile.suggested_questions
    assert any(section.heading == "FINDINGS" for section in profile.sections)


def test_profile_detects_academic_project_report_without_legal_contract_false_positive():
    document = make_document(
        "DRL Final Report.pdf",
        "\n".join(
            [
                "XIAMEN UNIVERSITY MALAYSIA",
                "Course Code : AIT306 Course Name : Deep Reinforcement Learning",
                "Lecturer : Goh Sim Kuan Academic Session : 2026/04",
                "Assessment Title : Project Submission Due Date : 17th July 2026",
                "Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock",
                "Table of Contents",
                "1. Overview & Objective ......................................................... 1",
                "2. Design Approach .............................................................. 1",
                "3. Observation: the 16-Dimensional Feature Contract ............................. 2",
                "4. Development Pipeline ......................................................... 3",
                "Results & Verification",
                "The trained PPO tennis agent keeps rallies alive and corrects the residual side asymmetry.",
            ]
        ),
        [
            (
                "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
                "Lecturer : Goh Sim Kuan Academic Session : 2026/04 Assessment Title : Project Submission "
                "Prepared by : Student ID Student Name AIT2309628 Nigel Cheong Tze Hock",
                None,
            ),
            (
                "Table of Contents 1. Overview & Objective ......................................................... 1 "
                "2. Design Approach .............................................................. 1 "
                "3. Observation: the 16-Dimensional Feature Contract ............................. 2",
                None,
            ),
            (
                "OVERVIEW The project trains a deep reinforcement learning agent for tennis rally control in Unity ML-Agents.",
                "OVERVIEW",
            ),
            (
                "RESULTS The trained PPO tennis agent keeps rallies alive and corrects the residual side asymmetry.",
                "RESULTS",
            ),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "academic_report"
    assert profile.title == "DRL Final Report"
    assert "What is this project report about?" in profile.suggested_questions
    assert "Who are the parties involved?" not in profile.suggested_questions
    assert "What obligations are mentioned?" not in profile.suggested_questions
    assert any(fact.label == "Due date" and fact.value == "17th July 2026" for fact in profile.key_dates)
    assert not any(fact.value == "1" and "Table of Contents" in fact.source_text for fact in profile.key_numbers)
    assert any(fact.label == "Lecturer" and fact.value == "Goh Sim Kuan" for fact in profile.key_entities)
    assert any(fact.label == "Prepared by" and "Nigel Cheong Tze Hock" in fact.value for fact in profile.key_entities)


@pytest.mark.parametrize("heading,label", [("ABSTRACT", "Contribution"), ("METHOD", "Method"), ("RESULTS", "Result")])
@pytest.mark.parametrize(
    "fragment",
    [
        "Transformer TSN I3D LSTM 2021 \u2713 2022 \u2717 2023 \u2713 91.10 89.58.",
        "TOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455.",
        "TOP1(%) TOP5(%) TSN 41.06 75.20.",
        "TOP1(%) TOP5(%) Random 30.650 85.028.",
        "[12] Smith J, Brown L (2021) A transformer for visual action recognition, IEEE Robotics 12 44-51.",
        "Keywords: transformer; visual encoder; temporal attention; action recognition; multimodal fusion.",
        "The architecture is described in Fig.",
    ],
)
def test_research_profile_omits_fragmentary_prose_facts(heading, label, fragment):
    document = make_document(
        "paper.pdf",
        f"Abstract\nThis paper studies robot collaboration.\n{heading}\n{fragment}\nReferences",
        [(f"{heading} {fragment}", heading)],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert not any(fact.label == label for fact in profile.key_entities)


def test_research_profile_keeps_method_prose_beside_table_and_complete_figure_reference():
    method = "The visual encoder fuses video and language features as shown in Fig. 3."
    document = make_document(
        "paper.pdf",
        f"Abstract\nThis paper studies robot collaboration.\nMethod\n{method}\nReferences",
        [(f"METHOD {method}\nTOP1(%) TOP5(%) TSN 41.06 75.20", "METHOD")],
    )

    profile = build_document_profile(document)

    assert any(
        fact.label == "Method" and fact.value == method.rstrip(".")
        for fact in profile.key_entities
    )


def test_research_profile_preserves_multiplication_in_method_prose():
    method = "The visual encoder processes 32 \u00d7 32 image patches with a transformer model."
    document = make_document(
        "paper.pdf",
        f"Abstract\nThis paper studies robot collaboration.\nMethod\n{method}\nReferences",
        [(f"METHOD {method}", "METHOD")],
    )

    profile = build_document_profile(document)

    assert [fact.value for fact in profile.key_entities if fact.label == "Method"] == [method.rstrip(".")]
    assert "What methods are used?" in profile.suggested_questions


def test_research_profile_preserves_narrative_top1_top5_results():
    result = "The encoder achieves TOP1 91.10 and TOP5 98.63 on unseen videos."
    document = make_document(
        "paper.pdf",
        f"Abstract\nThis paper studies robot collaboration.\nResults\n{result}\nReferences",
        [(f"RESULTS {result}", "RESULTS")],
    )

    profile = build_document_profile(document)

    assert [fact.value for fact in profile.key_entities if fact.label == "Result"] == [result.rstrip(".")]


def test_research_profile_does_not_suggest_methods_from_terse_metric_table():
    table = "TOP1(%) TOP5(%) Random 30.650 85.028."
    document = make_document(
        "paper.pdf",
        f"Abstract\nThis paper studies robot collaboration.\nMethod\n{table}\nReferences",
        [(f"METHOD {table}", "METHOD")],
    )

    profile = build_document_profile(document)

    assert "What methods are used?" not in profile.suggested_questions


def test_research_profile_does_not_promote_keywords_after_abstract_to_contribution():
    contribution = "We propose a visual encoder for robot collaboration."
    document = make_document(
        "paper.pdf",
        f"Abstract\n{contribution}\nKeywords\nTransformer; visual attention; multimodal fusion\nReferences",
        [(f"ABSTRACT {contribution} Keywords: transformer; visual attention; multimodal fusion.", "ABSTRACT")],
    )

    profile = build_document_profile(document)

    assert [fact.value for fact in profile.key_entities if fact.label == "Contribution"] == [
        contribution.rstrip(".")
    ]


@pytest.mark.parametrize(
    "filename,page_text,document_type,overview_question",
    [
        ("paper.pdf", "Abstract\nThis paper discusses robot collaboration.\nReferences", "research_paper", "What is this document about?"),
        ("project.pdf", "Course Code: ENG101\nAssessment Title: Project Submission\nOverview\nThe project explores robot collaboration.", "academic_report", "What is this project report about?"),
        ("notes.txt", "Garden Notes\nThe garden has a shaded planting area.", "generic", "What is this document about?"),
    ],
)
def test_profile_suggests_only_overview_when_specialized_evidence_is_absent(
    filename, page_text, document_type, overview_question
):
    document = make_document(filename, page_text, [(page_text, None)])

    profile = build_document_profile(document)

    assert profile.document_type == document_type
    assert profile.overview
    assert profile.suggested_questions == [overview_question]


def test_research_questions_ignore_empty_headings_keywords_and_bibliography():
    document = make_document(
        "paper.pdf",
        "Abstract\nThis paper discusses robot collaboration.\nMethod\nResults\nDataset\nLimitations\nKeywords\nMNIST\nReferences\n[1] A study of COCO.",
        [
            ("ABSTRACT This paper discusses robot collaboration.", "ABSTRACT"),
            ("KEYWORDS MNIST", "KEYWORDS"),
            ("REFERENCES [1] A study of COCO.", "REFERENCES"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.suggested_questions == ["What is this document about?"]


def test_research_questions_use_meaningful_page_sections_without_chunks():
    document = make_document(
        "paper.pdf",
        "Abstract\nWe propose a visual encoder for robot collaboration.\nMethod\nThe encoder fuses video and language features.\nDataset\nWe evaluate on the RobotBench collection of annotated videos.\nResults\nThe encoder improves recognition accuracy over the baseline.\nLimitations\nThe encoder requires paired video and language inputs.\nReferences",
        [],
    )

    profile = build_document_profile(document)

    assert profile.suggested_questions == [
        "What is this document about?",
        "What methods are used?",
        "What datasets are mentioned?",
        "What results are reported?",
        "What limitations or future work are discussed?",
    ]


@pytest.mark.parametrize(
    "filename,page_text,document_type",
    [
        ("invoice.pdf", "Invoice INV-1001\nAn invoice has been requested for the repair.", "invoice"),
        ("agreement.pdf", "Agreement\nThis agreement describes a proposed collaboration.", "contract"),
        ("report.pdf", "Executive Summary\nThe report reviews laboratory usage.", "report"),
    ],
)
def test_profile_omits_unsupported_questions_for_existing_document_types(filename, page_text, document_type):
    document = make_document(filename, page_text, [(page_text, None)])

    profile = build_document_profile(document)

    assert profile.document_type == document_type
    assert profile.suggested_questions == ["What is this document about?"]
