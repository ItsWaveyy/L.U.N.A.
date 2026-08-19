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


class TaskClassifier:
    """Classifies user requests into L.U.N.A. Core task categories."""

    def classify(self, prompt: str) -> Classification:
        text = prompt.lower().strip()

        if not text:
            return Classification(
                task="general",
                confidence=1.0,
                reason="Empty prompt.",
            )

        # ---------------------------------------------------------
        # CODING
        # ---------------------------------------------------------
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
            )

        # ---------------------------------------------------------
        # CREATIVE
        # ---------------------------------------------------------
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
            )

        # ---------------------------------------------------------
        # RESEARCH
        # ---------------------------------------------------------
        research_keywords = (
            "today",
            "latest",
            "recent",
            "news",
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
        )

        if any(keyword in text for keyword in research_keywords):
            return Classification(
                task="research",
                confidence=0.90,
                reason="Detected research or current-information terminology.",
            )

        # ---------------------------------------------------------
        # CONVERSATION
        # ---------------------------------------------------------
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
        )

        if any(keyword in text for keyword in conversation_keywords):
            return Classification(
                task="conversation",
                confidence=0.85,
                reason="Detected an open-ended conversational request.",
            )

        # ---------------------------------------------------------
        # FAST
        # ---------------------------------------------------------
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
        )

        if any(keyword in text for keyword in fast_keywords):
            return Classification(
                task="fast",
                confidence=0.85,
                reason="Detected a short factual or utility request.",
            )

        # ---------------------------------------------------------
        # DEFAULT
        # ---------------------------------------------------------
        return Classification(
            task="general",
            confidence=0.60,
            reason="No specialized task pattern detected.",
        )
