"""
AI-Driven Audit & Compliance Validator
=======================================
Single-file FastAPI backend that orchestrates:
  Document Upload → Neo4j Rule Retrieval → OpenAI Structured Audit → JSON Report

Author  : Hackathon Team
Python  : 3.11+
"""

from __future__ import annotations

import logging
import os
import textwrap
import time
from typing import List, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# 0. Logging Setup
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compliance_validator")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Environment & Client Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logger.info(
    "Startup config — model=%s  neo4j_uri=%s  neo4j_user=%s",
    LLM_MODEL, NEO4J_URI, NEO4J_USER,
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Pydantic Schemas (Structured Output Contract)
# ─────────────────────────────────────────────────────────────────────────────


class AuditFinding(BaseModel):
    """Represents the compliance evaluation of a single regulatory rule."""

    rule_id: str = Field(
        ...,
        description="Unique identifier of the compliance rule (e.g., 'GDPR-ART-5').",
    )
    rule_title: str = Field(
        ...,
        description="Human-readable title of the compliance rule.",
    )
    status: Literal["COMPLIANT", "NON-COMPLIANT", "NOT-APPLICABLE"] = Field(
        ...,
        description="Compliance status for this rule based on the provided document.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in this finding, between 0.0 and 1.0.",
    )
    evidence: str = Field(
        ...,
        description="Direct quote or reference from the document that supports the finding.",
    )
    regulatory_foundation: str = Field(
        ...,
        description="The legal or regulatory basis for this rule (e.g., article number).",
    )
    gap_analysis: str = Field(
        ...,
        description=(
            "Detailed explanation of what is missing or non-compliant, "
            "or confirmation of compliance. Empty string if NOT-APPLICABLE."
        ),
    )


class AuditReport(BaseModel):
    """Top-level structured audit report returned by the LLM."""

    framework_id: str = Field(
        ...,
        description="The compliance framework that was audited (e.g., 'GDPR', 'HIPAA').",
    )
    overall_compliance_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Aggregate compliance percentage across all evaluated rules.",
    )
    total_violations_found: int = Field(
        ...,
        ge=0,
        description="Count of rules with a NON-COMPLIANT status.",
    )
    findings: List[AuditFinding] = Field(
        ...,
        description="Per-rule audit findings.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Neo4j Helper — Fetch Compliance Rules
# ─────────────────────────────────────────────────────────────────────────────

_FALLBACK_RULES: str = textwrap.dedent(
    """\
    [SIMULATED — Neo4j offline]
    RULE-001 | Data Minimisation          | Collect only the minimum personal data necessary.
    RULE-002 | Consent Mechanism          | Explicit, granular consent must be obtained before processing.
    RULE-003 | Right to Erasure           | Users must be able to request permanent deletion of their data.
    RULE-004 | Data Breach Notification   | Breaches must be reported to the authority within 72 hours.
    RULE-005 | Data Encryption at Rest    | All stored personal data must be encrypted (AES-256 minimum).
    RULE-006 | Third-Party Data Sharing   | Third parties must sign a Data Processing Agreement (DPA).
    RULE-007 | Data Retention Policy      | Data must not be retained beyond its stated purpose period.
    RULE-008 | Access Control             | Role-based access control must restrict data to authorised users.
    """
)


async def fetch_neo4j_rules(framework_id: str) -> str:
    """
    Connects to Neo4j and retrieves compliance rules for a given framework.

    Falls back to a simulated rule set if the database is unreachable,
    ensuring the API remains functional during development / demos.

    Parameters
    ----------
    framework_id : str
        The compliance framework identifier (e.g., "GDPR", "HIPAA").

    Returns
    -------
    str
        A newline-separated string of rules ready to embed in an LLM prompt.
    """
    logger.info("[Neo4j] Fetching rules for framework_id='%s'", framework_id)
    try:
        # Import here to keep the fallback path clean if neo4j isn't installed.
        from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

        async with AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        ) as driver:
            query = textwrap.dedent(
                """\
                MATCH (f:Framework {id: $framework_id})-[:HAS_RULE]->(r:Rule)
                RETURN r.id    AS rule_id,
                       r.title AS title,
                       r.text  AS text
                ORDER BY r.id
                """
            )
            async with driver.session() as session:
                result = await session.run(query, framework_id=framework_id)
                records = await result.data()

        if not records:
            logger.warning(
                "[Neo4j] No rules found for framework_id='%s'. Using fallback.",
                framework_id,
            )
            return _FALLBACK_RULES

        logger.info(
            "[Neo4j] Retrieved %d rule(s) for framework_id='%s'",
            len(records), framework_id,
        )
        lines: List[str] = [
            f"{rec['rule_id']} | {rec['title']} | {rec['text']}"
            for rec in records
        ]
        return "\n".join(lines)

    except Exception as exc:  # noqa: BLE001
        # DB offline or misconfigured — use simulated rules so demo still works.
        logger.warning(
            "[Neo4j] Connection failed (%s). Using fallback rule set.", exc
        )
        return _FALLBACK_RULES


