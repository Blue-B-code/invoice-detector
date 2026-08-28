# 📄 Invoice Duplicate Detector — WhatsApp Business

Detects duplicate invoices submitted over the **WhatsApp Business API**.
Built with **FastAPI**, **SQLAlchemy** and **pdfplumber**.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](#)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-teal)](#)

---

## Overview

This service receives invoice PDFs sent through WhatsApp Business, extracts the invoice data, computes a SHA-256 hash of the file, and rejects any document that has already been processed — preventing the same invoice from being used more than once.

## Problem

Paper-based or manual invoice workflows are easy to abuse: a single invoice can be resubmitted multiple times, generating duplicate payments. Detecting duplicates reliably across WhatsApp submissions requires combining:

- file-level fingerprinting (so even a renamed file is caught),
- business-data extraction (invoice number, amount, date),
- and database-level integrity (unique constraints).

## Solution

A small, layered FastAPI service that turns WhatsApp media into a duplicate-safe invoice record:

1. WhatsApp user sends a PDF to the business number.
2. The WhatsApp Business API calls the service's `POST /webhook`.
3. The service downloads the media, computes a **SHA-256 hash**, and extracts `invoice_id`, `amount` and `date` with pdfplumber.
4. If the invoice or hash already exists, the message is answered as **duplicate**; otherwise it is stored as **valid**.

## Key features

- **WhatsApp webhook** with Meta verification (GET challenge) and message handling (POST).
- **Duplicate detection** via `UNIQUE` constraints on both `invoice_id` and `pdf_hash` — safe under concurrent requests.
- **PDF parsing** supporting several invoice layouts (French and English formats).
- **Multi-stage Dockerfile** (builder + runtime) and a **docker-compose** stack with PostgreSQL 16.
- **19 unit tests** covering PDF hashing, parsing, repository constraints and webhook routes.
- **Config via environment variables** (`.env.example` provided).

## Architecture

```
invoice-detector/
├── app/
│   ├── main.py                 # FastAPI entry point, lifespan, CORS, routers
│   ├── config.py               # Environment-driven settings (pydantic-settings)
│   ├── database.py             # SQLAlchemy engine & session
│   ├── schemas.py              # Pydantic validation schemas
│   ├── models/
│   │   └── invoice.py          # SQLAlchemy Invoice model
│   ├── repositories/
│   │   └── invoice_repository.py  # Data access layer
│   ├── services/
│   │   └── invoice_service.py  # Business orchestration
│   ├── routes/
│   │   ├── webhook.py          # GET/POST /webhook
│   │   └── health.py           # /health + /invoices
│   └── utils/
│       ├── pdf_utils.py        # SHA-256 hash + PDF data extraction
│       └── whatsapp_client.py  # WhatsApp Business API client
├── app/tests/test_invoice_system.py  # 19 unit tests (pytest)
├── scripts/test_webhook.sh     # Manual curl test script
├── examples/webhook_payload_example.json
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # API + PostgreSQL 16
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Workflow

```
WhatsApp User
     │  1. sends an invoice PDF
     ▼
WhatsApp Business API
     │  2. POST /webhook
     ▼
Invoice Detector API
     ├─ 3. download the PDF (WhatsApp Media API)
     ├─ 4. compute SHA-256 hash
     ├─ 5. extract invoice_id, amount, date
     ├─ 6. check for duplicates (UNIQUE constraints)
     │
     ├─ ✅ new invoice  → stored + "Facture valide" answer
     └─ ❌ duplicate    → "Facture déjà utilisée" answer
```

## Tech stack

- **Python 3.12**, **FastAPI**, **SQLAlchemy**, **Pydantic**
- **pdfplumber** for PDF text extraction
- **WhatsApp Business API** (Meta Graph API v18)
- **PostgreSQL 16** (SQLite for local/dev)
- **pytest** for tests · **Docker / docker-compose**

## Testing

```bash
pip install -r requirements.txt
pytest -v
```

19 tests cover PDF hashing (determinism, uniqueness), invoice parsing (full text, missing fields), repository behaviour (duplicate `invoice_id`, duplicate hash) and webhook routes (verification, invalid token, non-document payloads, PDF payload).

## Docker / deployment

```bash
# Start API + PostgreSQL
docker-compose up --build

# Background
docker-compose up -d --build

# Stop
docker-compose down
```

### Exposing the webhook locally

```bash
ngrok http 8000
```

Copy the generated HTTPS URL into the **Meta for Developers** dashboard as the webhook URL.

## Installation

### Prerequisites

- Python 3.11+
- pip

```bash
git clone https://github.com/Blue-B-code/invoice-detector.git
cd invoice-detector

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # then edit with your values
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000 · Swagger docs: http://localhost:8000/docs

### Environment variables

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `development` / `production` | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./invoices.db` |
| `WHATSAPP_API_URL` | WhatsApp Business API base URL | `https://graph.facebook.com/v18.0` |
| `WHATSAPP_PHONE_NUMBER_ID` | Business phone number ID | *(required in production)* |
| `WHATSAPP_ACCESS_TOKEN` | Meta access token | *(required in production)* |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token | `invoice_detector_verify_token` |
| `MAX_PDF_SIZE_MB` | Max PDF size in MB | `10` |
| `LOG_TO_FILE` | Write logs to `logs/app.log` | `false` |

## Usage

### Verify the webhook

```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=invoice_detector_verify_token&hub.challenge=test123"
```

### Simulate an invoice submission

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d @examples/webhook_payload_example.json
```

### List stored invoices

```bash
curl http://localhost:8000/invoices
```

## Supported PDF formats

**Invoice number:** `Facture N° : INV-2024-001`, `Invoice #: 12345`, `N° facture : FAC-001`
**Amount:** `Total : 1 250,00`, `Montant TTC : 500.00`, `Amount Due: 1,234.56`
**Date:** `15/01/2024`, `2024-01-15`, `15 janvier 2024`, `15 January 2024`

## Future improvements

- **Async queue** — Celery/ARQ + Redis for background processing
- **OCR** — Tesseract for scanned PDFs
- **Multi-tenant** — support multiple companies
- **Dashboard** — web UI to browse invoices
- **Alerts** — email/Slack notification on duplicate detection

## License

MIT
