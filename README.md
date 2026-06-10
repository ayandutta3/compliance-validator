# AI-Driven Audit & Compliance Validator

A lightweight, single-file FastAPI backend that uses **Neo4j** (graph database) for compliance rule storage and **OpenAI GPT-4o-mini** (structured outputs) to produce deterministic, schema-validated audit reports from uploaded documents.

---

## Architecture Overview

```
┌─────────────────┐     POST /api/v1/audit      ┌─────────────────────────────────┐
│  Client / UI    │ ──────────────────────────► │         FastAPI (main.py)        │
│  (Postman, etc) │ ◄────────────────────────── │                                 │
└─────────────────┘       AuditReport JSON       │  1. Read uploaded document      │
                                                 │  2. Fetch rules from Neo4j      │
                                                 │  3. Call OpenAI structured API  │
                          ┌──────────────┐       │  4. Return validated JSON       │
                          │   Neo4j DB   │ ◄──── └─────────────────────────────────┘
                          │ (Rules Graph)│
                          └──────────────┘
                                │ fallback if offline
                                ▼
                          Simulated Rule Set
                          (built-in strings)
```

**Data Flow:**
`Document Upload` → `Neo4j Rule Retrieval` → `OpenAI Structured Audit` → `JSON Report`

---

## Project Structure

```
compliance-validator/
├── main.py                          ← FastAPI app (models, DB, LLM, endpoints)
├── app.py                           ← Streamlit UI frontend
├── ingest_rules.py                  ← CLI utility: seed Neo4j from the CSV
├── synthetic_compliance_rules.csv   ← Source-of-truth compliance rules data
├── sample_requests_responses.txt    ← Sample API request/response pairs
├── requirements.txt                 ← Python dependencies
├── .env                             ← Your secrets (never commit this!)
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

Copy the template and fill in your credentials:

```bash
# The .env file is already pre-populated as a template.
# Open it and replace the placeholder values:
```

| Variable          | Description                                  | Default         |
|------------------|----------------------------------------------|-----------------|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`)              | **Required**    |
| `LLM_MODEL`      | OpenAI model to use                         | `gpt-4o-mini`   |
| `NEO4J_URI`      | Neo4j Bolt connection URI                   | `bolt://localhost:7687` |
| `NEO4J_USER`     | Neo4j username                              | `neo4j`         |
| `NEO4J_PASSWORD` | Neo4j password                              | **Required**    |
| `API_BASE_URL`   | Base URL the Streamlit UI calls             | `http://localhost:8000` |

> **Note:** If Neo4j is offline or unreachable, the app automatically falls back to a built-in simulated rule set so demos and development work without a running database.

### 4. Seed Neo4j with Compliance Rules

Use the bundled **`ingest_rules.py`** utility to populate the graph database from `synthetic_compliance_rules.csv` in one command:

```bash
python ingest_rules.py
```

Expected output:

```
============================================================
  Compliance Rules — Neo4j Ingestion Utility
============================================================
[INFO]  Loaded 12 rule(s) from: synthetic_compliance_rules.csv
[INFO]  Connecting to Neo4j at bolt://localhost:7687 …
  [  1/12] ✔  Merged Rule 'SEC-2026-A1' → Framework 'SEC-2026'
  [  2/12] ✔  Merged Rule 'SEC-2026-B2' → Framework 'SEC-2026'
  ...
  [ 12/12] ✔  Merged Rule 'ESG-SOC-02'  → Framework 'ESG-CORP'

------------------------------------------------------------
[DONE]  Ingestion complete — 12 succeeded, 0 failed.
------------------------------------------------------------
```

> **Idempotent:** The script uses Cypher `MERGE` statements, so running it multiple times is safe — it will update existing nodes rather than creating duplicates.

The app queries Neo4j using:
```cypher
MATCH (f:Framework {id: $framework_id})-[:HAS_RULE]->(r:Rule)
RETURN r.id AS rule_id, r.title AS title, r.text AS text
ORDER BY r.id
```

### 5. Launch the Application

```bash
# Via Python entrypoint (reload enabled)
python main.py

# Or directly via uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at: **http://localhost:8000**

---

## API Reference

### `GET /health`

Returns service status and active LLM model.

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

Runs a full compliance audit on an uploaded document.

**Request (multipart/form-data):**

| Field          | Type   | Description                                    |
|---------------|--------|------------------------------------------------|
| `file`        | File   | Plain-text document to audit (UTF-8 encoded)  |
| `framework_id`| String | Framework to audit against (e.g., `GDPR`)     |

**Example using `curl`:**
```bash
curl -X POST http://localhost:8000/api/v1/audit \
  -F "file=@privacy_policy.txt" \
  -F "framework_id=GDPR"
