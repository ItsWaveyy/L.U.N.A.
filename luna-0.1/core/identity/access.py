from dataclasses import dataclass

from core.identity.speaker import SpeakerMatch


@dataclass(frozen=True)
class AccessDecision:
    """
    Result of an L.U.N.A. identity authorization check.
    """

    allowed: bool
    name: str | None
    authorized: bool
    confidence: float
    reason: str


class AccessController:
    """
    Converts speaker identity matches into authorization decisions.

    SpeakerIdentity answers:
        "Who is speaking?"

    AccessController answers:
        "Is this person allowed to perform this action?"
    """

    def __init__(
        self,
        allow_unknown: bool = False,
    ):
        self.allow_unknown = allow_unknown

    # ---------------------------------------------------------
    # WAKE AUTHORIZATION
    # ---------------------------------------------------------

    def can_wake(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a detected speaker may wake L.U.N.A.

        Standby wake is intentionally strict:
            - enrolled + authorized -> allowed
            - enrolled + unauthorized -> denied
            - unknown -> denied
        """

        if match.name is None:
            return AccessDecision(
                allowed=self.allow_unknown,
                name=None,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    "Unknown speaker attempted standby wake."
                ),
            )

        if not match.authorized:
            return AccessDecision(
                allowed=False,
                name=match.name,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    f"Speaker '{match.name}' is not "
                    "authorized to wake L.U.N.A."
                ),
            )

        return AccessDecision(
            allowed=True,
            name=match.name,
            authorized=True,
            confidence=match.confidence,
            reason=(
                f"Authorized speaker '{match.name}' "
                "may wake L.U.N.A."
            ),
        )

    # ---------------------------------------------------------
    # INTERRUPTION AUTHORIZATION
    # ---------------------------------------------------------

    def can_interrupt(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker should receive normal
        interruption privileges while L.U.N.A. is speaking.

        Authorized speakers:
            normal interruption behavior.

        Known but unauthorized speakers:
            denied normal interruption privileges.

        Unknown speakers:
            denied normal interruption privileges.

        The AgentSession's existing interruption settings still
        determine the actual mechanics. This layer only provides
        identity-aware policy.
        """

        if match.name is None:
            return AccessDecision(
                allowed=False,
                name=None,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    "Unknown speaker does not receive "
                    "normal interruption privileges."
                ),
            )

        if not match.authorized:
            return AccessDecision(
                allowed=False,
                name=match.name,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    f"Speaker '{match.name}' is known but "
                    "not authorized for normal interruption."
                ),
            )

        return AccessDecision(
            allowed=True,
            name=match.name,
            authorized=True,
            confidence=match.confidence,
            reason=(
                f"Authorized speaker '{match.name}' "
                "may interrupt normally."
            ),
        )

    # ---------------------------------------------------------
    # GENERAL AUTHORIZATION
    # ---------------------------------------------------------

    def is_authorized(
        self,
        match: SpeakerMatch,
    ) -> bool:
        """
        Simple authorization check for general L.U.N.A. actions.
        """

        return bool(
            match.name is not None
            and match.authorized
        )

    def describe(
        self,
        match: SpeakerMatch,
    ) -> str:
        """
        Produce a human-readable identity description useful
        for logging and debugging.
        """

        if match.name is None:
            return (
                "Unknown speaker "
                f"(confidence={match.confidence:.2f})"
            )

        status = (
            "authorized"
            if match.authorized
            else "unauthorized"
        )

        return (
            f"{match.name} "
            f"({status}, "
            f"confidence={match.confidence:.2f})"
        )