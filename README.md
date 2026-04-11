# Rev-Ops-Forecasting-Agent

An AI Rev Ops agent that runs structured forecast calls with sales leaders,
reconciles their verbal updates against Salesforce, and rolls everything up
into a quarter-level forecast view.

## What it does

For each sales leader, on whatever cadence you set:

1. **Pulls** their team's open opportunities for the current quarter from Salesforce.
2. **Builds a pre-call briefing**: deals in priority order, MEDDPICC gaps,
   stage/category mismatches, stale activity, tight close dates.
3. **Runs the forecast call** with the leader — walking through every deal and
   asking targeted questions (commit/best/pipeline, close date, amount,
   next steps, risks) — and records each deal update via structured tool calls.
4. **Reconciles** the verbal updates against Salesforce and flags mismatches.
5. **Synthesizes** a quarter-level forecast report with narrative, rollup,
   gap to quota, and top risks.

## Architecture

```
Salesforce --> Briefing --> Interviewer (Claude + tool use) --> Reconciliation --> Synthesizer --> Report
                                  ^                                  |
                                  |                                  v
                         STT / TTS transport                Markdown / writeback
```

Core pieces:

- `salesforce/` — `SalesforceClient` protocol and a `MockSalesforceClient` with
  three fake sales leaders and a realistic Q2 2026 pipeline. Swap in a real
  `simple-salesforce` implementation behind the same interface.
- `briefing.py` — deterministic pre-call briefing generator.
- `agent/interviewer.py` — Claude-backed interviewer driving a tool-use loop
  (`record_deal_update`, `end_call`). The same state machine powers both the
  text CLI and the voice pipeline.
- `agent/reconciliation.py` — diffs verbal updates vs. SFDC state; emits typed
  flags with severities.
- `agent/synthesizer.py` — computes the forecast rollup deterministically,
  then asks Claude for an executive narrative.
- `reports.py` — renders a `ForecastReport` as Markdown.
- `voice/pipecat_pipeline.py` — optional Pipecat adapter that runs the same
  `ForecastInterviewer` over a Daily room with Deepgram STT and ElevenLabs TTS.

## Setup

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run it

```bash
# See who you can run a call with
revops-forecast list-leaders

# Review the pre-call briefing for a leader (no API calls, no LLM)
revops-forecast brief L-001

# Run an interactive forecast call (text mode) with a leader
revops-forecast run-call L-001

# Skip the interview and just see the deterministic synthesis
revops-forecast run-call L-001 --auto --skip-narrative
```

## Voice mode

The text CLI and the voice pipeline share the same `ForecastInterviewer` state
machine, so the voice layer is a thin adapter rather than a rewrite. To run a
real-time voice call:

```bash
pip install -e ".[voice]"
export DAILY_API_KEY=...
export DAILY_ROOM_URL=https://your-domain.daily.co/revops-forecast
export DEEPGRAM_API_KEY=...
export ELEVENLABS_API_KEY=...
export ELEVENLABS_VOICE_ID=...
```

Then call `revops_forecast_agent.voice.pipecat_pipeline.run_voice_call(briefing)`
from your own entrypoint and wire it to your scheduler (cron, Temporal, Lambda)
so it auto-joins a Daily room at the scheduled forecast call time and emails
the report afterwards.

## Roadmap

- [ ] Real Salesforce connector (`simple-salesforce`) behind the existing `SalesforceClient` protocol
- [ ] Slack distribution for the rollup digest (CRO / RevOps channel)
- [ ] SFDC field writeback (forecast category, next step, notes) after each call
- [ ] Multi-leader orchestrator: run calls sequentially, roll up into a company-wide forecast
- [ ] Persistent storage of transcripts + reports (Postgres)
- [ ] Voice: production Pipecat transport, barge-in handling, scheduler integration

## Tests

```bash
pytest
```

Tests cover the deterministic layers (models, mock SFDC, briefing,
reconciliation, synthesizer rollup). The LLM-backed interviewer and narrative
generator are not unit-tested — exercise them manually with `run-call`.
