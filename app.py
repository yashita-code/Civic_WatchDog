"""
app.py - Main Streamlit Web Application & Integration Engine
Civic-Watchdog Project
"""

import os
import streamlit as st
from ingestion import fetch_tender_pdf
from extractor import extract_project_details
from rules_and_reports import run_checks, save_citizen_report, load_citizen_reports

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Civic-Watchdog",
    page_icon="🛡️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #1E3A8A;}
    .sub-header {font-size: 1.1rem; color: #4B5563; margin-bottom: 20px;}
    .card {background-color: #F3F4F6; padding: 15px; border-radius: 10px; margin-bottom: 15px;}
    .flag-badge {background-color: #FEF3C7; color: #92400E; padding: 6px 12px; border-radius: 6px; font-weight: 600;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# App Title & Subtitle
# -----------------------------------------------------------------------------
st.title("🛡️ Civic-Watchdog — Citizen Infrastructure & Neighbourhood Reports")
st.markdown(
    '<div class="sub-header">Understand public infrastructure projects and report neighbourhood needs.</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Tabs Navigation
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📋 Public Project Watch", "🏘️ Your Neighbourhood Needs"])

# =============================================================================
# TAB 1: PUBLIC PROJECT WATCH
# =============================================================================
with tab1:
    st.subheader("Public Infrastructure Project Inspection")
    col_input, col_display = st.columns([1, 2])

    with col_input:
        st.markdown("### 📥 Select Document")
        uploaded_file = st.file_uploader("Upload Tender PDF", type=["pdf"])
        process_sample = st.button(
            "🚀 Process Sample Tender",
            use_container_width=True,
        )

    with col_display:
        if process_sample or uploaded_file:
            st.markdown("### 📊 Extracted Project Accountability Record")

            with st.spinner("Parsing document and running AI extraction..."):
                # Save uploaded PDF temporarily so fetch_tender_pdf receives a valid file path
                pdf_path = None
                if uploaded_file is not None:
                    os.makedirs("temp_uploads", exist_ok=True)
                    pdf_path = os.path.join("temp_uploads", uploaded_file.name)
                    with open(pdf_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                # 1. Ingestion
                ingest_data = fetch_tender_pdf(pdf_path)

                # 2. Extraction
                extracted_project = extract_project_details(ingest_data)

                # 3. Rule Engine (returns updated project dict with "checks" populated)
                final_project = run_checks(extracted_project)

            # Display Results
            st.success("Document Analyzed Successfully!")
            if process_sample and not uploaded_file:
                st.caption("📂 *Using cached sample tender document (Chikhloli, Ambernath).*")

            st.markdown(f"#### **{final_project.get('title', 'Not found in document')}**")

            budget_val = final_project.get("stated_budget_inr")
            budget_str = f"INR {budget_val:,}" if isinstance(budget_val, (int, float)) else "Not found in document"

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Stated Budget", budget_str)
            col_b.metric("Locality", final_project.get("locality") or "Not found in document")
            col_c.metric("Authority", final_project.get("authority") or "Not found in document")

            st.markdown("##### **Plain-English Summary**")
            summary_en = (final_project.get("summary") or {}).get("en") or "Not found in document."
            st.info(summary_en)

            st.markdown("##### **Extracted Fields**")
            st.json(final_project.get("extracted_fields", {}))

            # Red Flag Warning Section
            st.markdown("##### **⚠️ What Should I Check? (Audit Screening Flags)**")
            checks = final_project.get("checks", [])
            if checks:
                for check in checks:
                    check_type = str(check.get("check_type", "check")).upper()
                    explanation = check.get("explanation", "Requires human review.")
                    pages = check.get("source_pages_reviewed", [])
                    if check.get("requires_human_review"):
                        st.warning(
                            f"**[{check_type}]**: {explanation} (Source Pages: {pages})"
                        )
                    else:
                        st.success(f"**[{check_type}]**: {explanation}")
            else:
                st.success("No rule-based issues flagged in the checks run.")
        else:
            st.info("👈 Click **Process Sample Tender** or upload a PDF to inspect project promises and rule checks.")

# =============================================================================
# TAB 2: YOUR NEIGHBOURHOOD NEEDS
# =============================================================================
with tab2:
    st.subheader("Is something in your area not working? Tell us what needs attention.")
    st.caption(
        "Civic-Watchdog is not an emergency service or an official municipal complaint portal. "
        "Please do not include personal phone numbers, home addresses, or faces."
    )

    col_form, col_feed = st.columns([1, 1])

    with col_form:
        st.markdown("### 📝 Submit Issue")
        with st.form("citizen_report_form", clear_on_submit=True):
            category_display = st.selectbox(
                "Category",
                ["Drainage", "Potholes", "Garbage", "Water", "Streetlights", "Other"],
            )
            locality = st.text_input("Locality", value="Chikhloli, Ambernath")
            landmark = st.text_input("Landmark", placeholder="e.g., Near Railway Crossing")
            description = st.text_area(
                "Description",
                placeholder="Describe the issue in your own words...",
            )
            duration = st.selectbox(
                "How long has this been happening?",
                ["recently", "several_weeks", "several_months", "ongoing"],
            )

            submitted = st.form_submit_button("Submit Report to Civic-Watchdog")

            if submitted:
                if description.strip() and locality.strip():
                    # Map UI labels cleanly to schema category values
                    category_map = {
                        "Drainage": "drainage",
                        "Potholes": "roads_and_potholes",
                        "Garbage": "garbage",
                        "Water": "water_supply",
                        "Streetlights": "streetlights",
                        "Other": "other",
                    }
                    new_report = save_citizen_report(
                        category=category_map.get(category_display, "other"),
                        locality=locality.strip(),
                        landmark=landmark.strip(),
                        description=description.strip(),
                        duration=duration,
                    )
                    st.toast("Report saved in Civic-Watchdog", icon="✅")
                    st.success(
                        f"✅ Report saved in Civic-Watchdog! Report ID: **{new_report['report_id']}**"
                    )
                else:
                    st.error("Please provide both a locality and a brief description of the issue.")

    with col_feed:
        st.markdown("### 📢 Neighbourhood Reports Feed")
        reports = load_citizen_reports()
        if reports:
            for r in reversed(reports):
                rep_id = r.get("report_id", "NEED-XXXX")
                cat = str(r.get("category", "other")).upper()
                loc = r.get("locality", "Unknown")
                with st.expander(f"📍 {rep_id} — {cat} ({loc})", expanded=True):
                    st.write(f"**Landmark**: {r.get('landmark') or 'N/A'}")
                    st.write(f"**Description**: {r.get('description', '')}")
                    st.caption(
                        f"Status: {r.get('status', 'received_by_civic_watchdog')} | "
                        f"Submitted: {str(r.get('submitted_at', ''))[:10]}"
                    )
        else:
            st.info("No neighbourhood reports submitted yet. Use the form on the left to submit the first one!")
