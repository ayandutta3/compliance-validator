# AI-Driven Audit & Compliance Validator

A lightweight, single-file FastAPI backend that uses **Neo4j** (graph database) for compliance rule storage & historical audit persistence, and **OpenAI GPT-4o-mini** (structured outputs) to produce deterministic, schema-validated compliance audit reports. It includes a rich, dark-themed Streamlit UI featuring historical analytics trends and audit reload capabilities.

---

## Architecture Overview

```
┌─────────────────┐     POST /api/v1/audit      ┌─────────────────────────────────┐
│  Client / UI    │ ──────────────────────────► │         FastAPI (main.py)        │
│  (Streamlit)    │ ◄────────────────────────── │                                 │
└─────────────────┘       AuditReport JSON       │  1. Read uploaded document      │
        │                                       │  2. Fetch rules from Neo4j      │
        │                                       │  3. Call OpenAI structured API  │
        ▼ GET /api/v1/audits                    │  4. Save audit details to DB    │
┌──────────────────────────────┐                │  5. Return validated JSON       │
│  Audit History & Analytics   │                └─────────────────────────────────┘
│  - Compliance Score Trends   │                                 │
│  - Framework Distributions   │ ◄───────────────────────────────┘
│  - Historical Reports Loader │     Persist Audit & Findings
└──────────────────────────────┘
                                                ┌─────────────────────────────────┐
                                                │            Neo4j DB             │
                                                │  - Frameworks & Rules Graph     │
                                                │  - Audit Logs & Findings nodes  │
                                                └─────────────────────────────────┘
                                                                 │ fallback if offline
                                                                 ▼
                                                           Simulated Rule Set
                                                           (built-in strings)
```

**Data Flow:**
`Document Upload` → `Neo4j Rule Retrieval` → `OpenAI Structured Audit` → `Database Save` → `JSON Report & History Dashboard`

---

## Project Structure

```
compliance-validator/
├── main.py                          ← FastAPI app (Pydantic models, DB logic, LLM, endpoints)
├── app.py                           ← Streamlit UI frontend (Tabs for Run Audit & History Dashboard)
├── ingest_rules.py                  ← CLI utility: seed Neo4j from CSV (supports UTF-8 encoding)
├── synthetic_compliance_rules.csv   ← Source-of-truth compliance rules (10 rules per framework, 40 total)
├── sample_requests_responses.txt    ← Sample API request/response pairs
├── requirements.txt                 ← Python dependencies
├── .env                             ← Local environment variables (API secrets & Neo4j password)
├── .gitignore                       ← Ignored Python caches, virtual environments, .env, and OS metadata
├── sample_documents/                ← Directory containing 12 upload-ready test documents (3 per framework)
│   ├── sec_vertex_bank_disclosure.txt
│   ├── sec_apex_compliance_report.txt
│   ├── sec_nexus_financial_audit.txt
│   ├── hipaa_healthplus_security_policy.txt
│   ├── hipaa_carenet_privacy_practices.txt
│   ├── hipaa_medicloud_data_handling.txt
│   ├── gdpr_acme_privacy_policy.txt
│   ├── gdpr_globex_privacy_statement.txt
│   ├── gdpr_novatech_consent_policy.txt
│   ├── esg_greenpath_sustainability_report.txt
│   ├── esg_ecocorp_annual_disclosure.txt
│   └── esg_cleanenergy_governance_policy.txt
└── README.md                        ← This file
```

---

## Quick Start

### 1. Create & Activate a Virtual Environment

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory and configure the following variables:

| Variable          | Description                                  | Default         |
|------------------|----------------------------------------------|-----------------|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`)              | **Required**    |
| `LLM_MODEL`      | OpenAI model to use                         | `gpt-4o-mini`   |
| `NEO4J_URI`      | Neo4j Bolt connection URI                   | `bolt://localhost:7687` |
| `NEO4J_USER`     | Neo4j username                              | `neo4j`         |
| `NEO4J_PASSWORD` | Neo4j password                              | **Required**    |
| `API_BASE_URL`   | Base URL the Streamlit UI calls             | `http://localhost:8000` |

> **Note:** If Neo4j is offline or unreachable, the backend automatically falls back to a simulated rule set so that document audits remain fully operational.

### 4. Seed Neo4j with compliance rules (40 rules total)

Run the bundled **`ingest_rules.py`** utility to seed the Neo4j database from `synthetic_compliance_rules.csv` (uses `PYTHONIOENCODING=utf-8` on Windows to handle console unicode symbols):

```bash
# Windows
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe ingest_rules.py

# macOS / Linux
PYTHONIOENCODING=utf-8 python ingest_rules.py
```

Expected output:
```
============================================================
  Compliance Rules — Neo4j Ingestion Utility
============================================================
[INFO]  Loaded 40 rule(s) from: synthetic_compliance_rules.csv
[INFO]  Connecting to Neo4j at bolt://localhost:7687 …
  [  1/40] ✔  Merged Rule 'SEC-2026-01' → Framework 'SEC-2026'
  ...
  [ 40/40] ✔  Merged Rule 'ESG-SOC-10'  → Framework 'ESG-CORP'

────────────────────────────────────────────────────────────
[DONE]  Ingestion complete — 40 succeeded, 0 failed.
────────────────────────────────────────────────────────────
```

