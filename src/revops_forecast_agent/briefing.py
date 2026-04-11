"""Deterministic pre-call briefing generator.

Given a leader and a Salesforce client, produce a `LeaderBriefing` — the deals
in priority order plus per-deal target questions and risk notes. This runs
without any LLM call, so it's cheap, testable, and serves as the factual
backbone of the conversation the `ForecastInterviewer` then drives.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import ForecastCategory, Opportunity, OpportunityStage, SalesLeader
from .salesforce.client import SalesforceClient


EARLY_STAGES = {
    OpportunityStage.PROSPECTING,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.DISCOVERY,
}


@dataclass
class DealBriefing:
    opportunity: Opportunity
    target_questions: list[str]
    risk_notes: list[str]


@dataclass
class LeaderBriefing:
    leader: SalesLeader
    quarter_label: str
    quarter_start: date
    quarter_end: date
    opportunities: list[Opportunity]
    deal_briefings: list[DealBriefing]

    @property
    def sfdc_rollup(self) -> dict[str, float]:
        totals = {c.value: 0.0 for c in ForecastCategory}
        for o in self.opportunities:
            totals[o.forecast_category.value] += o.amount
        return totals


def _build_questions(opp: Opportunity, as_of: date) -> tuple[list[str], list[str]]:
    questions: list[str] = []
    risks: list[str] = []

    questions.append(
        f"What's your current call on {opp.name} ({opp.account}) — "
        "commit, best case, or pipeline?"
    )
    questions.append(f"Is the close date still {opp.close_date.isoformat()}?")
    questions.append(f"Is the amount still ${opp.amount:,.0f}?")

    if (
        opp.forecast_category == ForecastCategory.COMMIT
        and opp.stage in EARLY_STAGES
    ):
        risks.append(
            f"Category is COMMIT but stage is {opp.stage.value} — "
            "qualification is very thin for a committed deal."
        )
        questions.append(
            "This is called commit but the stage is still early. "
            "What's giving you commit-level confidence?"
        )

    missing = opp.meddpicc.missing_pillars()
    if missing:
        risks.append(f"MEDDPICC gaps: {', '.join(missing)}")
        if "economic_buyer" in missing:
            questions.append(
                "Who is the economic buyer, and has the rep met with them?"
            )
        if (
            "paper_process" in missing
            and opp.forecast_category == ForecastCategory.COMMIT
        ):
            questions.append(
                "Do we have a clear paper process — legal/procurement path to signature?"
            )
        if "decision_process" in missing:
            questions.append(
                "What does their decision process look like and who else needs to sign off?"
            )
        if "competition" in missing:
            questions.append("Who are we competing against on this deal?")
        if "champion" in missing:
            questions.append("Do we have a real champion, or just a coach?")

    if opp.last_activity_date is None:
        risks.append("No recorded activity in Salesforce.")
        questions.append("When was the last real customer touch on this deal?")
    else:
        days_stale = (as_of - opp.last_activity_date).days
        if days_stale > 14:
            risks.append(f"No activity in {days_stale} days.")
            questions.append(
                f"There hasn't been activity logged in {days_stale} days — "
                "what's actually happening with the customer?"
            )

    days_to_close = (opp.close_date - as_of).days
    if 0 <= days_to_close <= 14 and opp.stage != OpportunityStage.VERBAL:
        risks.append(
            f"Closes in {days_to_close} days but not yet at Verbal Commit."
        )
        questions.append(
            f"You're {days_to_close} days from close but stage is {opp.stage.value}. "
            "What needs to happen between now and then?"
        )

    if not opp.next_step:
        risks.append("No documented next step.")
        questions.append("What's the concrete next step on this deal?")

    return questions, risks


def _quarter_bounds(as_of: date) -> tuple[int, date, date, str]:
    quarter = (as_of.month - 1) // 3 + 1
    quarter_start_month = 3 * (quarter - 1) + 1
    quarter_start = date(as_of.year, quarter_start_month, 1)
    if quarter == 4:
        quarter_end = date(as_of.year, 12, 31)
    else:
        next_qs = date(as_of.year, quarter_start_month + 3, 1)
        quarter_end = next_qs - timedelta(days=1)
    return quarter, quarter_start, quarter_end, f"Q{quarter} {as_of.year}"


def build_leader_briefing(
    sfdc: SalesforceClient,
    leader_id: str,
    as_of: date,
) -> LeaderBriefing:
    _, quarter_start, quarter_end, label = _quarter_bounds(as_of)

    leader = sfdc.get_leader(leader_id)
    opps = sfdc.opportunities_for_leader(leader.id, quarter_start, quarter_end)

    # Largest deals first, ties broken by soonest close date.
    opps_sorted = sorted(opps, key=lambda o: (-o.amount, o.close_date))

    briefings: list[DealBriefing] = []
    for o in opps_sorted:
        qs, rs = _build_questions(o, as_of)
        briefings.append(
            DealBriefing(opportunity=o, target_questions=qs, risk_notes=rs)
        )

    return LeaderBriefing(
        leader=leader,
        quarter_label=label,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        opportunities=opps_sorted,
        deal_briefings=briefings,
    )
