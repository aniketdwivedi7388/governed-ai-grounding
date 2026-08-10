"""Heuristic evaluators for answers produced by data-grounded enterprise agents.

This module holds two things:

1. The small domain model shared by the whole evaluation package
   (:class:`ContextChunk`, :class:`EvalCase`, :class:`EvalResult`,
   :class:`Evaluator`).
2. A set of concrete, dependency-light evaluators that score a generated answer
   against the context it was supposedly grounded in.

Design intent
-------------
These evaluators are **regression gates**, not judges of truth. They are cheap,
deterministic, offline and explainable, which makes them safe to run on every
pull request. They are deliberately implemented with lexical/numeric heuristics
so that a CI pipeline needs no model endpoint, no API key and no network.

Honest statement of limits (please read before trusting a score)
---------------------------------------------------------------
* **Groundedness here is token overlap, not entailment.** An answer that
  reuses context vocabulary while stating the opposite meaning ("AUM *excludes*
  discretionary mandates") will score well. These heuristics catch *fabricated
  vocabulary*, not *inverted logic*.
* **Numeric consistency checks presence, not correctness of derivation.** A
  number copied from an unrelated row of the context passes.
* **Answer relevance is bag-of-words F1.** A fluent paraphrase using different
  business vocabulary is penalised unfairly.
* **Nothing here measures whether the retrieved context was the *right*
  context.** Retrieval quality must be evaluated separately, against a labelled
  retrieval set.

Use these to detect *drift* (a prompt change that starts producing uncited or
unsupported answers). Use human review, or an LLM-as-judge harness with its own
calibration set, to decide whether an answer is actually correct.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

__all__ = [
    "ContextChunk",
    "EvalCase",
    "EvalResult",
    "Evaluator",
    "GroundednessEvaluator",
    "CitationCoverageEvaluator",
    "NumericConsistencyEvaluator",
    "AbstentionCorrectnessEvaluator",
    "AnswerRelevanceEvaluator",
    "StalenessEvaluator",
    "default_evaluators",
]


# ---------------------------------------------------------------------------
# Lexical helpers
# ---------------------------------------------------------------------------

#: Small closed-class stopword list. Kept short and inspectable on purpose --
#: a large curated list would make scores harder to reason about.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but if then than that this these those there here
    is are was were be been being am do does did doing done
    have has had having of to in on at by for with from as into about
    it its it's we you your our their his her they them he she i me my
    not no nor so such only own same too very can will just should would
    could may might must shall per via across over under between
    what which who whom whose when where why how
    """.split()
)

#: Matches citation markers of the form ``[C1]`` / ``[C12]`` (case-insensitive).
CITATION_RE = re.compile(r"\[c(\d+)\]", re.IGNORECASE)

#: Matches numeric literals, optionally with thousands separators / decimals.
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")

#: Magnitude suffixes that commonly follow a number in enterprise prose.
SCALE_WORDS: Mapping[str, float] = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mm": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "bn": 1e9,
    "b": 1e9,
    "billion": 1e9,
    "tn": 1e12,
    "trn": 1e12,
    "trillion": 1e12,
}

#: Phrases that signal an explicit refusal to answer.
ABSTENTION_MARKERS: tuple[str, ...] = (
    "i do not have",
    "i don't have",
    "i cannot answer",
    "i can't answer",
    "cannot be answered",
    "not enough information",
    "insufficient context",
    "insufficient information",
    "no certified",
    "not available in the provided context",
    "unable to answer",
    "outside the provided context",
    "i am not able to",
    "i'm not able to",
    "cannot confirm",
    "declining to answer",
)

#: Phrases that signal a request for disambiguation rather than a refusal.
DISAMBIGUATION_MARKERS: tuple[str, ...] = (
    "which definition",
    "could you clarify",
    "can you clarify",
    "please clarify",
    "please confirm which",
    "two definitions",
    "more than one definition",
    "multiple definitions",
    "ambiguous",
    "do you mean",
    "which of these",
    "which measure",
)


