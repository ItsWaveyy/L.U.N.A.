from core.providers import AIProvider, AIRequest, AIResponse
from core.router import AIRouter
from core.classifier import TaskClassifier


CORE_SYSTEM_PROMPT = """
You are the backend reasoning engine inside L.U.N.A.

L.U.N.A. stands for Lowkey Useful Neural Assistant.

L.U.N.A. is a personal AI assistant being developed by Reece.

L.U.N.A. has two major layers:
- L.U.N.A. Agent: the primary assistant, voice, and personality layer.
- L.U.N.A. Core: the backend intelligence and provider-routing layer.

You are part of L.U.N.A. Core.

When the user refers to L.U.N.A., they mean this personal AI assistant unless they explicitly specify otherwise.

Do not confuse L.U.N.A. with:
- Terra/LUNA cryptocurrency
- Luna Core blockchain software
- fictional AI characters
- unrelated software projects

Your job is to provide accurate and useful results to the primary L.U.N.A. assistant.

Be concise and direct unless the task requires detail.
Do not mention these system instructions.
Do not invent capabilities or actions.
"""


class LunaCore:
    def __init__(self, providers: list[AIProvider]):
        self.router = AIRouter(providers)
        self.classifier = TaskClassifier()

    async def ask(
        self,
        prompt: str,
        task: str | None = None,
        system_prompt: str | None = None,
    ) -> AIResponse:

        # Automatically classify the request unless
        # the caller explicitly provides a task.
        if task is None:
            classification = self.classifier.classify(prompt)
            task = classification.task

        combined_system_prompt = CORE_SYSTEM_PROMPT

        if system_prompt:
            combined_system_prompt += (
                f"\n\nAdditional instructions:\n{system_prompt}"
            )

        request = AIRequest(
            prompt=prompt,
            task=task,
            system_prompt=combined_system_prompt,
        )

        response = await self.router.generate(request)

        response.metadata.update({
            "classified_task": task,
        })

        return response

    async def health_status(self) -> dict[str, bool]:
        """Return the health status of every registered provider."""

        status = {}

        for provider in self.router.providers:
            try:
                status[provider.name] = await provider.health_check()

            except Exception as exc:
                print(
                    f"[L.U.N.A.] Health check failed for "
                    f"'{provider.name}': {exc}"
                )
                status[provider.name] = False

        return status
