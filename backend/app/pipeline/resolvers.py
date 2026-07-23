"""Deterministic question resolvers.

These answer questions that have a single objectively correct answer *without*
calling any model: arithmetic, percentages, date math, unit conversions, and
lookups against approved structured records / answer keys.

Computational resolvers (arithmetic/percentage/date/unit) are self-evidently
correct and carry their computation as evidence. Lookup resolvers cite the
approved structured source they read from.

Precision-sensitive math uses `decimal.Decimal`.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation, getcontext

getcontext().prec = 50


@dataclass
class ResolvedCitation:
    source_id: str
    passage_id: str
    quotation: str


@dataclass
class ResolvedAnswer:
    answer: str
    claim_text: str
    kind: str
    detail: str = ""
    # Present only for lookup resolvers backed by an approved source.
    citation: ResolvedCitation | None = field(default=None)

    @property
    def source_backed(self) -> bool:
        return self.citation is not None


# --------------------------------------------------------------------------- #
# Arithmetic
# --------------------------------------------------------------------------- #

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def _safe_arith(expr: str) -> Decimal | None:
    """Evaluate a pure arithmetic expression using Decimal. None if not safe."""
    try:
        node = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError):
        return None

    def _eval(n: ast.AST) -> Decimal:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                raise ValueError("non-numeric constant")
            return Decimal(str(n.value))
        if isinstance(n, ast.BinOp) and type(n.op) in _ALLOWED_BINOPS:
            left, right = _eval(n.left), _eval(n.right)
            return Decimal(_ALLOWED_BINOPS[type(n.op)](left, right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            val = _eval(n.operand)
            return val if isinstance(n.op, ast.UAdd) else -val
        raise ValueError("unsupported expression")

    try:
        return _eval(node)
    except (ValueError, ZeroDivisionError, DivisionByZero, InvalidOperation, TypeError):
        return None


def _format_decimal(d: Decimal) -> str:
    d = d.normalize()
    s = format(d, "f")
    return s


def arithmetic_resolver(question: str) -> ResolvedAnswer | None:
    q = question.strip().rstrip("?").strip()
    q = re.sub(r"(?i)^(what\s+is|whats|what's|calculate|compute|evaluate)\s+", "", q).strip()
    # Only accept if it looks purely arithmetic (digits, operators, parens, spaces).
    if not re.fullmatch(r"[0-9\.\s\+\-\*/%\(\)\^]+", q):
        return None
    if not re.search(r"[\+\-\*/%\^]", q):
        return None
    expr = q.replace("^", "**")
    result = _safe_arith(expr)
    if result is None:
        return None
    formatted = _format_decimal(result)
    return ResolvedAnswer(
        answer=f"{q} = {formatted}",
        claim_text=f"{q} equals {formatted}.",
        kind="arithmetic",
        detail=f"Computed deterministically with Decimal: {q} = {formatted}",
    )


# --------------------------------------------------------------------------- #
# Percentage
# --------------------------------------------------------------------------- #

_PCT_RE = re.compile(
    r"(?i)what\s+is\s+([0-9]*\.?[0-9]+)\s*(?:%|percent(?:age)?)\s+of\s+([0-9]*\.?[0-9]+)"
)


def percentage_resolver(question: str) -> ResolvedAnswer | None:
    m = _PCT_RE.search(question)
    if not m:
        return None
    pct = Decimal(m.group(1))
    whole = Decimal(m.group(2))
    result = (pct / Decimal(100)) * whole
    formatted = _format_decimal(result)
    return ResolvedAnswer(
        answer=f"{_format_decimal(pct)}% of {_format_decimal(whole)} = {formatted}",
        claim_text=f"{_format_decimal(pct)} percent of {_format_decimal(whole)} equals {formatted}.",
        kind="percentage",
        detail=f"Computed deterministically: ({pct}/100) * {whole} = {formatted}",
    )


# --------------------------------------------------------------------------- #
# Date math
# --------------------------------------------------------------------------- #

_ISO = r"(\d{4}-\d{2}-\d{2})"
_BETWEEN_RE = re.compile(rf"(?i)days?\s+between\s+{_ISO}\s+and\s+{_ISO}")
_OFFSET_RE = re.compile(rf"(?i)(\d+)\s+days?\s+(after|before)\s+{_ISO}")


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def date_resolver(question: str) -> ResolvedAnswer | None:
    m = _BETWEEN_RE.search(question)
    if m:
        d1, d2 = _parse_date(m.group(1)), _parse_date(m.group(2))
        if not d1 or not d2:
            return None
        days = abs((d2 - d1).days)
        return ResolvedAnswer(
            answer=f"There are {days} days between {m.group(1)} and {m.group(2)}.",
            claim_text=f"There are {days} days between {m.group(1)} and {m.group(2)}.",
            kind="date",
            detail=f"Computed deterministically: |{m.group(2)} - {m.group(1)}| = {days} days",
        )
    m = _OFFSET_RE.search(question)
    if m:
        n = int(m.group(1))
        direction = m.group(2).lower()
        base = _parse_date(m.group(3))
        if not base:
            return None
        from datetime import timedelta

        result = base + timedelta(days=n if direction == "after" else -n)
        return ResolvedAnswer(
            answer=f"{n} days {direction} {m.group(3)} is {result.isoformat()}.",
            claim_text=f"{n} days {direction} {m.group(3)} is {result.isoformat()}.",
            kind="date",
            detail=f"Computed deterministically: {m.group(3)} {'+' if direction=='after' else '-'} {n}d",
        )
    return None


# --------------------------------------------------------------------------- #
# Unit conversion
# --------------------------------------------------------------------------- #

# factor to a canonical base unit within each dimension
_LENGTH = {"m": Decimal(1), "km": Decimal(1000), "cm": Decimal("0.01"), "mm": Decimal("0.001"),
           "mi": Decimal("1609.344"), "mile": Decimal("1609.344"), "miles": Decimal("1609.344"),
           "ft": Decimal("0.3048"), "feet": Decimal("0.3048"), "foot": Decimal("0.3048"),
           "in": Decimal("0.0254"), "inch": Decimal("0.0254"), "inches": Decimal("0.0254"),
           "yd": Decimal("0.9144"), "yard": Decimal("0.9144"), "yards": Decimal("0.9144")}
_MASS = {"g": Decimal(1), "kg": Decimal(1000), "mg": Decimal("0.001"),
         "lb": Decimal("453.59237"), "lbs": Decimal("453.59237"), "pound": Decimal("453.59237"),
         "pounds": Decimal("453.59237"), "oz": Decimal("28.349523125"),
         "ounce": Decimal("28.349523125"), "ounces": Decimal("28.349523125")}
_DIMENSIONS = {"length": _LENGTH, "mass": _MASS}

_CONV_RE = re.compile(
    r"(?i)convert\s+([0-9]*\.?[0-9]+)\s*([a-z]+)\s+(?:to|into|in)\s+([a-z]+)"
)


def unit_resolver(question: str) -> ResolvedAnswer | None:
    m = _CONV_RE.search(question)
    if not m:
        # temperature special-case: "convert 100 c to f"
        return _temperature_resolver(question)
    value = Decimal(m.group(1))
    from_u = m.group(2).lower()
    to_u = m.group(3).lower()
    for table in _DIMENSIONS.values():
        if from_u in table and to_u in table:
            base = value * table[from_u]
            result = base / table[to_u]
            formatted = _format_decimal(result.quantize(Decimal("0.0001")).normalize())
            return ResolvedAnswer(
                answer=f"{_format_decimal(value)} {from_u} = {formatted} {to_u}",
                claim_text=f"{_format_decimal(value)} {from_u} equals {formatted} {to_u}.",
                kind="unit_conversion",
                detail="Computed deterministically via base-unit factors.",
            )
    # Not a length/mass pair — may still be a temperature conversion.
    return _temperature_resolver(question)


_TEMP_RE = re.compile(
    r"(?i)convert\s+([0-9]*\.?-?[0-9]+)\s*(?:deg(?:rees)?\s*)?([cf])"
    r"\s+(?:to|into|in)\s+(?:deg(?:rees)?\s*)?([cf])"
)


def _temperature_resolver(question: str) -> ResolvedAnswer | None:
    m = _TEMP_RE.search(question)
    if not m:
        return None
    value = Decimal(m.group(1))
    from_u, to_u = m.group(2).lower(), m.group(3).lower()
    if from_u == to_u:
        result = value
    elif from_u == "c":
        result = value * Decimal("9") / Decimal("5") + Decimal("32")
    else:
        result = (value - Decimal("32")) * Decimal("5") / Decimal("9")
    formatted = _format_decimal(result.quantize(Decimal("0.01")).normalize())
    return ResolvedAnswer(
        answer=f"{_format_decimal(value)}°{from_u.upper()} = {formatted}°{to_u.upper()}",
        claim_text=f"{_format_decimal(value)} degrees {from_u.upper()} equals {formatted} degrees {to_u.upper()}.",
        kind="unit_conversion",
        detail="Computed deterministically with the standard C/F formula.",
    )


COMPUTATIONAL_RESOLVERS = [
    arithmetic_resolver,
    percentage_resolver,
    date_resolver,
    unit_resolver,
]


def resolve_computational(question: str) -> ResolvedAnswer | None:
    for resolver in COMPUTATIONAL_RESOLVERS:
        result = resolver(question)
        if result is not None:
            return result
    return None


# --------------------------------------------------------------------------- #
# Lookup resolvers (definitions / answer keys) — source-backed
# --------------------------------------------------------------------------- #


def definition_resolver(question: str, records: list[dict]) -> ResolvedAnswer | None:
    """`records`: [{term, definition, source_id, passage_id}]."""
    m = re.search(r"(?i)(?:what\s+is|what\s+does|define)\s+(?:the\s+(?:term|word)\s+)?(.+?)\s*(?:mean)?\??$", question)
    if not m:
        return None
    term = m.group(1).strip().strip('"').lower()
    for rec in records:
        if rec.get("term", "").strip().lower() == term:
            return ResolvedAnswer(
                answer=rec["definition"],
                claim_text=rec["definition"],
                kind="definition",
                detail="Exact match against an approved vocabulary record.",
                citation=ResolvedCitation(
                    source_id=rec["source_id"],
                    passage_id=rec["passage_id"],
                    quotation=rec["definition"],
                ),
            )
    return None


def answer_key_resolver(question: str, records: list[dict]) -> ResolvedAnswer | None:
    """`records`: [{question, answer, source_id, passage_id}] exact-match key."""
    norm = re.sub(r"\s+", " ", question.strip().rstrip("?").strip().lower())
    for rec in records:
        if re.sub(r"\s+", " ", rec.get("question", "").strip().rstrip("?").strip().lower()) == norm:
            return ResolvedAnswer(
                answer=rec["answer"],
                claim_text=rec["answer"],
                kind="answer_key",
                detail="Exact match against an approved answer key.",
                citation=ResolvedCitation(
                    source_id=rec["source_id"],
                    passage_id=rec["passage_id"],
                    quotation=rec["answer"],
                ),
            )
    return None
