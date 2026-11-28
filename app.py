"""
app.py - Main Streamlit Web Application & Lead Systems Architecture
Civic-Watchdog Project
"""

import os
import datetime
from typing import Any, Dict, List, Optional

import boto3
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# Page Configuration & Styling
st.set_page_config(
    page_title="Civic-Watchdog | Citizen Transparency Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .sub-header {font-size: 1.05rem; color: #4B5563; margin-bottom: 16px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# System 3: Pydantic Data Contract Validation
class ProjectRecordSchema(BaseModel):
    project_id: str = "CW-PROJ-000"
    title: str = "Untitled Public Project"
    authority: str = "Authority not stated in document"
    locality: str = "Locality not stated in document"
    work_category: str = "General Infrastructure"
    stated_budget_inr: float = 0.0
    currency: str = "INR"
    source: Dict[str, Any] = Field(default_factory=dict)
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, str] = Field(default_factory=lambda: {"en": "No summary available."})
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    record_status: str = "needs_review"


def validate_project_record(raw_project: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(raw_project, dict):
        return ProjectRecordSchema().model_dump()
    cleaned = {k: v for k, v in raw_project.items() if v is not None}
    validated = ProjectRecordSchema(**cleaned)
    return validated.model_dump()


# System 1: AWS S3 Storage Gateway (Optional / Non-Blocking)
def upload_pdf_to_s3(file_path: str, file_name: str) -> Optional[str]:
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        try:
            bucket_name = st.secrets.get("S3_BUCKET_NAME", None)
        except Exception:
            bucket_name = None

    if not bucket_name:
        return None

    try:
        s3_client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_DEFAULT_REGION", "ap-south-1"),
        )
        s3_key = f"tenders/{file_name}"
        s3_client.upload_file(file_path, bucket_name, s3_key)
        return f"s3://{bucket_name}/{s3_key}"
    except Exception:
        return None
# System 5: Modular Teammate Imports (with Resilient Fallbacks)
try:
    from ingestion import fetch_tender_pdf
except ImportError:
    def fetch_tender_pdf(path=None):
        return {
            "document_name": path or "Tender_Chikhloli.pdf",
            "pdf_url": "sample_tenders/Tender_Chikhloli.pdf",
            "retrieved_at": datetime.datetime.now().isoformat(),
            "pages_text": [{"page_number": 1, "text": "Sample Tender Text for Road & Drainage Work"}],
        }

try:
    from extractor import extract_project_details
except ImportError:
    def extract_project_details(ingest_data):
        return {
            "project_id": "CW-PROJ-001",
            "title": "Road Repair & Drainage Construction",
            "authority": "Ambernath Municipal Council",
            "locality": "Chikhloli, Ambernath",
            "work_category": "Roads & Drainage",
            "stated_budget_inr": 6626532,
            "currency": "INR",
            "source": {
                "document_name": ingest_data.get("document_name", "Tender.pdf"),
                "page_references": list(),
            },
            "extracted_fields": {
                "completion_period": "6 Months",
                "defect_liability_period": None,
            },
            "summary": {
                "en": "Construction of cement concrete road and side drains in Chikhloli area."
            },
            "checks": list(),
            "record_status": "needs_review",
        }

try:
    from rules_and_reports import run_checks, save_citizen_report, load_citizen_reports
except ImportError:
    def run_checks(project):
        checks = list()
        if not project.get("extracted_fields", {}).get("defect_liability_period"):
            checks.append({
                "check_id": "CHK-001",
                "check_type": "missing_field",
                "field_checked": "defect_liability_period",
                "result": "not_found",
                "explanation": "No defect liability period located in tender pages.",
                "requires_human_review": True,
            })
        if (project.get("stated_budget_inr") or 0) > 5000000:
            checks.append({
                "check_id": "CHK-002",
                "check_type": "budget_threshold",
                "field_checked": "stated_budget_inr",
                "result": "flagged",
                "explanation": "Budget exceeds INR 50,00,000 screening threshold requiring benchmark review.",
                "requires_human_review": True,
            })
        project["checks"] = checks
        return project

    def save_citizen_report(category, locality, landmark, description, duration):
        return {
            "report_id": f"NEED-{datetime.datetime.now().strftime('%M%S')}",
            "category": category,
            "locality": locality,
            "landmark": landmark,
            "description": description,
            "duration": duration,
            "submitted_at": datetime.datetime.now().isoformat(),
            "status": "received_by_civic_watchdog",
        }

    def load_citizen_reports():
        return list()


