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
import uuid
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
    audit_id: str = Field(
        default="",
        description="Unique identifier for the saved audit.",
    )
    file_name: str = Field(
        default="",
        description="Uploaded document filename.",
    )
    timestamp: int = Field(
        default=0,
        description="Audit execution timestamp.",
    )


class AuditHistoryItem(BaseModel):
    """Represents a simplified item in the audit history list."""

    audit_id: str = Field(..., description="Unique identifier for the audit.")
    timestamp: int = Field(..., description="Audit execution timestamp.")
    file_name: str = Field(..., description="Uploaded document filename.")
    framework_id: str = Field(..., description="Compliance framework identifier.")
    framework_name: str = Field(..., description="Compliance framework name.")
    overall_score: float = Field(..., description="Aggregate compliance percentage.")
    total_violations: int = Field(..., description="Count of rules with a NON-COMPLIANT status.")


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


async def save_audit_to_neo4j(
    audit_id: str,
    file_name: str,
    framework_id: str,
    report: AuditReport,
    timestamp: int,
) -> None:
    """
    Connects to Neo4j and persists the audit report details and findings.

    If the database is unreachable, it logs a warning but does not raise an exception,
    ensuring the API remains functional during development / demos.
    """
    logger.info("[Neo4j] Saving audit report for audit_id='%s', framework_id='%s'", audit_id, framework_id)
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

        findings_data = []
        for f in report.findings:
            findings_data.append({
                "rule_id": f.rule_id,
                "rule_title": f.rule_title,
                "status": f.status,
                "confidence_score": f.confidence_score,
                "evidence": f.evidence,
                "regulatory_foundation": f.regulatory_foundation,
                "gap_analysis": f.gap_analysis
            })

        query = textwrap.dedent(
            """\
            CREATE (a:Audit {
                id: $audit_id,
                timestamp: $timestamp,
                fileName: $file_name,
                overallScore: $overall_score,
                totalViolations: $total_violations
            })
            WITH a
            MERGE (f:Framework {id: $framework_id})
            ON CREATE SET f.name = $framework_id
            CREATE (a)-[:AUDITED_FRAMEWORK]->(f)
            WITH a
            UNWIND $findings AS finding
            MERGE (r:Rule {id: finding.rule_id})
            ON CREATE SET r.title = finding.rule_title, r.text = finding.evidence
            CREATE (a)-[h:HAS_FINDING {
                status: finding.status,
                confidence: finding.confidence_score,
                evidence: finding.evidence,
                regulatoryFoundation: finding.regulatory_foundation,
                gapAnalysis: finding.gap_analysis
            }]->(r)
            """
        )

        async with AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        ) as driver:
            async with driver.session() as session:
                await session.run(
                    query,
                    audit_id=audit_id,
                    timestamp=timestamp,
                    file_name=file_name,
                    overall_score=report.overall_compliance_score,
                    total_violations=report.total_violations_found,
                    framework_id=framework_id,
                    findings=findings_data
                )
        logger.info("[Neo4j] Successfully saved audit report '%s'", audit_id)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[Neo4j] Failed to save audit to Neo4j (%s). Audit was not persisted.", exc
        )


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
         (COMPLIANT count / (COMPLIANT + NON-COMPLIANT count)) × 100
       NOT-APPLICABLE rules must be EXCLUDED from both the numerator and denominator.
       If every rule is NOT-APPLICABLE, return 100.0.
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

    # Recompute all counters from actual findings (LLM can mis-count)
    actual_violations = sum(
        1 for f in report.findings if f.status == "NON-COMPLIANT"
    )
    not_applicable = sum(
        1 for f in report.findings if f.status == "NOT-APPLICABLE"
    )
    compliant = sum(
        1 for f in report.findings if f.status == "COMPLIANT"
    )

    # Recalculate score server-side — NOT-APPLICABLE rules are excluded from
    # both numerator and denominator so they don't dilute the score.
    evaluated = compliant + actual_violations  # only COMPLIANT + NON-COMPLIANT
    if evaluated > 0:
        corrected_score = round((compliant / evaluated) * 100, 2)
    else:
        corrected_score = 100.0  # all rules N/A — nothing to penalise

    # Patch both fields so the UI always shows the correct values
    report.total_violations_found = actual_violations
    report.overall_compliance_score = corrected_score

    logger.info(
        "[Audit] Score recalculated server-side — compliant=%d  non_compliant=%d  "
        "not_applicable=%d  evaluated=%d  score=%.1f%%",
        compliant, actual_violations, not_applicable, evaluated, corrected_score,
    )

    # Generate metadata fields
    audit_id = str(uuid.uuid4())
    current_ts = int(time.time())
    report.audit_id = audit_id
    report.file_name = file.filename
    report.timestamp = current_ts

    # Save to Neo4j
    await save_audit_to_neo4j(audit_id, file.filename, framework_id, report, current_ts)

    elapsed = time.perf_counter() - t_start
    logger.info(
        "[Audit] Complete in %.2fs — framework='%s'  file='%s'  "
        "score=%.1f%%  compliant=%d  non_compliant=%d  not_applicable=%d",
        elapsed, framework_id, file.filename,
        report.overall_compliance_score, compliant, actual_violations, not_applicable,
    )

    return report


