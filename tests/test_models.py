from revops_forecast_agent.models import MeddpiccScore


def test_meddpicc_completeness_empty():
    s = MeddpiccScore()
    assert s.completeness() == 0.0
    assert len(s.missing_pillars()) == 8


def test_meddpicc_completeness_full():
    s = MeddpiccScore(
        metrics=True,
        economic_buyer=True,
        decision_criteria=True,
        decision_process=True,
        paper_process=True,
        identified_pain=True,
        champion=True,
        competition=True,
    )
    assert s.completeness() == 1.0
    assert s.missing_pillars() == []


def test_meddpicc_partial():
    s = MeddpiccScore(metrics=True, champion=True)
    assert s.completeness() == 0.25
    assert "economic_buyer" in s.missing_pillars()
    assert "metrics" not in s.missing_pillars()
