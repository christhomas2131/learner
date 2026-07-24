"""Discovery data types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Candidate:
    """A candidate source surfaced by web discovery, awaiting user validation."""

    url: str
    title: str
    snippet: str = ""
    providers: list[str] = field(default_factory=list)
