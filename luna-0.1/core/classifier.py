from dataclasses import dataclass


TASK_TYPES = {
    "fast",
    "general",
    "conversation",
    "coding",
    "research",
    "creative",
}


@dataclass
class Classification:
    task: str
    confidence: float
    reason: str
    requires_network: bool = False


class TaskClassifier:
    """Classifies user requests into L.U.N.A. Core task categories."""

    def requires_network(self, prompt: str) -> tuple[bool, str]:
        text = prompt.lower().strip()

        network_keywords = (
            "today",
            "tonight",
            "tomorrow",
            "yesterday",
            "latest",
            "recent",
            "currently",
            "current",
            "right now",
            "this week",
            "this month",
            "this year",
            "news",
            "weather",
            "forecast",
            "temperature",
            "stock price",
            "stock market",
            "traffic",
            "score",
            "scores",
            "live",
            "real time",
            "real-time",
            "what happened",
            "what's happening",
            "who won",
            "who is winning",
        )

        for keyword in network_keywords:
            if keyword in text:
                return True, f"Detected live/current information request: '{keyword}'."

        return False, "Request does not require live information."

    def classify(self, prompt: str) -> Classification:
        text = prompt.lower().strip()
        requires_network, network_reason = self.requires_network(text)

        if not text:
            return Classification(
                task="general",
                confidence=1.0,
                reason="Empty prompt.",
                requires_network=requires_network,
            )

        # CONVERSATION
        conversation_keywords = (
            "what do you think",
            "do you think",
            "how do you feel",
            "what would you do",
            "your opinion",
            "tell me about yourself",
            "let's talk",
            "talk to me",
            "i feel",
            "i'm feeling",
            "i am feeling",
            "how are you",
            "how you doing",
            "how are things",
            "what's up",
            "whats up",
        )

        if any(keyword in text for keyword in conversation_keywords):
            return Classification(
                task="conversation",
                confidence=0.90,
                reason="Detected an open-ended conversational request.",
                requires_network=requires_network,
            )

        # WEATHER / LIVE UTILITY
        weather_keywords = (
            "weather",
            "forecast",
            "temperature",
            "rain",
            "snow",
            "humidity",
            "wind",
            "wind speed",
            "conditions",
        )

        if any(keyword in text for keyword in weather_keywords):
            return Classification(
                task="fast",
                confidence=0.95,
                reason="Detected a weather or live utility request.",
                requires_network=requires_network,
            )

        # CODING
        coding_keywords = (
            "python",
            "javascript",
            "typescript",
            "java ",
            "c++",
            "c#",
            "html",
            "css",
            "sql",
            "code",
            "coding",
            "program",
            "programming",
            "function",
            "variable",
            "bug",
            "debug",
            "error",
            "exception",
            "traceback",
            "api",
            "github",
            "git ",
            "script",
            "repository",
            "repo",
        )

        if any(keyword in text for keyword in coding_keywords):
            return Classification(
                task="coding",
                confidence=0.95,
                reason="Detected coding-related terminology.",
                requires_network=requires_network,
            )

        # CREATIVE
        creative_keywords = (
            "write me",
            "write a",
            "come up with",
            "make up",
            "brainstorm",
            "caption",
            "poem",
            "lyrics",
            "story",
            "joke",
            "slogan",
            "name ideas",
            "username",
            "creative",
            "design an idea",
        )

        if any(keyword in text for keyword in creative_keywords):
            return Classification(
                task="creative",
                confidence=0.90,
                reason="Detected a creative-generation request.",
                requires_network=requires_network,
            )

        # RESEARCH / CURRENT INFORMATION
        research_keywords = (
            "latest",
            "recent",
            "news",
            "currently",
            "current",
            "right now",
            "this week",
            "this month",
            "compare",
            "comparison",
            "research",
            "investigate",
            "according to",
            "sources",
            "statistics",
            "study",
            "studies",
            "what happened",
            "what's happening",
            "who won",
            "who is winning",
        )

        if any(keyword in text for keyword in research_keywords):
            return Classification(
                task="research",
                confidence=0.90,
                reason="Detected research or current-information terminology.",
                requires_network=requires_network,
            )

        # FAST
        fast_keywords = (
            "what is",
            "what's",
            "who is",
            "who's",
            "where is",
            "when is",
            "how much is",
            "how many",
            "define ",
            "meaning of",
            "calculate",
            "convert",
            "how long",
            "how far",
            "what about",
        )

        if any(keyword in text for keyword in fast_keywords):
            return Classification(
                task="fast",
                confidence=0.85,
                reason="Detected a short factual or utility request.",
                requires_network=requires_network,
            )

        return Classification(
            task="general",
            confidence=0.60,
            reason="No specialized task pattern detected.",
            requires_network=requires_network,
        )