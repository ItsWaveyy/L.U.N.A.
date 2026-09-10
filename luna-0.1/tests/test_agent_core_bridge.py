import asyncio

from agent import Assistant
from core.providers import AIResponse
from livekit.agents import llm


class FakeCore:
    def __init__(self):
        self.calls = []

    async def ask(self, **kwargs):
        self.calls.append(kwargs)
        return AIResponse(
            text="Routed reply",
            provider="local",
            model="test-model",
            metadata={"classified_task": "conversation"},
        )

    async def record_assistant_message(self, text):
        pass


def test_livekit_reply_is_generated_by_luna_core():
    asyncio.run(_test_livekit_reply_is_generated_by_luna_core())


async def _test_livekit_reply_is_generated_by_luna_core():
    core = FakeCore()
    assistant = Assistant(
        sleep_controller=object(),
        luna_core=core,
    )
    chat_ctx = llm.ChatContext.empty()
    chat_ctx.add_message(
        role="assistant",
        content="Good evening.",
    )
    chat_ctx.add_message(
        role="user",
        content="What is two plus two?",
    )

    replies = []

    async for reply in assistant.llm_node(
        chat_ctx=chat_ctx,
        tools=[],
        model_settings=None,
    ):
        replies.append(reply)

    assert replies == ["Routed reply"]
    assert core.calls[0]["prompt"] == "What is two plus two?"
    assert assistant.last_core_response.provider == "local"