```

**Response (`AuditReport` schema):**
```json
{
  "framework_id": "GDPR",
  "overall_compliance_score": 62.5,
  "total_violations_found": 3,
  "findings": [
    {
      "rule_id": "GDPR-ART-5",
      "rule_title": "Data Minimisation",
      "status": "COMPLIANT",
      "confidence_score": 0.91,
      "evidence": "We collect only the email address required to create your account.",
      "regulatory_foundation": "Article 5(1)(c) GDPR",
      "gap_analysis": ""
    },
    {
      "rule_id": "GDPR-ART-17",
      "rule_title": "Right to Erasure",
      "status": "NON-COMPLIANT",
      "confidence_score": 0.88,
      "evidence": "No deletion mechanism is mentioned in the document.",
      "regulatory_foundation": "Article 17 GDPR",
      "gap_analysis": "The document does not describe any process for users to request erasure of their personal data."
    }
  ]
}
```

---

## Streamlit UI (`app.py`)

A rich, dark-themed web dashboard that wraps the FastAPI backend with a visual audit interface.

### Launch

> The FastAPI backend (`python main.py`) must be running **before** starting the UI.

```bash
# Terminal 1 — start the API
python main.py

# Terminal 2 — start the Streamlit UI
streamlit run app.py
```

The UI opens at: **http://localhost:8501**

### Features

| Feature | Description |
|--------|-------------|
| **Framework selector** | Pick from SEC-2026, HIPAA-INS, GDPR-EU-2025, or ESG-CORP |
| **Document upload** | Drag-and-drop `.txt` / `.md` file |
| **Live API health indicator** | Pulsing dot shows backend status + active LLM model |
| **Compliance score gauge** | SVG arc gauge coloured green / amber / red |
| **Summary metric cards** | Rules evaluated, compliant, violations, not-applicable |
| **Per-rule finding cards** | Colour-coded cards with status badge, evidence, gap analysis, confidence bar |
| **Status filter** | Filter findings by COMPLIANT / NON-COMPLIANT / NOT-APPLICABLE |
| **JSON export** | Download the full `AuditReport` as a timestamped `.json` file |

---

## Ingestion Script Reference (`ingest_rules.py`)

A standalone CLI utility that reads `synthetic_compliance_rules.csv` and writes `Framework` and `Rule` nodes into Neo4j.

### Graph Schema

```
(:Framework {id, name}) -[:HAS_RULE]-> (:Rule {id, title, text})
```

### CSV → Graph Mapping

| CSV Column       | Node / Property              |
|-----------------|------------------------------|
| `framework_id`  | `Framework.id` *(merge key)* |
| `framework_name`| `Framework.name`             |
| `rule_id`       | `Rule.id` *(merge key)*      |
| `rule_title`    | `Rule.title`                 |
| `rule_text`     | `Rule.text`                  |

### Supported Frameworks (from CSV)

| Framework ID   | Framework Name                        | Rules |
|---------------|---------------------------------------|-------|
| `SEC-2026`    | Corporate Financial Regulations 2026  | 4     |
| `HIPAA-INS`   | Health Insurance Data Compliance Act  | 3     |
| `GDPR-EU-2025`| Global Data Protection Standard 2025  | 2     |
| `ESG-CORP`    | Corporate Sustainability Framework    | 2     |

### Error Handling

| Condition                        | Behaviour                                   |
|---------------------------------|---------------------------------------------|
| Missing `.env` variable          | Prints variable name, exits with code `1`  |
| CSV file not found               | Prints path, exits with code `1`           |
| CSV missing required columns     | Prints column diff, exits with code `1`    |
| Neo4j authentication failure     | Prints error, exits with code `1`          |
| Neo4j service unreachable        | Prints URI, exits with code `1`            |
| Individual row `MERGE` failure   | Logs the row, continues, exits `1` at end  |

### Required Environment Variables

All credentials are read from the project's `.env` file:

| Variable          | Description                          |
|------------------|--------------------------------------|
| `NEO4J_URI`      | Bolt URI (e.g. `bolt://localhost:7687`) |
| `NEO4J_USER`     | Neo4j username                       |
| `NEO4J_PASSWORD` | Neo4j password                       |

---

## Interactive API Docs

FastAPI auto-generates two documentation UIs:

| URL                           | Interface       |
|-------------------------------|-----------------|
| http://localhost:8000/docs    | Swagger UI      |
| http://localhost:8000/redoc   | ReDoc           |

---

## Key Design Decisions

- **Single-file architecture** — All models, DB logic, LLM helpers, and endpoints live in `main.py` for maximum hackathon simplicity.
- **Structured outputs** — Uses `openai.beta.chat.completions.parse` with Pydantic schema enforcement, eliminating the need for manual JSON parsing or error handling around malformed LLM responses.
- **Graceful Neo4j fallback** — A `try/except` around the DB call returns a built-in rule set, so the API remains fully functional without a running Neo4j instance.
- **Low temperature (0.1)** — Keeps compliance decisions deterministic and reproducible across runs.