def tokenize(text: str) -> list[str]:
    """Lowercase and split ``text`` into alphanumeric word tokens."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def content_tokens(text: str, min_length: int = 3) -> set[str]:
    """Return the set of meaningful tokens in ``text``.

    Stopwords and very short tokens are dropped so that the overlap metrics
    reflect domain vocabulary rather than English grammar.
    """
    return {
        token
        for token in tokenize(text)
        if token not in STOPWORDS and (len(token) >= min_length or token.isdigit())
    }


def strip_citations(text: str) -> str:
    """Remove ``[C1]``-style markers so their digits do not pollute number extraction."""
    return CITATION_RE.sub(" ", text)


@dataclass(frozen=True)
class NumberMention:
    """A numeric literal found in text, with the values it could plausibly denote."""

    raw: str
    value: float
    candidates: tuple[float, ...]

    def matches(self, other: "NumberMention", rel_tolerance: float = 0.005) -> bool:
        """True if any candidate reading of this number matches ``other``."""
        for left in self.candidates:
            for right in other.candidates:
                if _close(left, right, rel_tolerance):
                    return True
        return False


def _close(left: float, right: float, rel_tolerance: float) -> bool:
    """Relative-tolerance comparison that also tolerates rounding at 1 d.p."""
    if left == right:
        return True
    scale = max(abs(left), abs(right), 1e-9)
    if abs(left - right) / scale <= rel_tolerance:
        return True
    # Tolerate a value that is a rounded rendering of the other (12.4 vs 12.43).
    for places in (0, 1, 2):
        if round(left, places) == round(right, places):
            return True
    return False


def extract_numbers(text: str) -> list[NumberMention]:
    """Extract numeric mentions from ``text``, resolving magnitude suffixes.

    ``"USD 1.2bn"`` yields candidates ``(1.2, 1_200_000_000.0)`` so that an
    answer written in shorthand still matches a context that spells the figure
    out in full (and vice versa).
    """
    cleaned = strip_citations(text)
    mentions: list[NumberMention] = []
    for match in NUMBER_RE.finditer(cleaned):
        raw = match.group(0)
        try:
            value = float(raw.replace(",", ""))
        except ValueError:  # pragma: no cover - regex makes this unreachable
            continue
        candidates: set[float] = {value}
        trailer = cleaned[match.end() : match.end() + 12].lower().lstrip()
        suffix_match = re.match(r"[a-z]+", trailer)
        if suffix_match:
            multiplier = SCALE_WORDS.get(suffix_match.group(0))
            if multiplier:
                candidates.add(value * multiplier)
        mentions.append(NumberMention(raw=raw, value=value, candidates=tuple(sorted(candidates))))
    return mentions


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (with or without ``Z``) into an aware datetime."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        LOGGER.debug("Could not parse timestamp %r", value)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def contains_any(text: str, markers: Iterable[str]) -> str | None:
    """Return the first marker found in ``text``, or ``None``."""
    lowered = text.lower()
    for marker in markers:
        if marker in lowered:
            return marker
    return None


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass
class ContextChunk:
    """One retrieved unit of governed context handed to the model.

    The provenance fields mirror the context block contract documented in
    ``prompts/grounded-answer-template.md``. They are not decoration: every one
    of them is consumed by at least one control (citation, staleness,
    certification gating, entitlement audit).
    """

    id: str
    content: str
    source: str = "unknown"
    dataset: str = "unknown"
    certified: bool = False
    as_of: str | None = None
    owner: str | None = None
    sensitivity: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], fallback_id: str) -> "ContextChunk":
        """Build a chunk from a loosely-typed mapping, tolerating missing keys."""
        return cls(
            id=str(raw.get("id") or fallback_id),
            content=str(raw.get("content", "")),
            source=str(raw.get("source", "unknown")),
            dataset=str(raw.get("dataset", "unknown")),
            certified=bool(raw.get("certified", False)),
            as_of=raw.get("as_of"),
            owner=raw.get("owner"),
            sensitivity=raw.get("sensitivity"),
        )

    @property
    def as_of_datetime(self) -> datetime | None:
        """The chunk's as-of timestamp, parsed."""
        return parse_timestamp(self.as_of)


