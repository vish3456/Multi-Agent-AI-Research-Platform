"""
Bedrock Guardrails — screens input and output text using Amazon Bedrock's
``ApplyGuardrail`` API.

Configured to detect hate speech, PII, weapons-related content, and
prompt-injection / jailbreak attacks.  The guardrail resource itself is
provisioned via Terraform (see ``terraform/modules/bedrock/``).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)


class BedrockGuardrails:
    """Thin wrapper around the Bedrock Runtime ``apply_guardrail`` call."""

    def __init__(
        self,
        guardrail_id: str,
        guardrail_version: str = "DRAFT",
        region: str = "us-east-1",
        client: Any = None,
    ) -> None:
        if client is not None:
            self.client = client
        else:
            try:
                import boto3
                self.client = boto3.client("bedrock-runtime", region_name=region)
            except ImportError:
                self.client = None
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version

    async def check(
        self,
        text: str,
        source: Literal["INPUT", "OUTPUT"] = "INPUT",
    ) -> tuple[bool, str]:
        """
        Screen *text* against the configured Bedrock Guardrail.

        Parameters
        ----------
        text : str
            The user input or model output to evaluate.
        source : ``"INPUT"`` | ``"OUTPUT"``
            Tells Bedrock whether the content is a user prompt or a model
            response so it can apply the appropriate policy filters.

        Returns
        -------
        tuple[bool, str]
            ``(is_safe, processed_text)`` — when the guardrail intervenes
            ``is_safe`` is ``False`` and ``processed_text`` contains the
            guardrail's replacement message.
        """
        # If guardrail_id is not configured, pass through (local dev).
        if not self.guardrail_id:
            logger.warning("Bedrock Guardrails not configured — skipping check.")
            return True, text

        # If running in local dev / mock mode, apply safety patterns for PyRIT testing
        if self.guardrail_id.startswith("mock") or self.guardrail_id == "mock-guardrail-id":
            lower_text = text.lower()
            dangerous_patterns = [
                "ignore all previous instructions",
                "system prompt credentials",
                "dangerous weapons",
                "explosives",
                "social security numbers",
                "credit card details",
                "bypass critic node",
                "system override",
            ]
            if any(p in lower_text for p in dangerous_patterns):
                logger.warning("Local mock guardrail BLOCKED %s content: safety violation detected.", source)
                return False, "Your request was blocked by the safety filter."
            return True, text

        try:
            response = self.client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source=source,
                content=[{"text": {"text": text}}],
            )

            action = response.get("action", "NONE")

            if action == "GUARDRAIL_INTERVENED":
                # Extract the guardrail's replacement text
                outputs = response.get("outputs", [])
                blocked_text = (
                    outputs[0]["text"]
                    if outputs
                    else "Your request was blocked by the safety filter."
                )

                # Log the assessment details for debugging
                assessments = response.get("assessments", [])
                logger.warning(
                    "Bedrock Guardrail BLOCKED %s content. Assessments: %s",
                    source,
                    assessments,
                )
                return False, blocked_text

            return True, text

        except Exception as exc:
            logger.error("Bedrock GuardRail API error: %s", exc)
            # Fail-open in case of transient AWS errors so we don't break the
            # entire service; a stricter policy would be to fail-closed here.
            return True, text
