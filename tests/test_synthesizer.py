from datetime import date

from revops_forecast_agent.agent.synthesizer import synthesize_forecast
from revops_forecast_agent.briefing import build_leader_briefing
from revops_forecast_agent.models import DealUpdate, ForecastCategory
from revops_forecast_agent.salesforce.client import MockSalesforceClient


def test_synthesize_rollup_honors_leader_overrides():
    sfdc = MockSalesforceClient()
    briefing = build_leader_briefing(sfdc, "L-001", as_of=date(2026, 4, 11))

    # Force every deal into pipeline
    updates = {
        o.id: DealUpdate(
            opportunity_id=o.id,
            verbal_category=ForecastCategory.PIPELINE,
        )
        for o in briefing.opportunities
    }

    report = synthesize_forecast(
        briefing, updates, skip_narrative=True, as_of=date(2026, 4, 11)
    )
    assert report.rollup.commit == 0
    assert report.rollup.closed_won == 0
    assert report.rollup.pipeline == sum(
        o.amount for o in briefing.opportunities
    )
    # Gap to quota should equal full quota since committed_total is 0.
    assert report.gap_to_quota == briefing.leader.quarter_quota


def test_synthesize_no_updates_flags_every_deal_not_discussed():
    sfdc = MockSalesforceClient()
    briefing = build_leader_briefing(sfdc, "L-001", as_of=date(2026, 4, 11))
    report = synthesize_forecast(briefing, {}, skip_narrative=True)
    for d in report.deals:
        assert any(f.code == "NOT_DISCUSSED" for f in d.flags)
