"""
extractor.py - AI Document Intelligence & Extraction Module
Civic-Watchdog Project (Teammate 2)

Extracts structured civic project metadata and a 2-sentence English summary
from ingestion output (`ingestion.py`) using OpenAI when `OPENAI_API_KEY` is
configured, with a deterministic regex/rule-based fallback for offline use.
Missing values remain `None` (`null` in JSON) instead of being invented.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from typing import Any


def _combine_pages_text(pages_text: list[dict[str, Any]]) -> str:
    """Join text across extracted tender pages into a single searchable string."""
    parts: list[str] = []
    for page in pages_text:
        if isinstance(page, dict):
            text = page.get("text", "")
            if text:
                parts.append(str(text).strip())
    return "\n".join(parts)


def _parse_int_amount(raw_value: Any) -> int | None:
    """Convert numeric strings or numbers with commas into an integer, or None."""
    if raw_value is None or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value) if raw_value.is_integer() else int(round(raw_value))
    if isinstance(raw_value, str):
        cleaned = re.sub(r"[^\d]", "", raw_value)
        if cleaned:
            return int(cleaned)
    return None


def _clean_optional_str(value: Any) -> str | None:
    """Return a trimmed string or None if empty/missing/null-like."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "n/a", "na", "not mentioned", "not specified"}:
        return None
    return text


def _ensure_two_sentence_summary(
    raw_summary: str | None,
    title: str | None,
    authority: str | None,
    locality: str | None,
    stated_budget_inr: int | None,
    completion_period: str | None,
) -> str:
    """
    Build or normalize a concise 2-sentence English summary without inventing facts.
    """
    if raw_summary:
        cleaned = re.sub(r"\s+", " ", raw_summary.strip())
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) >= 2:
            s1 = sentences[0] if sentences[0].endswith((".", "!", "?")) else f"{sentences[0]}."
            s2 = sentences[1] if sentences[1].endswith((".", "!", "?")) else f"{sentences[1]}."
            return f"{s1} {s2}"

    # Deterministic fallback summary built strictly from available fields
    project_label = title or "This public tender"
    where_part = f" in {locality}" if locality else ""
    who_part = f" overseen by {authority}" if authority else ""
    first_sentence = f"{project_label}{where_part}{who_part}."

    details: list[str] = []
    if stated_budget_inr is not None:
        details.append(f"The stated budget is INR {stated_budget_inr:,}")
    if completion_period:
        details.append(f"the completion period is {completion_period}")

    if details:
        second_sentence = f"{'; '.join(details).capitalize()}."
    else:
        second_sentence = "Budget and completion timeline are not specified in the provided text."

    return f"{first_sentence} {second_sentence}"


def _offline_rule_extract(full_text: str) -> dict[str, Any]:
    """
    Offline regex and rule-based extractor used when no LLM API key is set
    or if an LLM call fails. Returns `None` for any field not found in text.
    """
    # 1. Title / Name of Work
    title_match = re.search(
        r"(?:Name of Work|Subject|Work\s*Title)\s*[:\-]\s*([^\n]+)",
        full_text,
        re.IGNORECASE,
    )
    title = _clean_optional_str(title_match.group(1)) if title_match else None
    if title:
        title = re.sub(r"\s+at\s+[A-Z][A-Za-z\s,]+$", "", title).strip(" .")

    # 2. Authority
    authority_match = re.search(
        r"([A-Za-z][A-Za-z\s&.-]{2,60}?(?:Municipal Council|Municipal Corporation|Corporation|Authority|Board|Department|Panchayat))",
        full_text,
        re.IGNORECASE,
    )
    authority = _clean_optional_str(authority_match.group(1)) if authority_match else None

    # 3. Locality
    locality_match = re.search(
        r"\b(?:at|in|locality|area|ward)\s*[:\-]?\s*([A-Z][A-Za-z0-9\s,.-]{2,50}?)(?=[.\n;]|$)",
        full_text,
    )
    locality = _clean_optional_str(locality_match.group(1).rstrip(" .")) if locality_match else None

    # 4. Work category (simple keyword rules)
    lower_text = full_text.lower()
    if any(k in lower_text for k in ("road", "drainage", "rcc", "asphalt", "culvert", "footpath")):
        work_category = "Roads & Drainage"
    elif any(k in lower_text for k in ("water", "pipeline", "reservoir", "supply", "borewell")):
        work_category = "Water Supply"
    elif any(k in lower_text for k in ("hospital", "clinic", "health", "school", "building", "civil")):
        work_category = "Civil & Public Infrastructure"
    elif any(k in lower_text for k in ("street light", "streetlight", "electrical", "solar")):
        work_category = "Streetlights & Electrical"
    else:
        work_category = None

    # 5. Stated budget in INR
    budget_match = re.search(
        r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)",
        full_text,
        re.IGNORECASE,
    )
    stated_budget_inr = _parse_int_amount(budget_match.group(1)) if budget_match else None

    # 6. Completion period
    period_match = re.search(
        r"(?:Completion\s*Period|Time\s*Limit|Period\s*of\s*Completion)\s*[:\-]?\s*([^\n.;]+)",
        full_text,
        re.IGNORECASE,
    )
    completion_period = _clean_optional_str(period_match.group(1)) if period_match else None

    # 7. Defect liability period (None if not mentioned)
    dlp_match = re.search(
        r"(?:defect\s*liability\s*period|DLP)\s*(?:of|is|:|-)?\s*([^\n.;]+)",
        full_text,
        re.IGNORECASE,
    )
    defect_liability_period = _clean_optional_str(dlp_match.group(1)) if dlp_match else None

    return {
        "title": title,
        "authority": authority,
        "locality": locality,
        "work_category": work_category,
        "stated_budget_inr": stated_budget_inr,
        "completion_period": completion_period,
        "defect_liability_period": defect_liability_period,
        "summary_en": None,
    }


