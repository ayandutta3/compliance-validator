"""
app.py — Streamlit Frontend
============================
Rich UI for the AI-Driven Audit & Compliance Validator.

Calls the FastAPI backend (main.py) at POST /api/v1/audit and renders
a full dashboard with compliance score gauge, per-rule finding cards,
confidence bars, and a downloadable JSON report.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import html
import json
import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Page Config  (MUST be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Compliance Validator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
AUDIT_ENDPOINT: str = f"{API_BASE_URL}/api/v1/audit"
HEALTH_ENDPOINT: str = f"{API_BASE_URL}/health"

FRAMEWORKS: dict[str, str] = {
    "SEC-2026":     "Corporate Financial Regulations 2026",
    "HIPAA-INS":    "Health Insurance Data Compliance Act",
    "GDPR-EU-2025": "Global Data Protection Standard 2025",
    "ESG-CORP":     "Corporate Sustainability Framework",
}

STATUS_CONFIG: dict[str, dict] = {
    "COMPLIANT":       {"icon": "✅", "color": "#22c55e", "bg": "#052e16"},
    "NON-COMPLIANT":   {"icon": "❌", "color": "#ef4444", "bg": "#2d0a0a"},
    "NOT-APPLICABLE":  {"icon": "➖", "color": "#94a3b8", "bg": "#1e293b"},
}

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Dark gradient background ── */
    .stApp {
        background: linear-gradient(135deg, #0a0f1e 0%, #0f172a 50%, #0a0f1e 100%);
        color: #e2e8f0;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0;
    }

    /* ── Hero header ── */
    .hero-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2847 50%, #1a1040 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 60%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #818cf8, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        font-weight: 400;
        margin: 0;
    }

    /* ── Metric cards ── */
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.4rem 1.6rem;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
        height: 100%;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .metric-label {
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #64748b;
        margin-bottom: 0.4rem;
    }
    .metric-value {
        font-size: 2.4rem;
        font-weight: 700;
        line-height: 1;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 0.3rem;
    }

    /* ── Score gauge container ── */
    .gauge-container {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
    }

    /* ── Finding cards ── */
    .finding-card {
        border-radius: 12px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1rem;
        border-left: 4px solid;
        transition: transform 0.15s;
    }
    .finding-card:hover {
        transform: translateX(4px);
    }
    .finding-rule-id {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        opacity: 0.7;
        margin-bottom: 0.2rem;
    }
    .finding-title {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .finding-badge {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        letter-spacing: 0.06em;
        margin-bottom: 0.8rem;
    }
    .finding-label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.55;
        margin-top: 0.8rem;
        margin-bottom: 0.2rem;
    }
    .finding-text {
        font-size: 0.88rem;
        line-height: 1.6;
        opacity: 0.85;
    }

    /* ── Section headers ── */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #e2e8f0;
        letter-spacing: -0.2px;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #1e293b;
    }

    /* ── Status indicator ── */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ── Upload zone ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #334155;
        border-radius: 12px;
        padding: 1rem;
        background: #0f172a;
        transition: border-color 0.2s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #6366f1;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #4f46e5);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        font-size: 0.95rem;
        width: 100%;
        transition: opacity 0.2s, transform 0.15s;
    }
    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }

    /* ── Select box ── */
    [data-testid="stSelectbox"] > div > div {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        color: #e2e8f0;
    }

    /* ── JSON download button ── */
    .stDownloadButton > button {
        background: transparent;
        color: #818cf8;
        border: 1px solid #4f46e5;
        border-radius: 8px;
        width: 100%;
        font-weight: 500;
        transition: background 0.2s;
    }
    .stDownloadButton > button:hover {
        background: rgba(99,102,241,0.1);
    }

    /* ── Progress bar colour ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6366f1, #38bdf8);
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

    /* ── Alert/info boxes ── */
    [data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* ── Divider ── */
    hr { border-color: #1e293b; }

    /* Hide Streamlit branding ── */
    #MainMenu, footer { visibility: hidden; }

    /* ── Sidebar nav buttons ── */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent;
        color: #94a3b8;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: 500;
        font-size: 0.92rem;
        width: 100%;
        text-align: left;
        transition: background 0.18s, color 0.18s, box-shadow 0.18s;
        margin-bottom: 0.25rem;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(99,102,241,0.12);
        color: #e2e8f0;
        transform: none;
        opacity: 1;
    }
    [data-testid="stSidebar"] .nav-active .stButton > button {
        background: linear-gradient(90deg, rgba(99,102,241,0.22), rgba(56,189,248,0.10));
        color: #818cf8;
        border-left: 3px solid #6366f1;
        padding-left: calc(1rem - 3px);
        font-weight: 600;
        box-shadow: 0 2px 12px rgba(99,102,241,0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def check_api_health() -> tuple[bool, str]:
    """Ping the FastAPI health endpoint."""
    try:
        resp = requests.get(HEALTH_ENDPOINT, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("llm_model", "unknown")
        return False, ""
    except requests.exceptions.RequestException:
        return False, ""


def run_audit(file_bytes: bytes, filename: str, framework_id: str) -> dict | None:
    """POST document + framework to the audit endpoint, return JSON dict."""
    try:
        response = requests.post(
            AUDIT_ENDPOINT,
            files={"file": (filename, file_bytes, "text/plain")},
            data={"framework_id": framework_id},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to the API. Is the FastAPI server running on `localhost:8000`?")
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The LLM is taking too long — try a shorter document.")
    except requests.exceptions.HTTPError as exc:
        detail = exc.response.json().get("detail", str(exc)) if exc.response else str(exc)
        st.error(f"API Error {exc.response.status_code}: {detail}")
    return None


def score_color(score: float) -> str:
    """Return a hex colour reflecting the compliance score."""
    if score >= 80:
        return "#22c55e"
    if score >= 50:
        return "#f59e0b"
    return "#ef4444"


def score_label(score: float) -> str:
    if score >= 80:
        return "High Compliance"
    if score >= 50:
        return "Partial Compliance"
    return "Low Compliance"


def render_gauge(score: float) -> None:
    """Render an SVG arc gauge for the compliance score."""
    pct = score / 100
    color = score_color(score)

    # Arc geometry: full arc = 251.2 (circumference of r=40 circle, 75% arc)
    arc_len = 251.2
    dash = pct * arc_len

    svg = f"""
    <div class="gauge-container">
        <svg viewBox="0 0 120 80" width="220" style="display:block;margin:auto;">
            <!-- Background arc -->
            <circle cx="60" cy="65" r="40"
                fill="none" stroke="#1e293b" stroke-width="10"
                stroke-dasharray="188.4 62.8"
                stroke-dashoffset="0"
                stroke-linecap="round"
                transform="rotate(135 60 65)"/>
            <!-- Foreground arc -->
            <circle cx="60" cy="65" r="40"
                fill="none" stroke="{color}" stroke-width="10"
                stroke-dasharray="{dash * 0.75:.1f} {arc_len:.1f}"
                stroke-dashoffset="0"
                stroke-linecap="round"
                transform="rotate(135 60 65)"
                style="transition: stroke-dasharray 1s ease;"/>
            <!-- Score text -->
            <text x="60" y="62" text-anchor="middle"
                font-family="Inter,sans-serif" font-size="18" font-weight="700"
                fill="{color}">{score:.0f}%</text>
            <text x="60" y="74" text-anchor="middle"
                font-family="Inter,sans-serif" font-size="5.5" font-weight="500"
                fill="#64748b">{score_label(score).upper()}</text>
        </svg>
        <div style="font-size:0.78rem;color:#64748b;margin-top:0.3rem;">
            Overall Compliance Score
        </div>
    </div>
    """
    st.markdown(svg, unsafe_allow_html=True)


def render_finding_card(finding: dict) -> None:
    """Render a styled HTML card for a single AuditFinding.

    HTML is assembled as a list joined on single newlines — no blank lines.
    Streamlit's CommonMark parser ends an HTML block at the FIRST blank line,
    so any blank line inside the HTML string causes everything after it to be
    output as raw text.  Joining on single newlines prevents this.

    All LLM-returned text is html.escape()'d to prevent stray angle-brackets
    or special characters from breaking the HTML structure.
    """
    status = finding.get("status", "NOT-APPLICABLE")
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["NOT-APPLICABLE"])
    confidence_pct = int(finding.get("confidence_score", 0) * 100)

    # Escape every LLM-supplied value before embedding in HTML
    rule_id    = html.escape(str(finding.get("rule_id", "")))
    rule_title = html.escape(str(finding.get("rule_title", "")))
    reg_found  = html.escape(str(finding.get("regulatory_foundation", "—")))
    evidence   = html.escape(str(finding.get("evidence", "—")))
    gap        = html.escape(finding.get("gap_analysis", "").strip())

    c  = cfg["color"]
    bg = cfg["bg"]

    lbl_style = (
        "font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.06em;opacity:0.55;margin-top:0.8rem;margin-bottom:0.2rem;"
    )
    txt_style = "font-size:0.88rem;line-height:1.6;opacity:0.85;"

    parts = [
        f'<div class="finding-card" style="background:{bg};border-left-color:{c};">',
        f'<div style="font-size:0.72rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:{c};opacity:0.7;margin-bottom:0.2rem;">{rule_id}</div>',
        f'<div style="font-size:1.05rem;font-weight:600;color:#f1f5f9;margin-bottom:0.5rem;">{cfg["icon"]} {rule_title}</div>',
        f'<span style="display:inline-block;font-size:0.72rem;font-weight:700;padding:0.2rem 0.7rem;border-radius:20px;letter-spacing:0.06em;margin-bottom:0.8rem;background:{c}22;color:{c};border:1px solid {c}44;">{status}</span>',
        f'<div style="{lbl_style}">Regulatory Foundation</div>',
        f'<div style="{txt_style}">{reg_found}</div>',
        f'<div style="{lbl_style}">Evidence</div>',
        f'<div style="{txt_style}">&ldquo;{evidence}&rdquo;</div>',
    ]

    if gap:
        parts += [
            f'<div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-top:0.8rem;margin-bottom:0.2rem;color:#f87171;">Gap Analysis</div>',
            f'<div style="font-size:0.88rem;line-height:1.6;color:#fca5a5;">{gap}</div>',
        ]

    parts += [
        f'<div style="{lbl_style}">Confidence</div>',
        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-top:0.3rem;">',
        f'<div style="flex:1;background:#1e293b;border-radius:4px;height:6px;overflow:hidden;">',
        f'<div style="width:{confidence_pct}%;height:100%;background:linear-gradient(90deg,{c},{c}99);border-radius:4px;transition:width 0.8s ease;"></div>',
        '</div>',
        f'<span style="font-size:0.78rem;color:{c};font-weight:600;min-width:2.5rem;">{confidence_pct}%</span>',
        '</div>',
        '</div>',
    ]

    st.markdown("\n".join(parts), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center;padding:1rem 0 1.5rem;">
            <div style="font-size:2.5rem;">⚖️</div>
            <div style="font-size:1rem;font-weight:700;color:#e2e8f0;
                        letter-spacing:-0.3px;">Compliance Validator</div>
            <div style="font-size:0.72rem;color:#64748b;margin-top:0.2rem;">
                AI-Driven Regulatory Audit
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Left Navigation ── (session_state tracks active view)
    if "active_view" not in st.session_state:
        st.session_state["active_view"] = "run_audit"

    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#475569;margin-bottom:0.5rem;">Navigation</div>',
        unsafe_allow_html=True,
    )

    NAV_ITEMS = [
        ("run_audit",     "🚀",  "Run Audit"),
        ("audit_history", "📊",  "Audit History & Trends"),
    ]

    for view_key, icon, label in NAV_ITEMS:
        is_active = st.session_state["active_view"] == view_key
        if is_active:
            # Render as a non-clickable highlighted HTML block
            st.markdown(
                f'<div style="'
                f'display:flex;align-items:center;gap:0.55rem;'
                f'background:linear-gradient(90deg,rgba(99,102,241,0.25),rgba(56,189,248,0.08));'
                f'border-left:3px solid #6366f1;'
                f'border-radius:0 8px 8px 0;'
                f'padding:0.55rem 1rem 0.55rem calc(1rem - 3px);'
                f'margin-bottom:0.3rem;'
                f'font-size:0.92rem;font-weight:600;color:#a5b4fc;'
                f'box-shadow:0 2px 12px rgba(99,102,241,0.15);'
                f'cursor:default;'
                f'">'
                f'<span style="font-size:1rem;">{icon}</span>'
                f'<span>{label}</span>'
                f'<span style="margin-left:auto;font-size:0.65rem;'
                f'background:#6366f1;color:#fff;padding:0.1rem 0.45rem;'
                f'border-radius:20px;font-weight:700;letter-spacing:0.05em;">ACTIVE</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{view_key}",
                use_container_width=True,
            ):
                st.session_state["active_view"] = view_key
                st.rerun()

    nav_selection = st.session_state["active_view"]


    st.divider()

    # ── API Health ──
    st.markdown("##### 🔌 API Status")
    is_healthy, model_name = check_api_health()
    if is_healthy:
        st.markdown(
            f'<span class="status-dot" style="background:#22c55e;"></span>'
            f'<span style="color:#22c55e;font-size:0.85rem;font-weight:500;">Online</span>'
            f'<span style="color:#64748b;font-size:0.78rem;"> · {model_name}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-dot" style="background:#ef4444;"></span>'
            '<span style="color:#ef4444;font-size:0.85rem;font-weight:500;">Offline</span>'
            '<span style="color:#64748b;font-size:0.78rem;"> · Start main.py first</span>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        '<div style="font-size:0.72rem;color:#475569;text-align:center;">'
        'Powered by OpenAI + Neo4j<br/>© 2026 Compliance Validator</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main content
# ─────────────────────────────────────────────────────────────────────────────

# ── Hero header ──
st.markdown(
    """
    <div class="hero-header">
        <div class="hero-title">⚖️ AI-Driven Audit & Compliance Validator</div>
        <div class="hero-subtitle">
            Upload a regulatory document · Select a framework · Get an AI-powered structured audit report
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

