import pdfplumber
import pytest

import parser


def pdf_with_stream(stream: str) -> bytes:
    """One-page PDF with a raw content stream, so tests control exact glyph positions."""
    content = stream.encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


# Words positioned with a 2.4pt gap and no space character, the way some lease generators write text.
TIGHT = "BT /F1 12 Tf 72 720 Td [(Lessee) -200 (shall) -200 (hold) -200 (harmless) -200 (the) -200 (Lessor.)] TJ ET"
# The same sentence with real space characters.
NORMAL = "BT /F1 12 Tf 72 720 Td (Lessee shall hold harmless the Lessor.) Tj ET"


def test_default_tolerance_reproduces_the_glued_words(tmp_path):
    path = tmp_path / "tight.pdf"
    path.write_bytes(pdf_with_stream(TIGHT))
    with pdfplumber.open(path) as pdf:
        assert "Lesseeshallholdharmless" in pdf.pages[0].extract_text().replace(" ", "")
        assert "hold harmless" not in pdf.pages[0].extract_text()


@pytest.mark.parametrize("stream", [TIGHT, NORMAL])
def test_extracted_words_keep_their_spaces(tmp_path, stream):
    path = tmp_path / "lease.pdf"
    path.write_bytes(pdf_with_stream(stream))
    assert parser.extract_text(str(path)) == "Lessee shall hold harmless the Lessor."


def test_wingdings_checkboxes_become_readable():
    text = " By the Bed  By the Unit"
    assert parser.normalize_checkboxes(text, {"", ""}) == "[X] By the Bed [ ] By the Unit"


def test_private_use_glyphs_from_other_fonts_are_left_alone():
    # Symbol fonts reuse the same code points (for example U+F06F for a Greek letter).
    assert parser.normalize_checkboxes(" value", set()) == " value"


def test_unicode_ballot_boxes_are_normalized():
    assert parser.normalize_checkboxes("☑ Renewal ☐ New ☒ Relet") == "[X] Renewal [ ] New [X] Relet"


@pytest.mark.parametrize("font, expected", [
    ("ABCDEF+Wingdings-Regular", "[X] By the Bed [ ] By the Unit"),
    ("DAAAAA+OpenSymbol", "[X] By the Bed [ ] By the Unit"),  # LibreOffice re-export of a Word lease
    ("Symbol", "\uf0fe By the Bed \uf06f By the Unit"),
])
def test_checkbox_mapping_depends_on_the_glyph_font(font, expected):
    from types import SimpleNamespace
    page = SimpleNamespace(
        extract_text=lambda x_tolerance: "\uf0fe By the Bed \uf06f By the Unit",
        chars=[{"text": "\uf0fe", "fontname": font}, {"text": "\uf06f", "fontname": font}, {"text": "B", "fontname": "Carlito"}],
    )
    assert parser.page_text(page) == expected
