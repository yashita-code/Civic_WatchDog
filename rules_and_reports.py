"""Explainable project checks and local citizen-report storage."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DATA_FILE = Path("project_data.json")
ALLOWED_CATEGORIES = {"drainage", "potholes", "garbage"}
BENCHMARK_BUDGET_INR = 5_000_000


def _next_check_id(checks: list[dict[str, Any]]) -> str:
    """Return a check ID that does not collide with existing check IDs."""
    highest_id = 0
    for check in checks:
        check_id = check.get("check_id")
        if isinstance(check_id, str) and check_id.startswith("CHK-"):
            try:
                highest_id = max(highest_id, int(check_id[4:]))
            except ValueError:
                continue
    return f"CHK-{highest_id + 1:03d}"


def _make_check(
    checks: list[dict[str, Any]],
    check_type: str,
    severity: str,
    field_checked: str,
    result: str,
    explanation: str,
) -> dict[str, Any]:
    """Create a check record using the established check_data.json shape."""
    check = {
        "check_id": _next_check_id(checks),
        "check_type": check_type,
        "severity": severity,
        "field_checked": field_checked,
        "result": result,
        "explanation": explanation,
        "source_pages_reviewed": [],
        "requires_human_review": True,
    }
    checks.append(check)
    return check


def _load_stored_projects(filepath: Path) -> list[dict[str, Any]]:
    """Load stored project records; a missing file means no records are available."""
    if not filepath.exists():
        return []

    with filepath.open("r", encoding="utf-8") as file:
        stored_projects = json.load(file)

    if not isinstance(stored_projects, list) or not all(
        isinstance(project, dict) for project in stored_projects
    ):
        raise ValueError(f"{filepath} must contain a JSON list of project records.")
    return stored_projects


def run_checks(project_json):
    """Append any audit findings to one project record and return that record."""
    if not isinstance(project_json, dict):
        raise TypeError("project_json must be a project dictionary.")

    checks = project_json.setdefault("checks", [])
    if not isinstance(checks, list) or not all(isinstance(item, dict) for item in checks):
        raise ValueError("project_json['checks'] must be a list of check dictionaries.")

    extracted_fields = project_json.get("extracted_fields", project_json)
    if not isinstance(extracted_fields, dict):
        raise ValueError("project_json['extracted_fields'] must be a dictionary.")

    for field in ("completion_period", "defect_liability_period"):
        if extracted_fields.get(field) is None:
            _make_check(
                checks,
                check_type="missing_field",
                severity="information_gap",
                field_checked=field,
                result="not_found",
                explanation=f"No {field.replace('_', ' ')} was provided for this project.",
            )

    stated_budget = project_json.get("stated_budget_inr")
    if stated_budget is not None:
        if isinstance(stated_budget, bool) or not isinstance(stated_budget, (int, float)):
            raise ValueError("stated_budget_inr must be a number or None.")
        if stated_budget > BENCHMARK_BUDGET_INR:
            _make_check(
                checks,
                check_type="budget_threshold",
                severity="benchmark_review",
                field_checked="stated_budget_inr",
                result="above_threshold",
                explanation=(
                    "The stated budget exceeds 5,000,000 INR and is flagged for "
                    "benchmark review."
                ),
            )

    category = project_json.get("category")
    locality = project_json.get("locality")
    if isinstance(category, str) and category.strip() and isinstance(locality, str) and locality.strip():
        normalized_category = category.strip().casefold()
        normalized_locality = locality.strip().casefold()
        stored_projects = _load_stored_projects(PROJECT_DATA_FILE)
        has_match = any(
            isinstance(project.get("category"), str)
            and isinstance(project.get("locality"), str)
            and project["category"].strip().casefold() == normalized_category
            and project["locality"].strip().casefold() == normalized_locality
            for project in stored_projects
        )
        if has_match:
            _make_check(
                checks,
                check_type="duplicate_candidate",
                severity="potential_overlap",
                field_checked="category, locality",
                result="potential_match",
                explanation=(
                    "A stored project has the same category and locality; "
                    "review for possible overlap."
                ),
            )

    return project_json


def _validated_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def load_citizen_reports(filepath="citizen_report.json"):
    """Read saved citizen reports, returning an empty list if no file exists."""
    report_path = Path(filepath)
    if not report_path.exists():
        return []

    with report_path.open("r", encoding="utf-8") as file:
        reports = json.load(file)

    # Accept the current single-report JSON object as well as a list of reports.
    if isinstance(reports, dict):
        return [reports]
    if not isinstance(reports, list) or not all(isinstance(report, dict) for report in reports):
        raise ValueError(f"{report_path} must contain a JSON report object or list of report records.")
    return reports


def save_citizen_report(
    category,
    locality,
    landmark,
    description,
    duration="several_weeks",
    impact="Waterlogging",
    filepath="citizen_report.json",
):
    """Validate, save, and return a citizen report."""
    validated_category = _validated_text(category, "category").casefold()
    if validated_category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
        raise ValueError(f"category must be one of: {allowed}.")

    validated_locality = _validated_text(locality, "locality")
    validated_landmark = _validated_text(landmark, "landmark")
    validated_description = _validated_text(description, "description")
    validated_duration = _validated_text(duration, "duration")
    validated_impact = _validated_text(impact, "impact")

    reports = load_citizen_reports(filepath)
    report_number = 0
    for report in reports:
        report_id = report.get("report_id")
        if isinstance(report_id, str) and report_id.startswith("NEED-"):
            try:
                report_number = max(report_number, int(report_id[5:]))
            except ValueError:
                continue

    report = {
        "report_id": f"NEED-{report_number + 1:04d}",
        "category": validated_category,
        "locality": validated_locality,
        "landmark": validated_landmark,
        "description": validated_description,
        "duration": validated_duration,
        "impact": validated_impact,
        "public_display_consent": False,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "status": "received_by_civic_watchdog",
    }

    reports.append(report)
    report_path = Path(filepath)
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(reports, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return report


if __name__ == "__main__":
    # Test Rule Engine and Citizen Intake
    print("Testing Rules and Reports Module...")
    sample_proj = {
        "project_id": "CW-PROJ-001",
        "stated_budget_inr": 6626532,
        "extracted_fields": {"completion_period": "6 Months", "defect_liability_period": None},
        "source": {"page_references": [1, 2, 3]},
    }

    checked_proj = run_checks(sample_proj)
    print(f"Generated {len(checked_proj['checks'])} Audit Checks.")

    report = save_citizen_report(
        category="drainage",
        locality="Chikhloli, Ambernath",
        landmark="Near Railway Crossing",
        description="Drain overflow after heavy rain.",
    )
    print(f"Saved Report ID: {report['report_id']}")
    print("Rules and Reports Module Test PASSED!")
