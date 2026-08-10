#!/usr/bin/env python3
"""Runnable demonstration of grounding an agent in a governed semantic layer.

Run it::

    python3 examples/glossary_grounding_demo.py
    python3 examples/glossary_grounding_demo.py --question "what is net new money?"

What this shows
---------------
The point of the repository in miniature. A tiny in-memory business glossary
and metric registry stand in for a real governed semantic layer. For each
question the demo:

1. resolves the natural-language question to governed terms via aliases;
2. applies **pre-retrieval** governance gates -- certification, freshness,
   ambiguity, entitlement, and question intent;
3. assembles a grounded context block in exactly the format documented in
   ``prompts/grounded-answer-template.md``;
4. prints the prompt that would be sent to the model, and the post-generation
   checks that would run on whatever came back.

The teaching point is step 2. In four of the five scenarios below, **no prompt
is ever assembled**, because the governance layer answered the question before
the model was reached. Prompt engineering could not have saved any of them.

Standard library only. No model is called; nothing here needs a Salesforce org,
an API key or a network connection.
"""

from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence

# Pinned so the demo output is byte-stable regardless of when it is run.
REFERENCE_NOW = datetime(2026, 8, 10, 9, 0, 0, tzinfo=timezone.utc)

WIDTH = 78


# ---------------------------------------------------------------------------
# The governed semantic layer (in-memory stand-in)
# ---------------------------------------------------------------------------


class TermKind(str, Enum):
    """Whether an entry is a measurable metric or a definitional term."""

    METRIC = "metric"
    TERM = "glossary_term"

    @property
    def context_source(self) -> str:
        """The `source` value emitted into the context block.

        Matches the enum documented in prompts/grounded-answer-template.md and
        used by the sample eval set, so the demo, the template and the
        evaluators all agree on one vocabulary.
        """
        return "metric_registry" if self is TermKind.METRIC else "business_glossary"


@dataclass(frozen=True)
class GovernedTerm:
    """One entry in the business glossary / metric registry.

    Every field here exists because some control downstream depends on it.
    ``certified`` and ``owner`` gate whether the term may ground a user-facing
    answer at all; ``as_of`` and ``max_age_days`` decide whether the value is
    still current enough to state; ``physical_mapping`` is what makes the
    definition auditable rather than aspirational; ``sensitivity`` and
    ``entitlement`` drive the pre-retrieval access filter.
    """

    name: str
    kind: TermKind
    definition: str
    aliases: tuple[str, ...]
    owner: str | None
    dataset: str
    physical_mapping: str
    grain: str
    unit: str
    certified: bool
    as_of: datetime
    max_age_days: float
    sensitivity: str
    entitlement: str
    source_system: str
    sample_value: str | None = None
    exclusions: str | None = None

    def age_days(self, now: datetime = REFERENCE_NOW) -> float:
        """Age of the underlying value, in days, at ``now``."""
        return (now - self.as_of).total_seconds() / 86_400.0

    def is_stale(self, now: datetime = REFERENCE_NOW) -> bool:
        """True when the value is older than its declared freshness tolerance."""
        return self.age_days(now) > self.max_age_days

    def content_block(self) -> str:
        """The prose handed to the model as grounding content."""
        parts = [f"{self.name}: {self.definition}."]
        if self.exclusions:
            parts.append(f"Exclusions: {self.exclusions}.")
        parts.append(f"Grain: {self.grain}. Unit: {self.unit}.")
        parts.append(f"Physical mapping: {self.physical_mapping}.")
        if self.sample_value:
            parts.append(f"Latest certified value: {self.sample_value}.")
        return " ".join(parts)


