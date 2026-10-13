"""Rebuild fictional, privacy-safe PDF examples. Requires reportlab."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "documents"
TEAL = colors.HexColor("#0f766e")
INK = colors.HexColor("#17212b")
LINE = colors.HexColor("#d5dee3")
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle("DemoTitle", fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=INK, spaceAfter=12))
STYLES.add(ParagraphStyle("DemoSection", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=TEAL, spaceBefore=17, spaceAfter=8))
STYLES.add(ParagraphStyle("DemoBody", fontName="Helvetica", fontSize=10, leading=16, textColor=INK, spaceAfter=8))
STYLES.add(ParagraphStyle("DemoSmall", fontName="Helvetica", fontSize=8, leading=12, textColor=TEAL, spaceAfter=9))


def paragraph(text, style="DemoBody"):
    return Paragraph(text, STYLES[style])


def footer(canvas, document):
    canvas.setStrokeColor(LINE)
    canvas.line(20 * mm, 19 * mm, 190 * mm, 19 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK)
    canvas.drawString(20 * mm, 13 * mm, "FICTIONAL SAMPLE | No real people, transactions, or obligations")
    canvas.drawRightString(190 * mm, 13 * mm, str(document.page))


def write_pdf(name, title, content):
    DESTINATION.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(DESTINATION / name), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm,
        bottomMargin=27 * mm, title=title, author="DocIntel AI demo",
        subject="Original fictional example, CC0-1.0")
    document.build([paragraph("DOCINTEL AI / SHAREABLE EXAMPLES", "DemoSmall"),
        paragraph(title, "DemoTitle"), *content], onFirstPage=footer, onLaterPages=footer)


def invoice():
    cells = [["Description", "Quantity", "Unit price", "Line total"],
        ["Document indexing service", "2", "USD 150.00", "USD 300.00"],
        ["Evidence review workshop", "1", "USD 200.00", "USD 200.00"]]
    table = Table(cells, colWidths=[89 * mm, 19 * mm, 29 * mm, 33 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE), ("ALIGN", (1, 1), (-1, -1), "RIGHT")]))
    write_pdf("sample-invoice.pdf", "Invoice", [
        paragraph("Invoice number: DEMO-INV-1042. Invoice date: 05 October 2026."),
        paragraph("Supplier: Northstar Analytics Demo Ltd. Bill to: Harbor Research Demo Co."),
        paragraph("Services", "DemoSection"), table, Spacer(1, 14 * mm),
        paragraph("Subtotal: USD 500.00. Tax: USD 50.00. Total amount due: USD 550.00."),
        paragraph("Payment terms", "DemoSection"),
        paragraph("Payment is due on 04 November 2026. Payment terms are net 30 days."),
        paragraph("This fictional invoice does not provide bank account details or a payment link.")])


def contract():
    write_pdf("sample-contract.pdf", "Services Agreement", [
        paragraph("Parties", "DemoSection"),
        paragraph("The parties are Northstar Analytics Demo Ltd (the supplier) and Harbor Research Demo Co (the client)."),
        paragraph("The effective date is 01 October 2026. The initial term ends on 31 December 2026."),
        paragraph("Obligations", "DemoSection"),
        paragraph("The supplier shall deliver a document indexing prototype and an evidence review workshop. The client shall provide approved, non-confidential sample documents."),
        paragraph("Payment", "DemoSection"),
        paragraph("The fixed service fee is USD 500.00 excluding tax. The client shall pay within 30 days of receiving an invoice."),
        paragraph("Confidentiality", "DemoSection"),
        paragraph("Neither party may disclose confidential information received from the other party without written consent. This duty continues for 12 months after termination."),
        paragraph("Termination", "DemoSection"),
        paragraph("Either party may terminate the agreement with 14 days of written notice. Completed work remains payable."),
        paragraph("Fictional demonstration only. This is not legal advice or a binding agreement.", "DemoSmall")])


def resume():
    write_pdf("sample-resume.pdf", "Jamie Rivera", [
        paragraph("FICTIONAL CANDIDATE / SOFTWARE ENGINEER", "DemoSmall"),
        paragraph("Contact: demo@example.com. Portfolio: https://example.com. No real personal data is used."),
        paragraph("Professional Summary", "DemoSection"),
        paragraph("Software engineer focused on document processing, retrieval systems, and reliable full-stack applications."),
        paragraph("Technical Skills", "DemoSection"),
        paragraph("Python, TypeScript, FastAPI, React, PostgreSQL, Docker, and automated testing."),
        paragraph("Experience", "DemoSection"),
        paragraph("Demo Software Studio: Software Engineer, January 2024 to September 2026. Built document APIs and maintained automated regression tests."),
        paragraph("Projects", "DemoSection"),
        paragraph("ArchiveLens: a searchable document workspace with page citations, OCR status, and evaluation reports. Community Scheduler: a TypeScript scheduling application."),
        paragraph("Education", "DemoSection"),
        paragraph("Bachelor of Computer Science, Example University, 2023."),
        paragraph("This resume is an original fictional example, not a modified or scraped real resume.", "DemoSmall")])


def receipt():
    write_pdf("sample-receipt-source.pdf", "Harbor Demo Cafe", [
        paragraph("RECEIPT / FICTIONAL TRANSACTION", "DemoSmall"),
        paragraph("Receipt number: DEMO-R-007. Receipt date: 06 October 2026."),
        paragraph("Items", "DemoSection"),
        paragraph("Coffee: USD 4.00. Sandwich: USD 6.00."),
        paragraph("Total paid: USD 10.00. Payment method: cash."),
        paragraph("No customer name, account number, or card details are recorded.")])


if __name__ == "__main__":
    invoice()
    contract()
    resume()
    receipt()
    print("Created four original fictional PDF examples in demo/documents.")