@dataclass
class EvalCase:
    """A single evaluation record loaded from the JSONL eval set."""

    id: str
    question: str
    expected_answer: str = ""
    expected_sources: list[str] = field(default_factory=list)
    retrieved_context: list[ContextChunk] = field(default_factory=list)
    generated_answer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvalCase":
        """Build an :class:`EvalCase` from a decoded JSONL line."""
        chunks_raw = raw.get("retrieved_context") or []
        chunks = [
            ContextChunk.from_dict(chunk, fallback_id=f"C{index}")
            for index, chunk in enumerate(chunks_raw, start=1)
        ]
        return cls(
            id=str(raw.get("id", "<unknown>")),
            question=str(raw.get("question", "")),
            expected_answer=str(raw.get("expected_answer", "")),
            expected_sources=[str(s) for s in (raw.get("expected_sources") or [])],
            retrieved_context=chunks,
            generated_answer=str(raw.get("generated_answer", "")),
            metadata=dict(raw.get("metadata") or {}),
        )

    # -- convenience accessors ------------------------------------------------

    @property
    def expected_behaviour(self) -> str:
        """One of ``answer``, ``abstain`` or ``disambiguate``.

        ``metadata.expected_behaviour`` is authoritative; the legacy boolean
        ``metadata.should_abstain`` is honoured as a fallback.
        """
        declared = self.metadata.get("expected_behaviour")
        if isinstance(declared, str) and declared in {"answer", "abstain", "disambiguate"}:
            return declared
        if self.metadata.get("should_abstain"):
            return "abstain"
        return "answer"

    @property
    def as_of_tolerance_days(self) -> float | None:
        """Maximum acceptable age of the grounding context, in days."""
        raw = self.metadata.get("as_of_tolerance_days")
        return float(raw) if isinstance(raw, (int, float)) else None

    @property
    def evaluated_at(self) -> datetime | None:
        """Pinned reference time, so eval-set scores are reproducible."""
        return parse_timestamp(self.metadata.get("evaluated_at"))

    @property
    def context_text(self) -> str:
        """All retrieved content concatenated, for lexical comparisons."""
        return "\n".join(chunk.content for chunk in self.retrieved_context)

    def cited_ids(self) -> list[str]:
        """Citation markers present in the generated answer, upper-cased."""
        return [f"C{number}" for number in CITATION_RE.findall(self.generated_answer)]

    def is_abstaining(self) -> bool:
        """True if the answer explicitly declines to answer."""
        return contains_any(self.generated_answer, ABSTENTION_MARKERS) is not None

    def is_disambiguating(self) -> bool:
        """True if the answer asks the user to choose between definitions."""
        return contains_any(self.generated_answer, DISAMBIGUATION_MARKERS) is not None


@dataclass
class EvalResult:
    """The score one evaluator assigned to one case."""

    evaluator: str
    score: float
    rationale: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = max(0.0, min(1.0, float(self.score)))

    def as_dict(self) -> dict[str, Any]:
        """JSON-serialisable view."""
        return {
            "evaluator": self.evaluator,
            "score": round(self.score, 4),
            "rationale": self.rationale,
            "details": self.details,
        }


class Evaluator(ABC):
    """Base class for all evaluators.

    Implementations must be pure functions of the case: no network, no clock
    reads (use ``case.evaluated_at`` or the injected reference time), no global
    state. That is what makes the suite usable as a CI gate.
    """

    #: Stable machine-readable name, used as a JSON key and CSV header.
    name: str = "evaluator"
    #: Compact label for the console table.
    short_name: str = "eval"
    #: Relative weight when computing a case's overall score.
    weight: float = 1.0

    @abstractmethod
    def evaluate(self, case: EvalCase) -> EvalResult:
        """Score ``case`` and return a result in the closed interval [0, 1]."""

    # Small helper so subclasses stay terse.
    def _result(self, score: float, rationale: str, **details: Any) -> EvalResult:
        return EvalResult(self.name, score, rationale, details)

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        return f"<{type(self).__name__} name={self.name!r} weight={self.weight}>"


# ---------------------------------------------------------------------------
# Concrete evaluators
# ---------------------------------------------------------------------------


