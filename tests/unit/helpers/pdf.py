def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_text_pdf(pages: list[str]) -> bytes:
    if not pages:
        pages = [""]
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(len(pages)))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(pages):
        content_id = 5 + 2 * index
        stream = f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET"
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects.append(
            f"<< /Length {len(stream.encode('latin-1'))} >>\n"
            f"stream\n{stream}\nendstream"
        )

    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    position = len(header)
    for index, obj in enumerate(objects, start=1):
        chunk = f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        offsets.append(position)
        body += chunk
        position += len(chunk)

    xref_lines = ["xref", f"0 {len(objects) + 1}", "0000000000 65535 f "]
    xref_lines.extend(f"{offset:010d} 00000 n " for offset in offsets[1:])
    xref = ("\n".join(xref_lines) + "\n").encode("latin-1")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{position}\n%%EOF\n"
    ).encode("latin-1")
    return header + body + xref + trailer
