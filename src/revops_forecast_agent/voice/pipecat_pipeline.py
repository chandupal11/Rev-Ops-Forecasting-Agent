"""Pipecat-based voice pipeline for the Rev Ops forecast agent.

Wires the text-mode `ForecastInterviewer` into a real-time voice pipeline:

    Daily transport -> Deepgram STT -> ForecastInterviewer -> ElevenLabs TTS -> Daily

This module is an adapter, not a core dependency. It will only import cleanly
when the `voice` extra is installed:

    pip install -e '.[voice]'

This file is an intentional starting point — you should expect to tune it for
your preferred transport (Twilio / LiveKit / Zoom SDK), STT (Whisper / Azure),
TTS (Cartesia / OpenAI), and barge-in behavior before running it in production.
The Pipecat import paths and service APIs evolve fast; verify against the
version you install.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from ..agent.interviewer import ForecastInterviewer
from ..briefing import LeaderBriefing


async def run_voice_call(
    briefing: LeaderBriefing,
    *,
    room_url: Optional[str] = None,
) -> ForecastInterviewer:
    """Run a live voice forecast call in a Daily room.

    Requires `pipecat-ai[daily,deepgram,elevenlabs]` and these env vars:
    DAILY_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID.

    Returns the `ForecastInterviewer` after the call ends so the caller can
    read `interviewer.state.recorded_updates` and pass them to
    `synthesize_forecast`.
    """
    try:
        from pipecat.frames.frames import EndFrame, TextFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineTask
        from pipecat.processors.frame_processor import (
            FrameDirection,
            FrameProcessor,
        )
        from pipecat.services.deepgram import DeepgramSTTService
        from pipecat.services.elevenlabs import ElevenLabsTTSService
        from pipecat.transports.services.daily import DailyParams, DailyTransport
    except ImportError as e:
        raise RuntimeError(
            "Voice mode requires the `voice` extra. "
            "Install with: pip install -e '.[voice]'"
        ) from e

    interviewer = ForecastInterviewer(briefing)

    class InterviewerProcessor(FrameProcessor):
        """Bridges STT output into `ForecastInterviewer.respond` and emits
        the agent's reply as a TextFrame for downstream TTS."""

        async def process_frame(self, frame, direction: FrameDirection):
            await super().process_frame(frame, direction)
            if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
                reply = await asyncio.to_thread(interviewer.respond, frame.text)
                if reply:
                    await self.push_frame(
                        TextFrame(reply), FrameDirection.DOWNSTREAM
                    )
                if interviewer.state.ended:
                    await self.push_frame(EndFrame(), FrameDirection.DOWNSTREAM)
            else:
                await self.push_frame(frame, direction)

    transport = DailyTransport(
        room_url or os.environ["DAILY_ROOM_URL"],
        None,
        f"RevOps Agent — {briefing.leader.name}",
        DailyParams(audio_out_enabled=True, audio_in_enabled=True),
    )
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            InterviewerProcessor(),
            tts,
            transport.output(),
        ]
    )

    task = PipelineTask(pipeline)

    # Kick off the call with the agent's opening line so the TTS speaks first.
    opener = await asyncio.to_thread(interviewer.open_call)
    await task.queue_frame(TextFrame(opener))

    runner = PipelineRunner()
    await runner.run(task)
    return interviewer
