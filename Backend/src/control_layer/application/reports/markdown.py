from __future__ import annotations

from datetime import datetime
from typing import Any

from control_layer.application.reports.owasp_catalog import OWASP_CATALOG


def render_markdown(
    *,
    generated_at: datetime,
    period: str,
    summary: dict[str, Any],
    top_rules: list[dict[str, Any]],
    top_users: list[dict[str, Any]],
    owasp_coverage: list[Any],
    recommendations: list[str],
) -> str:
    lines = [
        "# Security report",
        "",
        f"Generated at {generated_at.isoformat()} for period `{period}`.",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- **{key}**: {value}")

    lines += ["", "## Top rules", ""]
    if top_rules:
        lines.append("| Rule | Count | Stage |")
        lines.append("|---|---|---|")
        for row in top_rules:
            lines.append(f"| {row['rule_id']} | {row['count']} | {row.get('stage') or '-'} |")
    else:
        lines.append("No rule violations recorded in this period.")

    lines += ["", "## Top users", ""]
    if top_users:
        lines.append("| User | Blocked | Masked | Escalated |")
        lines.append("|---|---|---|---|")
        for row in top_users:
            lines.append(
                f"| {row['name']} | {row['blocked']} | {row['masked']} | {row['escalated']} |"
            )
    else:
        lines.append("No user activity recorded in this period.")

    lines += ["", "## OWASP coverage", ""]
    lines.append(f"Mapping of every {len(OWASP_CATALOG)} LLM/Agentic OWASP control to "
                 "events observed in this period.")
    lines.append("")
    lines.append("| ID | Title | Events | Status |")
    lines.append("|---|---|---|---|")
    for row in owasp_coverage:
        lines.append(f"| {row.id} | {row.title} | {row.events} | {row.status} |")

    lines += ["", "## Recommendations", ""]
    if recommendations:
        for rec in recommendations:
            lines.append(f"- {rec}")
    else:
        lines.append("No action items identified for this period.")

    return "\n".join(lines) + "\n"
