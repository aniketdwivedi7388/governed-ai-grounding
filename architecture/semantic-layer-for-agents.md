# The Semantic Layer for Agents

> If you can fund exactly one thing to improve agent accuracy over enterprise data, fund this. Not a better model, not a better prompt, not a bigger context window.

## Contents

- [Why this is the highest-leverage investment](#why-this-is-the-highest-leverage-investment)
- [The metric definition as a contract](#the-metric-definition-as-a-contract)
- [Synonyms and business aliases](#synonyms-and-business-aliases)
- [Disambiguation strategy](#disambiguation-strategy)
- [Time grain](#time-grain)
- [Units and currency](#units-and-currency)
- [The certified surface](#the-certified-surface)
- [Exposing the layer to an agent](#exposing-the-layer-to-an-agent)
- [Worked example: Assets under Management](#worked-example-assets-under-management)
- [Worked example: Active Customer](#worked-example-active-customer)
- [Operating the layer](#operating-the-layer)
- [Common objections](#common-objections)

---

## Why this is the highest-leverage investment

A model's job in a grounded architecture is narrow: understand the question, pick a tool, narrate a result. It is good at all three. What it cannot do — what nothing can do from the outside — is know that *your* organisation counts a customer as active after ninety days rather than sixty, that your management revenue excludes intra-group eliminations, or that your AUM figure omits custody-only arrangements.

Those facts are not in the model, not in the prompt, and not reliably in the data either. They live in the heads of the people who built the reports, and in the SQL of the jobs that produce them. The semantic layer is the act of writing them down in a form a machine can query.

The leverage comes from a compounding property:

| Investment | Improves | Effect on the next agent |
| --- | --- | --- |
| Better prompt | One agent, one behaviour | None |
| Better model | Fluency, reasoning; not your definitions | None |
| Bigger context window | How much context fits | None — more of the wrong context is worse |
| **Semantic layer** | Every consumer that resolves a term | **The whole cost is already paid** |

The second agent is dramatically cheaper than the first, and the tenth is nearly free — but only if the definitions were externalised rather than embedded in each agent's prompt. This is also why the investment survives a change of AI platform: prompts do not port, and definitions do.

There is a second, less obvious return. Building a semantic layer forces the organisation to *notice* that it holds three definitions of revenue. That discovery is uncomfortable and enormously valuable, and it happens whether or not the agent programme proceeds.

---

## The metric definition as a contract

A definition is a contract when it makes testable promises. The test is simple: **can an automated check tell whether a given number honours this definition?** If not, it is documentation.

Required elements:

| Element | Contract obligation | Failure if absent |
| --- | --- | --- |
| **Identifier** | Stable, machine-referenceable, never reused | Definitions referenced by name drift with wording |
| **Name and business definition** | The certified wording, used verbatim | Each consumer paraphrases; scope quietly shifts |
| **Owner** | A named accountable person | No one to arbitrate a conflict |
| **Grain** | The lowest level at which it is valid | Silent invalid aggregation |
| **Unit** | Currency, count, ratio, index, with a scale | "2.5" means nothing on its own |
| **Physical mapping** | Column, filter, aggregation | The definition cannot be executed or tested |
| **Inclusions and exclusions** | What is deliberately out of scope | The most common source of two right answers |
| **Temporal semantics** | As-of behaviour, restatement policy | Yesterday's answer changes without explanation |
| **Version and status** | Semantic version, lifecycle state | No way to say which definition was in force |
| **Freshness tolerance** | How old the value may be for this metric | Certified but stale answers |
| **Sensitivity and entitlement** | Who may see it | Retrieval becomes a bypass |
| **Related and conflicting metrics** | Explicit links to near neighbours | Ambiguity cannot be detected |

Two elements deserve emphasis because they are the ones most often skipped.

**Exclusions carry more information than inclusions.** "Assets under Management is the market value of client assets" is unarguable and useless. "…excluding custody-only arrangements and assets under advisement without a mandate" is where the actual business rule lives, and where two teams' figures diverge.

**`related_metrics` is what makes ambiguity detectable.** A definition that does not know about its near neighbours cannot warn anyone. Declaring `conflicts_with: revenue.management` on the statutory revenue metric is what lets the retrieval layer return both and force the question.

---

## Synonyms and business aliases

Users do not speak in registry identifiers. The alias set is the bridge, and it must be treated as governed data with an owner and a review cycle — not a convenience list someone maintains ad hoc.

Three distinct relationships, often conflated:

| Relationship | Meaning | Handling |
| --- | --- | --- |
| **Synonym** | Different word, same certified concept | Resolve silently to the canonical term |
| **Homonym** | Same word, different concepts | **Never resolve silently.** Disambiguate |
| **Near-synonym** | Overlapping but not identical | Resolve to the most specific match, and say which was used |

Near-synonyms are the dangerous middle. "Client" and "customer" may be interchangeable in one organisation and denote different legal relationships in another. The registry must record which, because the alias set is where a subtle scope error becomes systematic.

Sources worth mining for aliases, in rough order of value:

1. **Report and dashboard titles** — the vocabulary users already accept
2. **Column names and comments** in curated layers — how builders think
3. **Actual questions** users ask the agent (and the ones it fails to resolve — a resolution-failure log is the highest-signal backlog you will get)
4. **Regulatory and policy documents** — formal names that differ from colloquial ones
5. **Acronyms**, with their expansions, and any collisions between them

Practical rules:

- **Aliases are case- and punctuation-insensitive, but word-boundary aware.** Substring matching turns "aum" into a match inside "aumentar" and "premium".
- **Register the plural and the possessive.** Cheap, and it removes a whole class of resolution misses.
- **An alias may point to several terms.** That is not a bug in the registry; it is a correctly detected homonym.
- **Never auto-generate aliases from embeddings without review.** Semantic similarity is exactly the mechanism that conflates "gross revenue" with "net revenue".

---

## Disambiguation strategy

When a term maps to more than one certified definition, the agent has four options. Only one of them is generally correct.

| Strategy | When it is right | Risk |
| --- | --- | --- |
| **Ask the user** | Default | Friction; users dislike being asked twice |
| **Resolve from context** | The question or session supplies a discriminator | Wrong inference is invisible |
| **Apply a scoped default** | A team has a registered, owned default | The default outlives its rationale |
| **Answer with all definitions** | Few options, small answers | Unusable beyond two or three |

**Ask.** A clarifying question costs a few seconds. A silently wrong metric costs a decision, and the cost lands later, on someone else, with no indication of where it came from.

A workable resolution order:

1. **Explicit qualifier in the question.** "statutory revenue" resolves; "revenue" does not.
2. **Registered scoped default.** If the caller's role or reporting unit has an owned default for this term, apply it **and state that you did** — "using the management view, the default for your division". A silent default is indistinguishable from a guess.
3. **Session continuity.** If the term was disambiguated earlier in the same session, carry it forward, and re-confirm when the topic changes.
4. **Ask**, presenting the definitions and their differences rather than just their names. "Statutory or management?" is a worse question than showing what each excludes.

Two implementation details that make this work in practice:

- **The clarifying question must be generated from the registry**, not written into a prompt. The moment a new revenue definition is registered, the clarification updates itself.
- **Log every disambiguation.** A term asked about repeatedly is telling you either that the alias set is wrong or that the business genuinely needs to rename something. This log is one of the most useful governance artefacts the agent produces.

---

## Time grain

Most "the numbers don't match" escalations are temporal, not arithmetic. Four properties, declared per metric:

**Grain** — the finest period at which the metric is valid. A metric defined monthly cannot answer a daily question. The agent must refuse rather than interpolate, and the refusal should name the available grain.

**Aggregation rule** — how the metric composes across periods. This is where the majority of silent errors live:

| Metric type | Across time | Example |
| --- | --- | --- |
| Flow | Sum | Net new money |
| Stock / snapshot | **Never sum** — take the endpoint or average | Assets under management |
| Ratio | **Never sum, never average the ratios** — recompute from components | Cost-income ratio |
| Distinct count | **Never sum** — recount over the window | Active customers |

Summing twelve monthly AUM snapshots produces a number twelve times too large that still looks plausible in a chart. Averaging twelve monthly ratios produces a number that is wrong in a way nobody can eyeball. The registry must carry the rule, and the tool must enforce it, because the model will not know.

**As-of semantics** — does this metric represent a point in time, a period, or a current state? "Active customers" at month end is a point-in-time count over a trailing window; both facts must be stated or the number cannot be reproduced.

**Restatement policy** — may a historical value change? If yes, under what circumstances, and how far back? An agent asked the same question twice, months apart, should be able to explain a different answer rather than merely produce one.

---

## Units and currency

Under-specified units are the quietest failure mode in the whole layer, because the number looks right.

Declare, per metric:

- **Unit type** — currency, count, ratio, percentage, duration, index
- **Scale** — units, thousands, millions, billions. Store in base units; format at presentation. Storing "412.6" with the scale implied elsewhere invites a thousand-fold error.
- **Currency and conversion basis** — reporting currency, which rate, sourced from where, and as at which date. "EUR at the closing rate for the reporting date" is a contract. "EUR" is not.
- **Ratio denominator** — 0–1 or 0–100. Both conventions exist in most organisations, frequently in the same report.
- **Sign convention** — are outflows negative, or positive-and-subtracted? Both are defensible; mixing them is not.

Rules for the agent surface:

1. **Every figure carries its unit in the tool result**, not only in the formatted string. The guardrail checks the structured field.
2. **The agent never converts.** Conversion is a tool call with a stated rate and rate date, or it does not happen.
3. **Mixed-currency aggregation is refused by default**, not silently converted.

---

## The certified surface

The **certified surface** is the subset of the semantic layer an agent is permitted to resolve against. It is deliberately smaller than the whole layer.

| Property | Certified surface | The rest of the layer |
| --- | --- | --- |
| Owner | Named individual | May be a team or absent |
| Definition | Reviewed, versioned | May be draft |
| Physical mapping | Tested against source | May be aspirational |
| Quality SLA | Declared and monitored | Best effort |
| Change process | Reviewed, notified | Ad hoc |
| Agent may resolve | **Yes** | No — or only in a labelled exploratory agent |

Making the surface explicit is what allows an agent to say "that term exists but is not certified for this use" instead of either refusing blindly or answering from ungoverned data. The demo in [`../examples/glossary_grounding_demo.py`](../examples/glossary_grounding_demo.py) shows this as a distinct gate.

**Certification decays.** Attach a review interval to every certified term, and demote automatically when it lapses. A definition certified three years ago and never revisited is more dangerous than an uncertified one, because it carries an owner's name and nobody thinks to question it.

---

## Exposing the layer to an agent

**Expose typed tools. Do not expose raw SQL.**

Text-to-SQL over a warehouse is a seductive design: it appears to generalise to any question at no marginal cost per metric. In a governed setting it undoes most of the architecture:

| Concern | Typed tools | Generated SQL |
| --- | --- | --- |
| Definition fidelity | Definition is *in* the tool | Model re-derives it, plausibly, differently each time |
| Entitlement | Enforced in the tool | Depends on database-level controls being complete and correct |
| Aggregation rules | Enforced | Model may sum a snapshot |
| Auditability | Tool, parameters and version logged | Reconstruct intent from generated SQL |
| Testability | Unit-testable | Effectively unbounded surface |
| Failure mode | Explicit error | Syntactically valid query, wrong semantics, plausible number |

The last row is the decisive one. A typed tool given a bad parameter fails loudly. Generated SQL given a bad assumption returns a number, and the number looks exactly like a correct one.

Text-to-SQL has a legitimate place — exploratory analysis by users who can read the SQL and are accountable for their own conclusions, clearly labelled as ungoverned. It is not the interface for a customer-facing or decision-support agent.

### Tool design principles

1. **One tool per intent, not per table.** `get_metric_value`, `get_metric_definition`, `compare_metric_periods`, `list_metrics_for_domain` — four tools covering most of the definitional and factual space.
2. **Constrained enumerations for identifiers.** `metric_id` as an enum fails loudly on a bad value; as a free string it fails quietly with the wrong metric.
3. **Return structure, not prose.** The tool returns value, unit, scale, currency, as-of, definition, owner, certification tier. The model composes the sentence; the guardrail checks the fields.
4. **Return provenance in every result**, so the citation resolves to something real.
5. **Make refusal a first-class result.** `status: refused` with a machine-readable reason — `stale`, `not_certified`, `not_entitled`, `grain_unavailable`, `ambiguous` — and a candidate list where relevant. This is what lets the agent explain rather than merely fail.

---

## Worked example: Assets under Management

End to end, from glossary term to agent-facing tool signature.

### 1. Glossary term

```yaml
term:
  id: term.assets_under_management
  name: Assets under Management
  abbreviation: AUM
  status: certified
  version: 3.1.0
  definition: >
    The end-of-day market value of client assets for which the firm holds a
    discretionary or advisory mandate.
  inclusions:
    - Discretionary mandates
    - Advisory mandates with an executed agreement
  exclusions:
    - Custody-only arrangements
    - Assets under advisement with no executed mandate
    - Assets of terminated relationships after the termination date
  aliases: [aum, assets under management, managed assets, client assets under mandate]
  conflicts_with:
    - term.assets_under_administration   # includes custody; commonly confused
  stewardship:
    accountable_owner: Head of Investment Data Domain
    delegated_steward: Investment Data Stewardship
    review_interval_months: 12
    last_reviewed: 2026-04-18
```

### 2. Metric contract

```yaml
metric:
  id: metric.aum.firm_wide
  term_id: term.assets_under_management
  name: Assets under Management (firm-wide)
  status: certified
  version: 3.1.0

  grain:
    entity: legal_entity
    period: daily
    as_of_basis: point_in_time
    valid_grains: [daily, monthly, quarterly]

  aggregation:
    across_entities: sum
    across_time: endpoint          # snapshot metric -- summing periods is invalid
    across_time_note: >
      Never sum across periods. For a period view take the closing value, or the
      period average where explicitly requested and labelled as such.

  unit:
    type: currency
    currency: EUR
    scale: units                   # stored in base units; formatted at presentation
    conversion_basis: closing reference rate for the reporting date
    sign_convention: positive

  physical_mapping:
    dataset: finance_curated.aum_daily_snapshot
    value_column: aum_eur
    entity_column: legal_entity_code
    as_of_column: business_date
    filters:
      - mandate_type IN ('DISCRETIONARY','ADVISORY')
      - record_status = 'ACTIVE'
    certification_tier: certified

  temporal:
    freshness_tolerance_hours: 30      # published after close; one missed run is visible
    restatement_policy: >
      Values may be restated for up to five business days following corrections
      in portfolio accounting. Restatements are versioned and audit-logged.

  access:
    sensitivity: Internal
    entitlement: role:finance_reporting

  quality:
    completeness_threshold: 0.995
    validity_threshold: 0.99
    on_breach: demote_from_certified_surface

  lineage:
    source_system: portfolio accounting
    transformation_job: fin_aum_daily_build
    lineage_captured: column_level
```

### 3. Agent-facing tool signature

```json
{
  "name": "get_metric_value",
  "description": "Return the certified value of a governed metric for a period and entity. Never computes a metric that is not registered. Returns status='refused' with a machine-readable reason rather than an approximate answer.",
  "parameters": {
    "type": "object",
    "required": ["metric_id", "period_end"],
    "properties": {
      "metric_id": {
        "type": "string",
        "enum": ["metric.aum.firm_wide", "metric.nnm.reporting_unit", "metric.active_customers"],
        "description": "Registered metric identifier. Resolve names via lookup_term first."
      },
      "period_end": { "type": "string", "format": "date" },
      "period_grain": { "type": "string", "enum": ["daily", "monthly", "quarterly"] },
      "entity_code": { "type": "string", "description": "Legal entity or reporting unit. Omit for firm-wide." }
    },
    "additionalProperties": false
  },
  "returns": {
    "type": "object",
    "properties": {
      "status":  { "type": "string", "enum": ["ok", "refused"] },
      "reason":  { "type": "string", "enum": ["stale", "not_certified", "not_entitled", "grain_unavailable", "no_data", "ambiguous"] },
      "value":   { "type": "number" },
      "unit":    { "type": "object", "properties": { "type": {"type":"string"}, "currency": {"type":"string"}, "scale": {"type":"string"} } },
      "as_of":   { "type": "string", "format": "date-time" },
      "definition": { "type": "string", "description": "Certified wording, to be reproduced verbatim." },
      "owner":   { "type": "string" },
      "certification_tier": { "type": "string", "enum": ["certified", "managed", "exploratory"] },
      "provenance": {
        "type": "object",
        "properties": {
          "dataset": {"type":"string"},
          "metric_version": {"type":"string"},
          "lineage_ref": {"type":"string"}
        }
      }
    }
  }
}
```

### 4. What the agent may and may not do with the result

| May | May not |
| --- | --- |
| State the value with its unit and as-of | Convert the currency |
| Reproduce the certified definition verbatim | Restate it in "simpler" words that change scope |
| Cite the provenance reference | Present it without a source |
| Report a `refused` status and its reason | Fall back to an uncertified source |
| Call `compare_metric_periods` for a change | Subtract two values in prose |

---

## Worked example: Active Customer

A definitional term rather than a currency metric — the shape most enterprise questions actually take.

```yaml
term:
  id: term.active_customer
  name: Active Customer
  status: certified
  version: 2.0.0
  definition: >
    A customer party with at least one funded account and at least one financial
    transaction in the trailing 90 days, measured at month end.
  inclusions:
    - Retail and business customer parties
    - Joint parties, counted once at party level
  exclusions:
    - Dormant accounts as flagged by the dormancy process
    - Internal test parties
    - Staff accounts, which are reported separately
  aliases: [active customer, active client, active customers, active clients]
  conflicts_with:
    - term.engaged_customer     # marketing definition, 30-day digital interaction
  stewardship:
    accountable_owner: Head of Customer Data Domain
    delegated_steward: Customer Data Stewardship
    review_interval_months: 12
    last_reviewed: 2026-02-09
  change_log:
    - version: 2.0.0
      date: 2026-02-09
      change: >
        Trailing window changed from 60 to 90 days following review. History was
        NOT restated; series before 2026-02 uses the 60-day basis.
      approved_by: Customer Data Governance Forum

metric:
  id: metric.active_customers
  term_id: term.active_customer
  status: certified
  grain:
    entity: reporting_unit
    period: monthly
    as_of_basis: point_in_time_over_trailing_window
    trailing_window_days: 90
  aggregation:
    across_entities: sum
    across_time: recount          # distinct count -- never sum monthly counts
  unit:
    type: count
    scale: units
  physical_mapping:
    dataset: customer_curated.active_customer_monthly
    value_column: active_customer_count
    definition_column: reference_curated.client_master.active_flag
    filters:
      - party_type IN ('RETAIL','BUSINESS')
      - test_party_flag = FALSE
  access:
    sensitivity: Internal
    entitlement: role:customer_analytics
```

**Note the `change_log` entry.** The window changed from 60 to 90 days and history was not restated. Without that record, an agent comparing 2025 with 2026 produces a real-looking trend that is an artefact of a definition change. With it, the agent can state the discontinuity — which is the difference between a tool that reports numbers and one that can be trusted with them.

---

## Operating the layer

It is a product, not a project.

| Activity | Cadence | Owner |
| --- | --- | --- |
| Review resolution-failure log | Weekly | Semantic layer product owner |
| Review disambiguation log for recurring conflicts | Monthly | Data governance forum |
| Re-certify terms reaching review interval | Continuous | Term owners |
| Test physical mappings against source | Per release, and on schema change | Data engineering |
| Reconcile registry values against certified reports | Monthly | Stewardship |
| Retire deprecated terms and definitions | Quarterly | Semantic layer product owner |

Four metrics worth tracking — all measurable from the layer's own logs:

1. **Resolution rate** — share of questions resolving to a certified term. Rising means alias coverage is improving.
2. **Disambiguation rate** — share requiring a clarifying question. Persistently high for one term means the business needs to rename something.
3. **Certified coverage of asked terms** — of terms users actually ask about, what share is certified. Far more useful than total term count.
4. **Definition age distribution** — how much of the certified surface is overdue for review.

Note what is *not* on that list: total number of registered terms. It is the easiest number to grow and the least informative.

---

## Common objections

**"This is just a data catalogue we never finished."** Largely yes — and that is the point. The agent use case supplies the forcing function and the visible consequence that earlier catalogue efforts lacked. The difference is that a catalogue nobody queries decays silently, whereas a semantic layer serving an agent fails visibly, in front of users, the day it drifts.

**"We can't define everything first."** Do not. Start with the twenty terms that appear in the questions users actually ask, which is a much shorter list than the estate. Ship the agent restricted to those. Grow the surface from the resolution-failure log, which tells you exactly what to define next in priority order.

**"The business won't agree on definitions."** Then the business does not currently agree on the numbers either — the disagreement is simply distributed across spreadsheets where nobody has to confront it. The registry does not create the conflict; it makes an existing conflict addressable. Registering both definitions with different names and owners is a legitimate, and common, outcome.

**"Modern models are good enough to infer this."** They infer confidently and consistently — and consistently to the industry-standard definition, not yours. The failure is invisible precisely because the inference is reasonable. Your ninety-day window is not deducible from anything the model has seen.

**"Won't this be obsolete when models improve?"** The constraint is not model capability. Nothing external can determine which of your organisation's two certified revenue definitions a given user meant, because that information exists only inside your organisation. Better models make the *narration* better. They cannot make the definition unambiguous.
