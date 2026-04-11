from datetime import date

from revops_forecast_agent.briefing import build_leader_briefing
from revops_forecast_agent.salesforce.client import MockSalesforceClient


def test_briefing_builds_quarter_window():
    sfdc = MockSalesforceClient()
    b = build_leader_briefing(sfdc, "L-001", as_of=date(2026, 4, 11))
    assert b.quarter_label == "Q2 2026"
    assert b.quarter_start == date(2026, 4, 1)
    assert b.quarter_end == date(2026, 6, 30)
    assert len(b.deal_briefings) == len(b.opportunities)


def test_briefing_flags_commit_on_early_stage_deal():
    sfdc = MockSalesforceClient()
    b = build_leader_briefing(sfdc, "L-001", as_of=date(2026, 4, 11))
    target = next(db for db in b.deal_briefings if db.opportunity.id == "OPP-1003")
    assert any(
        "COMMIT" in r or "commit" in r.lower() for r in target.risk_notes
    )


def test_briefing_sorted_by_amount_desc():
    sfdc = MockSalesforceClient()
    b = build_leader_briefing(sfdc, "L-001", as_of=date(2026, 4, 11))
    amounts = [o.amount for o in b.opportunities]
    assert amounts == sorted(amounts, reverse=True)
