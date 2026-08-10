# Evaluation

> A dependency-light, deterministic regression gate for grounded agent answers. Runs offline, in seconds, on every pull request.

## Contents

- [Running it](#running-it)
- [What the output means](#what-the-output-means)
- [The metrics](#the-metrics)
- [What these metrics are not](#what-these-metrics-are-not)
- [The eval-set format](#the-eval-set-format)
- [Building your own eval set](#building-your-own-eval-set)
- [Wiring it into CI](#wiring-it-into-ci)
- [Choosing a threshold](#choosing-a-threshold)
- [Extending the framework](#extending-the-framework)
- [What this does not cover](#what-this-does-not-cover)

---

## Running it

No installation is required. Python 3.10 or later, standard library only.

```bash
# Default: the bundled sample set
python3 evaluation/eval_framework.py

# Explicit eval set
python3 evaluation/eval_framework.py --eval-set evaluation/sample_eval_set.jsonl

# CI mode: write artefacts, fail below threshold
python3 evaluation/eval_framework.py \
    --eval-set evaluation/sample_eval_set.jsonl \
    --out build/ \
    --fail-under 0.85

# A subset of evaluators
python3 evaluation/eval_framework.py --evaluators numeric_consistency,citation_coverage
```

### Options

| Flag | Default | Purpose |
| --- | --- | --- |
| `--eval-set` | bundled sample | Path to the JSONL eval set |
| `--out` | none | Directory for `eval_report.json` and `eval_report.csv` |
| `--fail-under` | `0.75` | Exit non-zero if the weighted aggregate falls below this |
| `--case-threshold` | `0.70` | Per-metric score below which a case appears in the findings digest |
| `--evaluators` | all | Comma-separated subset by name |
| `--reference-date` | now | Reference time for staleness where a case does not pin its own |
| `-v, --verbose` | off | Debug logging to stderr |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Aggregate at or above `--fail-under` |
| `1` | Aggregate below `--fail-under` — the gate tripped |
| `2` | Usage or input error (missing file, malformed JSON, unknown evaluator) |

Distinguishing `1` from `2` matters in a pipeline: a broken eval set should not look like a quality regression.

---

## What the output means

Three sections. Per-case scores:

```text
+==========+========+======+=========+=========+===========+=======+=========+
| case     | ground | cite | numeric | abstain | relevance | fresh | overall |
+==========+========+======+=========+=========+===========+=======+=========+
| eval-001 | 0.97   | 1.00 | 1.00    | 1.00    | 0.89      | 1.00  | 0.98    |
| eval-005 | 1.00   | 1.00 | 1.00    | 0.00    | 0.15      | 0.00  | 0.57    |
| eval-006 | 0.56   | 1.00 | 0.67    | 1.00    | 0.51      | 1.00  | 0.79    |
| eval-007 | 1.00   | 0.00 | 1.00    | 1.00    | 1.00      | 1.00  | 0.86    |
+==========+========+======+=========+=========+===========+=======+=========+
```

Then aggregate means per metric and a weighted overall. Then a **findings digest** naming every case with a metric below `--case-threshold`, with the rationale string from the evaluator:

```text
  eval-006  (overall 0.79)
    Q: How complete is the counterparty reference data used for agent grounding?
    [0.67] numeric_consistency: 2/3 numbers traceable to context; unsupported: 88.4
```

The digest is the part to read. The aggregate tells you whether to merge; the digest tells you what broke.

**`overall` is weighted, not averaged.** Weights encode severity:

| Evaluator | Weight | Reasoning |
| --- | --- | --- |
| `groundedness` | 1.5 | Fabricated content is a top-severity failure |
| `numeric_consistency` | 1.5 | Fabricated figures are the highest-severity failure |
| `abstention_correctness` | 1.5 | Answering when you should refuse is a control failure |
| `citation_coverage` | 1.0 | Correct but indefensible is still a failure |
| `staleness` | 1.0 | Right answer, wrong point in time |
| `answer_relevance` | 0.75 | Weakest signal — lexical proxy for correctness |

Adjust the weights in `default_evaluators()` to match your own risk profile, and write down why you changed them.

---

## The metrics

### `groundedness` — is the answer's vocabulary supported by the context?

Tokenises the answer, drops stopwords and short tokens, and measures what fraction of the remainder appears in the retrieved context (question vocabulary counts as supported — echoing the user is not fabrication).

**Catches.** Content introduced from nowhere: an invented product name, a policy that does not exist, an attribute the context never mentioned.

**Misses.** Negation and reversal. "AUM *excludes* discretionary mandates" scores identically to "*includes*". There is no stemming, so `excludes` does not match `excluded`.

**Expect 0.80–1.00 for well-behaved answers, not a clean 1.00.** Calibrate on your own corpus. Not applicable when a case correctly abstains — it returns 1.0 with `applicable: false` rather than punishing a refusal for containing few context tokens.

### `citation_coverage` — does the answer cite, and do its citations resolve?

Averages three things: presence (a substantive answer carries at least one `[Cn]`), validity (every marker resolves to a chunk that was retrieved), and recall (chunks named in `expected_sources` are cited).

**Catches.** Uncited answers, and fabricated citations — `[C7]` when only three chunks were retrieved.

**Misses.** Whether the citation is attached to the *right* sentence. An answer citing `[C1]` for a claim that came from `[C2]` scores full marks.

### `numeric_consistency` — is every figure traceable to context?

Extracts numeric literals from the answer (ignoring citation markers), resolves magnitude suffixes (`1.2bn` matches `1200000000`), and checks each against the context under a relative tolerance that forgives rounding.

**The most valuable check in the set.** Precise, cheap, and aimed at the highest-severity failure.

**Catches.** Any figure that is not in the context — `eval-006`.

**Misses.** A number lifted from the wrong row. Presence is not correctness.

**Deliberate behaviour.** Legitimately derived figures — a ratio of two supported numbers — are flagged. That is intentional: arithmetic in prose is itself the anti-pattern. Compute it in a tool, put the result in context, and it passes.

### `abstention_correctness` — did it do the right thing under insufficient context?

Reads `metadata.expected_behaviour`, one of:

| Value | Required behaviour |
| --- | --- |
| `answer` | A substantive, non-refusing answer |
| `abstain` | An explicit refusal — context missing, stale, uncertified, out of remit |
| `disambiguate` | Ask which definition is meant, rather than choosing |

**Binary by design.** Partial credit for "nearly refused" would hide exactly the behaviour this exists to catch. Also scores 0.0 for over-refusal on an answerable question — an agent that refuses everything is not safe, it is useless.

**Detection is phrase-based**, so it depends on the response contract producing recognisable refusals. Extend `ABSTENTION_MARKERS` and `DISAMBIGUATION_MARKERS` in `metrics.py` to match your own phrasing.

### `answer_relevance` — token F1 against the reference answer

**The weakest metric here, and weighted accordingly.** It rewards vocabulary agreement, not semantic equivalence: a correct answer in different business language scores poorly, a wrong answer borrowing the reference's wording scores well.

Use it to detect large regressions in answer *shape*. Never as a correctness oracle. In the sample run, correct abstentions score 0.70 and 0.76 purely because refusal wording differs from the reference — which is a limitation of the metric, not a defect in the answers.

### `staleness` — was the context fresh enough for this question?

Compares the oldest retrieved chunk's `as_of` against `metadata.as_of_tolerance_days`. Scores 1.0 within tolerance, decaying linearly to 0.0 at three times tolerance.

**Tolerance is per case** because freshness is a business decision, not a technical one: a policy definition may be valid for a year, an intraday position for minutes.

**The reference time is `metadata.evaluated_at` when present.** Pin it in every case — otherwise scores decay as the file ages and yesterday's green build fails today for no reason anyone changed.

Missing `as_of` on every chunk scores 0.0: freshness that cannot be evidenced is not freshness.

---

## What these metrics are not

Stated plainly, because an evaluation harness that oversells itself is worse than none.

**These are heuristics, not judges of truth.** Every one is lexical or numeric. None understands meaning. They exist because a regression gate must be fast, deterministic, offline and explainable — properties a model-based judge does not have, and which are exactly what you need on every pull request.

| They can tell you | They cannot tell you |
| --- | --- |
| The answer stopped citing its sources | The answer is correct |
| A figure appeared that was not in the context | The right figure was chosen |
| The agent stopped refusing questions it used to refuse | The refusal was appropriate in the circumstances |
| The context is older than declared tolerance | The data was right |
| The answer diverged from the reference in vocabulary | The answer is worse |
| **That something changed** | **That something is good** |

The bottom row is the honest summary. Treat a score movement as a prompt to investigate.

**A complete evaluation programme has three layers.** This harness is one of them:

1. **Automated heuristics** (here) — every commit, catches drift and gross failure.
2. **Model-based judging** — periodically, on a sample, with its own calibration set and a documented agreement rate against human labels.
3. **Human review** — continuously, on a sample and on all escalations. The only layer that establishes truth.

Running only the first is common and is a known, accepted gap. Running only the first while *claiming* the accuracy is assured is the failure.

---

## The eval-set format

One JSON object per line. Blank lines and `#` comment lines are ignored, so eval sets stay reviewable in a pull request.

```json
{
  "id": "eval-001",
  "question": "What is Assets under Management and what was the firm-wide figure at the last close?",
  "expected_answer": "Assets under Management is the certified end-of-day market value...",
  "expected_sources": ["C1"],
  "retrieved_context": [
    {
      "id": "C1",
      "source": "metric_registry",
      "dataset": "finance_curated.aum_daily_snapshot",
      "certified": true,
      "as_of": "2026-08-09T22:00:00Z",
      "owner": "Investment Data Stewardship",
      "sensitivity": "Internal",
      "content": "Assets under Management (AUM) is the certified end-of-day..."
    }
  ],
  "generated_answer": "Assets under Management is the certified end-of-day market value... [C1]",
  "metadata": {
    "expected_behaviour": "answer",
    "as_of_tolerance_days": 2,
    "evaluated_at": "2026-08-10T09:00:00Z",
    "domain": "investment_finance",
    "note": "Baseline good case: certified metric, fresh, cited."
  }
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Stable. Referenced in findings and CI output. |
| `question` | yes | Verbatim, as a user would ask it |
| `expected_answer` | no | Reference answer. Omit to skip `answer_relevance`. |
| `expected_sources` | no | Chunk ids that must be cited |
| `retrieved_context` | yes | Chunks in the format from [`../prompts/grounded-answer-template.md`](../prompts/grounded-answer-template.md). May be empty for no-context cases. |
| `generated_answer` | yes | What the system produced |
| `metadata.expected_behaviour` | recommended | `answer`, `abstain` or `disambiguate`. Defaults to `answer`. |
| `metadata.as_of_tolerance_days` | recommended | Omit to skip `staleness` |
| `metadata.evaluated_at` | **strongly recommended** | Pins the reference time so scores are reproducible |
| `metadata.note` | no | Why this case exists. Write it. |

The legacy boolean `metadata.should_abstain` is honoured as a fallback for `expected_behaviour`.

---

## Building your own eval set

**Source cases from reality, not imagination.** In rough order of value:

1. **Questions users actually asked**, including the ones the agent failed. Highest signal available.
2. **Every escalation and correction.** A reviewer who corrected an answer has produced an eval case for free — capture it at the point of correction.
3. **Each failure mode in the [README](../README.md#the-problem).** One case per mode, minimum.
4. **Each guardrail in [`../prompts/guardrail-patterns.md`](../prompts/guardrail-patterns.md).** One case that should trip it, one that should not.
5. **Every definitional dispute the business has had.** Those become the ambiguity cases.

**Required composition.** A set of only well-behaved cases measures nothing — it will score highly against a broken system.

| Category | Share | Why |
| --- | --- | --- |
| Good cases | ~50% | The baseline; catches broad regression |
| Required abstentions | ~15% | The behaviour most likely to break silently |
| Ambiguous terms | ~10% | Needs at least one handled well and one badly |
| Numeric failures | ~10% | Highest severity |
| Citation failures | ~10% | Audit defensibility |
| Edge cases | ~5% | Empty context, single chunk, very long context |

**Include failing cases deliberately.** The bundled set contains cases whose `generated_answer` is *wrong on purpose* — `eval-005`, `eval-006`, `eval-007`, `eval-009`. They prove the evaluators detect what they claim to detect. An evaluator that has never failed has never been tested.

**Practical rules.**

- **Everything synthetic.** Never real customer data, real internal metrics or real system names. The sample set is entirely invented.
- **Pin `evaluated_at`** on every case, or staleness scores drift with the calendar.
- **Write the `note`.** Six months later, "why does this case expect abstention?" needs an answer.
- **Start with 20–30 cases** covering the composition above. Grow from production failures rather than by writing more from scratch.
- **Version it with the code.** An eval set that lives in a spreadsheet is not a gate.

---

## Wiring it into CI

The harness exits non-zero below threshold, so no wrapper is needed.

**GitHub Actions:**

```yaml
name: agent-eval
on: [pull_request, push]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Compile check
        run: python3 -m py_compile evaluation/*.py examples/*.py

      - name: Grounding demo smoke test
        run: python3 examples/glossary_grounding_demo.py > /dev/null

      - name: Answer quality gate
        run: |
          python3 evaluation/eval_framework.py \
            --eval-set evaluation/sample_eval_set.jsonl \
            --out build/ \
            --fail-under 0.85

      - name: Upload eval report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: build/
```

**Generic pipeline:**

```bash
set -e
python3 -m py_compile evaluation/*.py examples/*.py
python3 evaluation/eval_framework.py --eval-set eval/production_set.jsonl --out artifacts/ --fail-under 0.85
```

### Making it a real gate

| Practice | Why |
| --- | --- |
| **Block the merge**, do not just report | An advisory gate is a dashboard |
| Run on **every** prompt, retriever and semantic-definition change | All three change answer behaviour |
| Publish the JSON report as a build artefact | It is the evidence an auditor asks for |
| **Track the aggregate over time** | The trend catches slow erosion that a single threshold does not |
| Alert on **abstention rate** movement in either direction | A falling abstention rate usually means the agent started guessing |
| Require a written justification to lower the threshold | Thresholds ratchet down silently otherwise |

**Generating `generated_answer` for the eval set.** Two approaches, both legitimate:

- **Frozen answers** (what this repo ships): answers captured once and committed. Deterministic and fast — this tests the *evaluators* and the eval set, and it is what makes CI reproducible.
- **Live regeneration**: run each question through the real pipeline at CI time, then evaluate. Tests the *system*, but introduces model non-determinism and network dependency.

Most teams need both: frozen in the fast pre-merge gate, live on a nightly or pre-release schedule.

---

## Choosing a threshold

Do not pick a number from this document. Derive it:

1. Run against a set of answers you have **manually confirmed are acceptable**.
2. Note the aggregate — that is your realistic ceiling.
3. Set the threshold a little below it, allowing for lexical variation.
4. Confirm your known-bad cases fall clearly below.
5. Re-derive after any material change to the eval set.

The bundled sample set scores **0.888** and passes the default 0.75. Its known-bad cases sit at 0.57, 0.67, 0.79 and 0.86 — which shows both that the evaluators discriminate, and that a whole-suite aggregate is a blunt instrument. **The findings digest, not the aggregate, is what tells you something broke**; the aggregate exists to be a gate.

For a stricter gate, add per-metric floors:

```bash
python3 evaluation/eval_framework.py --evaluators numeric_consistency --fail-under 1.0
```

Numeric consistency is a reasonable candidate for a floor of 1.0: any fabricated figure at all should block a release.

---

## Extending the framework

Subclass `Evaluator` in `metrics.py`:

```python
class UnitConsistencyEvaluator(Evaluator):
    """Every figure in the answer carries a unit that matches its source chunk."""

    name = "unit_consistency"
    short_name = "units"

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    def evaluate(self, case: EvalCase) -> EvalResult:
        # ... deterministic, no network, no clock reads ...
        return self._result(score, "3/3 figures carry a matching unit", checked=3)
```

Register it in `default_evaluators()` and it appears in the table, the aggregate, the JSON and the CSV automatically.

**Contract for a new evaluator:**

1. **Score in [0, 1].** `EvalResult` clamps, but return a sane value.
2. **Always return a rationale.** It is what appears in the findings digest, and a digest of bare numbers is useless.
3. **Be deterministic.** No network, no clock reads (use `case.evaluated_at` or the injected reference time), no global state.
4. **Handle abstention.** Decide explicitly whether your metric applies to a refusal, and return `applicable: False` when it does not.
5. **Document the limits in the docstring.** Every heuristic has them; an undocumented one will be over-trusted.

Ideas worth building: schema conformance of the context block, currency consistency, temporal-grain validation (did a monthly metric answer a daily question), exclusion-term preservation for definition fidelity, and citation-to-sentence alignment.

---

## What this does not cover

**Retrieval quality.** The largest gap, and the most consequential. Every metric here assumes `retrieved_context` was the right context. If retrieval fetched the wrong chunk, a perfectly grounded, cited, numerically consistent answer will be wrong and every metric will report success. **Build a separate labelled retrieval set** — question to expected-chunk mappings — and measure precision and recall. Most teams skip it, and it is where the accuracy actually comes from.

**Multi-turn behaviour.** Cases are single-turn. Context carry-over, disambiguation follow-through and topic switching need a conversational harness.

**Latency and cost.** Measure separately; they are real constraints on which architecture you can afford.

**Tool selection.** Whether the agent chose the right action for the question is routing evaluation, better served by platform testing tooling.

**Adversarial robustness.** Injection and jailbreak resistance need a dedicated red-team suite, exercised on a schedule rather than in the merge gate.