# System 2: Session State Initialization
if "stored_projects" not in st.session_state:
    initial_ingest = fetch_tender_pdf(None)
    initial_extract = validate_project_record(extract_project_details(initial_ingest))
    initial_checked = validate_project_record(run_checks(initial_extract))
    st.session_state.stored_projects = [initial_checked]

# Sidebar Control Panel
st.sidebar.title("🛡️ Civic-Watchdog")
st.sidebar.caption("Citizen-First Civic Oversight Platform")
st.sidebar.markdown("---")

available_localities = ["All Localities"] + sorted(
    {p.get("locality", "Unknown") for p in st.session_state.stored_projects if p.get("locality")}
)
locality_filter = st.sidebar.selectbox("📍 Filter Projects by Locality:", available_localities)

st.sidebar.markdown("---")
aws_configured = bool(os.getenv("S3_BUCKET_NAME"))
if aws_configured:
    st.sidebar.success("☁️ AWS S3 Storage Connected")
else:
    st.sidebar.info("💻 Local + Cached Demo Mode Active")

st.sidebar.caption(
    "Civic-Watchdog is an information screening tool and community reporting board, "
    "not a government portal or corruption detector."
)

# Main App Title & 3-Tab Layout
st.title("🛡️ Civic-Watchdog — Citizen Infrastructure & Neighbourhood Reports")
st.markdown(
    '<div class="sub-header">Understand public infrastructure projects and report neighbourhood needs.</div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs([
    "📋 Public Project Watch",
    "🏘️ Your Neighbourhood Needs",
    "📊 Civic Analytics Dashboard",
])

# TAB 1: PUBLIC PROJECT WATCH
with tab1:
    st.header("Public Municipal Project Directory")
    st.caption("Inspect indexed municipal tenders or upload a new PDF notice for AI extraction and screening checks.")

    with st.expander("➕ Upload & Analyze Municipal Tender PDF", expanded=True):
        uploaded_file = st.file_uploader("Upload Municipal Tender PDF Document", type=["pdf"])
        if uploaded_file is not None:
            if st.button("🚀 Process Tender PDF", type="primary"):
                with st.spinner("Extracting text pages, running AI extraction, and executing screening checks..."):
                    os.makedirs("temp_uploads", exist_ok=True)
                    temp_path = os.path.join("temp_uploads", uploaded_file.name)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    s3_uri = upload_pdf_to_s3(temp_path, uploaded_file.name)
                    ingest_res = fetch_tender_pdf(temp_path)
                    extracted_proj = validate_project_record(extract_project_details(ingest_res))
                    final_proj = validate_project_record(run_checks(extracted_proj))

                    st.session_state.stored_projects = [
                        p for p in st.session_state.stored_projects if p.get("title") != final_proj.get("title")
                    ]
                    st.session_state.stored_projects.insert(0, final_proj)

                    if s3_uri:
                        st.success(f"Successfully processed {uploaded_file.name} and archived to AWS S3 ({s3_uri})!")
                    else:
                        st.success(f"Successfully processed {uploaded_file.name}!")
                    st.rerun()

    filtered_projects = st.session_state.stored_projects
    if locality_filter != "All Localities":
        filtered_projects = [p for p in filtered_projects if p.get("locality") == locality_filter]

    st.subheader(f"Active Project Records ({len(filtered_projects)})")

    for proj in filtered_projects:
        with st.container(border=True):
            st.markdown(f"### 🏗️ {proj.get('title')}")
            col1, col2, col3 = st.columns(3)
            budget = proj.get("stated_budget_inr", 0)
            col1.metric("Stated Budget (INR)", f"₹{budget:,.0f}" if budget else "Not stated")
            col2.metric("Locality", proj.get("locality", "Not stated"))
            col3.metric("Authority", proj.get("authority", "Not stated"))

            st.markdown("**Plain-English Summary:**")
            st.info(proj.get("summary", {}).get("en", "No summary available."))

            with st.expander("📑 View Extracted Specifications & Timelines"):
                st.json(proj.get("extracted_fields", {}))

            st.markdown("**⚠️ What Should I Check? (Audit Screening Flags):**")
            checks = proj.get("checks", list())
            if checks:
                for chk in checks:
                    chk_label = str(chk.get("check_type", "notice")).replace("_", " ").title()
                    explanation = chk.get("explanation", "Requires human review.")
                    pages = chk.get("source_pages_reviewed") or list()
                    page_note = f" (Source Pages: {', '.join(map(str, pages))})" if pages else ""
                    st.warning(f"🚩 **{chk_label}:** {explanation}{page_note}")
            else:
                st.success("✅ No rule-based screening issues flagged in checks run.")