#: A deliberately small registry. Real ones hold thousands of terms; the
#: governance mechanics are identical at either scale.
REGISTRY: tuple[GovernedTerm, ...] = (
    GovernedTerm(
        name="Assets under Management",
        kind=TermKind.METRIC,
        definition=(
            "the end-of-day market value of client assets for which the firm holds a "
            "discretionary or advisory mandate"
        ),
        aliases=("aum", "assets under management", "managed assets"),
        owner="Investment Data Stewardship",
        dataset="finance_curated.aum_daily_snapshot",
        physical_mapping="finance_curated.aum_daily_snapshot.aum_eur",
        grain="legal entity, daily close",
        unit="EUR",
        certified=True,
        as_of=datetime(2026, 8, 9, 22, 0, tzinfo=timezone.utc),
        max_age_days=2,
        sensitivity="Internal",
        entitlement="role:finance_reporting",
        source_system="portfolio accounting",
        sample_value="EUR 412.6 billion at the 2026-08-09 close",
        exclusions="custody-only arrangements; assets under advisement without a mandate",
    ),
    GovernedTerm(
        name="Net New Money",
        kind=TermKind.METRIC,
        definition=(
            "client inflows less client outflows over a period, isolating commercial "
            "performance from market movement"
        ),
        aliases=("nnm", "net new money", "net inflows"),
        owner="Investment Data Stewardship",
        dataset="finance_curated.client_flows_monthly",
        physical_mapping="finance_curated.client_flows_monthly.net_new_money_eur",
        grain="reporting unit, monthly",
        unit="EUR",
        certified=True,
        as_of=datetime(2026, 7, 31, 23, 0, tzinfo=timezone.utc),
        max_age_days=45,
        sensitivity="Internal",
        entitlement="role:finance_reporting",
        source_system="portfolio accounting",
        sample_value="EUR 3.9 billion for the month ending 2026-07-31",
        exclusions="market performance; foreign exchange movement; internal transfers",
    ),
    GovernedTerm(
        name="Active Customer",
        kind=TermKind.TERM,
        definition=(
            "a customer party with at least one funded account and at least one "
            "financial transaction in the trailing 90 days, measured at month end"
        ),
        aliases=("active customer", "active customers", "active client", "active clients"),
        owner="Customer Data Domain Steward",
        dataset="governance_curated.glossary_terms",
        physical_mapping="reference_curated.client_master.active_flag",
        grain="customer party, month end",
        unit="count",
        certified=True,
        as_of=datetime(2026, 7, 31, 23, 0, tzinfo=timezone.utc),
        max_age_days=45,
        sensitivity="Internal",
        entitlement="role:customer_analytics",
        source_system="client master",
        sample_value="1,284,406 at the 2026-07-31 month end",
        exclusions="dormant accounts; internal test parties; staff accounts",
    ),
    GovernedTerm(
        name="Revenue (Statutory)",
        kind=TermKind.METRIC,
        definition="IFRS-reported total revenue for the legal entity, as published in the financial statements",
        aliases=("revenue", "turnover", "total revenue", "statutory revenue"),
        owner="Group Finance",
        dataset="finance_curated.statutory_pnl",
        physical_mapping="finance_curated.statutory_pnl.total_revenue_eur",
        grain="legal entity, quarterly",
        unit="EUR",
        certified=True,
        as_of=datetime(2026, 6, 30, 23, 0, tzinfo=timezone.utc),
        max_age_days=120,
        sensitivity="Internal",
        entitlement="role:finance_reporting",
        source_system="general ledger",
        sample_value="EUR 7.42 billion for the quarter ending 2026-06-30",
        exclusions="nothing; this is the published statutory figure",
    ),
    GovernedTerm(
        name="Revenue (Management View)",
        kind=TermKind.METRIC,
        definition=(
            "internal management-basis revenue allocated to business divisions, used "
            "for divisional steering rather than external reporting"
        ),
        aliases=("revenue", "management revenue", "divisional revenue"),
        owner="Divisional Finance",
        dataset="finance_curated.management_pnl",
        physical_mapping="finance_curated.management_pnl.revenue_eur",
        grain="division, monthly",
        unit="EUR",
        certified=True,
        as_of=datetime(2026, 7, 31, 23, 0, tzinfo=timezone.utc),
        max_age_days=120,
        sensitivity="Internal",
        entitlement="role:divisional_finance",
        source_system="management reporting",
        sample_value="EUR 2.51 billion for the month ending 2026-07-31",
        exclusions="intra-group eliminations; one-off items; not reconcilable line-for-line to statutory",
    ),
    GovernedTerm(
        name="Client Domicile",
        kind=TermKind.TERM,
        definition="the country of residence recorded for a customer party, standardised to ISO 3166-1 alpha-2",
        aliases=("client domicile", "domicile", "country of residence"),
        owner="Reference Data Stewardship",
        dataset="reference_curated.client_master",
        physical_mapping="reference_curated.client_master.client_domicile",
        grain="customer party, current state",
        unit="ISO 3166-1 alpha-2 code",
        certified=True,
        as_of=datetime(2026, 6, 30, 23, 0, tzinfo=timezone.utc),
        max_age_days=180,
        sensitivity="Confidential",
        entitlement="role:client_reference_reader",
        source_system="onboarding platform",
        sample_value=None,
        exclusions="correspondence address; tax residence, which is a separate governed attribute",
    ),
    GovernedTerm(
        name="Treasury Cash Position (End of Day)",
        kind=TermKind.METRIC,
        definition="the closing cash balance of the treasury book, published once per business day after close",
        aliases=("cash position", "treasury cash position", "treasury cash"),
        owner="Treasury Data Stewardship",
        dataset="treasury_curated.cash_position_snapshot",
        physical_mapping="treasury_curated.cash_position_snapshot.cash_eur",
        grain="treasury book, end of day",
        unit="EUR",
        certified=True,
        as_of=datetime(2026, 8, 7, 17, 0, tzinfo=timezone.utc),
        max_age_days=1,
        sensitivity="Confidential",
        entitlement="role:treasury_reader",
        source_system="treasury management",
        sample_value="EUR 1.84 billion at the 2026-08-07 close",
        exclusions="intraday positions, which are not published to the governed layer",
    ),
    GovernedTerm(
        name="Customer Engagement Score",
        kind=TermKind.METRIC,
        definition="an experimental index of customer interaction frequency across digital channels",
        aliases=("engagement score", "customer engagement score", "engagement index"),
        owner=None,
        dataset="marketing_sandbox.engagement_extract",
        physical_mapping="marketing_sandbox.engagement_extract.score",
        grain="customer party, weekly",
        unit="index 0-100",
        certified=False,
        as_of=datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc),
        max_age_days=30,
        sensitivity="Internal",
        entitlement="role:marketing_analytics",
        source_system="marketing sandbox",
        sample_value=None,
        exclusions=None,
    ),
)


