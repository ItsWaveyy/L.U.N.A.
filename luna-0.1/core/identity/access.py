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
    Central authorization policy for L.U.N.A.

    SpeakerIdentity answers:
        "Who is speaking?"

    AccessController answers:
        "What is this person allowed to do?"

    Identity and authorization are intentionally separate.
    A recognized speaker does not automatically receive every
    available privilege.
    """

    # ---------------------------------------------------------
    # ROLE / PRIVILEGE DEFINITIONS
    # ---------------------------------------------------------

    OWNER = "owner"
    GUEST = "guest"
    UNKNOWN = "unknown"

    PRIVILEGE_WAKE = "wake"
    PRIVILEGE_INTERRUPT = "interrupt"
    PRIVILEGE_TOOLS = "tools"
    PRIVILEGE_MEMORY = "memory"
    PRIVILEGE_EMAIL = "email"
    PRIVILEGE_SYSTEM = "system"
    PRIVILEGE_CONFIG = "config"
    PRIVILEGE_SELF_IMPROVE = "self_improve"

    def __init__(
        self,
        allow_unknown: bool = False,
    ):
        self.allow_unknown = allow_unknown

    # ---------------------------------------------------------
    # IDENTITY → ROLE
    # ---------------------------------------------------------

    def role_for(
        self,
        match: SpeakerMatch,
    ) -> str:
        """
        Convert a speaker identity result into an authorization role.

        Current policy:
            authorized speaker -> owner
            known unauthorized speaker -> guest
            unknown speaker -> unknown

        Roles are policy concepts. SpeakerIdentity itself does not
        assign privileges.
        """

        if match.name is None:
            return self.UNKNOWN

        if match.authorized:
            return self.OWNER

        return self.GUEST

    # ---------------------------------------------------------
    # PRIVILEGE POLICY
    # ---------------------------------------------------------

    def has_privilege(
        self,
        match: SpeakerMatch,
        privilege: str,
    ) -> bool:
        """
        Determine whether a speaker may perform a specific action.

        This is the central privilege policy used by future Core
        and tool integrations.

        Owner:
            full privileges.

        Guest:
            no sensitive privileges yet.

        Unknown:
            no privileges unless explicitly permitted by a
            future policy.

        Keep sensitive capabilities explicit rather than deriving
        them implicitly from speaker recognition.
        """

        role = self.role_for(match)

        if role == self.OWNER:
            return True

        # Guests and unknown speakers currently receive no
        # sensitive privileges.
        return False

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

    # ---------------------------------------------------------
    # EXPLICIT PRIVILEGE CHECKS
    # ---------------------------------------------------------

    def can_execute_tool(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may execute L.U.N.A. tools.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_TOOLS,
            "execute tools",
        )

    def can_access_memory(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may access L.U.N.A.'s
        persistent/private memory.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_MEMORY,
            "access private memory",
        )

    def can_send_email(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may instruct L.U.N.A.
        to send email.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_EMAIL,
            "send email",
        )

    def can_control_system(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may perform system-level
        actions.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_SYSTEM,
            "control the system",
        )

    def can_modify_config(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may modify L.U.N.A.'s
        configuration.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_CONFIG,
            "modify L.U.N.A. configuration",
        )

    def can_self_improve(
        self,
        match: SpeakerMatch,
    ) -> AccessDecision:
        """
        Determine whether a speaker may authorize L.U.N.A.
        to modify or improve its own behavior.

        This is intentionally an explicit privilege rather than
        something implied by generic authorization.
        """

        return self._privilege_decision(
            match,
            self.PRIVILEGE_SELF_IMPROVE,
            "authorize self-improvement",
        )

    # ---------------------------------------------------------
    # PRIVILEGE DECISION HELPER
    # ---------------------------------------------------------

    def _privilege_decision(
        self,
        match: SpeakerMatch,
        privilege: str,
        action_description: str,
    ) -> AccessDecision:
        """
        Convert a privilege check into a complete AccessDecision.
        """

        allowed = self.has_privilege(match, privilege)
        role = self.role_for(match)

        if match.name is None:
            return AccessDecision(
                allowed=False,
                name=None,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    f"Unknown speaker is not authorized to "
                    f"{action_description}."
                ),
            )

        if not match.authorized:
            return AccessDecision(
                allowed=False,
                name=match.name,
                authorized=False,
                confidence=match.confidence,
                reason=(
                    f"Speaker '{match.name}' has role '{role}' "
                    f"and is not authorized to "
                    f"{action_description}."
                ),
            )

        if not allowed:
            return AccessDecision(
                allowed=False,
                name=match.name,
                authorized=True,
                confidence=match.confidence,
                reason=(
                    f"Speaker '{match.name}' is authorized but "
                    f"does not have privilege '{privilege}'."
                ),
            )

        return AccessDecision(
            allowed=True,
            name=match.name,
            authorized=True,
            confidence=match.confidence,
            reason=(
                f"Authorized speaker '{match.name}' may "
                f"{action_description}."
            ),
        )

    # ---------------------------------------------------------
    # DESCRIPTION / LOGGING
    # ---------------------------------------------------------

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

        role = self.role_for(match)

        return (
            f"{match.name} "
            f"({status}, role={role}, "
            f"confidence={match.confidence:.2f})"
        )