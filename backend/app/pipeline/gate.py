"""The release gate — implemented entirely in Python.

This is the only place a final top-level status is decided. The model cannot
reach it, cannot bypass it, and cannot influence it except by producing claims
that the deterministic layers already validated. Given a fully-assembled,
already-validated gate input, `decide` returns the authoritative status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import ClaimStatus, TopLevelStatus


@dataclass
class GateInput:
    deterministic: bool
    approved_support_count: int
    material_claim_statuses: list[ClaimStatus]
    all_quotations_valid: bool
    contradiction: bool
    model_calls_exhausted: bool  # malformed/timeout retries ran out -> ERROR
    stage_failed: bool
    error_message: str | None = None


@dataclass
class GateDecision:
    status: TopLevelStatus
    reasons: list[str] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        return self.status == TopLevelStatus.VERIFIED


def decide(gi: GateInput) -> GateDecision:
    reasons: list[str] = []

    if gi.stage_failed or gi.error_message:
        reasons.append(gi.error_message or "A required pipeline stage failed.")
        return GateDecision(TopLevelStatus.ERROR, reasons)

    if gi.model_calls_exhausted:
        reasons.append("Model call retry limit exceeded before a valid response.")
        return GateDecision(TopLevelStatus.ERROR, reasons)

    if gi.contradiction:
        reasons.append("Approved sources contradict a material claim.")
        return GateDecision(TopLevelStatus.CONTRADICTION, reasons)

    # Deterministic computational answers are self-evident ground truth.
    if gi.deterministic:
        reasons.append("Answer produced by a deterministic resolver.")
        return GateDecision(TopLevelStatus.VERIFIED, reasons)

    if gi.approved_support_count < 1:
        reasons.append("No approved source supported the answer.")
        return GateDecision(TopLevelStatus.INSUFFICIENT_EVIDENCE, reasons)

    if not gi.all_quotations_valid:
        reasons.append("One or more supporting quotations failed validation.")
        return GateDecision(TopLevelStatus.INSUFFICIENT_EVIDENCE, reasons)

    if not gi.material_claim_statuses:
        reasons.append("No material claim was supported by evidence.")
        return GateDecision(TopLevelStatus.INSUFFICIENT_EVIDENCE, reasons)

    if all(s == ClaimStatus.SUPPORTED for s in gi.material_claim_statuses):
        reasons.append("Every material claim is supported by an approved source.")
        return GateDecision(TopLevelStatus.VERIFIED, reasons)

    reasons.append("A material claim is not supported by approved evidence.")
    return GateDecision(TopLevelStatus.INSUFFICIENT_EVIDENCE, reasons)
