"""Report generation (PDF / Excel)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import DATA_DIR

REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_stock_pdf(title: str, analysis: dict) -> str:
    fname = f"stock_analysis_{analysis.get('symbol', 'NA')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = REPORTS_DIR / fname
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Disclaimer", fontSize=8, textColor=colors.grey))
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>{analysis.get('company_name')}</b> ({analysis.get('symbol')})", styles["Heading2"]))
    story.append(Paragraph(f"Latest Price: {analysis.get('latest_price')} | Change: {analysis.get('change_pct')}%", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    pred = analysis.get("prediction") or {}
    story.append(Paragraph("AI Probability Report", styles["Heading2"]))
    story.append(
        Paragraph(
            f"Bullish: {pred.get('bullish_probability')}% | Bearish: {pred.get('bearish_probability')}% | "
            f"Direction: {pred.get('expected_direction')} | Confidence: {pred.get('confidence')} | Risk: {pred.get('risk')}",
            styles["Normal"],
        )
    )
    story.append(Paragraph(pred.get("disclaimer", ""), styles["Disclaimer"]))
    story.append(Spacer(1, 0.15 * inch))

    trend = analysis.get("trend") or {}
    story.append(Paragraph(f"Trend: {trend.get('trend')} (score {trend.get('score')})", styles["Normal"]))

    vol = analysis.get("volume") or {}
    story.append(
        Paragraph(
            f"Volume Spike: {vol.get('volume_spike')} | Buying Pressure: {vol.get('buying_pressure')} | "
            f"Selling Pressure: {vol.get('selling_pressure')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    patterns = analysis.get("chart_patterns") or []
    if patterns:
        story.append(Paragraph("Chart Patterns", styles["Heading3"]))
        data = [["Pattern", "Signal", "Strength"]] + [
            [p["pattern_name"], p["signal"], str(p.get("strength"))] for p in patterns[:10]
        ]
        t = Table(data, colWidths=[2.5 * inch, 1.2 * inch, 1 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(t)

    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "Disclaimer: This report provides statistical analysis and historical pattern matching only. "
            "It does not guarantee future prices or profits and is not financial advice.",
            styles["Disclaimer"],
        )
    )
    doc.build(story)
    return str(path)


def generate_excel_report(title: str, rows: list[dict], filename_prefix: str = "report") -> str:
    fname = f"{filename_prefix}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = REPORTS_DIR / fname
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append([title])
    ws.append([])
    if not rows:
        ws.append(["No data"])
    else:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    wb.save(path)
    return str(path)


def generate_portfolio_pdf(title: str, portfolio: dict) -> str:
    fname = f"portfolio_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = REPORTS_DIR / fname
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Total Investment: {portfolio.get('total_investment')}", styles["Normal"]),
        Paragraph(f"Total Value: {portfolio.get('total_value')}", styles["Normal"]),
        Paragraph(f"P&L: {portfolio.get('total_pnl')} ({portfolio.get('total_return_pct')}%)", styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]
    holdings = portfolio.get("holdings") or []
    if holdings:
        data = [["Symbol", "Qty", "Avg", "Price", "P&L%"]]
        for h in holdings:
            sym = h.get("stock", {}).get("symbol") if isinstance(h.get("stock"), dict) else h.get("stock_id")
            data.append(
                [
                    str(sym),
                    str(h.get("quantity")),
                    str(h.get("avg_buy_price")),
                    str(h.get("current_price")),
                    str(h.get("pnl_pct")),
                ]
            )
        t = Table(data, colWidths=[1.4 * inch, 0.8 * inch, 1 * inch, 1 * inch, 1 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ]
            )
        )
        story.append(t)
    doc.build(story)
    return str(path)