# ---------------------------------------------------------------------------
# Caller context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Caller:
    """The requesting user. Retrieval runs under *their* entitlements, not the agent's."""

    user_id: str
    display_name: str
    roles: frozenset[str]
    purpose: str

    def may_access(self, term: GovernedTerm) -> bool:
        """True when the caller holds the role the term requires."""
        return term.entitlement in self.roles


#: The demo caller deliberately holds most, but not all, roles: Client Domicile
#: requires an entitlement they lack, which drives the entitlement scenario.
DEMO_CALLER = Caller(
    user_id="u-40817",
    display_name="Demo Analyst",
    roles=frozenset(
        {
            "role:finance_reporting",
            "role:customer_analytics",
            "role:marketing_analytics",
            "role:treasury_reader",
        }
    ),
    purpose="internal_management_reporting",
)


# ---------------------------------------------------------------------------
# Resolution (the "retriever")
# ---------------------------------------------------------------------------


#: Words that signal the user is asking about the future. No governed dataset
#: can answer a forward-looking question, so this is a pre-retrieval stop.
FORWARD_LOOKING_MARKERS = (
    "will be", "will we", "next quarter", "next year", "next month",
    "forecast", "projected", "projection", "predict", "expected to be",
    "going to be", "outlook for",
)


@dataclass
class Match:
    """A registry entry matched by an alias, with the alias that matched it."""

    term: GovernedTerm
    matched_alias: str

    @property
    def specificity(self) -> int:
        """Longer aliases are more specific: 'treasury cash position' beats 'cash position'."""
        return len(self.matched_alias)


@dataclass
class Resolution:
    """The outcome of resolving a question against the registry."""

    question: str
    matches: list[Match] = field(default_factory=list)
    ambiguous_alias: str | None = None
    contenders: list[GovernedTerm] = field(default_factory=list)

    @property
    def best(self) -> GovernedTerm | None:
        """The most specific single match, when there is one."""
        if self.ambiguous_alias or not self.matches:
            return None
        return max(self.matches, key=lambda m: m.specificity).term


