# Synthetic test data for LedgerAI

Use these files to test upload, reconcile, GST/TDS, and compliance flows.

## OCR (PDF / image uploads)

Scanned PDFs and invoice photos use **Gemini Vision OCR** (`app/extraction/ocr.py`).

Set before running locally or on Render:

```bash
export GEMINI_API_KEY=your_key_here
```

Extraction paths:

| File type | Method |
|---|---|
| `.json` | Direct parse |
| Text-layer `.pdf` | Fast PDF text parse (`pdf_text`) |
| Scanned `.pdf` | Gemini OCR fallback (`gemini_ocr`) |
| `.png`, `.jpg`, `.jpeg`, `.webp` | Gemini OCR (`gemini_ocr`) |

Preview without saving:

```bash
curl -X POST -F "file=@tests/fixtures/synthetic_invoice_sales_scan.png" \
  http://127.0.0.1:8000/api/invoices/ocr
```

Generate scan-style PNG:

```bash
python tests/fixtures/generate_sample_pdfs.py
```

## Files

| File | Upload as |
|---|---|
| `synthetic_invoices.json` | Invoices (JSON) |
| `synthetic_invoice_sales.pdf` | Single sales invoice (PDF) |
| `synthetic_invoice_purchase.pdf` | Single purchase invoice (PDF) |
| `synthetic_transactions.csv` | Bank statement (CSV) |

## What this dataset exercises

### Reconcile / match
| Invoice | Expected match behavior |
|---|---|
| S-101 Sharma Electronics ₹25,000 | **Auto match** — exact amount + name in bank |
| S-102 Patel Traders ₹12,000 | **Auto match** — exact amount + name |
| S-103 Walk-in ₹3,500 | **Auto match** — exact amount |
| S-104 Bright Office ₹8,500 | **Review** — bank shows ₹8,400 (slightly off) |
| S-105 Unmatched Client ₹15,000 | **No match** — no corresponding bank credit |

### GST
- **S-101, S-104, S-103** — intrastate Maharashtra (CGST+SGST)
- **S-102, S-105** — interstate (IGST)
- **P-201** — eligible ITC (valid vendor GSTIN)
- **P-202** — ITC blocked (missing vendor GSTIN) → Action Center flag

### TDS
- Rent ₹55,000 → **194I** (PAN missing → higher rate flag)
- Contractor ₹82,000 → **194C**
- CA fees ₹45,000 → **194J**
- TDS challan ₹8,500 → detected as deposit

### Categorize
- Zomato / Swiggy → Food
- Netflix → Uncategorized debit
- AWS → Software & Tools

## Quick test

```bash
# Upload via API
curl -X POST -F "file=@tests/fixtures/synthetic_invoices.json" http://127.0.0.1:8000/api/invoices/upload
curl -X POST -F "file=@tests/fixtures/synthetic_transactions.csv" http://127.0.0.1:8000/api/transactions/upload

# Or use Upload screen in the UI, then set period to 2026-01
```

## Reset demo data

Click **Reload demo data** in the sidebar, or:

```bash
curl -X POST http://127.0.0.1:8000/api/seed
```

Note: seed loads the original `sample_*` fixtures. To test synthetic data, upload the files above instead.
