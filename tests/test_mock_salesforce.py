from datetime import date

from revops_forecast_agent.salesforce.client import MockSalesforceClient


def test_list_leaders():
    sfdc = MockSalesforceClient()
    leaders = sfdc.list_leaders()
    assert len(leaders) >= 3
    assert all(leader.quarter_quota > 0 for leader in leaders)


def test_get_leader_by_id_or_name():
    sfdc = MockSalesforceClient()
    l1 = sfdc.get_leader("L-001")
    l2 = sfdc.get_leader(l1.name)
    assert l1.id == l2.id


def test_opportunities_for_leader_in_quarter():
    sfdc = MockSalesforceClient()
    opps = sfdc.opportunities_for_leader(
        "L-001", date(2026, 4, 1), date(2026, 6, 30)
    )
    assert len(opps) > 0
    for o in opps:
        assert date(2026, 4, 1) <= o.close_date <= date(2026, 6, 30)