def normalise(text: str) -> str:
    """Lowercase and strip punctuation so alias matching is robust."""
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def resolve(question: str, registry: Sequence[GovernedTerm] = REGISTRY) -> Resolution:
    """Map a natural-language question onto governed terms via alias lookup.

    This is deliberately a **structured lookup**, not a vector search. "What is
    Active Customer" has an exact governed answer sitting in a registry row;
    embedding it and hoping for a nearest neighbour adds latency, cost and a new
    failure mode in exchange for nothing. Vector retrieval earns its place over
    unstructured prose, not over a glossary.

    Ambiguity is detected when a single alias resolves to more than one term --
    the situation where an ungoverned agent quietly picks one and produces a
    confidently wrong answer.
    """
    normalised = normalise(question)
    matches: list[Match] = []
    by_alias: dict[str, list[GovernedTerm]] = {}

    for term in registry:
        best_alias: str | None = None
        for alias in term.aliases:
            if re.search(rf"\b{re.escape(alias)}\b", normalised):
                if best_alias is None or len(alias) > len(best_alias):
                    best_alias = alias
        if best_alias is not None:
            matches.append(Match(term=term, matched_alias=best_alias))
            by_alias.setdefault(best_alias, []).append(term)

    resolution = Resolution(question=question, matches=matches)
    for alias, terms in by_alias.items():
        if len(terms) > 1:
            resolution.ambiguous_alias = alias
            resolution.contenders = terms
            break
    return resolution


def is_forward_looking(question: str) -> bool:
    """True when the question asks about a future state."""
    normalised = normalise(question)
    return any(marker in normalised for marker in FORWARD_LOOKING_MARKERS)


# ---------------------------------------------------------------------------
# Governance gates
# ---------------------------------------------------------------------------


class Decision(str, Enum):
    """What the governance layer decided to do with the question."""

    GROUND = "GROUND AND ANSWER"
    DISAMBIGUATE = "ASK THE USER TO DISAMBIGUATE"
    ABSTAIN = "ABSTAIN"


@dataclass
class Gate:
    """One pre-retrieval check and its verdict."""

    name: str
    passed: bool
    detail: str

    @property
    def marker(self) -> str:
        """``PASS`` / ``STOP`` label for the console."""
        return "PASS" if self.passed else "STOP"


@dataclass
class GateOutcome:
    """The full pre-retrieval verdict for one question."""

    gates: list[Gate]
    decision: Decision
    reason: str
    grounded_term: GovernedTerm | None = None
    contenders: list[GovernedTerm] = field(default_factory=list)


