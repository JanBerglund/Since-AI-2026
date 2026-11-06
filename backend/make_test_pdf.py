from pathlib import Path


def make_demo_pdf(output: Path) -> None:
    content = b"BT /F1 16 Tf 50 100 Td (Demo PDF) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    startxref = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n"
        + b"<< /Root 1 0 R /Size " + str(len(objects) + 1).encode() + b" >>\n"
        + b"startxref\n"
        + str(startxref).encode()
        + b"\n%%EOF"
    )
    pdf += trailer

    output.write_bytes(pdf)
    print(f"created {output} ({len(pdf)} bytes)")


if __name__ == "__main__":
    make_demo_pdf(Path(__file__).resolve().parent / "test_upload.pdf")
