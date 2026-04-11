"""Reconcile a leader's verbal update against the Salesforce snapshot.

Produces a list of `ReconciliationFlag`s with severities. The flags are
then rolled into the per-deal summary and surfaced in the final report.
"""

from __future__ import annotations

from datetime import date

from ..models import (
    DealUpdate,
    FlagSeverity,
    ForecastCategory,
    Opportunity,
    OpportunityStage,
    ReconciliationFlag,
)

EARLY_STAGES = {
    OpportunityStage.PROSPECTING,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.DISCOVERY,
}

CATEGORY_ORDER = [
    ForecastCategory.PIPELINE,
    ForecastCategory.BEST_CASE,
    ForecastCategory.COMMIT,
    ForecastCategory.CLOSED_WON,
]


def _cat_rank(c: ForecastCategory) -> int:
    try:
        return CATEGORY_ORDER.index(c)
    except ValueError:
        return -1


def reconcile(
    opportunity: Opportunity,
    update: DealUpdate | None,
    *,
    as_of: date,
) -> list[ReconciliationFlag]:
    flags: list[ReconciliationFlag] = []
    oid = opportunity.id

    def flag(code: str, severity: FlagSeverity, message: str) -> None:
        flags.append(
            ReconciliationFlag(
                opportunity_id=oid, code=code, severity=severity, message=message
            )
        )

    # --- SFDC-only structural checks (always run) ---
    if (
        opportunity.forecast_category == ForecastCategory.COMMIT
        and opportunity.stage in EARLY_STAGES
    ):
        flag(
            "COMMIT_EARLY_STAGE",
            FlagSeverity.CRITICAL,
            f"Deal is in category COMMIT but stage is {opportunity.stage.value}. "
            "Committed deals should be at Proposal or later.",
        )

    missing = opportunity.meddpicc.missing_pillars()
    if opportunity.forecast_category == ForecastCategory.COMMIT and missing:
        flag(
            "COMMIT_MEDDPICC_GAP",
            FlagSeverity.WARN,
            f"Commit deal has MEDDPICC gaps: {', '.join(missing)}.",
        )

    if opportunity.last_activity_date is not None:
        stale_days = (as_of - opportunity.last_activity_date).days
        if stale_days > 14:
            flag(
                "STALE_ACTIVITY",
                FlagSeverity.WARN,
                f"No logged activity in {stale_days} days.",
            )
    else:
        flag(
            "NO_ACTIVITY",
            FlagSeverity.WARN,
            "No activity ever logged in Salesforce.",
        )

    if not opportunity.next_step:
        flag(
            "NO_NEXT_STEP",
            FlagSeverity.INFO,
            "No documented next step in Salesforce.",
        )

    # --- Verbal vs SFDC reconciliation ---
    if update is None:
        flag(
            "NOT_DISCUSSED",
            FlagSeverity.WARN,
            "Deal was not covered on the forecast call.",
        )
        return flags

    if (
        update.verbal_category
        and update.verbal_category != opportunity.forecast_category
    ):
        verbal_rank = _cat_rank(update.verbal_category)
        sfdc_rank = _cat_rank(opportunity.forecast_category)
        direction = "upgrade" if verbal_rank > sfdc_rank else "downgrade"
        severity = (
            FlagSeverity.WARN if direction == "downgrade" else FlagSeverity.INFO
        )
        flag(
            "CATEGORY_DIFF",
            severity,
            f"Leader called it {update.verbal_category.value} but SFDC has "
            f"{opportunity.forecast_category.value} ({direction}).",
        )

    if (
        update.verbal_close_date
        and update.verbal_close_date != opportunity.close_date
    ):
        slip = (update.verbal_close_date - opportunity.close_date).days
        if abs(slip) >= 7:
            flag(
                "CLOSE_DATE_SLIP" if slip > 0 else "CLOSE_DATE_PULL_IN",
                FlagSeverity.WARN if slip > 0 else FlagSeverity.INFO,
                f"Leader's close date ({update.verbal_close_date.isoformat()}) "
                f"differs from SFDC ({opportunity.close_date.isoformat()}) by "
                f"{abs(slip)} days.",
            )

    if update.verbal_amount is not None and opportunity.amount > 0:
        delta = update.verbal_amount - opportunity.amount
        pct = abs(delta) / opportunity.amount
        if pct >= 0.10:
            flag(
                "AMOUNT_CHANGE",
                FlagSeverity.WARN,
                f"Leader's amount ${update.verbal_amount:,.0f} differs from SFDC "
                f"${opportunity.amount:,.0f} ({pct:.0%}).",
            )

    if (
        update.verbal_category == ForecastCategory.COMMIT
        and update.leader_confidence is not None
        and update.leader_confidence <= 3
    ):
        flag(
            "WEAK_COMMIT_CONFIDENCE",
            FlagSeverity.WARN,
            f"Leader called commit but only rated confidence "
            f"{update.leader_confidence}/5.",
        )

    return flags