def apply_gates(
    resolution: Resolution, caller: Caller, now: datetime = REFERENCE_NOW
) -> GateOutcome:
    """Run the pre-retrieval governance gates, in order, and stop at the first failure.

    Order matters. Entitlement is evaluated *before* context is assembled, so
    unentitled content is never placed in a prompt in the first place -- you
    cannot un-see a leaked value by filtering the response afterwards.
    """
    gates: list[Gate] = []

    # 1. Intent -- can any governed dataset answer this shape of question?
    forward = is_forward_looking(resolution.question)
    gates.append(
        Gate(
            "intent is answerable from governed data",
            not forward,
            "historical / current-state question"
            if not forward
            else "forward-looking question; the governed layer holds no approved projections",
        )
    )
    if forward:
        return GateOutcome(
            gates,
            Decision.ABSTAIN,
            "No certified dataset carries forward-looking values. Route to the function "
            "that owns approved forecasts.",
        )

    # 2. Resolution -- did the question hit the registry at all?
    gates.append(
        Gate(
            "question resolves to governed term(s)",
            bool(resolution.matches),
            ", ".join(sorted({m.term.name for m in resolution.matches})) or "no registry match",
        )
    )
    if not resolution.matches:
        return GateOutcome(
            gates,
            Decision.ABSTAIN,
            "No governed term matched. Answering would mean inventing a definition; "
            "the correct output is a referral to the stewardship team.",
        )

    # 3. Ambiguity -- does one alias map to several certified definitions?
    ambiguous = resolution.ambiguous_alias is not None
    gates.append(
        Gate(
            "term resolves unambiguously",
            not ambiguous,
            "single definition"
            if not ambiguous
            else f"'{resolution.ambiguous_alias}' maps to {len(resolution.contenders)} certified definitions",
        )
    )
    if ambiguous:
        return GateOutcome(
            gates,
            Decision.DISAMBIGUATE,
            f"'{resolution.ambiguous_alias}' has more than one certified definition. Two users "
            "asking the same question would otherwise receive different, individually defensible numbers.",
            contenders=resolution.contenders,
        )

    term = resolution.best
    assert term is not None  # guaranteed by the ambiguity gate above

    # 4. Certification -- is this term allowed to ground an answer?
    gates.append(
        Gate(
            "term is certified with a named owner",
            term.certified and term.owner is not None,
            f"certified, owner {term.owner}"
            if term.certified
            else "uncertified, no accountable owner, no quality SLA",
        )
    )
    if not (term.certified and term.owner):
        return GateOutcome(
            gates,
            Decision.ABSTAIN,
            f"'{term.name}' is not certified. Exploratory data may support exploratory agents; "
            "it may not ground an answer a user will act on.",
            grounded_term=term,
        )

    # 5. Entitlement -- checked BEFORE any content is assembled.
    entitled = caller.may_access(term)
    gates.append(
        Gate(
            "caller entitled (checked pre-retrieval)",
            entitled,
            f"caller holds {term.entitlement}"
            if entitled
            else f"caller lacks {term.entitlement}; content never assembled",
        )
    )
    if not entitled:
        return GateOutcome(
            gates,
            Decision.ABSTAIN,
            "The caller is not entitled to this data. The agent reports that the answer exists "
            "but is not available to them -- it does not retrieve and then redact.",
            grounded_term=term,
        )

    # 6. Freshness -- certified is not the same as current.
    stale = term.is_stale(now)
    gates.append(
        Gate(
            "value within freshness tolerance",
            not stale,
            f"{term.age_days(now):.1f}d old, tolerance {term.max_age_days:.0f}d",
        )
    )
    if stale:
        return GateOutcome(
            gates,
            Decision.ABSTAIN,
            f"The certified value is {term.age_days(now):.1f} days old against a "
            f"{term.max_age_days:.0f}-day tolerance. Certification is not currency.",
            grounded_term=term,
        )

    return GateOutcome(
        gates,
        Decision.GROUND,
        "All pre-retrieval gates passed; context may be assembled.",
        grounded_term=term,
    )


# ---------------------------------------------------------------------------
# Context assembly -- the format from prompts/grounded-answer-template.md
# ---------------------------------------------------------------------------


SYSTEM_FRAMING = textwrap.dedent(
    """\
    You are an enterprise data assistant. You answer only from the governed context
    supplied in <retrieved_context>. You do not use prior knowledge about this
    organisation, and you do not infer values that are not present.

    Rules:
    1. Cite the chunk id [Cn] after every sentence containing a fact or figure.
    2. If the context does not support a complete answer, say so and stop. Partial
       is acceptable; invented is not.
    3. Do not perform arithmetic in prose. State figures exactly as they appear.
    4. State the as-of date whenever you state a figure.
    5. Use the certified definition verbatim where one is supplied."""
)


def build_context_block(terms: Sequence[GovernedTerm]) -> str:
    """Render governed terms into the provenance-carrying context block.

    The provenance fields are not decoration. ``certified`` and ``owner`` tell
    the reader who stands behind the answer, ``as_of`` makes staleness visible
    in the answer itself, and the chunk id is what a citation resolves to when
    somebody asks, six months later, where a number came from.
    """
    lines = ["<retrieved_context>"]
    for index, term in enumerate(terms, start=1):
        lines.extend(
            [
                f"[C{index}]",
                f"source: {term.kind.context_source}",
                f"dataset: {term.dataset}",
                f"certified: {str(term.certified).lower()}",
                f"as_of: {term.as_of.isoformat().replace('+00:00', 'Z')}",
                f"owner: {term.owner or 'UNASSIGNED'}",
                f"sensitivity: {term.sensitivity}",
                "content: >",
            ]
        )
        lines.extend(
            f"  {line}"
            for line in textwrap.wrap(term.content_block(), width=WIDTH - 4)
        )
    lines.append("</retrieved_context>")
    return "\n".join(lines)


