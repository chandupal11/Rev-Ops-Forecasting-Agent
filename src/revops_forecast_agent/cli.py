"""Typer CLI: list leaders, show briefings, run forecast calls in text mode."""

from __future__ import annotations

import os
from datetime import date

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from .agent.interviewer import ForecastInterviewer
from .agent.synthesizer import synthesize_forecast
from .briefing import build_leader_briefing
from .reports import render_markdown
from .salesforce.client import MockSalesforceClient

app = typer.Typer(
    help="Rev Ops Forecast Agent — run structured forecast calls with sales leaders.",
    no_args_is_help=True,
)
console = Console()


@app.command("list-leaders")
def list_leaders() -> None:
    """List sales leaders available in the mock Salesforce."""
    sfdc = MockSalesforceClient()
    for leader in sfdc.list_leaders():
        console.print(
            f"[bold]{leader.id}[/]  {leader.name}  ({leader.team})  "
            f"quota=${leader.quarter_quota:,.0f}"
        )


@app.command("brief")
def brief(leader: str = typer.Argument(..., help="Leader id or name")) -> None:
    """Show the pre-call briefing for a leader (no API calls, no LLM)."""
    sfdc = MockSalesforceClient()
    briefing = build_leader_briefing(sfdc, leader, as_of=date.today())
    console.rule(f"[bold]Briefing: {briefing.leader.name} — {briefing.quarter_label}")
    for i, db in enumerate(briefing.deal_briefings, 1):
        o = db.opportunity
        console.print(
            f"\n[bold]{i}. {o.name}[/] — {o.account} — "
            f"${o.amount:,.0f} — {o.stage.value} — cat={o.forecast_category.value}"
        )
        if db.risk_notes:
            console.print("  [red]Risks:[/]")
            for r in db.risk_notes:
                console.print(f"    - {r}")
        if db.target_questions:
            console.print("  [cyan]Questions:[/]")
            for q in db.target_questions:
                console.print(f"    - {q}")


@app.command("run-call")
def run_call(
    leader: str = typer.Argument(..., help="Leader id or name"),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Skip the interactive interview and synthesize directly from SFDC.",
    ),
    skip_narrative: bool = typer.Option(
        False,
        "--skip-narrative",
        help="Skip the Claude-generated narrative (useful without an API key).",
    ),
    output: str = typer.Option(
        "", "--output", "-o", help="Write the report markdown to a file."
    ),
) -> None:
    """Run a forecast call (text mode) with the given sales leader."""
    sfdc = MockSalesforceClient()
    briefing = build_leader_briefing(sfdc, leader, as_of=date.today())
    console.rule(
        f"[bold green]Forecast Call — {briefing.leader.name} — {briefing.quarter_label}"
    )
    console.print(
        f"[dim]{len(briefing.opportunities)} deals in scope. "
        f"Quota: ${briefing.leader.quarter_quota:,.0f}[/dim]\n"
    )

    updates: dict = {}

    if not auto:
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print(
                "[red]ANTHROPIC_API_KEY is not set. Use --auto to skip the live interview.[/]"
            )
            raise typer.Exit(code=1)

        interviewer = ForecastInterviewer(briefing)
        try:
            opener = interviewer.open_call()
        except Exception as e:
            console.print(f"[red]Failed to open call: {e}[/]")
            raise typer.Exit(code=1)
        console.print(f"[bold cyan]Agent:[/] {opener}\n")

        while not interviewer.state.ended:
            try:
                leader_msg = Prompt.ask("[bold yellow]Leader[/]")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Interrupted. Synthesizing what we have…[/]")
                break
            if not leader_msg.strip():
                continue
            if leader_msg.strip().lower() in {"/quit", "/end"}:
                console.print("[dim]Manual end. Synthesizing…[/]")
                break
            try:
                reply = interviewer.respond(leader_msg)
            except Exception as e:
                console.print(f"[red]Interviewer error: {e}[/]")
                break
            if reply:
                console.print(f"\n[bold cyan]Agent:[/] {reply}\n")

        updates = dict(interviewer.state.recorded_updates)
        if interviewer.state.final_summary:
            console.print(
                f"\n[dim]Call summary: {interviewer.state.final_summary}[/]\n"
            )

    console.rule("[bold]Synthesizing forecast")
    report = synthesize_forecast(
        briefing,
        updates,
        skip_narrative=skip_narrative or not os.getenv("ANTHROPIC_API_KEY"),
    )
    md = render_markdown(report)
    console.print(Markdown(md))

    if output:
        with open(output, "w") as f:
            f.write(md)
        console.print(f"\n[green]Wrote {output}[/]")


if __name__ == "__main__":
    app()