def _llm_extract(full_text: str) -> dict[str, Any] | None:
    """
    Extract structured fields using OpenAI when `OPENAI_API_KEY` is present.
    Returns None if the key is missing or an error occurs so the caller can fall back.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not full_text.strip():
        return None

    try:
        from openai import OpenAI  # Imported lazily so offline runs never require API calls
    except ImportError:
        return None

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a strict civic tender data extractor for Civic-Watchdog. "
        "Extract fields ONLY from the provided tender text. Never guess or invent facts, "
        "budgets, locations, authorities, or periods. If a field is absent, return null. "
        "Write `summary_en` as exactly 2 clear English sentences grounded strictly in the text."
    )

    user_prompt = (
        "Return a JSON object with keys: "
        "title, authority, locality, work_category, stated_budget_inr, "
        "completion_period, defect_liability_period, summary_en.\n\n"
        f"Tender Text:\n{full_text[:12000]}"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            return None
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        return {
            "title": _clean_optional_str(parsed.get("title")),
            "authority": _clean_optional_str(parsed.get("authority")),
            "locality": _clean_optional_str(parsed.get("locality")),
            "work_category": _clean_optional_str(parsed.get("work_category")),
            "stated_budget_inr": _parse_int_amount(parsed.get("stated_budget_inr")),
            "completion_period": _clean_optional_str(parsed.get("completion_period")),
            "defect_liability_period": _clean_optional_str(parsed.get("defect_liability_period")),
            "summary_en": _clean_optional_str(parsed.get("summary_en")),
        }
    except Exception:
        return None


def extract_project_details(ingestion_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Extract structured project data from `ingestion.py` output.

    Uses OpenAI when `OPENAI_API_KEY` is set, and falls back seamlessly to
    offline regex/rule parsing when no API key is configured.
    """
    safe_ingestion = ingestion_dict if isinstance(ingestion_dict, dict) else {}
    document_name = _clean_optional_str(safe_ingestion.get("document_name")) or "Unknown_Tender.pdf"
    pages_text = safe_ingestion.get("pages_text")
    pages = pages_text if isinstance(pages_text, list) else []

    full_text = _combine_pages_text(pages)
    rule_data = _offline_rule_extract(full_text)
    llm_data = _llm_extract(full_text)

    # Prefer LLM values when present, otherwise use offline rule results (or None)
    def pick(key: str) -> Any:
        if llm_data and llm_data.get(key) is not None:
            return llm_data[key]
        return rule_data.get(key)

    title = pick("title")
    authority = pick("authority")
    locality = pick("locality")
    work_category = pick("work_category")
    stated_budget_inr = pick("stated_budget_inr")
    completion_period = pick("completion_period")
    defect_liability_period = pick("defect_liability_period")
    raw_summary = llm_data.get("summary_en") if llm_data else None

    summary_en = _ensure_two_sentence_summary(
        raw_summary=raw_summary,
        title=title,
        authority=authority,
        locality=locality,
        stated_budget_inr=stated_budget_inr,
        completion_period=completion_period,
    )

    page_references = [
        p.get("page_number")
        for p in pages
        if isinstance(p, dict) and p.get("page_number") is not None
    ]

    retrieved_at = (
        _clean_optional_str(safe_ingestion.get("retrieved_at"))
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    return {
        "project_id": _clean_optional_str(safe_ingestion.get("project_id")) or "CW-PROJ-001",
        "title": title,
        "authority": authority,
        "locality": locality,
        "work_category": work_category,
        "stated_budget_inr": stated_budget_inr,
        "currency": "INR",
        "source": {
            "document_name": document_name,
            "source_page_url": _clean_optional_str(safe_ingestion.get("source_page_url")),
            "pdf_url": _clean_optional_str(safe_ingestion.get("pdf_url")) or document_name,
            "retrieved_at": retrieved_at,
            "page_references": page_references,
        },
        "extracted_fields": {
            "completion_period": completion_period,
            "defect_liability_period": defect_liability_period,
        },
        "summary": {
            "en": summary_en,
        },
        "checks": [],
        "record_status": "needs_review",
    }


if __name__ == "__main__":
    sample_ingestion = {
        "document_name": "Tender_Chikhloli_Road_Drainage.pdf",
        "source_page_url": "https://example.com/tenders/088",
        "pdf_url": "sample_data/Tender_Chikhloli_Road_Drainage.pdf",
        "retrieved_at": "2026-11-23T22:00:00Z",
        "pages_text": [
            {
                "page_number": 1,
                "text": (
                    "Ambernath Municipal Council. Name of Work: Construction of RCC Drainage "
                    "and Road Repair at Chikhloli, Ambernath."
                ),
            },
            {
                "page_number": 2,
                "text": "Estimated Cost: INR 6,626,532. Completion Period: 6 Months.",
            },
        ],
    }

    result = extract_project_details(sample_ingestion)
    print(json.dumps(result, indent=2))
    print("Extractor Module Test PASSED!")