def build_prompt(question: str, terms: Sequence[GovernedTerm], caller: Caller) -> str:
    """Assemble the complete prompt that would be sent to the model."""
    tolerance = min((term.max_age_days for term in terms), default=0)
    request_context = (
        "<request_context>\n"
        f"user_purpose: {caller.purpose}\n"
        "entitlements_applied: true\n"
        f"as_of_tolerance_days: {tolerance:g}\n"
        "</request_context>"
    )
    return "\n\n".join(
        [
            SYSTEM_FRAMING,
            request_context,
            build_context_block(terms),
            f"<question>\n{question}\n</question>",
        ]
    )


# ---------------------------------------------------------------------------
# Post-generation checks (described, not executed -- no model is called here)
# ---------------------------------------------------------------------------


def post_generation_checks(terms: Sequence[GovernedTerm]) -> list[str]:
    """The checks that would run on the model's response before a user sees it."""
    ids = ", ".join(f"[C{i}]" for i in range(1, len(terms) + 1))
    return [
        f"attribution: every factual sentence carries a marker resolving to {ids or 'a retrieved chunk'}",
        "numeric consistency: every figure in the response appears verbatim in the context block",
        "no-arithmetic: no derived figure (ratio, delta, growth rate) computed in prose",
        "definition fidelity: the certified wording is not silently paraphrased into a different scope",
        "as-of disclosure: any stated figure is accompanied by its as-of date",
        "egress: no attribute above the caller's clearance appears in the response",
        "escalation: response withheld for human review if attribution or numeric checks fail",
    ]


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def rule(char: str = "-") -> str:
    """A horizontal rule."""
    return char * WIDTH


def wrap(text: str, indent: str = "    ") -> str:
    """Wrap prose to the console width with a hanging indent."""
    return textwrap.fill(text, width=WIDTH, initial_indent=indent, subsequent_indent=indent)


