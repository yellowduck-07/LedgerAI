"""Generate synthetic PNG invoice image for OCR testing."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from pypdf import PdfReader

OUTPUT_DIR = Path(__file__).resolve().parent


def write_invoice_pdf(path: Path, lines: list[str]) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in lines:
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def pdf_to_png(pdf_path: Path, png_path: Path) -> None:
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), dpi=200)
        images[0].save(png_path, "PNG")
        return
    except Exception:
        pass

    _render_simple_png(png_path)


def _render_simple_png(png_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    lines = [
        "TAX INVOICE",
        "Invoice Type: Sales",
        "Invoice No: S-101",
        "Date: 2026-01-03",
        "Customer: Sharma Electronics",
        "GSTIN: 27AABCS1429B1ZV",
        "Place of Supply: Maharashtra",
        "HSN/SAC: 8517",
        "Taxable Amount: 25000.00",
        "GST Rate: 18%",
    ]
    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 48
    img.save(png_path)


def main() -> None:
    sales_pdf = OUTPUT_DIR / "synthetic_invoice_sales.pdf"
    if not sales_pdf.exists():
        write_invoice_pdf(
            sales_pdf,
            [
                "TAX INVOICE",
                "Invoice Type: Sales",
                "Invoice No: S-101",
                "Date: 2026-01-03",
                "Customer: Sharma Electronics",
                "GSTIN: 27AABCS1429B1ZV",
                "Place of Supply: Maharashtra",
                "HSN/SAC: 8517",
                "Taxable Amount: 25000.00",
                "GST Rate: 18%",
            ],
        )

    pdf_to_png(sales_pdf, OUTPUT_DIR / "synthetic_invoice_sales_scan.png")
    print(f"Generated OCR test assets in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