if nav_selection == "run_audit":
    st.markdown('<div class="section-header">🚀 Run Compliance Audit</div>', unsafe_allow_html=True)
    
    col_framework, col_file = st.columns([1, 1])
    
    with col_framework:
        st.markdown("##### 📋 Compliance Framework")
        framework_options = {v: k for k, v in FRAMEWORKS.items()}
        selected_name = st.selectbox(
            "Select framework",
            options=list(framework_options.keys()),
            label_visibility="collapsed",
        )
        selected_framework_id = framework_options[selected_name]
        st.markdown(
            f'<div style="font-size:0.75rem;color:#64748b;margin-top:-0.5rem;margin-bottom:1rem;">'
            f'ID: <code style="color:#818cf8;">{selected_framework_id}</code></div>',
            unsafe_allow_html=True,
        )
        
    with col_file:
        st.markdown("##### 📄 Document Upload")
        uploaded_file = st.file_uploader(
            "Upload document",
            type=["txt", "md"],
            help="Plain-text (.txt) or Markdown (.md) document to audit. Max 5 MB.",
            label_visibility="collapsed",
        )
        if uploaded_file:
            st.markdown(
                f'<div style="font-size:0.78rem;color:#64748b;margin-top:0.4rem;">'
                f'📎 {uploaded_file.name} · '
                f'{uploaded_file.size / 1024:.1f} KB</div>',
                unsafe_allow_html=True,
            )

    # Confirmation box — helps prevent framework/document mismatches
    if uploaded_file and is_healthy:
        st.markdown(
            f'<div style="background:#0f2847;border:1px solid #1e3a5f;border-radius:8px;'
            f'padding:0.75rem 1rem;margin-top:1rem;margin-bottom:1rem;font-size:0.78rem;color:#94a3b8;">'
            f'<div style="color:#38bdf8;font-weight:600;margin-bottom:0.3rem;">'
            f'📋 Audit Summary</div>'
            f'<div>📄 Document: <span style="color:#e2e8f0;">{uploaded_file.name}</span></div>'
            f'<div>🏷️ Framework: <code style="color:#818cf8;">{selected_framework_id}</code> ({selected_name})</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Run button ──
    run_clicked = st.button("🚀 Run Compliance Audit", disabled=not uploaded_file or not is_healthy)
    
    if not is_healthy:
        st.warning("Start the FastAPI server first:\n```\npython main.py\n```")
    elif not uploaded_file:
        st.info("Upload a document to begin.")

    # Execute audit
    if run_clicked and uploaded_file:
        file_bytes = uploaded_file.read()

        with st.spinner("🔍 Retrieving rules from Neo4j and running AI audit…"):
            progress = st.progress(0, text="Connecting to backend…")
            time.sleep(0.3)
            progress.progress(20, text="Uploading document…")
            time.sleep(0.2)
            progress.progress(40, text="Fetching compliance rules from Neo4j…")

            result = run_audit(file_bytes, uploaded_file.name, selected_framework_id)

            if result:
                progress.progress(80, text="Processing AI findings…")
                time.sleep(0.4)
                progress.progress(100, text="Complete!")
                time.sleep(0.3)
                progress.empty()
                st.session_state["audit_result"] = result
                st.session_state["audit_framework"] = selected_name
                st.session_state["audit_filename"] = uploaded_file.name
            else:
                progress.empty()

    # Render results
    if "audit_result" in st.session_state:
        report: dict = st.session_state["audit_result"]
        findings: list[dict] = report.get("findings", [])
        score: float = report.get("overall_compliance_score", 0.0)
        violations: int = sum(1 for f in findings if f.get("status") == "NON-COMPLIANT")
        compliant_count = sum(1 for f in findings if f.get("status") == "COMPLIANT")
        na_count = sum(1 for f in findings if f.get("status") == "NOT-APPLICABLE")

        st.markdown(
            f'<div class="section-header">📊 Audit Report — {st.session_state["audit_framework"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:0.8rem;color:#64748b;margin-top:-0.8rem;margin-bottom:1.2rem;">'
            f'Document: <span style="color:#94a3b8;">{st.session_state["audit_filename"]}</span> · '
            f'Framework ID: <code style="color:#818cf8;">{report.get("framework_id")}</code></div>',
            unsafe_allow_html=True,
        )

        # ── Top metrics row ──
        col_gauge, col_m1, col_m2, col_m3, col_m4 = st.columns([2, 1, 1, 1, 1])

        with col_gauge:
            render_gauge(score)

        with col_m1:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Rules Evaluated</div>'
                f'<div class="metric-value" style="color:#818cf8;">{len(findings)}</div>'
                f'<div class="metric-sub">total rules</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_m2:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Compliant</div>'
                f'<div class="metric-value" style="color:#22c55e;">{compliant_count}</div>'
                f'<div class="metric-sub">rules passed</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_m3:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Violations</div>'
                f'<div class="metric-value" style="color:#ef4444;">{violations}</div>'
                f'<div class="metric-sub">non-compliant</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_m4:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Not Applicable</div>'
                f'<div class="metric-value" style="color:#94a3b8;">{na_count}</div>'
                f'<div class="metric-sub">out of scope</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Filter toolbar ──
        left_col, right_col = st.columns([3, 1])
        with left_col:
            st.markdown('<div class="section-header">📋 Per-Rule Findings</div>', unsafe_allow_html=True)
        with right_col:
            filter_status = st.selectbox(
                "Filter by status",
                options=["All", "NON-COMPLIANT", "COMPLIANT", "NOT-APPLICABLE"],
                label_visibility="collapsed",
            )

        # ── Finding cards ──
        filtered = findings if filter_status == "All" else [
            f for f in findings if f.get("status") == filter_status
        ]

        if not filtered:
            st.info(f"No findings with status **{filter_status}**.")
        else:
            # Sort: NON-COMPLIANT first, then COMPLIANT, then NOT-APPLICABLE
            order = {"NON-COMPLIANT": 0, "COMPLIANT": 1, "NOT-APPLICABLE": 2}
            filtered_sorted = sorted(filtered, key=lambda f: order.get(f.get("status", ""), 99))

            for finding in filtered_sorted:
                render_finding_card(finding)

        st.divider()

        # ── Summary banner ──
        if violations == 0:
            st.success(
                f"🎉 **Fully Compliant** — All {len(findings)} rules passed for the "
                f"**{report.get('framework_id')}** framework."
            )
        else:
            st.warning(
                f"⚠️ **{violations} violation(s) found** — Review the NON-COMPLIANT findings above "
                f"and address the identified gaps to achieve full compliance."
            )

        # ── Download report ──
        st.markdown('<div class="section-header">💾 Export Report</div>', unsafe_allow_html=True)
        json_str = json.dumps(report, indent=2)
        st.download_button(
            label="⬇️ Download Full JSON Report",
            data=json_str,
            file_name=f"audit_{report.get('framework_id', 'report')}_{int(time.time())}.json",
            mime="application/json",
        )

    else:
        st.markdown(
            """
            <div style="text-align:center;padding:4rem 2rem;color:#475569;">
                <div style="font-size:4rem;margin-bottom:1rem;">📄</div>
                <div style="font-size:1.2rem;font-weight:600;color:#64748b;margin-bottom:0.5rem;">
                    Ready to Audit
                </div>
                <div style="font-size:0.9rem;color:#475569;max-width:400px;margin:auto;line-height:1.6;">
                    Select a compliance framework, upload your document,
                    then click <strong style="color:#818cf8;">Run Compliance Audit</strong> to generate an AI-powered report.
                </div>
                <div style="margin-top:2rem;display:flex;justify-content:center;gap:1.5rem;flex-wrap:wrap;">
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                                 padding:0.8rem 1.2rem;font-size:0.82rem;color:#94a3b8;">
                        🏦 SEC-2026 · Financial Regulations
                    </div>
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                                 padding:0.8rem 1.2rem;font-size:0.82rem;color:#94a3b8;">
                        🏥 HIPAA-INS · Health Insurance
                    </div>
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                                 padding:0.8rem 1.2rem;font-size:0.82rem;color:#94a3b8;">
                        🌍 GDPR-EU-2025 · Data Protection
                    </div>
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                                 padding:0.8rem 1.2rem;font-size:0.82rem;color:#94a3b8;">
                        🌱 ESG-CORP · Sustainability
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


elif nav_selection == "audit_history":
    st.markdown('<div class="section-header">📊 Compliance History & Analytics</div>', unsafe_allow_html=True)

    # 1. Fetch historical audits list from backend
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/audits", timeout=5)
        if resp.status_code == 200:
            history = resp.json()
        else:
            history = []
            st.error(f"Failed to fetch audit history. API status code: {resp.status_code}")
    except Exception as exc:
        history = []
        st.warning("⚠️ Could not retrieve history. Ensure the FastAPI backend is running and Neo4j is online.")

    if not history:
        st.markdown(
            """
            <div style="text-align:center;padding:4rem 2rem;color:#475569;">
                <div style="font-size:4rem;margin-bottom:1rem;">📈</div>
                <div style="font-size:1.2rem;font-weight:600;color:#64748b;margin-bottom:0.5rem;">
                    No History Recorded Yet
                </div>
                <div style="font-size:0.9rem;color:#475569;max-width:400px;margin:auto;line-height:1.6;">
                    Once you complete compliance audits in the <strong>Run Audit</strong> section,
                    the results will be persisted and visualized here.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        import pandas as pd
        import datetime

        # Create DataFrame
        df = pd.DataFrame(history)
        
        # Convert timestamp to human readable date
        df["date"] = df["timestamp"].apply(lambda ts: datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"))
        
        # Sort chronologically for trends
        df_sorted = df.sort_values("timestamp")

        # ── Dashboard Statistics Row ──
        st.markdown("##### 📈 Overall Statistics")
        avg_score = df["overall_score"].mean()
        total_audits = len(df)
        total_violations = df["total_violations"].sum()

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Total Audits Run</div>'
                f'<div class="metric-value" style="color:#818cf8;">{total_audits}</div>'
                f'<div class="metric-sub">documents audited</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_stat2:
            color = score_color(avg_score)
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Average Compliance Score</div>'
                f'<div class="metric-value" style="color:{color};">{avg_score:.1f}%</div>'
                f'<div class="metric-sub">{score_label(avg_score)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_stat3:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Total Violations Detected</div>'
                f'<div class="metric-value" style="color:#ef4444;">{total_violations}</div>'
                f'<div class="metric-sub">rules violated</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Chart Row: Trend & Framework Breakdown ──
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("##### 📈 Compliance Score Trend")
            chart_df = df_sorted[["date", "overall_score"]].set_index("date")
            st.line_chart(chart_df, height=250)

        with col_chart2:
            st.markdown("##### 🏷️ Framework Distribution")
            framework_counts = df["framework_id"].value_counts().reset_index()
            framework_counts.columns = ["Framework", "Count"]
            st.bar_chart(framework_counts.set_index("Framework"), height=250)

        st.divider()

        # ── Historical Explorer Row ──
        st.markdown("##### 🔍 Historical Reports Explorer")

        # Load Audit Option
        audit_options = {
            f"[{rec['date']}] {rec['file_name']} ({rec['framework_id']}) — Score: {rec['overall_score']:.0f}%": rec["audit_id"]
            for rec in df.to_dict("records")
        }

        selected_past_audit_label = st.selectbox(
            "Select a historical audit to load and view details:",
            options=["-- Select an Audit --"] + list(audit_options.keys())
        )

        if selected_past_audit_label != "-- Select an Audit --":
            selected_audit_id = audit_options[selected_past_audit_label]

            with st.spinner("⏳ Loading audit report from database..."):
                try:
                    past_resp = requests.get(f"{API_BASE_URL}/api/v1/audits/{selected_audit_id}", timeout=5)
                    if past_resp.status_code == 200:
                        past_report = past_resp.json()

                        st.markdown(
                            f'<div class="section-header">📜 Loaded Historical Audit — {selected_past_audit_label}</div>',
                            unsafe_allow_html=True
                        )

                        past_findings = past_report.get("findings", [])
                        past_score = past_report.get("overall_compliance_score", 0.0)
                        past_violations = sum(1 for f in past_findings if f.get("status") == "NON-COMPLIANT")
                        past_compliant = sum(1 for f in past_findings if f.get("status") == "COMPLIANT")
                        past_na = sum(1 for f in past_findings if f.get("status") == "NOT-APPLICABLE")

                        p_col_gauge, p_col_m1, p_col_m2, p_col_m3, p_col_m4 = st.columns([2, 1, 1, 1, 1])

                        with p_col_gauge:
                            render_gauge(past_score)

                        with p_col_m1:
                            st.markdown(
                                f'<div class="metric-card">'
                                f'<div class="metric-label">Rules Evaluated</div>'
                                f'<div class="metric-value" style="color:#818cf8;">{len(past_findings)}</div>'
                                f'<div class="metric-sub">total rules</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        with p_col_m2:
                            st.markdown(
                                f'<div class="metric-card">'
                                f'<div class="metric-label">Compliant</div>'
                                f'<div class="metric-value" style="color:#22c55e;">{past_compliant}</div>'
                                f'<div class="metric-sub">rules passed</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        with p_col_m3:
                            st.markdown(
                                f'<div class="metric-card">'
                                f'<div class="metric-label">Violations</div>'
                                f'<div class="metric-value" style="color:#ef4444;">{past_violations}</div>'
                                f'<div class="metric-sub">non-compliant</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        with p_col_m4:
                            st.markdown(
                                f'<div class="metric-card">'
                                f'<div class="metric-label">Not Applicable</div>'
                                f'<div class="metric-value" style="color:#94a3b8;">{past_na}</div>'
                                f'<div class="metric-sub">out of scope</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        st.divider()

                        p_left, p_right = st.columns([3, 1])
                        with p_left:
                            st.markdown('<div class="section-header">📋 Historical Findings</div>', unsafe_allow_html=True)
                        with p_right:
                            p_filter_status = st.selectbox(
                                "Filter findings",
                                options=["All", "NON-COMPLIANT", "COMPLIANT", "NOT-APPLICABLE"],
                                key="past_filter_status",
                                label_visibility="collapsed"
                            )

                        p_filtered = past_findings if p_filter_status == "All" else [
                            f for f in past_findings if f.get("status") == p_filter_status
                        ]

                        if not p_filtered:
                            st.info(f"No findings with status **{p_filter_status}**.")
                        else:
                            p_order = {"NON-COMPLIANT": 0, "COMPLIANT": 1, "NOT-APPLICABLE": 2}
                            p_filtered_sorted = sorted(p_filtered, key=lambda f: p_order.get(f.get("status", ""), 99))

                            for finding in p_filtered_sorted:
                                render_finding_card(finding)

                        st.divider()

                        st.markdown('<div class="section-header">💾 Export Loaded Report</div>', unsafe_allow_html=True)
                        p_json_str = json.dumps(past_report, indent=2)
                        st.download_button(
                            label="⬇️ Download Loaded JSON Report",
                            data=p_json_str,
                            file_name=f"audit_{past_report.get('framework_id', 'report')}_{past_report.get('timestamp')}.json",
                            mime="application/json",
                            key="past_download_btn"
                        )
                    else:
                        st.error(f"Failed to fetch historical audit details (Status Code: {past_resp.status_code})")
                except Exception as exc:
                    st.error(f"Error loading historical audit: {exc}")

        st.divider()

        st.markdown("##### 📂 All Recorded Audits")
        display_df = df_sorted[["date", "file_name", "framework_id", "overall_score", "total_violations"]].copy()
        display_df.columns = ["Date & Time", "Filename", "Framework ID", "Compliance Score", "Violations"]
        st.dataframe(
            display_df.sort_values("Date & Time", ascending=False),
            use_container_width=True,
            hide_index=True
        )