class GroundednessEvaluator(Evaluator):
    """Fraction of the answer's domain vocabulary that also appears in context.

    **Heuristic.** Tokenise the answer, drop stopwords and short tokens, and
    measure how many of the remaining tokens occur in the retrieved context.
    A confidently fabricated sentence introduces vocabulary the context never
    contained, so it scores low.

    **Limits.** This is lexical overlap, not entailment. It cannot detect a
    negated or reversed claim built from context vocabulary; it penalises
    legitimate paraphrase; and because there is no stemming, ``excludes`` does
    not match ``excluded``. Expect well-behaved answers to land in the 0.80-1.00
    band rather than at a clean 1.00, and calibrate the threshold on your own
    corpus. Treat a *drop* in this score as a signal to look, not as proof of
    hallucination.
    """

    name = "groundedness"
    short_name = "ground"

    def __init__(self, weight: float = 1.5, min_token_length: int = 3) -> None:
        self.weight = weight
        self.min_token_length = min_token_length

    def evaluate(self, case: EvalCase) -> EvalResult:
        if case.expected_behaviour in {"abstain", "disambiguate"} and (
            case.is_abstaining() or case.is_disambiguating()
        ):
            return self._result(
                1.0,
                "Not applicable: answer correctly withholds a substantive claim.",
                applicable=False,
            )

        answer_tokens = content_tokens(strip_citations(case.generated_answer), self.min_token_length)
        if not answer_tokens:
            return self._result(0.0, "Answer contains no scoreable content tokens.", applicable=True)

        context_tokens = content_tokens(case.context_text, self.min_token_length)
        # Question vocabulary is fair game: echoing the user's own words is not
        # a fabrication, so we treat it as supported.
        context_tokens |= content_tokens(case.question, self.min_token_length)

        supported = answer_tokens & context_tokens
        unsupported = sorted(answer_tokens - context_tokens)
        score = len(supported) / len(answer_tokens)
        rationale = (
            f"{len(supported)}/{len(answer_tokens)} content tokens supported by context"
        )
        if unsupported:
            rationale += f"; unsupported e.g. {', '.join(unsupported[:6])}"
        return self._result(
            score,
            rationale,
            applicable=True,
            unsupported_tokens=unsupported[:25],
            supported_count=len(supported),
            answer_token_count=len(answer_tokens),
        )


class CitationCoverageEvaluator(Evaluator):
    """Does the answer cite, and do its citations resolve to real context?

    Scores three things and averages them:

    * **Presence** -- a substantive answer carries at least one ``[Cn]`` marker.
    * **Validity** -- every marker resolves to a chunk that was actually
      retrieved (a dangling ``[C7]`` is a fabricated citation).
    * **Recall** -- the chunks named in ``expected_sources`` are cited.

    Uncited answers are the single most common reason a correct answer still
    fails an audit: without provenance nobody can defend it after the fact.
    """

    name = "citation_coverage"
    short_name = "cite"

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    def evaluate(self, case: EvalCase) -> EvalResult:
        if case.expected_behaviour in {"abstain", "disambiguate"} and (
            case.is_abstaining() or case.is_disambiguating()
        ):
            return self._result(
                1.0, "Not applicable: no substantive claim requiring citation.", applicable=False
            )

        available = {chunk.id.upper() for chunk in case.retrieved_context}
        cited = case.cited_ids()
        cited_set = {marker.upper() for marker in cited}

        if not cited_set:
            return self._result(
                0.0,
                "No citation markers found in a substantive answer.",
                applicable=True,
                cited=[],
                available=sorted(available),
            )

        valid = cited_set & available
        dangling = sorted(cited_set - available)
        validity = len(valid) / len(cited_set)

        expected = {source.upper() for source in case.expected_sources}
        if expected:
            recall = len(expected & cited_set) / len(expected)
        else:
            recall = 1.0

        score = (1.0 + validity + recall) / 3.0
        rationale = (
            f"cited {sorted(cited_set)}; validity {validity:.2f}, expected-source recall {recall:.2f}"
        )
        if dangling:
            rationale += f"; dangling markers {dangling}"
        return self._result(
            score,
            rationale,
            applicable=True,
            cited=sorted(cited_set),
            dangling=dangling,
            expected_sources=sorted(expected),
        )


