# Prompts

> Prompts are the last mile. They are not the fix.

## Contents

- [The principle](#the-principle)
- [What's here](#whats-here)
- [How to use these templates](#how-to-use-these-templates)
- [Prompts are code](#prompts-are-code)
- [Versioning](#versioning)
- [Reviewing a prompt change](#reviewing-a-prompt-change)
- [What belongs in a prompt, and what does not](#what-belongs-in-a-prompt-and-what-does-not)
- [Anti-patterns](#anti-patterns)

---

## The principle

By the time a prompt is assembled, every decision that determines whether the answer will be *correct* has already been made. Which datasets were eligible. Whether the term resolved to one definition or three. Whether the caller was entitled to the data. Whether the value was fresh enough to state. Whether a number came from a tool or will be invented.

A prompt cannot repair any of that. What it can do is make the difference between context that is used faithfully and context that is used loosely — which is a real and worthwhile contribution, and a much narrower one than prompt engineering is usually asked to make.

The diagnostic is straightforward:

| Symptom | Actual layer | Prompt can help? |
| --- | --- | --- |
| Two users get different numbers for the same question | Semantic layer — ambiguous definition | **No** |
| Answer is out of date | Data layer — freshness gate missing | **No** |
| Answer cites data the user shouldn't see | Access control — entitlement after retrieval | **No** |
| Answer contains a number that exists nowhere | Runtime — arithmetic in prose instead of a tool | **Partly** — rules help; only tools fix it |
| Answer is right but has no citation | **Prompt** — no citation contract | **Yes** |
| Answer paraphrases a certified definition into a different scope | **Prompt** — no verbatim rule | **Yes** |
| Answer states a figure without its as-of date | **Prompt** — no disclosure contract | **Yes** |
| Answer guesses instead of refusing | **Prompt** — abstention not made safe | **Yes** |

Four of eight are prompt problems. The other four consume most of the effort in most programmes, because rewording an instruction is faster than registering a definition — and produces the appearance of progress while the underlying failure remains.

**A useful rule of thumb:** if you are on the third rewording of the same instruction and the behaviour has not stabilised, you are working on the wrong layer. Stop and go read [`../architecture/semantic-layer-for-agents.md`](../architecture/semantic-layer-for-agents.md).

---

## What's here

| File | Purpose |
| --- | --- |
| [`grounded-answer-template.md`](grounded-answer-template.md) | An annotated, reusable template for a grounded enterprise answer. Every block explains why it exists, with a filled worked example. |
| [`guardrail-patterns.md`](guardrail-patterns.md) | Guardrails across pre-retrieval, in-context, post-generation and human-in-the-loop, each with the failure it prevents, an implementation sketch and how to test it. |

The context block format used in the template is the same one produced by [`../examples/glossary_grounding_demo.py`](../examples/glossary_grounding_demo.py) and consumed by [`../evaluation/metrics.py`](../evaluation/metrics.py). That is deliberate: the format is an interface, and everything that touches it agrees.

---

## How to use these templates

**Start from the whole template, then remove.** Every block earns its place by preventing a specific failure. Removing one is a decision to accept that failure — legitimate, but it should be explicit rather than incidental.

**Keep the block order.** System framing, request context, retrieved context, question. Reordering changes behaviour in ways that are hard to predict and easy to miss, and the audit record assumes the structure.

**Do not put definitions in the prompt.** Definitions come from the semantic layer, at runtime, in the context block. A definition written into a prompt is a fork: it will diverge from the registry, and nobody will notice until two agents disagree.

**Adapt the wording, keep the contracts.** The tone should suit your users. The citation requirement, the abstention rule, the no-arithmetic rule and the as-of disclosure are contracts that downstream checks depend on. Change the wording; keep the obligation.

**Test the abstention path first.** It is the behaviour most likely to break silently and the one nobody demonstrates. Write the refusal cases before the happy path.

---

## Prompts are code

A prompt is a production behaviour specification. Treat it accordingly.

| Practice | Why |
| --- | --- |
| **Source control** | A prompt edited in a production console has no history, no review, and no rollback |
| **Two-person review** | Wording changes have non-obvious behavioural consequences |
| **Automated evaluation as a merge gate** | The only way to know a change did not regress something else |
| **Versioned deployment** | The audit record must name the instructions that produced an answer |
| **Rollback** | Prompt changes fail like code, and need the same remedy |
| **Change log** | "Why is this instruction here?" must have an answer |
| **Environment promotion** | Development, test, production — with an eval run at each boundary |

The instinct to treat prompts as content is understandable — they are prose, editable by non-engineers, and appear low-risk. They are none of those things once a business decision depends on the output.

---

## Versioning

Semantic versioning maps cleanly onto prompt changes:

| Change | Bump | Examples |
| --- | --- | --- |
| **Major** | Behaviour contract changes | Removing the citation requirement; changing the abstention rule; restructuring blocks |
| **Minor** | New capability, contract preserved | Adding an as-of disclosure rule; adding a new context field |
| **Patch** | Wording, no behaviour change | Typos; clarifying phrasing; formatting |

The version identifier belongs in three places: the template metadata, the deployment record, and **every audit record for an answer it produced**. Without the third, no historical answer can be explained.

A minimal header worth carrying in every template:

```yaml
template:
  id: prompt.grounded_answer
  version: 2.1.0
  owner: Agent Platform Team
  last_reviewed: 2026-07-14
  eval_set: evaluation/sample_eval_set.jsonl
  min_aggregate_score: 0.85
  changelog:
    - version: 2.1.0
      change: Added explicit as-of disclosure requirement to the response contract.
      eval_delta: "staleness 0.82 -> 0.94; no regression elsewhere"
```

Recording `eval_delta` alongside the change is what converts a change log into evidence.

---

## Reviewing a prompt change

A checklist for the reviewer. The author should have run it first.

**Contracts**
- [ ] Citation requirement intact
- [ ] Abstention rule intact, and abstention still framed as an acceptable outcome
- [ ] No-arithmetic rule intact
- [ ] As-of disclosure intact
- [ ] Verbatim-definition rule intact

**Content**
- [ ] No business definitions embedded in the prompt (they belong in the semantic layer)
- [ ] No hard-coded values, thresholds, entity names or dates
- [ ] No instruction that duplicates a control enforced elsewhere — duplicated controls drift
- [ ] Nothing that would leak internal system detail into a user-facing answer

**Structure**
- [ ] Block order unchanged
- [ ] Context block schema unchanged, or the change is coordinated with retrieval and the evaluators
- [ ] Output format still parseable by whatever consumes it

**Evidence**
- [ ] Evaluation suite run; results attached to the change
- [ ] Abstention cases specifically checked — did the change make the agent more willing to answer?
- [ ] Version bumped appropriately
- [ ] Change log entry explains *why*, not just *what*

The question that catches most regressions: **"does this change make the agent more likely to answer when it should refuse?"** Instructions added to make an agent more helpful very often do, and the effect shows up in the abstention cases rather than the ones anybody demonstrated.

---

## What belongs in a prompt, and what does not

| Belongs in the prompt | Belongs elsewhere | Where |
| --- | --- | --- |
| Role and scope framing | Which datasets are eligible | Certification register |
| Citation requirement | Whether the user may see the data | Entitlement service |
| Abstention rule and how to phrase it | Whether context is stale | Freshness gate |
| Output format contract | The definition of a business term | Semantic layer |
| Tone and register | The value of a metric | Deterministic tool |
| How to present uncertainty | Whether the source is certified | Catalogue |
| Instruction not to compute in prose | The computation itself | Deterministic tool |

The right-hand column is the more important one. Every item that migrates from prompt to platform becomes testable, reusable across agents, and auditable — three properties a prompt instruction never has.

---

## Anti-patterns

**The growing prompt.** Each incident adds an instruction. Six months later the prompt is two thousand words, instructions contradict each other, and nobody can say which are load-bearing. When a prompt grows after an incident, ask which layer the incident actually belonged to.

**"Be accurate" instructions.** "Be accurate", "do not hallucinate", "only use real data" are unfalsifiable and unenforceable. Replace with a mechanical, checkable rule: "cite the chunk id after every sentence containing a figure" is testable; "be accurate" is not.

**Definitions in the prompt.** Creates a second source of truth that will diverge from the registry. Always.

**Few-shot examples containing real data.** Examples get logged, cached, sometimes surfaced. Use synthetic examples exclusively.

**Prompt-based access control.** "Do not reveal salary information" is a request, not a control. If the data reached the context block, the control already failed.

**Undifferentiated context.** Dumping retrieved content without provenance fields. The answer then cannot cite, no check can verify, and the audit trail is a transcript rather than an explanation.

**Optimising for demonstrations.** Prompts tuned on the questions people demonstrate produce agents that excel at those and degrade on the long tail — which is where the users are. Tune against the eval set, and build the eval set from real questions including the ones that failed.
