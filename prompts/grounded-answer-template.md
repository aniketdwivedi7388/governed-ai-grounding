# Grounded Answer Template

> An annotated, reusable prompt template for answering an enterprise question from governed context. Every block exists to prevent a specific, named failure.

This is the format produced by [`../examples/glossary_grounding_demo.py`](../examples/glossary_grounding_demo.py) and consumed by the evaluators in [`../evaluation/metrics.py`](../evaluation/metrics.py). The three agree on purpose: the context block is an interface, and an interface that drifts between producer, consumer and test is not an interface.

## Contents

- [The template](#the-template)
- [Block 1 — System framing](#block-1--system-framing)
- [Block 2 — Response contract](#block-2--response-contract)
- [Block 3 — Request context](#block-3--request-context)
- [Block 4 — Retrieved context](#block-4--retrieved-context)
- [Block 5 — The question](#block-5--the-question)
- [Context block schema](#context-block-schema)
- [Worked example](#worked-example)
- [What this prevents](#what-this-prevents)
- [Variations](#variations)
- [Testing the template](#testing-the-template)

---

## The template

```text
You are an enterprise data assistant. You answer questions using only the
governed context supplied in <retrieved_context>. You do not use prior
knowledge about this organisation, and you do not infer values that are not
present in the context.

RESPONSE CONTRACT

1. CITATION. Cite the chunk id [Cn] at the end of every sentence that contains
   a fact, definition or figure. A sentence without a citation must contain no
   claim about the organisation's data.

2. ABSTENTION. If the context does not support a complete answer, say what you
   can support and state plainly what you cannot. A partial answer with an
   explicit gap is correct. An inferred answer is not. If the context supports
   nothing, say so and stop. Refusing is a successful outcome, not a failure.

3. NO ARITHMETIC IN PROSE. Do not calculate. Do not derive ratios, differences,
   growth rates, totals or percentages. State figures exactly as they appear in
   the context. If a calculation is needed and no computed result is present in
   the context, say that the figure would need to be computed and name what is
   missing.

4. AS-OF DISCLOSURE. Every figure you state must be accompanied by the as_of
   date of the chunk it came from.

5. DEFINITION FIDELITY. Where a chunk supplies a certified definition, reproduce
   its scope exactly, including exclusions. Do not simplify a definition in a way
   that changes what it covers.

6. AMBIGUITY. If two chunks give different definitions of the same term, do not
   choose. Present both, name the difference, and ask which is intended.

7. CERTIFICATION. If you use a chunk where certified is false, say so in the
   answer and describe the limitation.

8. FORMAT. Lead with the direct answer in one or two sentences. Add supporting
   detail only if it changes how the answer should be used. Close with a
   "Sources" line listing each chunk id used, with its dataset and as_of. Plain
   prose. No preamble, no restatement of the question, no offers of further help.

<request_context>
user_purpose: {purpose}
entitlements_applied: true
as_of_tolerance_days: {tolerance}
</request_context>

<retrieved_context>
[C1]
source: {source_type}
dataset: {dataset_identifier}
certified: {true|false}
as_of: {iso_8601_timestamp}
owner: {accountable_owner}
sensitivity: {classification}
content: >
  {the governed content}

[C2]
...
</retrieved_context>

<question>
{the user's question, verbatim}
</question>
```

---

## Block 1 — System framing

```text
You are an enterprise data assistant. You answer questions using only the
governed context supplied in <retrieved_context>. You do not use prior
knowledge about this organisation, and you do not infer values that are not
present in the context.
```

**Why it exists.** A model carries a great deal of general knowledge about how banks, asset managers and enterprises typically work. That knowledge is the problem. Asked how "active customer" is defined, it can produce a thoroughly reasonable industry-standard definition — a definition that is not yours, arrived at confidently, with no signal to the user that it came from nowhere.

The framing draws the boundary: *this organisation's* facts come from the context, and only from the context. General knowledge remains available for language, structure and explanation, which is what it is good for.

**Without it.** The most dangerous failure mode in the whole system: plausible answers assembled from general knowledge, indistinguishable in tone from grounded ones. There is no downstream check that reliably catches a well-formed industry-standard answer, because it looks exactly like a correct one.

**Note the phrase "do not infer values".** This is narrower and more enforceable than "do not hallucinate". It names the specific behaviour — producing a value not present — and the numeric consistency evaluator tests exactly that.

---

## Block 2 — Response contract

Each rule earns its place.

### Rule 1 — Citation

**Why.** An answer that cannot be traced cannot be defended, corrected or reproduced. Citation is also the mechanism that makes automated attribution checking possible: without markers there is nothing to verify.

The second sentence — *a sentence without a citation must contain no claim* — is what stops citation-washing, where an answer carries one marker at the end covering paragraphs of mixed grounded and invented content.

**Without it.** Correct answers that fail audit. See eval case `eval-007`: substantively right, uncited, and therefore indefensible six months later.

### Rule 2 — Abstention

**Why.** Models are trained to be helpful, and helpfulness under insufficient context means guessing. Abstention has to be made explicitly safe, or the model treats a refusal as a failure to be avoided.

Three deliberate choices:

- **Partial answers are legitimate.** "The definition is X; the current value is not in the context" is more useful than either a guess or a blanket refusal.
- **"Refusing is a successful outcome"** directly counteracts the helpfulness bias.
- **Naming what is missing** turns a dead end into a routable request.

**Without it.** The failure in `eval-005`: a stale February figure presented as the current rate, in August, with no hedging at all.

### Rule 3 — No arithmetic in prose

**Why.** The highest-severity failure in a regulated setting, and the one users are least able to catch. Asked for a ratio, a language model produces a plausibly-shaped number. There is no visible difference between a computed 12.4% and an invented one.

This rule is a backstop. The real control is architectural: numbers come from deterministic tools, and the tool result is placed in the context. The rule exists because architecture is never complete and the model will otherwise fill the gap.

The final clause matters — telling the user *what would need to be computed* keeps the interaction useful instead of merely refusing.

**Without it.** `eval-006`: 88.4% appears nowhere in the context and is indistinguishable, in the answer, from the two figures that do.

### Rule 4 — As-of disclosure

**Why.** A figure without a date is uninterpretable and quietly implies currency. Forcing the date into the answer surfaces staleness at the point of use, where the user can judge it, rather than burying it in metadata nobody reads.

It also creates a second line of defence behind the freshness gate: if a stale chunk slips through retrieval, the answer at least announces its age.

**Without it.** Users assume figures are current, because that is the reasonable default assumption about a system that answers instantly.

### Rule 5 — Definition fidelity

**Why.** Paraphrase changes scope. "Assets under Management is the market value of client assets" is a perfectly natural simplification of a definition that excludes custody-only arrangements — and it is now a different metric. Certified wording is certified precisely because a steward agreed to its boundaries.

**Without it.** Definitions drift toward the generic with every retelling, and the exclusions — which is where the business rule lives — are the first casualty.

### Rule 6 — Ambiguity

**Why.** When retrieval returns two certified definitions, the model's instinct is to pick the more relevant-looking one and answer. That produces two colleagues with different, individually defensible numbers.

**Without it.** `eval-009`: two certified revenue definitions in context, one silently chosen, no indication to the user that a choice was made.

**Note.** The primary control is upstream — the semantic layer should detect the conflict and refuse to assemble a prompt at all, as in the demo. This rule covers conflicts the registry did not know about.

### Rule 7 — Certification disclosure

**Why.** Sometimes lower-tier data is the only data, and using it is a legitimate decision. What is not legitimate is presenting it identically to certified data. Disclosure lets the user calibrate.

**Without it.** A sandbox extract answers a question with exactly the authority of a certified dataset.

### Rule 8 — Format

**Why.** Three reasons, in order of importance: consistency lets users build a reliable habit of reading answers; a stable structure makes automated checking possible; and the "Sources" line makes provenance visible without cluttering every sentence.

The suppressions — no preamble, no restatement, no offers of help — are not stylistic. Conversational padding around a factual answer dilutes it and, in a compliance context, makes transcripts harder to review.

---

## Block 3 — Request context

```text
<request_context>
user_purpose: internal_management_reporting
entitlements_applied: true
as_of_tolerance_days: 2
</request_context>
```

**Why it exists.** Three jobs:

1. **`user_purpose`** records why the question is being asked, which is the field purpose-limitation controls key on. It reaches the audit record from here.
2. **`entitlements_applied: true`** is an assertion by the runtime that filtering already happened. It is documentation for humans reading the transcript and for the audit trail — **it is not a control**, and the model must never be asked to enforce entitlement.
3. **`as_of_tolerance_days`** tells the model what "current" means for this question, so it can hedge appropriately when the context sits near the boundary.

**Keep it small.** Everything here is available to the model and everything is logged. Session state, user attributes and internal identifiers do not belong in a prompt.

---

## Block 4 — Retrieved context

```text
<retrieved_context>
[C1]
source: metric_registry
dataset: finance_curated.aum_daily_snapshot
certified: true
as_of: 2026-08-09T22:00:00Z
owner: Investment Data Stewardship
sensitivity: Internal
content: >
  Assets under Management: the end-of-day market value of client assets for
  which the firm holds a discretionary or advisory mandate. Exclusions:
  custody-only arrangements; assets under advisement without a mandate.
</retrieved_context>
```

**Why the fields exist.** Each is consumed by at least one control. None is decoration.

| Field | Consumed by | If absent |
| --- | --- | --- |
| `[Cn]` id | Citation rule; attribution check; audit record | Nothing to cite; nothing to verify |
| `source` | Reliability weighting; the model's sense of what kind of claim this is | Registry entries and prose chunks look identical |
| `dataset` | Sources line; audit record; lineage trace | The answer names no provenance |
| `certified` | Rule 7; certification gate | Sandbox data carries certified authority |
| `as_of` | Rule 4; staleness evaluator; freshness gate | Staleness is invisible at the point of use |
| `owner` | Escalation routing; accountability in the audit record | No one to ask when it is wrong |
| `sensitivity` | Egress checks; handling rules | No signal for downstream filtering |
| `content` | The answer itself | — |

**Format notes.**

- **Sequential ids from `C1`.** Stable and simple; the citation regex depends on it.
- **Key–value lines, then content.** Trivially parseable by producer, model and evaluator alike.
- **Metadata before content**, so provenance is read as belonging to the chunk rather than as a trailing afterthought.
- **Do not sort by relevance alone.** Order by governance strength first — certified before managed, fresher before staler. Position influences use.
- **Cap the chunk count.** More context dilutes attention and widens the entitlement surface. Five to eight chunks is usually plenty for a definitional or factual question.

---

## Block 5 — The question

```text
<question>
What is Assets under Management and what was the figure at the last close?
</question>
```

**Why last, and why verbatim.** Last, because instructions and context should be established before the task. Verbatim, because a rewritten question is a silently changed question — and the audit record must show what the user actually asked, not what the runtime decided they meant.

If query rewriting or expansion happens, it belongs in retrieval, and both forms belong in the audit record.

---

## Context block schema

For implementers. The machine-readable equivalent of the text format above.

```json
{
  "type": "object",
  "required": ["id", "source", "dataset", "certified", "as_of", "content"],
  "properties": {
    "id":          { "type": "string", "pattern": "^C[0-9]+$" },
    "source":      { "type": "string", "enum": ["metric_registry", "business_glossary", "data_catalogue", "lineage_service", "data_quality_service", "policy_library", "architecture_standard", "document_chunk", "tool_result"] },
    "dataset":     { "type": "string", "description": "Fully qualified governed identifier, not a display name." },
    "certified":   { "type": "boolean" },
    "certification_tier": { "type": "string", "enum": ["certified", "managed", "exploratory"] },
    "as_of":       { "type": "string", "format": "date-time" },
    "owner":       { "type": ["string", "null"] },
    "sensitivity": { "type": "string", "enum": ["Public", "Internal", "Confidential", "Restricted"] },
    "content":     { "type": "string" },
    "lineage_ref": { "type": "string", "description": "Optional. Resolves to a lineage record for audit." }
  }
}
```

`source: tool_result` is worth calling out. When a deterministic tool computes a figure, its output enters the context as a chunk like any other — which is what makes the figure citable, checkable by the numeric consistency evaluator, and traceable in the audit record.

---

## Worked example

### The assembled prompt

```text
You are an enterprise data assistant. You answer questions using only the
governed context supplied in <retrieved_context>. You do not use prior
knowledge about this organisation, and you do not infer values that are not
present in the context.

RESPONSE CONTRACT
[... rules 1-8 as above ...]

<request_context>
user_purpose: internal_management_reporting
entitlements_applied: true
as_of_tolerance_days: 2
</request_context>

<retrieved_context>
[C1]
source: metric_registry
dataset: finance_curated.aum_daily_snapshot
certified: true
as_of: 2026-08-09T22:00:00Z
owner: Investment Data Stewardship
sensitivity: Internal
content: >
  Assets under Management: the end-of-day market value of client assets for
  which the firm holds a discretionary or advisory mandate. Exclusions:
  custody-only arrangements; assets under advisement without a mandate.
  Grain: legal entity, daily close. Unit: EUR. Reported at the closing
  reference rate for the reporting date.

[C2]
source: tool_result
dataset: finance_curated.aum_daily_snapshot
certified: true
as_of: 2026-08-09T22:00:00Z
owner: Investment Data Stewardship
sensitivity: Internal
content: >
  get_metric_value(metric_id=metric.aum.firm_wide, period_end=2026-08-09,
  period_grain=daily) -> status=ok, value=412600000000, unit=EUR,
  formatted="EUR 412.6 billion", as_of=2026-08-09T22:00:00Z.

[C3]
source: data_quality_service
dataset: governance_curated.dq_measurement_runs
certified: true
as_of: 2026-08-09T04:00:00Z
owner: Data Governance Office
sensitivity: Internal
content: >
  finance_curated.aum_daily_snapshot measurement run 2026-08-09: completeness
  99.8%, validity 99.6%. Both above threshold. Status green.
</retrieved_context>

<question>
What is Assets under Management and what was the figure at the last close?
</question>
```

### A compliant response

```text
Assets under Management is the end-of-day market value of client assets for
which the firm holds a discretionary or advisory mandate, excluding
custody-only arrangements and assets under advisement without a mandate [C1].
At the last close, firm-wide AUM was EUR 412.6 billion as of
2026-08-09T22:00:00Z [C2].

The figure is reported in EUR at the closing reference rate for the reporting
date [C1]. The underlying dataset was measured at 99.8% completeness and 99.6%
validity on its most recent run, both above threshold [C3].

Sources:
[C1] finance_curated.aum_daily_snapshot (metric registry), as of 2026-08-09T22:00:00Z
[C2] finance_curated.aum_daily_snapshot (tool result), as of 2026-08-09T22:00:00Z
[C3] governance_curated.dq_measurement_runs, as of 2026-08-09T04:00:00Z
```

Why it passes: the definition reproduces the exclusions rather than simplifying them; the figure came from a tool result and is cited to it; the as-of accompanies the figure; every claim-bearing sentence carries a marker; and the Sources line closes the loop.

### A non-compliant response, and what catches it

```text
Assets under Management is the total market value of client assets we manage.
Firm-wide AUM currently stands at EUR 412.6 billion, up around 3% on the prior
quarter, with data quality at 99.8%.
```

| Problem | Rule breached | Caught by |
| --- | --- | --- |
| "total market value of client assets" — exclusions dropped, scope changed | 5 | Human review; definition fidelity check |
| "currently stands" — implies live, no as-of | 4 | As-of disclosure check |
| "up around 3%" — appears nowhere in context, computed in prose | 3 | `NumericConsistencyEvaluator` |
| "data quality at 99.8%" — real number, wrong subject (completeness, not overall quality) | 5 | Human review — **not caught automatically**, because the number is present in context |
| No citations at all | 1 | `CitationCoverageEvaluator` |

The fourth row is the honest limitation. A number lifted from the right context but attached to the wrong claim passes every lexical check in this repository. That is precisely why [`../evaluation/README.md`](../evaluation/README.md) is explicit that these evaluators are regression gates, not correctness oracles, and why sampled human review remains part of the control set.

---

## What this prevents

| Failure | Prevented by |
| --- | --- |
| Industry-standard definition presented as the organisation's | Block 1 framing |
| Uncited answer that cannot be defended in audit | Rule 1 |
| Guessing when context is insufficient | Rule 2 |
| Fabricated ratios, growth rates and totals | Rule 3 (plus tool-based computation) |
| Stale figure presented as current | Rule 4, plus the as_of field |
| Certified definition simplified into a different scope | Rule 5 |
| Silent choice between two certified definitions | Rule 6 |
| Exploratory data carrying certified authority | Rule 7, plus the certified field |
| Inconsistent answer shape that users cannot skim reliably | Rule 8 |
| Provenance that cannot be reconstructed later | Context block schema |
| Question silently rewritten before it was answered | Block 5 verbatim rule |

And, stated plainly, what it does **not** prevent: retrieval fetching the wrong context in the first place; a number attached to the wrong claim; a subtly reversed statement built from context vocabulary; or a definition that is certified, correctly reproduced, and wrong. Those need retrieval evaluation, human review, and a working stewardship process respectively.

---

## Variations

**Low-stakes internal agent.** Rules 1, 2 and 3 are the irreducible core. Rules 4, 5 and 7 can relax where consequences are bounded. Relaxing rule 2 is rarely wise at any stakes level — an agent that guesses is worse than no agent, because it consumes trust it did not earn.

**Document-grounded (prose) agent.** Add a rule requiring quotation of the operative sentence for any policy claim, and a field for the document's effective date. Chunking separates qualifications from the rules they qualify, so the agent must be able to show the sentence it relied on.

**Multi-source synthesis.** Add a rule for conflicting sources: name the conflict, cite both, and state which is more authoritative *by governance tier* rather than by apparent relevance. Never merge conflicting claims into a single smoothed statement.

**Action-taking agent.** Add a confirmation contract: restate the action, its parameters and its consequence, and require explicit confirmation before execution. Grounding rules still apply to any facts stated in the confirmation.

---

## Testing the template

Before deploying a change:

1. **Run the eval suite.** `python3 evaluation/eval_framework.py --eval-set your_set.jsonl --fail-under 0.85`
2. **Check the abstention cases specifically.** They are the ones a "more helpful" edit quietly breaks, and the aggregate score can rise while they regress.
3. **Test with empty context.** The agent must refuse cleanly rather than fall back on general knowledge. This is the single highest-value test in the set.
4. **Test with stale context.** It must surface the age rather than quietly present it as current.
5. **Test with two conflicting definitions.** It must ask rather than choose.
6. **Test with uncertified context.** It must disclose the tier.
7. **Test with a number absent from context.** Ask a question requiring a derivation the context does not contain; the agent must decline to compute and say what is missing.
8. **Read twenty real answers end to end.** No automated metric substitutes for this, and it is the step most reliably skipped.