# ─────────────────────────────────────────────────────────────────────────────
# 4. OpenAI Helper — Run Structured Compliance Audit
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = textwrap.dedent(
    """\
    You are a senior AI compliance auditor specialising in regulatory frameworks.
    Your task is to analyse the provided document excerpt and evaluate it against
    the compliance rules supplied below.

    ── COMPLIANCE FRAMEWORK ────────────────────────────────────────────────────
    Framework : {framework_id}

    ── RULES TO EVALUATE ────────────────────────────────────────────────────────
    {rules}

    ── INSTRUCTIONS ─────────────────────────────────────────────────────────────
    1. Evaluate the document against EVERY rule listed above.
    2. For each rule, determine whether the document is COMPLIANT, NON-COMPLIANT,
       or NOT-APPLICABLE (if the rule is clearly outside the document's scope).
    3. Provide a confidence_score between 0.0 (uncertain) and 1.0 (certain).
    4. Quote direct evidence from the document to support each finding.
    5. Identify the regulatory_foundation (specific article / clause reference).
    6. For NON-COMPLIANT findings, clearly articulate the gap in gap_analysis.
    7. Calculate overall_compliance_score as:
         (COMPLIANT count / total evaluated rules) × 100
    8. Return your analysis as a single structured JSON object matching the
       AuditReport schema exactly — no markdown, no commentary, just JSON.
    """
)


async def run_compliance_audit(
    document_text: str,
    rules: str,
    framework_id: str,
) -> AuditReport:
    """
    Sends the document and rules to OpenAI using structured output parsing.

    Parameters
    ----------
    document_text : str
        Raw text extracted from the uploaded compliance document.
    rules : str
        Formatted compliance rules retrieved from Neo4j (or fallback).
    framework_id : str
        The compliance framework identifier for prompt context.

    Returns
    -------
    AuditReport
        A fully validated Pydantic model containing all findings.
    """
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        framework_id=framework_id,
        rules=rules,
    )

    completion = await openai_client.beta.chat.completions.parse(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Please audit the following document:\n\n"
                    f"──────────────────────────────────────\n"
                    f"{document_text}\n"
                    f"──────────────────────────────────────"
                ),
            },
        ],
        response_format=AuditReport,
        temperature=0.1,  # Low temperature for deterministic compliance decisions.
    )

    audit_report: AuditReport = completion.choices[0].message.parsed
    return audit_report


# ─────────────────────────────────────────────────────────────────────────────
# 5. FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI-Driven Audit & Compliance Validator",
    description=(
        "Upload a document and select a compliance framework. "
        "The API retrieves rules from Neo4j and uses OpenAI to produce a "
        "structured audit report with per-rule findings and compliance scores."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Returns the service status and the configured LLM model name.
    Use this endpoint to verify the API is online before submitting audits.
    """
    return {
        "status": "online",
        "llm_model": LLM_MODEL,
        "service": "AI-Driven Audit & Compliance Validator",
    }


# ── Audit Endpoint ────────────────────────────────────────────────────────────


@app.post(
    "/api/v1/audit",
    response_model=AuditReport,
    tags=["Audit"],
    summary="Run a compliance audit on an uploaded document",
    response_description="Structured audit report with per-rule findings.",
)
async def run_audit(
    file: UploadFile = File(..., description="Plain-text or UTF-8 document to audit."),
    framework_id: str = Form(
        ...,
        description="Compliance framework identifier (e.g., GDPR, HIPAA, SOC2).",
    ),
) -> AuditReport:
    """
    Accepts a document file and a framework identifier, then:

    1. Reads the document text.
    2. Fetches compliance rules from Neo4j (with automatic fallback).
    3. Sends both to OpenAI using structured output parsing.
    4. Returns a fully validated `AuditReport` JSON object.
    """
    t_start = time.perf_counter()

    # ── Step 1: Read document ─────────────────────────────────────────────────
    try:
        raw_bytes: bytes = await file.read()
        document_text: str = raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception as exc:
        logger.error("[Audit] Failed to read file '%s': %s", file.filename, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    if not document_text:
        logger.warning("[Audit] Uploaded file '%s' is empty.", file.filename)
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is empty. Please provide a non-empty document.",
        )

    logger.info(
        "[Audit] Request received — file='%s'  framework='%s'  doc_chars=%d",
        file.filename, framework_id, len(document_text),
    )

    # ── Step 2: Fetch Neo4j rules ─────────────────────────────────────────────
    rules: str = await fetch_neo4j_rules(framework_id)
    rule_count = rules.count("\n") + 1 if rules.strip() else 0
    logger.info(
        "[Audit] Rules loaded for '%s' — %d rule line(s)",
        framework_id, rule_count,
    )

    # ── Step 3: Run OpenAI compliance audit ───────────────────────────────────
    logger.info("[Audit] Calling OpenAI model='%s' …", LLM_MODEL)
    try:
        report: AuditReport = await run_compliance_audit(
            document_text=document_text,
            rules=rules,
            framework_id=framework_id,
        )
    except Exception as exc:
        logger.error("[Audit] OpenAI call failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI audit failed: {exc}",
        ) from exc

    # Recompute violation count from actual findings (LLM can mis-count)
    actual_violations = sum(
        1 for f in report.findings if f.status == "NON-COMPLIANT"
    )
    not_applicable = sum(
        1 for f in report.findings if f.status == "NOT-APPLICABLE"
    )
    compliant = sum(
        1 for f in report.findings if f.status == "COMPLIANT"
    )
    # Patch the field so the UI always shows the correct count
    report.total_violations_found = actual_violations

    elapsed = time.perf_counter() - t_start
    logger.info(
        "[Audit] Complete in %.2fs — framework='%s'  file='%s'  "
        "score=%.1f%%  compliant=%d  non_compliant=%d  not_applicable=%d",
        elapsed, framework_id, file.filename,
        report.overall_compliance_score, compliant, actual_violations, not_applicable,
    )

    return report


# ─────────────────────────────────────────────────────────────────────────────
# 6. Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
