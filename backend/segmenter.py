"""Split contract text into clause-sized segments that remember their pages and position.

The per-item pipeline sends each checklist item only the few segments that mention it, so a segment must be large
enough to carry a whole clause (with its "unless" tail) and small enough that a fee schedule does not arrive as one
block. Boundaries come from headings ("1.4 SECURITY DEPOSIT", "12. Lessee shall", "ARTICLE IV", "第十二条", an
all-caps title line); long stretches without headings (fee tables, handbooks) are cut at line ends.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PAGE_SEPARATOR = "\n\n"  # parser.extract_text joins pages with this
MAX_SEGMENT_CHARS = 1200
MIN_SEGMENT_CHARS = 80
# Fee schedules are short lines; a group of about 20 rows keeps one fee type together without one card per row.
MAX_SEGMENT_LINES = 22
# Pamphlets and question-and-answer summaries repeat statutes; they are not lease terms.
INFO_MARKERS = re.compile(r"protect your family|\bepa\b|radon guide|iema|what (?:happens|if|is|are|can|does)\b[^?]{0,120}\?", re.I)
SIGNED_FORM = re.compile(r"lessor's disclosure|tenant's acknowledgment|lessee's acknowledgment|by signing below", re.I)
# Ordinance summaries speak of "the landlord" and "the tenant" in lower case; leases capitalize their defined terms
# ("Landlord", "Lessee"). Case-sensitive on purpose: on a real lease these hit only the attached ordinance summary.
STATUTE_MARKERS = re.compile(r"\bthe (?:landlord|tenant) (?:shall|may|must|is|has)\b|\b[Tt]his [Oo]rdinance\b")


def is_informational_page(text: str) -> bool:
    """Two or more pamphlet or ordinance-summary markers, and not a disclosure form that the tenant signs."""
    if SIGNED_FORM.search(text):
        return False
    return len(INFO_MARKERS.findall(text)) + len(STATUTE_MARKERS.findall(text)) >= 2

ALL_CAPS_LINE = re.compile(r"^[ \t]*[A-Z][A-Z0-9&,/'’()\- ]{2,60}[A-Z)]:?[ \t]*$")
CASE_SENSITIVE_HEADING = re.compile(
    r"^[ \t]*(?:\d{1,3}(?:\.\d{1,3}){1,3}\.?[ \t]+\S|\d{1,3}[.)][ \t]+[A-Z(\"“]|(?:[Ss]ection|SECTION|[Aa]rticle|ARTICLE)[ \t]+[\dIVXLC]+\b"
    r"|第[一二三四五六七八九十百零〇\d]+[条章节])"
)


@dataclass
class Segment:
    id: str
    start: int
    end: int
    pages: list[int]
    text: str
    heading: str | None = None
    # The enclosing numbered or all-caps heading ("2.5 PARKING" for its sub-item "1. Lessor will not be responsible").
    section: str | None = None
    # On a pamphlet or ordinance-summary page: retrieved only when nothing in the lease itself matches.
    informational: bool = False
    lower: str = field(default="", repr=False)

    def as_dict(self) -> dict:
        return {"id": self.id, "start": self.start, "end": self.end, "pages": self.pages, "heading": self.heading,
                "section": self.section, "informational": self.informational, "text": self.text}


# Headings that open a section, as opposed to "1." sub-items inside one.
SECTION_HEADING = re.compile(r"^(?:\d{1,3}\.\d{1,3}\b|(?:[Ss]ection|SECTION|[Aa]rticle|ARTICLE)\s|第.+?[条章节]|[A-Z][A-Z0-9&,/'’()\- ]{2,60}[A-Z)]:?$)")


def page_starts(pages: list[str]) -> list[int]:
    starts, offset = [], 0
    for index, page in enumerate(pages):
        starts.append(offset)
        offset += len(page) + (len(PAGE_SEPARATOR) if index < len(pages) - 1 else 0)
    return starts


def is_heading(line: str) -> bool:
    if "$" in line or len(line.strip()) < 3:
        return False
    if CASE_SENSITIVE_HEADING.match(line):
        return True
    words = re.findall(r"[A-Za-z]{2,}", line)
    return bool(ALL_CAPS_LINE.match(line)) and len(words) >= 1 and sum(len(w) for w in words) >= 4


def line_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for match in re.finditer(r"\n", text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return spans


def split_long(text: str, start: int, end: int, limit: int, max_lines: int = MAX_SEGMENT_LINES) -> list[tuple[int, int]]:
    """Cut [start, end) at line ends, preferring lines that close a sentence, so no piece exceeds limit or max_lines."""
    pieces, piece_start, best_cut, lines = [], start, None, 0
    for line_start, line_end in line_spans(text[start:end]):
        line_start += start
        line_end += start
        lines += 1
        if (line_end - piece_start > limit or lines > max_lines) and best_cut is not None and best_cut > piece_start:
            pieces.append((piece_start, best_cut))
            piece_start = best_cut
            best_cut = None
            lines = text.count("\n", piece_start, line_end) + 1
        cut = line_end + 1 if line_end < end else line_end
        if best_cut is None or text[line_start:line_end].rstrip().endswith((".", ";", ":", "。", "；")):
            best_cut = cut
        elif line_end - piece_start <= limit * 0.6:
            best_cut = cut
    if piece_start < end:
        pieces.append((piece_start, end))
    # A single line longer than the limit (rare: text without line breaks) is cut at sentence ends.
    result = []
    for a, b in pieces:
        while b - a > limit * 1.5:
            window = text[a:a + limit]
            stops = [m.end() for m in re.finditer(r"[.;。；](?=\s)", window)]
            cut = a + (stops[-1] if stops and stops[-1] > limit // 3 else limit)
            result.append((a, cut))
            a = cut
        result.append((a, b))
    return result


def segment_pages(pages: list[str], *, max_chars: int = MAX_SEGMENT_CHARS, min_chars: int = MIN_SEGMENT_CHARS) -> list[Segment]:
    """Segments over PAGE_SEPARATOR.join(pages); start/end index that joined text, pages are 1-based."""
    text = PAGE_SEPARATOR.join(pages)
    starts = page_starts(pages)
    boundaries = {0}
    for line_start, line_end in line_spans(text):
        if is_heading(text[line_start:line_end]):
            boundaries.add(line_start)
    informational_pages = {i + 1 for i, page in enumerate(pages) if is_informational_page(page)}
    # A pamphlet page never shares a segment with a lease page.
    for number in range(2, len(pages) + 1):
        if (number in informational_pages) != (number - 1 in informational_pages):
            boundaries.add(starts[number - 1])
    cuts = sorted(boundaries) + [len(text)]
    raw = [(a, b) for a, b in zip(cuts, cuts[1:]) if text[a:b].strip()]
    # A heading alone ("ARTICLE 3 - RENT") belongs to the clause after it; other fragments join the clause before.
    merged: list[list[int]] = []
    carry = None
    for index, (a, b) in enumerate(raw):
        if carry is not None:
            a, carry = carry, None
        piece = text[a:b].strip()
        if len(piece) < min_chars and is_heading(piece.split("\n", 1)[0]) and index < len(raw) - 1:
            carry = a
            continue
        if merged and len(piece) < min_chars:
            merged[-1][1] = b
            continue
        merged.append([a, b])
    spans = []
    for a, b in merged:
        too_long = b - a > max_chars or text.count("\n", a, b) >= MAX_SEGMENT_LINES
        spans.extend(split_long(text, a, b, max_chars) if too_long else [(a, b)])
    segments = []
    section = None
    for a, b in spans:
        # Trim whitespace but keep offsets exact.
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a >= b:
            continue
        on_pages = [i + 1 for i, s in enumerate(starts) if s < b and s + len(pages[i]) > a] or [1]
        first_line = text[a:b].split("\n", 1)[0].strip()
        segment_text = text[a:b]
        heading = first_line[:120] if is_heading(first_line) else None
        if heading and SECTION_HEADING.match(heading):
            section = heading
        segments.append(Segment(id=f"s{len(segments) + 1}", start=a, end=b, pages=on_pages, text=segment_text,
                                heading=heading, section=section if section != heading else None,
                                informational=bool(on_pages) and set(on_pages) <= informational_pages, lower=segment_text.lower()))
    return segments


def segment_text(text: str, **kwargs) -> list[Segment]:
    """For text whose page breaks are unknown (documents uploaded before pages were stored): pages are left empty."""
    segments = segment_pages([text], **kwargs)
    for segment in segments:
        segment.pages = []
    return segments