class NumericConsistencyEvaluator(Evaluator):
    """Every number stated in the answer must appear in the retrieved context.

    **Heuristic.** Extract numeric literals from the answer (ignoring citation
    markers), resolve magnitude suffixes such as ``bn``/``million``, and check
    each against the numbers present in the context under a relative tolerance
    that also forgives rounding.

    **Why it matters.** Free-text generation of figures is the highest-severity
    failure mode in a finance or regulatory setting, and it is the one users are
    least likely to catch. The architectural fix is to compute numbers with a
    deterministic tool and let the model narrate them; this evaluator is the
    regression test that proves the fix is still in place.

    **Limits.** Presence is not correctness. A number lifted from the wrong row
    of the context passes. Numbers the agent legitimately derives (a ratio of
    two supported figures) are flagged as unsupported -- which is intentional:
    arithmetic in prose is itself the anti-pattern.
    """

    name = "numeric_consistency"
    short_name = "numeric"

    def __init__(self, weight: float = 1.5, rel_tolerance: float = 0.005) -> None:
        self.weight = weight
        self.rel_tolerance = rel_tolerance

    def evaluate(self, case: EvalCase) -> EvalResult:
        answer_numbers = extract_numbers(case.generated_answer)
        if not answer_numbers:
            return self._result(
                1.0, "No numeric claims in the answer.", applicable=False, number_count=0
            )

        context_numbers = extract_numbers(case.context_text)
        unsupported: list[str] = []
        for mention in answer_numbers:
            if not any(
                mention.matches(candidate, self.rel_tolerance) for candidate in context_numbers
            ):
                unsupported.append(mention.raw)

        supported_count = len(answer_numbers) - len(unsupported)
        score = supported_count / len(answer_numbers)
        rationale = f"{supported_count}/{len(answer_numbers)} numbers traceable to context"
        if unsupported:
            rationale += f"; unsupported: {', '.join(unsupported[:6])}"
        return self._result(
            score,
            rationale,
            applicable=True,
            number_count=len(answer_numbers),
            unsupported_numbers=unsupported,
        )


class AbstentionCorrectnessEvaluator(Evaluator):
    """Did the agent do the right thing when the context did not support an answer?

    Three expected behaviours are supported via ``metadata.expected_behaviour``:

    * ``answer`` -- a substantive, non-refusing answer is required.
    * ``abstain`` -- an explicit refusal is required (context missing, stale,
      uncertified, or outside the agent's remit).
    * ``disambiguate`` -- the term maps to more than one governed definition,
      so the agent must ask which one is meant rather than silently choosing.

    Scoring is intentionally binary. Partial credit for "nearly refused" would
    hide exactly the behaviour this control exists to catch.
    """

    name = "abstention_correctness"
    short_name = "abstain"

    def __init__(self, weight: float = 1.5) -> None:
        self.weight = weight

    def evaluate(self, case: EvalCase) -> EvalResult:
        expected = case.expected_behaviour
        abstained = case.is_abstaining()
        disambiguated = case.is_disambiguating()

        if expected == "abstain":
            score = 1.0 if abstained else 0.0
            verdict = "correctly abstained" if abstained else "answered despite insufficient context"
        elif expected == "disambiguate":
            score = 1.0 if disambiguated else 0.0
            verdict = (
                "correctly requested disambiguation"
                if disambiguated
                else "resolved an ambiguous term silently"
            )
        else:
            score = 0.0 if abstained else 1.0
            verdict = "over-refused a supportable question" if abstained else "answered as expected"

        return self._result(
            score,
            f"expected={expected}; {verdict}",
            applicable=True,
            expected_behaviour=expected,
            detected_abstention=abstained,
            detected_disambiguation=disambiguated,
        )


