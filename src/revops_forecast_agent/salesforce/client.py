"""Salesforce client protocol and an in-memory mock for development and tests.

The production implementation will replace `MockSalesforceClient` with a
`simple-salesforce`-backed client that honors the same `SalesforceClient`
protocol. Nothing else in the codebase depends on the mock.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from ..models import (
    ForecastCategory,
    MeddpiccScore,
    Opportunity,
    OpportunityStage,
    SalesLeader,
)


class SalesforceClient(Protocol):
    def list_leaders(self) -> list[SalesLeader]: ...
    def get_leader(self, leader_id: str) -> SalesLeader: ...
    def opportunities_for_leader(
        self,
        leader_id: str,
        quarter_start: date,
        quarter_end: date,
    ) -> list[Opportunity]: ...


# ----------------------------- mock fixture data ----------------------------

_LEADERS: list[SalesLeader] = [
    SalesLeader(
        id="L-001",
        name="Jordan Rivera",
        email="jordan.rivera@example.com",
        team="Enterprise West",
        quarter_quota=2_500_000,
        rep_ids=["R-101", "R-102", "R-103"],
    ),
    SalesLeader(
        id="L-002",
        name="Priya Shah",
        email="priya.shah@example.com",
        team="Enterprise East",
        quarter_quota=2_250_000,
        rep_ids=["R-201", "R-202"],
    ),
    SalesLeader(
        id="L-003",
        name="Marcus Chen",
        email="marcus.chen@example.com",
        team="Mid-Market",
        quarter_quota=1_500_000,
        rep_ids=["R-301", "R-302", "R-303"],
    ),
]


def _opp(**kwargs) -> Opportunity:
    meddpicc = kwargs.pop("meddpicc", MeddpiccScore())
    return Opportunity(meddpicc=meddpicc, **kwargs)


_OPPS_BY_LEADER: dict[str, list[Opportunity]] = {
    "L-001": [
        _opp(
            id="OPP-1001",
            name="Acme Corp - Platform Expansion",
            account="Acme Corp",
            owner="Sam Patel",
            owner_email="sam.patel@example.com",
            amount=480_000,
            stage=OpportunityStage.NEGOTIATION,
            forecast_category=ForecastCategory.COMMIT,
            close_date=date(2026, 5, 15),
            created_date=date(2025, 11, 3),
            last_activity_date=date(2026, 4, 8),
            next_step="Legal redlines back from Acme",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=True, identified_pain=True,
                champion=True, competition=True,
            ),
            notes="Strong champion. Paper in legal.",
        ),
        _opp(
            id="OPP-1002",
            name="Globex - Data Cloud",
            account="Globex",
            owner="Sam Patel",
            owner_email="sam.patel@example.com",
            amount=320_000,
            stage=OpportunityStage.PROPOSAL,
            forecast_category=ForecastCategory.BEST_CASE,
            close_date=date(2026, 6, 20),
            created_date=date(2025, 12, 15),
            last_activity_date=date(2026, 3, 22),
            next_step="Proposal review call scheduled",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=False, decision_criteria=True,
                decision_process=False, paper_process=False, identified_pain=True,
                champion=True, competition=False,
            ),
            notes="Economic buyer still unclear. No exec alignment yet.",
        ),
        _opp(
            id="OPP-1003",
            name="Initech - AI Add-on",
            account="Initech",
            owner="Rita Wu",
            owner_email="rita.wu@example.com",
            amount=185_000,
            stage=OpportunityStage.DISCOVERY,
            forecast_category=ForecastCategory.COMMIT,  # intentional mismatch
            close_date=date(2026, 6, 28),
            created_date=date(2026, 2, 10),
            last_activity_date=date(2026, 4, 1),
            next_step="Technical deep-dive with platform team",
            meddpicc=MeddpiccScore(
                metrics=False, economic_buyer=False, decision_criteria=False,
                decision_process=False, paper_process=False, identified_pain=True,
                champion=False, competition=False,
            ),
            notes="Very early. Called commit by rep but stage says Discovery.",
        ),
        _opp(
            id="OPP-1004",
            name="Wonka Industries - Renewal + Expansion",
            account="Wonka Industries",
            owner="Rita Wu",
            owner_email="rita.wu@example.com",
            amount=610_000,
            stage=OpportunityStage.VERBAL,
            forecast_category=ForecastCategory.COMMIT,
            close_date=date(2026, 4, 30),
            created_date=date(2025, 10, 1),
            last_activity_date=date(2026, 4, 10),
            next_step="Countersignature",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=True, identified_pain=True,
                champion=True, competition=True,
            ),
        ),
        _opp(
            id="OPP-1005",
            name="Soylent - Analytics Seat Expansion",
            account="Soylent",
            owner="Alex Kim",
            owner_email="alex.kim@example.com",
            amount=225_000,
            stage=OpportunityStage.PROPOSAL,
            forecast_category=ForecastCategory.BEST_CASE,
            close_date=date(2026, 6, 15),
            created_date=date(2026, 1, 20),
            last_activity_date=date(2026, 3, 10),  # stale
            next_step=None,
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=False, paper_process=False, identified_pain=True,
                champion=True, competition=False,
            ),
            notes="No activity in 30+ days. No documented next step.",
        ),
    ],
    "L-002": [
        _opp(
            id="OPP-2001",
            name="Umbrella Corp - Core Platform",
            account="Umbrella Corp",
            owner="Dani Okafor",
            owner_email="dani.okafor@example.com",
            amount=950_000,
            stage=OpportunityStage.NEGOTIATION,
            forecast_category=ForecastCategory.COMMIT,
            close_date=date(2026, 5, 30),
            created_date=date(2025, 9, 12),
            last_activity_date=date(2026, 4, 9),
            next_step="MSA countersigned by procurement",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=True, identified_pain=True,
                champion=True, competition=True,
            ),
        ),
        _opp(
            id="OPP-2002",
            name="Stark Industries - Pilot to Production",
            account="Stark Industries",
            owner="Dani Okafor",
            owner_email="dani.okafor@example.com",
            amount=420_000,
            stage=OpportunityStage.PROPOSAL,
            forecast_category=ForecastCategory.BEST_CASE,
            close_date=date(2026, 6, 10),
            created_date=date(2025, 12, 1),
            last_activity_date=date(2026, 4, 5),
            next_step="ROI readout to CFO on Apr 22",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=False, identified_pain=True,
                champion=True, competition=True,
            ),
        ),
        _opp(
            id="OPP-2003",
            name="Cyberdyne - Data Platform",
            account="Cyberdyne",
            owner="Leo Brandt",
            owner_email="leo.brandt@example.com",
            amount=275_000,
            stage=OpportunityStage.QUALIFICATION,
            forecast_category=ForecastCategory.PIPELINE,
            close_date=date(2026, 6, 30),
            created_date=date(2026, 3, 14),
            last_activity_date=date(2026, 4, 7),
            next_step="Discovery workshop",
            meddpicc=MeddpiccScore(identified_pain=True),
        ),
        _opp(
            id="OPP-2004",
            name="Wayne Enterprises - Security Suite",
            account="Wayne Enterprises",
            owner="Leo Brandt",
            owner_email="leo.brandt@example.com",
            amount=560_000,
            stage=OpportunityStage.PROPOSAL,
            forecast_category=ForecastCategory.BEST_CASE,
            close_date=date(2026, 5, 22),
            created_date=date(2025, 11, 18),
            last_activity_date=date(2026, 4, 3),
            next_step="Security review with their CISO",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=False, decision_criteria=True,
                decision_process=True, paper_process=False, identified_pain=True,
                champion=True, competition=True,
            ),
            notes="CISO is gatekeeper. Real economic buyer not yet engaged.",
        ),
    ],
    "L-003": [
        _opp(
            id="OPP-3001",
            name="Hooli - Starter Package",
            account="Hooli",
            owner="Nora Blake",
            owner_email="nora.blake@example.com",
            amount=95_000,
            stage=OpportunityStage.VERBAL,
            forecast_category=ForecastCategory.COMMIT,
            close_date=date(2026, 4, 25),
            created_date=date(2026, 1, 10),
            last_activity_date=date(2026, 4, 10),
            next_step="Order form sent",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=True, identified_pain=True,
                champion=True, competition=False,
            ),
        ),
        _opp(
            id="OPP-3002",
            name="Pied Piper - Growth",
            account="Pied Piper",
            owner="Nora Blake",
            owner_email="nora.blake@example.com",
            amount=140_000,
            stage=OpportunityStage.PROPOSAL,
            forecast_category=ForecastCategory.BEST_CASE,
            close_date=date(2026, 6, 15),
            created_date=date(2026, 2, 1),
            last_activity_date=date(2026, 4, 6),
            next_step="Pricing review",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=False, paper_process=False, identified_pain=True,
                champion=True, competition=False,
            ),
        ),
        _opp(
            id="OPP-3003",
            name="Dunder Mifflin - AI Pilot",
            account="Dunder Mifflin",
            owner="Tyson Lee",
            owner_email="tyson.lee@example.com",
            amount=72_000,
            stage=OpportunityStage.DISCOVERY,
            forecast_category=ForecastCategory.PIPELINE,
            close_date=date(2026, 6, 28),
            created_date=date(2026, 3, 1),
            last_activity_date=date(2026, 4, 4),
            next_step="Stakeholder mapping",
            meddpicc=MeddpiccScore(identified_pain=True, champion=True),
        ),
        _opp(
            id="OPP-3004",
            name="Vandelay - Logistics Module",
            account="Vandelay Industries",
            owner="Tyson Lee",
            owner_email="tyson.lee@example.com",
            amount=210_000,
            stage=OpportunityStage.NEGOTIATION,
            forecast_category=ForecastCategory.COMMIT,
            close_date=date(2026, 5, 8),
            created_date=date(2025, 12, 20),
            last_activity_date=date(2026, 4, 9),
            next_step="Contract in legal",
            meddpicc=MeddpiccScore(
                metrics=True, economic_buyer=True, decision_criteria=True,
                decision_process=True, paper_process=True, identified_pain=True,
                champion=True, competition=True,
            ),
        ),
    ],
}


class MockSalesforceClient:
    """Deterministic in-memory Salesforce stand-in for development and tests."""

    def __init__(
        self,
        leaders: list[SalesLeader] | None = None,
        opportunities: dict[str, list[Opportunity]] | None = None,
    ) -> None:
        self._leaders = leaders or _LEADERS
        self._opps = opportunities or _OPPS_BY_LEADER

    def list_leaders(self) -> list[SalesLeader]:
        return list(self._leaders)

    def get_leader(self, leader_id: str) -> SalesLeader:
        for leader in self._leaders:
            if leader.id == leader_id or leader.name == leader_id:
                return leader
        raise KeyError(f"Unknown leader: {leader_id}")

    def opportunities_for_leader(
        self,
        leader_id: str,
        quarter_start: date,
        quarter_end: date,
    ) -> list[Opportunity]:
        leader = self.get_leader(leader_id)
        opps = self._opps.get(leader.id, [])
        return [
            o
            for o in opps
            if quarter_start <= o.close_date <= quarter_end
            and o.stage != OpportunityStage.CLOSED_LOST
        ]