# ── Audit History Endpoints ───────────────────────────────────────────────────


@app.get(
    "/api/v1/audits",
    response_model=List[AuditHistoryItem],
    tags=["Audit"],
    summary="List all historical audit reports",
)
async def list_audits() -> List[AuditHistoryItem]:
    """
    Retrieves a list of all historically saved audit reports from Neo4j,
    sorted by timestamp in descending order.
    """
    logger.info("[API] Listing all audits")
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

        query = textwrap.dedent(
            """\
            MATCH (a:Audit)-[:AUDITED_FRAMEWORK]->(f:Framework)
            RETURN a.id AS audit_id,
                   a.timestamp AS timestamp,
                   a.fileName AS file_name,
                   f.id AS framework_id,
                   f.name AS framework_name,
                   a.overallScore AS overall_score,
                   a.totalViolations AS total_violations
            ORDER BY a.timestamp DESC
            """
        )

        async with AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        ) as driver:
            async with driver.session() as session:
                result = await session.run(query)
                records = await result.data()

        logger.info("[API] Retrieved %d past audits from Neo4j", len(records))
        return [
            AuditHistoryItem(
                audit_id=rec["audit_id"],
                timestamp=rec["timestamp"],
                file_name=rec["file_name"],
                framework_id=rec["framework_id"],
                framework_name=rec["framework_name"],
                overall_score=rec["overall_score"],
                total_violations=rec["total_violations"],
            )
            for rec in records
        ]

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[Neo4j] Connection failed while fetching history (%s). Returning empty list.", exc
        )
        return []


@app.get(
    "/api/v1/audits/{audit_id}",
    response_model=AuditReport,
    tags=["Audit"],
    summary="Get details of a specific past audit",
)
async def get_audit_detail(audit_id: str) -> AuditReport:
    """
    Retrieves the full AuditReport details and findings for a given audit_id from Neo4j.
    """
    logger.info("[API] Fetching details for audit_id='%s'", audit_id)
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

        query = textwrap.dedent(
            """\
            MATCH (a:Audit {id: $audit_id})-[:AUDITED_FRAMEWORK]->(f:Framework)
            OPTIONAL MATCH (a)-[r:HAS_FINDING]->(rule:Rule)
            RETURN f.id AS framework_id,
                   a.overallScore AS overall_compliance_score,
                   a.totalViolations AS total_violations_found,
                   a.fileName AS file_name,
                   a.timestamp AS timestamp,
                   collect({
                       rule_id: rule.id,
                       rule_title: rule.title,
                       status: r.status,
                       confidence_score: r.confidence,
                       evidence: r.evidence,
                       regulatory_foundation: r.regulatoryFoundation,
                       gap_analysis: r.gapAnalysis
                   }) AS findings
            """
        )

        async with AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        ) as driver:
            async with driver.session() as session:
                result = await session.run(query, audit_id=audit_id)
                record = await result.single()

        if not record or not record.get("framework_id"):
            logger.warning("[API] Audit not found: audit_id='%s'", audit_id)
            raise HTTPException(
                status_code=404,
                detail=f"Audit with ID '{audit_id}' not found.",
            )

        findings_data = []
        for finding in record.get("findings", []):
            if finding.get("rule_id"):  # Filter out empty entries from OPTIONAL MATCH
                findings_data.append(
                    AuditFinding(
                        rule_id=finding["rule_id"],
                        rule_title=finding["rule_title"] or finding["rule_id"],
                        status=finding["status"] or "NOT-APPLICABLE",
                        confidence_score=finding["confidence_score"] or 0.0,
                        evidence=finding["evidence"] or "",
                        regulatory_foundation=finding["regulatory_foundation"] or "",
                        gap_analysis=finding["gap_analysis"] or "",
                    )
                )

        return AuditReport(
            framework_id=record["framework_id"],
            overall_compliance_score=record["overall_compliance_score"],
            total_violations_found=record["total_violations_found"],
            findings=findings_data,
            audit_id=audit_id,
            file_name=record["file_name"] or "",
            timestamp=record["timestamp"] or 0,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("[API] Failed to fetch audit from Neo4j: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit from Neo4j: {exc}",
        )


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
