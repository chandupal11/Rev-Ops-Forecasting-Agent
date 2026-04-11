"""Render a `ForecastReport` as Markdown."""

from __future__ import annotations

from .models import FlagSeverity, ForecastReport


SEV_ICON = {
    FlagSeverity.CRITICAL: "[!]",
    FlagSeverity.WARN: "[*]",
    FlagSeverity.INFO: "[i]",
}


def render_markdown(report: ForecastReport) -> str:
    L = report.leader
    R = report.rollup
    lines = [
        f"# Forecast — {L.name} — {report.quarter_label}",
        "",
        f"_Generated {report.as_of.strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Rollup",
        "",
        "| Category | Amount |",
        "|---|---|",
        f"| Closed Won | ${R.closed_won:,.0f} |",
        f"| Commit | ${R.commit:,.0f} |",
        f"| Best Case | ${R.best_case:,.0f} |",
        f"| Pipeline | ${R.pipeline:,.0f} |",
        f"| **Committed total (CW+Commit)** | **${R.committed_total:,.0f}** |",
        f"| Best case total | ${R.best_case_total:,.0f} |",
        f"| Quota | ${L.quarter_quota:,.0f} |",
        f"| Gap to quota (committed) | ${report.gap_to_quota:,.0f} |",
        "",
    ]

    if report.narrative:
        lines += ["## Narrative", "", report.narrative, ""]

    if report.top_risks:
        lines += ["## Top Risks", ""]
        for r in report.top_risks:
            lines.append(f"- {r}")
        lines.append("")

    lines += ["## Deals", ""]
    for d in report.deals:
        update = d.update
        leader_call = (
            update.verbal_category.value
            if update and update.verbal_category
            else "—"
        )
        confidence = (
            str(update.leader_confidence)
            if update and update.leader_confidence
            else "—"
        )
        lines.append(f"### {d.account} — {d.name}")
        lines.append("")
        lines.append(f"- SFDC amount: ${d.sfdc_amount:,.0f}")
        lines.append(f"- SFDC stage: {d.sfdc_stage.value}")
        lines.append(f"- SFDC category: {d.sfdc_category.value}")
        lines.append(f"- SFDC close date: {d.sfdc_close_date.isoformat()}")
        lines.append(f"- Leader call: {leader_call}")
        lines.append(f"- Leader confidence: {confidence}")
        if update and update.verbal_close_date:
            lines.append(
                f"- Verbal close date: {update.verbal_close_date.isoformat()}"
            )
        if update and update.verbal_amount is not None:
            lines.append(f"- Verbal amount: ${update.verbal_amount:,.0f}")
        if update and update.risks:
            lines.append(f"- Risks: {', '.join(update.risks)}")
        if update and update.next_steps:
            lines.append(f"- Next steps: {', '.join(update.next_steps)}")
        if update and update.notes:
            lines.append(f"- Notes: {update.notes}")
        if d.flags:
            lines.append("- Flags:")
            for f in d.flags:
                lines.append(
                    f"  - {SEV_ICON[f.severity]} `{f.code}`: {f.message}"
                )
        lines.append("")

    return "\n".join(lines)
