"""Rebuild the PDF and replay metadata from the existing synthetic English lease."""
import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'backend'))
from chunker import chunk_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=REPO / 'demo')
    args = parser.parse_args()
    text = (REPO / 'backend/eval/contracts/lease_en.txt').read_text(encoding='utf-8')
    assert text.isascii(), 'Update font handling before adding non-ASCII source text.'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pdf = args.output_dir / 'lease_en.pdf'
    ink = colors.HexColor('#18243B')
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=14, textColor=ink, spaceAfter=10,
                          allowWidows=0, allowOrphans=0)
    title = ParagraphStyle('title', parent=body, fontName='Helvetica-Bold', fontSize=20, leading=24, spaceAfter=12)
    notice = ParagraphStyle('notice', parent=body, fontSize=9, leading=12, textColor=colors.HexColor('#566171'), spaceAfter=18)
    blocks = [Paragraph('Synthetic Urbana residential lease', title),
              Paragraph('DEMO FIXTURE - not a signed contract or a recommended lease. This document reproduces the existing English evaluation text. It intentionally contains terms used for risk-analysis demonstrations.', notice)]
    for paragraph in text.strip().split('\n\n'):
        safe = escape(paragraph).replace('\n', '<br/>')
        match = re.match(r"^(\d+\. [A-Z][A-Z /&'-]*\.) ", paragraph)
        if match:
            label = escape(match.group(1))
            safe = '<b>' + label + '</b>' + safe[len(label):]
        blocks.append(Paragraph(safe, body))
    blocks.append(Spacer(1, 6))

    def footer(page_canvas, doc):
        page_canvas.saveState()
        page_canvas.setFont('Helvetica', 8)
        page_canvas.setFillColor(colors.HexColor('#566171'))
        page_canvas.drawString(48, 27, 'Synthetic evaluation fixture | Contract Risk Analyzer | Not legal advice')
        page_canvas.drawRightString(letter[0] - 48, 27, str(doc.page))
        page_canvas.restoreState()

    doc = SimpleDocTemplate(str(pdf), pagesize=letter, leftMargin=48, rightMargin=48,
                            topMargin=44, bottomMargin=48, title='Synthetic Urbana residential lease',
                            author='Contract Risk Analyzer demo', invariant=1)
    doc.build(blocks, onFirstPage=footer, onLaterPages=footer)
    chunks = chunk_text(text)
    questions = []
    for question, needle, answer in [
        ('押金多久退还？', 'Within 45 days after Tenant vacates', '预设示例：合同第5条写明，搬离后45日内返还押金，扣除合法扣款；损坏扣款须提供逐项说明。这里描述合同约定，不判断它是否满足法律要求。【合同原文1】'),
        ('会自动续租吗？', 'This Lease shall automatically renew', '预设示例：合同第12条写有自动续租一年、按房东确定的市场租金续租的约定，除非一方至少提前60日书面通知不续租。这里不判断该条款的法律效力。【合同原文1】'),
    ]:
        offset = text.index(needle)
        index = min(offset // 450, len(chunks) - 1)
        indices = list(range(index, min(index + 2, len(chunks))))
        questions.append({'question': question, 'answer': answer, 'sources': [{'chunk': i, 'text': chunks[i]} for i in indices]})
    fixture = {'mode': 'recorded analysis plus scripted Q&A; no model or embedding calls',
               'pdf_sha256': sha256(pdf.read_bytes()).hexdigest(), 'text_sha256': sha256(text.encode()).hexdigest(),
               'text_source': 'backend/eval/contracts/lease_en.txt',
               'analysis_source': 'backend/eval/results/analysis_20261028-161231.json',
               'preview': text[:200], 'n_chunks': len(chunks), 'questions': questions}
    (args.output_dir / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Created synthetic PDF and replay metadata in', args.output_dir)


if __name__ == '__main__':
    main()
