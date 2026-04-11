"""Voice-mode forecast call transport.

The text CLI ships a `ForecastInterviewer` state machine that is exactly the
same object driven by the voice pipeline. To run a real live voice call,
install the `voice` extra:

    pip install -e ".[voice]"

and then call `run_voice_call(briefing)` from
`revops_forecast_agent.voice.pipecat_pipeline`.

Required environment variables for the default Pipecat stack:
    DAILY_API_KEY, DAILY_ROOM_URL, DEEPGRAM_API_KEY,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
"""
