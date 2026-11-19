import pdfplumber

MAX_PDF_PAGES = 200
# Real student leases often append required disclosures (lead-paint and radon pamphlets, ordinance
# summaries); a 48-page Urbana lease extracts to about 120,000 characters.
MAX_DOCUMENT_CHARS = 200_000
# pdfplumber's default (3) glues words together in PDFs that position each word without a space
# character ("holdharmlesstheLessor"); 1.5 restores the spaces and leaves normally spaced PDFs unchanged.
X_TOLERANCE = 1.5
# Word exports checkboxes as Wingdings glyphs in the Unicode private-use area (LibreOffice re-exports keep
# the code points under OpenSymbol); extracted as-is they are unreadable, so the model cannot tell
# "By the Bed" from "By the Unit".
CHECKBOX_FONTS = ("wingding", "opensymbol")
WINGDINGS_BOXES = {"": "[X]", "": "[X]", "": "[X]", "": "[ ]", "": "[ ]", "": "[ ]"}
UNICODE_BOXES = {"☐": "[ ]", "☑": "[X]", "☒": "[X]"}


class PDFLimitError(ValueError):
    """The PDF exceeds the prototype's page or extracted-text limits."""


def normalize_checkboxes(text: str, wingdings_glyphs: set[str] = frozenset()) -> str:
    """Replace checkbox glyphs with [X] / [ ]. Private-use glyphs are mapped only when they came from a
    Wingdings-compatible font, because other symbol fonts reuse the same code points for other characters."""
    for glyph, box in UNICODE_BOXES.items():
        text = text.replace(glyph, box)
    for glyph in wingdings_glyphs & WINGDINGS_BOXES.keys():
        text = text.replace(glyph, WINGDINGS_BOXES[glyph])
    return text


def page_text(page) -> str:
    text = page.extract_text(x_tolerance=X_TOLERANCE) or ""
    wingdings = {char["text"] for char in page.chars if any(font in char.get("fontname", "").lower() for font in CHECKBOX_FONTS)}
    return normalize_checkboxes(text, wingdings)


def extract_pages(file_path: str) -> list[str]:
    pages = []
    size = 0
    with pdfplumber.open(file_path) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise PDFLimitError(f"PDF 最多支持 {MAX_PDF_PAGES} 页，请拆分后上传")
        for page in pdf.pages:
            text = page_text(page)
            size += len(text) + (2 if pages else 0)
            if size > MAX_DOCUMENT_CHARS:
                raise PDFLimitError(f"提取文字超过 {MAX_DOCUMENT_CHARS} 字符，请拆分 PDF 后上传")
            pages.append(text)
    return pages


def extract_text(file_path: str) -> str:
    return "\n\n".join(extract_pages(file_path))
