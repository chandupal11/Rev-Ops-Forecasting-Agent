from datetime import date

from revops_forecast_agent.agent.reconciliation import reconcile
from revops_forecast_agent.models import (
    DealUpdate,
    ForecastCategory,
    MeddpiccScore,
    Opportunity,
    OpportunityStage,
)


def _opp(**overrides):
    base = dict(
        id="OPP-TEST",
        name="Test Deal",
        account="Test Inc",
        owner="Rep",
        owner_email="r@x.com",
        amount=100_000,
        stage=OpportunityStage.NEGOTIATION,
        forecast_category=ForecastCategory.COMMIT,
        close_date=date(2026, 5, 15),
        created_date=date(2026, 1, 1),
        last_activity_date=date(2026, 4, 10),
        next_step="Contract signing",
        meddpicc=MeddpiccScore(
            metrics=True,
            economic_buyer=True,
            decision_criteria=True,
            decision_process=True,
            paper_process=True,
            identified_pain=True,
            champion=True,
            competition=True,
        ),
    )
    base.update(overrides)
    return Opportunity(**base)


AS_OF = date(2026, 4, 11)


def test_commit_on_discovery_is_critical():
    opp = _opp(stage=OpportunityStage.DISCOVERY)
    flags = reconcile(opp, None, as_of=AS_OF)
    codes = {f.code for f in flags}
    assert "COMMIT_EARLY_STAGE" in codes


def test_stale_activity_flag():
    opp = _opp(last_activity_date=date(2026, 3, 1))
    flags = reconcile(opp, None, as_of=AS_OF)
    assert any(f.code == "STALE_ACTIVITY" for f in flags)


def test_close_date_slip():
    opp = _opp()
    update = DealUpdate(
        opportunity_id=opp.id,
        verbal_close_date=date(2026, 6, 30),
    )
    flags = reconcile(opp, update, as_of=AS_OF)
    assert any(f.code == "CLOSE_DATE_SLIP" for f in flags)


def test_category_downgrade():
    opp = _opp(forecast_category=ForecastCategory.COMMIT)
    update = DealUpdate(
        opportunity_id=opp.id,
        verbal_category=ForecastCategory.BEST_CASE,
    )
    flags = reconcile(opp, update, as_of=AS_OF)
    assert any(f.code == "CATEGORY_DIFF" for f in flags)


def test_amount_change():
    opp = _opp()
    update = DealUpdate(opportunity_id=opp.id, verbal_amount=70_000)
    flags = reconcile(opp, update, as_of=AS_OF)
    assert any(f.code == "AMOUNT_CHANGE" for f in flags)


def test_not_discussed_flag():
    opp = _opp()
    flags = reconcile(opp, None, as_of=AS_OF)
    assert any(f.code == "NOT_DISCUSSED" for f in flags)