---

## API Reference

### `GET /health`
Returns service status and the active LLM model.

**Response:**
```json
{
  "status": "online",
  "llm_model": "gpt-4o-mini",
  "service": "AI-Driven Audit & Compliance Validator"
}
```

---

### `POST /api/v1/audit`
Audits an uploaded document and persists the results in Neo4j.

**Request (multipart/form-data):**
- `file`: The plain-text file to audit.
- `framework_id`: The compliance framework ID (`SEC-2026`, `HIPAA-INS`, `GDPR-EU-2025`, `ESG-CORP`).

**Response (`AuditReport` schema):**
```json
{
  "framework_id": "GDPR-EU-2025",
  "overall_compliance_score": 100.0,
  "total_violations_found": 0,
  "findings": [
    {
      "rule_id": "GDPR-2025-01",
      "rule_title": "Right to Erasure",
      "status": "COMPLIANT",
      "confidence_score": 0.95,
      "evidence": "Upon verification, all personal data will be permanently purged within 30 days.",
      "regulatory_foundation": "Article 17 GDPR",
      "gap_analysis": ""
    }
  ],
  "audit_id": "0d22263f-e2ba-46af-8ea2-6fd690b337d3",
  "file_name": "gdpr_acme_privacy_policy.txt",
  "timestamp": 1781382821
}
```

---

### `GET /api/v1/audits`
Retrieves a list of all historically saved audit reports from Neo4j, sorted chronologically.

**Response:**
```json
[
  {
    "audit_id": "0d22263f-e2ba-46af-8ea2-6fd690b337d3",
    "timestamp": 1781382821,
    "file_name": "gdpr_acme_privacy_policy.txt",
    "framework_id": "GDPR-EU-2025",
    "framework_name": "GDPR-EU-2025",
    "overall_score": 100.0,
    "total_violations": 0
  }
]
```

---

### `GET /api/v1/audits/{audit_id}`
Retrieves the complete audit report details and rule findings for the given `audit_id`.

**Response:** Returns a full `AuditReport` JSON object identical in schema to `POST /api/v1/audit`.

---

## Running the Application

You need to run both the FastAPI backend (as a Uvicorn server) and the Streamlit UI frontend in separate terminals.

### 1. Start the Backend API (Uvicorn Server)

The FastAPI backend runs on a high-performance **Uvicorn ASGI server**. You can start it in one of two ways:

* **Option A: Run programmatically via Python** (Runs the built-in entrypoint in `main.py`):
  ```bash
  python main.py
  ```

* **Option B: Run directly via Uvicorn CLI** (Launches the server with live reload):
  ```bash
  uvicorn main:app --reload --port 8000
  ```
  *(If the `uvicorn` command is not directly available in your system path, use: `python -m uvicorn main:app --reload --port 8000`)*

### 2. Start the Streamlit UI Frontend

Open a second terminal, activate the virtual environment, and run:
  ```bash
  streamlit run app.py
  ```


### Dashboard Tabs

1. **🚀 Run Audit**
   - Upload new `.txt` / `.md` files.
   - Select compliance frameworks from a safe confirmation summary panel.
   - Display overall score with a custom color-coded SVG arc gauge.
   - Inspect status-filtered, interactive audit finding cards with evidence quotes and gap analysis.
   - Export report directly as a JSON file.

2. **📊 Audit History & Trends**
   - **System Statistics**: Displays aggregate metadata metrics across all audits (Total Audits, Average Score, Total Violations).
   - **Trend Charting**: Renders a line chart of compliance scores over time and a bar chart of framework audit counts.
   - **Historical Explorer**: Select and reload any past audit report. The UI retrieves the data and renders the complete report view (score gauge, metrics, cards) exactly like a fresh execution.
   - **Audits Log**: View a sorted interactive dataframe table of all past audits.

---

## Ingestion Script Reference (`ingest_rules.py`)

Seeds Neo4j with the graph structure:
```
(:Framework {id, name}) -[:HAS_RULE]-> (:Rule {id, title, text})
```

### Supported Frameworks (from CSV)

| Framework ID   | Framework Name                        | Rules |
|---------------|---------------------------------------|-------|
| `SEC-2026`    | Corporate Financial Regulations 2026  | **10**|
| `HIPAA-INS`   | Health Insurance Data Compliance Act  | **10**|
| `GDPR-EU-2025`| Global Data Protection Standard 2025  | **10**|
| `ESG-CORP`    | Corporate Sustainability Framework    | **10**|
| **Total**     |                                       | **40**|

---

## Key Design Decisions

- **Auditing Persistence in Graphs** — Audit reports and findings are saved to Neo4j and modeled as relationships between a `(:Audit)` node and corresponding `(:Rule)` nodes.
- **Robust Schema Bootstrapping** — If an audit is run using backend fallback rules, Cypher `MERGE` clauses dynamically bootstrap the frameworks and rules in the graph database.
- **Strict Structured Parsing** — Leverages `openai.beta.chat.completions.parse` with Pydantic type matching for deterministic, schema-safe audits.
- **Graceful DB Fallbacks** — The backend remains fully operational even if the Neo4j instance goes offline, falling back silently to simulated checks and logging warnings.
