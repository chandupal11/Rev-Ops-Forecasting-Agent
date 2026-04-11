"""Synthesize a `ForecastReport` from a briefing + leader updates.

The rollup and per-deal summaries are computed deterministically. The
executive narrative is written by Claude on top of the structured rollup —
set `skip_narrative=True` to get just the deterministic output (useful
for tests and for running without an Anthropic API key).
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

import anthropic

from ..briefing import LeaderBriefing
from ..models import (
    DealSummary,
    DealUpdate,
    FlagSeverity,
    ForecastCategory,
    ForecastReport,
    ForecastRollup,
    Opportunity,
)
from .prompts import SYNTHESIZER_SYSTEM_PROMPT
from .reconciliation import reconcile


DEFAULT_MODEL = os.getenv("REVOPS_SYNTHESIZER_MODEL", "claude-sonnet-4-6")


def _effective_category(
    opp: Opportunity, update: Optional[DealUpdate]
) -> ForecastCategory:
    if update and update.verbal_category:
        return update.verbal_category
    return opp.forecast_category


def _effective_amount(opp: Opportunity, update: Optional[DealUpdate]) -> float:
    if update and update.verbal_amount is not None:
        return update.verbal_amount
    return opp.amount


def _build_rollup(
    briefing: LeaderBriefing,
    updates: dict[str, DealUpdate],
) -> ForecastRollup:
    rollup = ForecastRollup()
    for o in briefing.opportunities:
        update = updates.get(o.id)
        cat = _effective_category(o, update)
        amt = _effective_amount(o, update)
        if cat == ForecastCategory.CLOSED_WON:
            rollup.closed_won += amt
        elif cat == ForecastCategory.COMMIT:
            rollup.commit += amt
        elif cat == ForecastCategory.BEST_CASE:
            rollup.best_case += amt
        elif cat == ForecastCategory.PIPELINE:
            rollup.pipeline += amt
    return rollup


def _top_risks(deals: list[DealSummary]) -> list[str]:
    severity_score = {
        FlagSeverity.CRITICAL: 3,
        FlagSeverity.WARN: 2,
        FlagSeverity.INFO: 1,
    }
    risks: list[tuple[float, str]] = []
    for d in deals:
        for f in d.flags:
            score = severity_score[f.severity] * (d.sfdc_amount / 1000.0)
            risks.append((score, f"{d.account}: {f.message}"))
    risks.sort(key=lambda r: -r[0])

    seen: set[str] = set()
    result: list[str] = []
    for _, msg in risks:
        if msg in seen:
            continue
        seen.add(msg)
        result.append(msg)
        if len(result) == 5:
            break
    return result


def _render_context_for_narrative(
    briefing: LeaderBriefing,
    rollup: ForecastRollup,
    deals: list[DealSummary],
    gap_to_quota: float,
) -> str:
    lines = [
        f"Leader: {briefing.leader.name} ({briefing.leader.team})",
        f"Quarter: {briefing.quarter_label}",
        f"Quota: ${briefing.leader.quarter_quota:,.0f}",
        "",
        "Rollup (after leader's updates):",
        f"- Closed Won: ${rollup.closed_won:,.0f}",
        f"- Commit: ${rollup.commit:,.0f}",
        f"- Best Case: ${rollup.best_case:,.0f}",
        f"- Pipeline: ${rollup.pipeline:,.0f}",
        f"- Committed total (Closed+Commit): ${rollup.committed_total:,.0f}",
        f"- Best case total: ${rollup.best_case_total:,.0f}",
        f"- Gap to quota (committed basis): ${gap_to_quota:,.0f}",
        "",
        "Per-deal status:",
    ]
    for d in deals:
        if d.update and d.update.verbal_category:
            leader_call = d.update.verbal_category.value
        else:
            leader_call = "not covered"
        if d.update and d.update.leader_confidence:
            conf = str(d.update.leader_confidence)
        else:
            conf = "—"
        lines.append(
            f"- {d.account} ({d.name}) ${d.sfdc_amount:,.0f} | "
            f"SFDC={d.sfdc_category.value}/{d.sfdc_stage.value} | "
            f"Leader={leader_call} (conf {conf}) | "
            f"Flags: {len(d.flags)}"
        )
        for f in d.flags:
            lines.append(f"    [{f.severity.value}] {f.code}: {f.message}")
    return "\n".join(lines)


def synthesize_forecast(
    briefing: LeaderBriefing,
    updates: dict[str, DealUpdate],
    *,
    as_of: Optional[date] = None,
    client: Optional[anthropic.Anthropic] = None,
    model: str = DEFAULT_MODEL,
    skip_narrative: bool = False,
) -> ForecastReport:
    as_of = as_of or date.today()

    deals: list[DealSummary] = []
    for o in briefing.opportunities:
        update = updates.get(o.id)
        flags = reconcile(o, update, as_of=as_of)
        deals.append(
            DealSummary(
                opportunity_id=o.id,
                name=o.name,
                account=o.account,
                sfdc_amount=o.amount,
                sfdc_stage=o.stage,
                sfdc_category=o.forecast_category,
                sfdc_close_date=o.close_date,
                update=update,
                flags=flags,
            )
        )

    rollup = _build_rollup(briefing, updates)
    gap_to_quota = briefing.leader.quarter_quota - rollup.committed_total
    top_risks = _top_risks(deals)

    narrative = ""
    if not skip_narrative:
        client = client or anthropic.Anthropic()
        ctx = _render_context_for_narrative(briefing, rollup, deals, gap_to_quota)
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": SYNTHESIZER_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": ctx}],
        )
        narrative = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        ).strip()

    return ForecastReport(
        leader=briefing.leader,
        as_of=datetime.now(),
        quarter_label=briefing.quarter_label,
        rollup=rollup,
        gap_to_quota=gap_to_quota,
        deals=deals,
        top_risks=top_risks,
        narrative=narrative,
    )
