import pdfplumber

MAX_PDF_PAGES = 200
MAX_DOCUMENT_CHARS = 100_000


class PDFLimitError(ValueError):
    """The PDF exceeds the prototype's page or extracted-text limits."""


def extract_text(file_path: str) -> str:
    pages = []
    size = 0
    with pdfplumber.open(file_path) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise PDFLimitError(f"PDF 最多支持 {MAX_PDF_PAGES} 页，请拆分后上传")
        for page in pdf.pages:
            text = page.extract_text() or ""
            size += len(text) + (2 if pages else 0)
            if size > MAX_DOCUMENT_CHARS:
                raise PDFLimitError(f"提取文字超过 {MAX_DOCUMENT_CHARS} 字符，请拆分 PDF 后上传")
            pages.append(text)
    return "\n\n".join(pages)
