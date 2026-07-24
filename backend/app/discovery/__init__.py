"""Auto source discovery: keyless web search for candidate sources.

When a question finds no relevant approved source, the pipeline abstains
(INSUFFICIENT_EVIDENCE). This package searches the web — Wikipedia, DuckDuckGo,
and (if the CLI is present) the local Claude subscription — for candidate pages,
fuses them with reciprocal rank fusion, and returns them for the user to
validate. Chosen candidates are re-fetched server-side (SSRF-guarded) and
ingested as APPROVED sources; the deterministic pipeline then re-runs and still
cites-or-abstains. The model never asserts a fact unchecked — it only helps
*find* candidates. No paid API is ever called.
"""