# TAB 2: YOUR NEIGHBOURHOOD NEEDS
with tab2:
    st.header("Is something in your area not working? Tell us what needs attention.")
    st.caption(
        "Civic-Watchdog is not an emergency service or an official municipal complaint portal. "
        "Please do not include personal phone numbers, home addresses, or faces."
    )

    col_form, col_feed = st.columns([1, 1])

    with col_form:
        st.subheader("📝 Submit Issue Report")
        with st.form("citizen_form", clear_on_submit=True):
            cat_label = st.selectbox(
                "Issue Category",
                ["Drainage", "Potholes", "Garbage", "Water", "Streetlights", "Other"],
            )
            loc = st.text_input("Locality / Area", value="Chikhloli, Ambernath")
            land = st.text_input("Landmark / Nearest Street", placeholder="e.g., Near Railway Crossing")
            desc = st.text_area("Detailed Description of Problem", placeholder="Describe the issue in your own words...")
            dur = st.selectbox(
                "Duration of Issue",
                ["recently", "several_weeks", "several_months", "ongoing"],
            )

            submitted = st.form_submit_button("📢 Submit Report to Civic-Watchdog", type="primary")
            if submitted:
                if desc.strip() and loc.strip():
                    category_map = {
                        "Drainage": "drainage",
                        "Potholes": "roads_and_potholes",
                        "Garbage": "garbage",
                        "Water": "water_supply",
                        "Streetlights": "streetlights",
                        "Other": "other",
                    }
                    new_rep = save_citizen_report(
                        category=category_map.get(cat_label, "other"),
                        locality=loc.strip(),
                        landmark=land.strip(),
                        description=desc.strip(),
                        duration=dur,
                    )
                    st.toast("Report saved in Civic-Watchdog", icon="✅")
                    st.success(f"Report saved in Civic-Watchdog! ID: **{new_rep.get('report_id')}**")
                else:
                    st.error("Please enter both a locality and a description before submitting.")

    with col_feed:
        st.subheader("📢 Live Community Report Feed")
        reports = load_citizen_reports()
        if reports:
            for r in reversed(reports):
                rep_id = r.get("report_id", "NEED-XXXX")
                cat_text = str(r.get("category", "other")).replace("_", " ").title()
                loc_text = r.get("locality", "Unknown")
                land_text = r.get("landmark") or "N/A"
                desc_text = r.get("description", "")
                status_text = r.get("status", "received_by_civic_watchdog")
                date_text = str(r.get("submitted_at", ""))[:10]

                with st.container(border=True):
                    st.markdown(f"**📍 {rep_id} — {cat_text}** ({loc_text})")
                    st.write(f"**Landmark:** {land_text}")
                    st.write(desc_text)
                    st.caption(f"Status: `{status_text}` | Submitted: {date_text}")
        else:
            st.info("No neighbourhood reports submitted yet. Use the form on the left to add one.")

# TAB 3: VISUAL ANALYTICS DASHBOARD
with tab3:
    st.header("📊 Civic Budget & Community Issue Analytics")
    st.caption("Visual comparison of documented project budgets and resident-reported neighbourhood needs.")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Municipal Budget Allocation by Project")
        chart_data = [
            {
                "Project": (p.get("title", "Project")[:32] + "...") if len(p.get("title", "")) > 32 else p.get("title", "Project"),
                "Category": p.get("work_category", "General"),
                "Budget (INR)": p.get("stated_budget_inr", 0),
            }
            for p in st.session_state.stored_projects
        ]
        if chart_data:
            fig1 = px.bar(
                chart_data,
                x="Project",
                y="Budget (INR)",
                color="Category",
                title="Stated Tender Budgets (INR)",
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Upload or process a tender PDF in Tab 1 to view budget analytics.")

    with col_chart2:
        st.subheader("Neighbourhood Issues by Category")
        reps = load_citizen_reports()
        cat_counts: Dict[str, int] = dict()
        for r in reps:
            c = str(r.get("category", "other")).replace("_", " ").title()
            cat_counts[c] = cat_counts.get(c, 0) + 1

        donut_data = [{"Category": k, "Count": v} for k, v in cat_counts.items()]
        if donut_data:
            fig2 = px.pie(
                donut_data,
                names="Category",
                values="Count",
                hole=0.45,
                title="Reported Community Needs Proportion",
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Submit reports in Tab 2 to view category proportions.")
