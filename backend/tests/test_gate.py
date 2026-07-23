"""Release gate tests — the gate is the sole authority and cannot be bypassed."""

from __future__ import annotations

from app.core.enums import ClaimStatus, TopLevelStatus
from app.pipeline import gate


def _base(**over) -> gate.GateInput:
    defaults = dict(
        deterministic=False, approved_support_count=1,
        material_claim_statuses=[ClaimStatus.SUPPORTED], all_quotations_valid=True,
        contradiction=False, model_calls_exhausted=False, stage_failed=False,
        error_message=None,
    )
    defaults.update(over)
    return gate.GateInput(**defaults)


def test_verified_happy_path():
    assert gate.decide(_base()).status == TopLevelStatus.VERIFIED


def test_no_support_abstains():
    d = gate.decide(_base(approved_support_count=0))
    assert d.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


def test_unsupported_material_abstains():
    d = gate.decide(_base(material_claim_statuses=[ClaimStatus.INSUFFICIENT_EVIDENCE]))
    assert d.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


def test_invalid_quotations_abstain():
    d = gate.decide(_base(all_quotations_valid=False))
    assert d.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


def test_contradiction_wins():
    d = gate.decide(_base(contradiction=True))
    assert d.status == TopLevelStatus.CONTRADICTION


def test_stage_failure_is_error():
    d = gate.decide(_base(stage_failed=True, error_message="boom"))
    assert d.status == TopLevelStatus.ERROR


def test_model_exhaustion_is_error():
    d = gate.decide(_base(model_calls_exhausted=True))
    assert d.status == TopLevelStatus.ERROR


def test_deterministic_is_verified_without_sources():
    d = gate.decide(_base(deterministic=True, approved_support_count=0,
                          material_claim_statuses=[ClaimStatus.SUPPORTED]))
    assert d.status == TopLevelStatus.VERIFIED


def test_error_precedence_over_contradiction():
    d = gate.decide(_base(stage_failed=True, contradiction=True, error_message="x"))
    assert d.status == TopLevelStatus.ERROR
