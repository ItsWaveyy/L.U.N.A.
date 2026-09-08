from brains.gemini import GeminiProvider
from brains.groq import GroqProvider
from brains.ollama import OllamaProvider
from brains.openai import OpenAIProvider


def load_providers():
    providers = []

    provider_factories = (
        ("gemini", GeminiProvider),
        ("groq", GroqProvider),
        ("openai", OpenAIProvider),
        ("local", OllamaProvider),
    )

    for name, factory in provider_factories:
        try:
            provider = factory()
            providers.append(provider)

            print(
                f"[L.U.N.A.] Brain loaded: "
                f"{name} ({provider.model})"
            )

        except Exception as exc:
            print(
                f"[L.U.N.A.] Brain unavailable: "
                f"{name} ({exc})"
            )

    return providers