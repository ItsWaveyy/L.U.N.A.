from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool, RunContext
from livekit.agents.llm import StopResponse
from livekit.plugins import ai_coustics, google
from core.orchestrator import LunaCore, SessionSleepWakeController
from prompts import AGENT_INSTRUCTION, build_session_instruction
from tools.memory import initialize_database, remember, recall


@function_tool()
async def get_weather(context: RunContext, city: str) -> str:
    from tools.weather import get_weather as _get_weather
    return await _get_weather(context, city)


@function_tool()
async def get_weather_forecast(context: RunContext, city: str, days: int = 3) -> str:
    from tools.weather import get_weather as _get_weather
    return await _get_weather(context, city, days=days)


@function_tool()
async def send_email(context: RunContext, recipient: str, subject: str, body: str) -> str:
    from tools.email import send_email as _send_email
    return await _send_email(context, recipient, subject, body)


@function_tool()
async def delegate_task(prompt: str, task: str = "general") -> str:
    from tools.delegate import delegate_task as _delegate_task
    return await _delegate_task(prompt=prompt, task=task)


load_dotenv()
initialize_database()


class Assistant(Agent):
    def __init__(self, sleep_controller: SessionSleepWakeController) -> None:
        self.sleep_controller = sleep_controller
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Despina",
                temperature=0.7,
            ),
            tools=[
                get_weather,
                get_weather_forecast,
                send_email,
                remember,
                recall,
                delegate_task,
            ],
        )

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        transcript = getattr(new_message, "text_content", None)
        if callable(transcript):
            transcript = transcript()
        if transcript is None:
            transcript = getattr(new_message, "raw_text_content", "")

        self.sleep_controller.handle_transcript(transcript)
        if not self.sleep_controller.luna_core.listening:
            raise StopResponse()
        

server = AgentServer()

@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: agents.JobContext):
    session = AgentSession()
    luna_core = LunaCore([])
    sleep_controller = SessionSleepWakeController(session, luna_core)

    await session.start(
        room=ctx.room,
        agent=Assistant(sleep_controller),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(model=ai_coustics.EnhancerModel.QUAIL_VF_S),
            ),
        ),
    )

    sleep_controller.sync_session_input()
    session.on("user_input_transcribed", sleep_controller.handle_transcription_event)

    await session.generate_reply(
        instructions=build_session_instruction()
    )


if __name__ == "__main__":
    agents.cli.run_app(server)