def run_scenario(label: str, question: str, caller: Caller = DEMO_CALLER) -> None:
    """Resolve, gate, assemble and report on one question."""
    print()
    print(rule("="))
    print(f"{label}")
    print(rule("="))
    print(f"QUESTION : {question}")
    print(f"CALLER   : {caller.display_name} ({caller.user_id})  purpose={caller.purpose}")
    print()

    resolution = resolve(question)
    outcome = apply_gates(resolution, caller)

    print("[1] RESOLUTION AGAINST THE GOVERNED REGISTRY")
    if resolution.matches:
        for match in sorted(resolution.matches, key=lambda m: -m.specificity):
            flag = "certified" if match.term.certified else "UNCERTIFIED"
            print(f"    '{match.matched_alias}' -> {match.term.name}  [{match.term.kind.value}, {flag}]")
    else:
        print("    no governed term matched this question")

    print()
    print("[2] PRE-RETRIEVAL GOVERNANCE GATES")
    for gate in outcome.gates:
        print(f"    [{gate.marker}] {gate.name}")
        print(f"           {gate.detail}")

    print()
    print(f"[3] DECISION: {outcome.decision.value}")
    print(wrap(outcome.reason))

    if outcome.decision is Decision.GROUND and outcome.grounded_term:
        terms = [outcome.grounded_term]
        print()
        print("[4] PROMPT ASSEMBLED AND SENT TO THE MODEL")
        print(rule("."))
        print(build_prompt(question, terms, caller))
        print(rule("."))
        print()
        print("[5] POST-GENERATION CHECKS THAT WOULD RUN ON THE RESPONSE")
        for check in post_generation_checks(terms):
            print(f"    - {check}")

    elif outcome.decision is Decision.DISAMBIGUATE:
        print()
        print("[4] NO PROMPT ASSEMBLED - THE AGENT ASKS BEFORE IT ANSWERS")
        for term in outcome.contenders:
            print(f"    - {term.name}")
            print(f"        {term.definition}")
            print(f"        owner {term.owner} | grain {term.grain} | maps to {term.physical_mapping}")
        print()
        print("    Response returned to the user:")
        options = " or ".join(f"'{t.name}'" for t in outcome.contenders)
        print(wrap(
            f'"That term has more than one certified definition here: {options}. '
            'They are not interchangeable. Which do you need, and for which reporting unit?"',
            indent="      ",
        ))

    else:
        print()
        print("[4] NO PROMPT ASSEMBLED - THE GOVERNANCE LAYER ANSWERED FIRST")
        print(wrap(
            "No context block was built, so there was nothing for the model to ground in "
            "and nothing for a post-generation filter to catch. This is the cheapest place "
            "in the stack to stop a bad answer.",
            indent="      ",
        ))


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Demonstrate grounding an agent in a governed semantic layer.",
    )
    parser.add_argument(
        "--question",
        default=None,
        help="Run a single ad-hoc question against the registry instead of the demo scenarios.",
    )
    parser.add_argument(
        "--list-terms", action="store_true", help="Print the governed registry and exit."
    )
    args = parser.parse_args(argv)

    print(rule("="))
    print("GOVERNED GROUNDING DEMO".center(WIDTH))
    print("resolving questions against a governed semantic layer".center(WIDTH))
    print(rule("="))
    print(f"registry: {len(REGISTRY)} governed terms | reference time: "
          f"{REFERENCE_NOW.isoformat().replace('+00:00', 'Z')}")

    if args.list_terms:
        print()
        for term in REGISTRY:
            flag = "certified" if term.certified else "UNCERTIFIED"
            print(f"  {term.name:<38} {flag:<12} owner={term.owner or 'UNASSIGNED'}")
        return 0

    if args.question:
        run_scenario("AD-HOC QUESTION", args.question)
        return 0

    scenarios: list[tuple[str, str]] = [
        (
            "SCENARIO A - certified, fresh, single definition -> answer",
            "What is Assets under Management and what was the figure at the last close?",
        ),
        (
            "SCENARIO B - one alias, two certified definitions -> disambiguate",
            "What was revenue last quarter?",
        ),
        (
            "SCENARIO C - term exists but is uncertified -> abstain",
            "What is the customer engagement score for private clients?",
        ),
        (
            "SCENARIO D - certified but past its freshness tolerance -> abstain",
            "What is the treasury cash position right now?",
        ),
        (
            "SCENARIO E - caller not entitled, checked before assembly -> abstain",
            "How is client domicile defined in the client master?",
        ),
        (
            "SCENARIO F - forward-looking question, no governed source -> abstain",
            "What will assets under management be at the end of next quarter?",
        ),
    ]
    for label, question in scenarios:
        run_scenario(label, question)

    print()
    print(rule("="))
    print("WHAT THIS DEMONSTRATES")
    print(rule("="))
    takeaways = [
        "Five of six questions were resolved without ever calling the model. "
        "Governance is a pre-retrieval concern, not a post-generation filter, and "
        "no amount of prompt engineering would have changed any of these outcomes.",
        "The ambiguity in Scenario B is not a model weakness. Two certified "
        "definitions of 'revenue' exist, both correct; only a human can say which "
        "one is meant. An ungoverned agent would have picked one silently, and two "
        "colleagues would have walked into a meeting with different numbers.",
        "Scenario D shows why 'certified' and 'current' are separate controls. The "
        "data was certified, owned and correct - and 2.7 days old against a one-day "
        "tolerance, because the question asked for 'right now' and the dataset "
        "publishes once a day after close.",
        "Scenario E filters on entitlement before assembling context, not after "
        "generating a response. A value the caller may not see is never placed in a "
        "prompt, so there is nothing to leak and nothing to redact.",
        "Every field in the context block earns its place: certified and owner gate "
        "the answer, as_of makes staleness visible in the answer itself, and the "
        "chunk id is what a citation resolves to when the answer is challenged "
        "months later by someone who was not in the room.",
    ]
    for index, takeaway in enumerate(takeaways, start=1):
        print()
        print(wrap(f"{index}. {takeaway}", indent="  "))
    print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
