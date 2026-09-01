from io import BytesIO

from docx import Document


def build_docx(
    *,
    paragraphs: tuple[str, ...] = (),
    sections: tuple[tuple[int, str, str], ...] = (),
    title: str | None = None,
    author: str | None = None,
) -> bytes:
    document = Document()
    if sections:
        for level, heading, body in sections:
            document.add_heading(heading, level=level)
            if body:
                document.add_paragraph(body)
    else:
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
    if title:
        document.core_properties.title = title
    if author:
        document.core_properties.author = author
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
