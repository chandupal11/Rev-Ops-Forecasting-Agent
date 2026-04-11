"""Claude-backed forecast interviewer.

A single `ForecastInterviewer` state machine powers both text mode (CLI
prompt loop) and voice mode (Pipecat pipeline). Transports just feed
`respond()` with the leader's latest utterance and render whatever the
method returns.

The interviewer uses Anthropic tool use to capture structured deal updates:
- `record_deal_update` — called once per deal when the agent has enough info
- `end_call` — called when every deal has been covered
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import anthropic

from ..briefing import LeaderBriefing
from ..models import DealUpdate, ForecastCategory, OpportunityStage
from .prompts import INTERVIEWER_SYSTEM_PROMPT


DEFAULT_MODEL = os.getenv("REVOPS_INTERVIEWER_MODEL", "claude-sonnet-4-6")


TOOLS: list[dict[str, Any]] = [
    {
        "name": "record_deal_update",
        "description": (
            "Call this once you have collected the leader's verbal update on a "
            "specific deal. One call per deal. Leave any field null if the "
            "leader did not actually give you that information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "opportunity_id": {"type": "string"},
                "verbal_category": {
                    "type": "string",
                    "enum": [c.value for c in ForecastCategory],
                    "description": "Leader's forecast category call for this deal.",
                },
                "verbal_stage": {
                    "type": "string",
                    "enum": [s.value for s in OpportunityStage],
                },
                "verbal_close_date": {
                    "type": "string",
                    "description": "ISO date (YYYY-MM-DD) if the leader gave a new close date.",
                },
                "verbal_amount": {"type": "number"},
                "leader_confidence": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "1 = no confidence, 5 = in the bank.",
                },
                "risks": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
            },
            "required": ["opportunity_id"],
        },
    },
    {
        "name": "end_call",
        "description": (
            "Call this when every deal in the briefing has been covered and "
            "you have thanked the leader for their time. Provide a short "
            "one-paragraph recap of the conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
            "required": ["summary"],
        },
    },
]


def _briefing_to_context(briefing: LeaderBriefing, as_of: date) -> str:
    lines = [
        "# Forecast Call Briefing",
        "",
        f"Leader: {briefing.leader.name} ({briefing.leader.team})",
        f"Quarter: {briefing.quarter_label} "
        f"({briefing.quarter_start.isoformat()} to {briefing.quarter_end.isoformat()})",
        f"Quarterly quota: ${briefing.leader.quarter_quota:,.0f}",
        f"As of: {as_of.isoformat()}",
        "",
        "## Salesforce rollup (current)",
    ]
    for cat, amt in briefing.sfdc_rollup.items():
        lines.append(f"- {cat}: ${amt:,.0f}")
    lines.append("")
    lines.append("## Deals to cover (in priority order)")
    lines.append("")
    for i, db in enumerate(briefing.deal_briefings, start=1):
        o = db.opportunity
        lines.append(f"### {i}. {o.name} ({o.account}) — `{o.id}`")
        lines.append(f"- Owner: {o.owner}")
        lines.append(f"- Amount: ${o.amount:,.0f}")
        lines.append(f"- Stage: {o.stage.value}")
        lines.append(f"- SFDC category: {o.forecast_category.value}")
        lines.append(f"- Close date: {o.close_date.isoformat()}")
        lines.append(
            "- Last activity: "
            f"{o.last_activity_date.isoformat() if o.last_activity_date else 'none'}"
        )
        lines.append(f"- Next step: {o.next_step or 'not documented'}")
        missing = o.meddpicc.missing_pillars()
        meddpicc_line = (
            f"- MEDDPICC: {int(o.meddpicc.completeness() * 100)}% complete"
        )
        if missing:
            meddpicc_line += f" (missing: {', '.join(missing)})"
        lines.append(meddpicc_line)
        if o.notes:
            lines.append(f"- Notes: {o.notes}")
        if db.risk_notes:
            lines.append("- Flagged risks:")
            for r in db.risk_notes:
                lines.append(f"  * {r}")
        if db.target_questions:
            lines.append("- Target questions:")
            for q in db.target_questions:
                lines.append(f"  * {q}")
        lines.append("")
    return "\n".join(lines)


@dataclass
class InterviewerState:
    messages: list[dict[str, Any]] = field(default_factory=list)
    recorded_updates: dict[str, DealUpdate] = field(default_factory=dict)
    ended: bool = False
    final_summary: str = ""


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


class ForecastInterviewer:
    """Claude-backed interviewer that runs a forecast call, one turn at a time.

    Usage:

        interviewer = ForecastInterviewer(briefing)
        print(interviewer.open_call())
        while not interviewer.state.ended:
            leader_msg = get_leader_utterance()
            print(interviewer.respond(leader_msg))
    """

    def __init__(
        self,
        briefing: LeaderBriefing,
        *,
        client: Optional[anthropic.Anthropic] = None,
        model: str = DEFAULT_MODEL,
        as_of: Optional[date] = None,
        max_tokens: int = 1024,
    ) -> None:
        self.briefing = briefing
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.as_of = as_of or date.today()
        self.max_tokens = max_tokens
        self.state = InterviewerState()
        self._briefing_context = _briefing_to_context(briefing, self.as_of)

    # ----- public API -----

    def open_call(self) -> str:
        """Kick off the call. Returns the agent's opening remarks + first question."""
        self.state.messages.append(
            {
                "role": "user",
                "content": (
                    "[Stage direction from the RevOps scheduler: the forecast "
                    "call is starting now. Greet the leader by first name, "
                    "state what quarter you're covering and how many deals "
                    "are on today's list, and open with your first question "
                    "about the highest-priority deal. This message is not "
                    "from the leader — do not thank them for anything yet.]"
                ),
            }
        )
        return self._drive_until_text()

    def respond(self, leader_utterance: str) -> str:
        """Feed the leader's latest utterance and return the agent's next turn."""
        if self.state.ended:
            return ""
        self.state.messages.append(
            {"role": "user", "content": leader_utterance}
        )
        return self._drive_until_text()

    # ----- internals -----

    def _drive_until_text(self) -> str:
        """Call the model, run any tools, loop until we have text for the leader
        or the call ends."""
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": INTERVIEWER_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": self._briefing_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                tools=TOOLS,
                messages=self.state.messages,
            )

            # Echo the assistant turn into history. We construct the echo
            # explicitly (rather than `model_dump`) to avoid SDK version
            # drift on optional fields.
            echoed: list[dict[str, Any]] = []
            spoken_text_parts: list[str] = []
            tool_results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    echoed.append({"type": "text", "text": block.text})
                    spoken_text_parts.append(block.text)
                elif block.type == "tool_use":
                    echoed.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    result = self._handle_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

            self.state.messages.append({"role": "assistant", "content": echoed})

            if tool_results:
                self.state.messages.append(
                    {"role": "user", "content": tool_results}
                )

            if self.state.ended:
                return "\n".join(spoken_text_parts).strip()

            if response.stop_reason == "end_turn" and spoken_text_parts:
                return "\n".join(spoken_text_parts).strip()

            if response.stop_reason == "tool_use":
                # Loop back around so the model can follow up after tool results.
                continue

            return "\n".join(spoken_text_parts).strip()

    def _handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "record_deal_update":
            return self._record_update(args)
        if name == "end_call":
            self.state.ended = True
            self.state.final_summary = args.get("summary", "")
            return {"status": "call_ended"}
        return {"status": "unknown_tool", "name": name}

    def _record_update(self, args: dict[str, Any]) -> dict[str, Any]:
        opp_id = args.get("opportunity_id")
        if not opp_id:
            return {"status": "error", "message": "opportunity_id is required"}

        known_ids = {o.id for o in self.briefing.opportunities}
        if opp_id not in known_ids:
            return {
                "status": "error",
                "message": (
                    f"Unknown opportunity_id {opp_id}. "
                    f"Valid ids: {sorted(known_ids)}"
                ),
            }

        def _enum(val, cls):
            if val is None:
                return None
            try:
                return cls(val)
            except ValueError:
                return None

        update = DealUpdate(
            opportunity_id=opp_id,
            verbal_category=_enum(args.get("verbal_category"), ForecastCategory),
            verbal_stage=_enum(args.get("verbal_stage"), OpportunityStage),
            verbal_close_date=_parse_date(args.get("verbal_close_date")),
            verbal_amount=args.get("verbal_amount"),
            leader_confidence=args.get("leader_confidence"),
            risks=args.get("risks") or [],
            next_steps=args.get("next_steps") or [],
            notes=args.get("notes"),
        )
        self.state.recorded_updates[opp_id] = update

        remaining = sorted(known_ids - set(self.state.recorded_updates))
        return {
            "status": "recorded",
            "opportunity_id": opp_id,
            "remaining_deals": remaining,
        }
