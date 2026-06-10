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
├── main.py            ← Entire application (models, DB, LLM, endpoints)
├── requirements.txt   ← Python dependencies
├── .env               ← Your secrets (never commit this!)
└── README.md          ← This file
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

| Variable         | Description                                  | Default         |
|-----------------|----------------------------------------------|-----------------|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`)              | **Required**    |
| `LLM_MODEL`      | OpenAI model to use                         | `gpt-4o-mini`   |
| `NEO4J_URI`      | Neo4j Bolt connection URI                   | `bolt://localhost:7687` |
| `NEO4J_USER`     | Neo4j username                              | `neo4j`         |
| `NEO4J_PASSWORD` | Neo4j password                              | **Required**    |

> **Note:** If Neo4j is offline or unreachable, the app automatically falls back to a built-in simulated rule set so demos and development work without a running database.

### 4. (Optional) Seed Neo4j with Rules

Connect to your Neo4j instance (via Neo4j Desktop or Browser) and run a Cypher query like:

```cypher
CREATE (f:Framework {id: "GDPR"})
CREATE (r1:Rule {
    rule_id: "GDPR-ART-5",
    title: "Data Minimisation",
    description: "Collect only the minimum personal data necessary for the stated purpose.",
    article: "Article 5(1)(c)"
})
CREATE (f)-[:HAS_RULE]->(r1);
```

The app queries the following Cypher pattern:
```cypher
MATCH (f:Framework {id: $framework_id})-[:HAS_RULE]->(r:Rule)
RETURN r.rule_id, r.title, r.description, r.article
ORDER BY r.rule_id
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