class AnswerRelevanceEvaluator(Evaluator):
    """Token-level F1 between the generated answer and the reference answer.

    **Limits.** This rewards vocabulary agreement, not semantic equivalence. A
    correct answer phrased in different business language scores poorly, and a
    wrong answer that borrows the reference's wording scores well. Use it to
    detect large regressions in answer shape, never as a correctness oracle.
    """

    name = "answer_relevance"
    short_name = "relevance"

    def __init__(self, weight: float = 0.75) -> None:
        self.weight = weight

    def evaluate(self, case: EvalCase) -> EvalResult:
        if not case.expected_answer.strip():
            return self._result(1.0, "No reference answer supplied.", applicable=False)

        predicted = content_tokens(strip_citations(case.generated_answer))
        reference = content_tokens(case.expected_answer)
        if not predicted or not reference:
            return self._result(0.0, "Empty token set on one side.", applicable=True)

        overlap = predicted & reference
        if not overlap:
            return self._result(0.0, "No lexical overlap with reference answer.", applicable=True)

        precision = len(overlap) / len(predicted)
        recall = len(overlap) / len(reference)
        f1 = 2 * precision * recall / (precision + recall)
        return self._result(
            f1,
            f"token F1 {f1:.2f} (precision {precision:.2f}, recall {recall:.2f})",
            applicable=True,
            precision=round(precision, 4),
            recall=round(recall, 4),
        )


class StalenessEvaluator(Evaluator):
    """Is the grounding context fresh enough for the question that was asked?

    Freshness tolerance is per-case (``metadata.as_of_tolerance_days``) because
    it is a business decision, not a technical one: a policy definition may be
    valid for a year, an intraday position for minutes.

    The reference time is ``metadata.evaluated_at`` when present -- pinning it
    keeps eval-set scores reproducible instead of decaying as the file ages --
    otherwise the runner's injected reference time is used.

    Scoring: 1.0 within tolerance, then a linear decay to 0.0 at three times the
    tolerance, so a mildly late feed is distinguishable from a dead one.
    """

    name = "staleness"
    short_name = "fresh"

    def __init__(self, weight: float = 1.0, reference_time: datetime | None = None) -> None:
        self.weight = weight
        self.reference_time = reference_time

    def evaluate(self, case: EvalCase) -> EvalResult:
        tolerance = case.as_of_tolerance_days
        if tolerance is None:
            return self._result(1.0, "No freshness tolerance declared for this case.", applicable=False)

        reference = case.evaluated_at or self.reference_time or datetime.now(timezone.utc)
        timestamps = [
            chunk.as_of_datetime for chunk in case.retrieved_context if chunk.as_of_datetime
        ]
        if not timestamps:
            return self._result(
                0.0,
                "No as-of timestamp on any retrieved chunk; freshness cannot be evidenced.",
                applicable=True,
            )

        oldest = min(timestamps)
        age_days = (reference - oldest).total_seconds() / 86_400.0
        if age_days <= tolerance:
            score = 1.0
            verdict = "within tolerance"
        elif age_days >= tolerance * 3:
            score = 0.0
            verdict = "severely stale"
        else:
            score = 1.0 - (age_days - tolerance) / (tolerance * 2)
            verdict = "past tolerance"

        return self._result(
            score,
            f"oldest context {age_days:.1f}d old vs {tolerance:.0f}d tolerance ({verdict})",
            applicable=True,
            age_days=round(age_days, 2),
            tolerance_days=tolerance,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def default_evaluators(reference_time: datetime | None = None) -> list[Evaluator]:
    """The standard suite, in report column order.

    Weights encode severity: fabricating a number or answering when you should
    have refused is worse than paraphrasing the reference answer loosely.
    """
    return [
        GroundednessEvaluator(),
        CitationCoverageEvaluator(),
        NumericConsistencyEvaluator(),
        AbstentionCorrectnessEvaluator(),
        AnswerRelevanceEvaluator(),
        StalenessEvaluator(reference_time=reference_time),
    ]


def select_evaluators(
    names: Sequence[str] | None, reference_time: datetime | None = None
) -> list[Evaluator]:
    """Filter :func:`default_evaluators` by name, preserving report order."""
    suite = default_evaluators(reference_time=reference_time)
    if not names:
        return suite
    wanted = {name.strip().lower() for name in names if name.strip()}
    unknown = wanted - {evaluator.name for evaluator in suite}
    if unknown:
        raise ValueError(
            f"Unknown evaluator(s): {sorted(unknown)}. "
            f"Available: {sorted(e.name for e in suite)}"
        )
    return [evaluator for evaluator in suite if evaluator.name in wanted]
