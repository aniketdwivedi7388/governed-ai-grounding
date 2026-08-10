# Data 360 and Agentforce: Grounding Implementation Notes

> The reference implementation. Each section states **the pattern** in platform-neutral terms first, then **how it maps here**. Read the pattern; treat the mapping as one worked example of it.

> [!IMPORTANT]
> **Verify every product specific against current Salesforce documentation before you build.**
>
> This platform moves quickly — capabilities, names and boundaries have all changed materially across recent releases, and Data Cloud has been rebranded to **Data 360**. These notes are written at a **conceptual** level on purpose: where a mechanism is stable and well established it is named; where a detail is release-sensitive, the pattern is described generically rather than asserted as a product fact.
>
> Nothing here is a substitute for official documentation, and nothing here should be read as a configuration guide. If a statement below conflicts with current Salesforce documentation, the documentation is right.

## Contents

- [A note on naming](#a-note-on-naming)
- [Mapping summary](#mapping-summary)
- [1. Environment segregation](#1-environment-segregation)
- [2. Canonical data model and mapping](#2-canonical-data-model-and-mapping)
- [3. Identity resolution and the unified profile](#3-identity-resolution-and-the-unified-profile)
- [4. Governed metrics](#4-governed-metrics)
- [5. Structured retrieval](#5-structured-retrieval)
- [6. Unstructured retrieval](#6-unstructured-retrieval)
- [7. Agent runtime](#7-agent-runtime)
- [8. Prompt templates](#8-prompt-templates)
- [9. Trust and safety controls](#9-trust-and-safety-controls)
- [10. Testing and evaluation](#10-testing-and-evaluation)
- [What the platform does not give you](#what-the-platform-does-not-give-you)
- [Implementation sequence](#implementation-sequence)

---

## A note on naming

Salesforce's customer data platform, launched as Customer Data Platform and long known as **Data Cloud**, is now branded **Data 360**. Documentation, certifications, community content and the product UI have moved at different speeds, so all three names are in circulation and refer to substantially the same platform lineage.

Names used below:

| Term | What it refers to |
| --- | --- |
| **Data 360** / Data Cloud | The data platform: ingestion, harmonisation, identity resolution, insights, retrieval |
| **Agentforce** | The agent platform: agents, topics, actions, reasoning |
| **Prompt Builder** | Reusable, grounded prompt templates |
| **Einstein Trust Layer** | The set of trust controls applied around model interactions |

---

## Mapping summary

| Abstract layer | Data 360 / Agentforce construct | Notes |
| --- | --- | --- |
| Environment segregation | **Data spaces** | Partition by brand, region, entity or sensitivity |
| Raw landing | **Data streams** into data lake objects | Source-shaped, pre-harmonisation |
| Canonical model | **Data model objects (DMOs)** and mapping | Where "one customer shape" is agreed |
| Unified party | **Identity resolution** → unified profile | Match and reconciliation rules |
| Governed metrics | **Calculated insights**, semantic modelling | Metric definitions as platform objects |
| Low-latency structured grounding | **Data graphs** | Pre-joined, cached views for retrieval |
| Unstructured grounding | Unstructured ingestion, chunking, vector index, **retrievers** | Prose only |
| Agent runtime | **Agentforce agents, topics, actions** | Scope, intent, capability |
| Prompt assembly | **Prompt Builder templates** | Versioned, grounded, reviewable |
| Control plane | **Einstein Trust Layer**, sharing and access model, audit trail | Masking, retention, checks, logging |

---

## 1. Environment segregation

**The pattern.** Data grounded for one purpose, brand, jurisdiction or sensitivity tier must not silently ground another. Segregation should be a structural boundary, not a filter someone remembers to apply.

**How it maps here.** **Data spaces** provide logical partitions within a single Data 360 org, each with its own scoped data and access. They are the natural boundary for:

- **Jurisdiction** — where data residency or cross-border restrictions apply
- **Brand or business line** — where the same term legitimately means different things
- **Sensitivity tier** — separating a broad internal grounding surface from a restricted one
- **Assurance tier** — a certified space that grounds user-facing agents, distinct from an exploratory space

Design notes:

- **Decide the space model before ingestion.** Re-partitioning after the fact is a migration, and every downstream mapping, insight and retriever inherits the original choice.
- **Bind each agent to a space explicitly**, and treat that binding as a reviewable configuration item. An agent's grounding surface is defined as much by its space as by its retrievers.
- **Do not over-partition.** Every additional space multiplies mapping, identity resolution and insight maintenance. Partition where a real control boundary exists, not per team.

---

## 2. Canonical data model and mapping

**The pattern.** Source-shaped data cannot ground reliably: field names encode a source system's history, not the business's meaning. A canonical model is where the organisation agrees what a customer, an account and a transaction *are*, and mapping is where that agreement is made concrete and testable.

**How it maps here.** Ingested data lands in source-shaped **data lake objects**, then is mapped to **data model objects (DMOs)** — the harmonised, canonical layer. Salesforce ships a standard data model that most implementations extend rather than replace.

This mapping step is the platform's most under-appreciated governance control, because it is where three things become explicit and reviewable:

| Decision made at mapping | Governance significance |
| --- | --- |
| Which source field means which canonical concept | The definitional agreement, made concrete |
| What is transformed, standardised or defaulted | Provenance; also where silent quality damage happens |
| What is deliberately *not* mapped | Scope, minimisation, and the exclusion list |

Practical guidance:

- **Treat mapping as reviewed configuration.** Export it, version it, and require review for changes. An unreviewed mapping change alters the meaning of every downstream answer with no visible signal.
- **Record the business rationale, not only the field pairing.** "Registered address, not correspondence address, because domicile is a regulatory concept" is the durable artefact.
- **Map deliberately, not exhaustively.** Every mapped field is a field an agent might surface. Unmapped is a legitimate minimisation control.
- **Reconcile after mapping.** Compare canonical counts and totals to source. Mapping errors are systematic and quiet.

---

## 3. Identity resolution and the unified profile

**The pattern.** Two things break when a party is fragmented across systems. Answers are incomplete — a client with three source records gets a third of the picture. And **entitlement is evaluated against the wrong subject**, which is the more serious failure: access rules written for "this client's data" cannot be enforced correctly if the platform does not know which records are that client's.

**How it maps here.** **Identity resolution** applies configured **match rules** (which records refer to the same party) and **reconciliation rules** (which value wins when they disagree) to produce a **unified profile** across sources.

Why this matters specifically for grounding:

1. **Entitlement correctness.** Rules that grant access to a relationship's data depend on a correct, complete definition of that relationship. Under-matching leaks nothing but hides data; **over-matching merges two people, and an agent then answers one client's question with another's data.** That is a data breach produced by a match-rule configuration, and it is the highest-severity risk in this layer.
2. **Answer completeness.** "What do we hold for this client?" is only answerable against a unified view.
3. **Consent and purpose.** Consent attaches to a party. Fragmented parties mean fragmented, unenforceable consent.

Design notes:

- **Tune match rules conservatively for agent grounding.** The cost asymmetry is stark: a missed match produces an incomplete answer that a user will notice; a false match produces a cross-client disclosure that they may not.
- **Carry match confidence into the retrieval surface** where the platform exposes it, so a low-confidence unification can be treated as a reason to caveat or abstain.
- **Reconciliation rules are business decisions.** Which source wins for domicile is a stewardship question, not a technical default.
- **Version and audit rule changes.** A match-rule change silently alters the population behind every answer.

---

## 4. Governed metrics

**The pattern.** Metric definitions live as first-class, owned, versioned objects that all consumers resolve against — never re-derived per agent, per dashboard or per prompt. See [`semantic-layer-for-agents.md`](semantic-layer-for-agents.md).

**How it maps here.** **Calculated insights** define metrics over the canonical model, computed at scale and made available as queryable objects; streaming variants support near-real-time cases. Salesforce has also been investing in explicit **semantic modelling** capabilities that describe metrics and their relationships for consumption by analytics and agents — an area worth checking current documentation on, as it is evolving quickly.

The governance point is independent of which mechanism you use:

| Requirement | Implementation approach |
| --- | --- |
| Definition is authoritative | The insight *is* the definition. Nothing recomputes it downstream. |
| Owner is named | Maintain ownership in your governance register, keyed to the insight identifier |
| Grain is explicit | Encoded in the insight's dimensions; document the valid aggregations separately |
| Version is tracked | Source-control the definitions; deploy through your normal release process |
| Certification tier is visible | Naming convention or an accompanying registry the agent can also read |

Guidance:

- **Expose insights to agents as typed actions**, not as an open query surface. The action takes a metric identifier and a period, and returns a structured result — value, unit, as-of, definition, owner.
- **Do not let a prompt template re-derive a metric** from underlying objects. If a template computes a ratio, the definition now exists in two places and they will diverge.
- **Encode the aggregation rule in the action.** The platform will happily sum a snapshot metric across months if asked. See the aggregation table in the semantic layer document.
- **Keep the definition text with the metric**, so the agent can reproduce certified wording verbatim rather than paraphrasing it into a different scope.

---

## 5. Structured retrieval

**The pattern.** Most enterprise questions are structured lookups against governed objects. Vector search is the wrong default for data that has a key.

**How it maps here.** Two complementary mechanisms:

**Data graphs** pre-join and cache related canonical data into a denormalised, low-latency view. For grounding this is valuable because it collapses a multi-object traversal into a single fast read, which matters when a real-time agent interaction has a latency budget measured in hundreds of milliseconds. Design the graph around the questions the agent must answer, not around the data model's shape.

**Queries and actions over canonical objects and insights**, invoked through Flow, Apex or API-backed actions with typed parameters. This is where definitional and metric lookups belong.

A useful discipline: for any question the agent must answer, write down whether it is a lookup, a computation or a prose search **before** configuring anything. In practice a large majority of enterprise questions fall into the first two, and both are better served by structured paths than by a vector index.

---

## 6. Unstructured retrieval

**The pattern.** Vector retrieval earns its place over prose whose vocabulary cannot be predicted — policy, procedure, contract and note text. It does not earn its place over a glossary.

**How it maps here.** Data 360 supports ingesting unstructured content, chunking it, generating embeddings into a search index, and configuring **retrievers** that define what an agent may retrieve and how results are shaped for grounding.

Governance considerations that are easy to miss:

- **The index is a copy.** Whatever governed the source document — classification, retention, access — must be re-established for the index, or the index becomes the least-governed copy of your most sensitive prose.
- **Chunking destroys context.** A paragraph stating "this does not apply to entity X" can be separated from the rule it qualifies, and the agent will then apply the rule universally. Chunk on document structure, and carry section headings into chunk text.
- **Retriever configuration is a control.** It defines the grounding surface. Version it, review it, and know which agents use which retriever.
- **Document currency is invisible in prose.** A chunk from a superseded policy reads exactly like a current one. Carry effective-from and effective-to metadata, filter on it at retrieval, and surface it in the answer.
- **Scope retrievers narrowly.** One retriever spanning every document type produces context that is plausible and off-target. Separate retrievers per document class, selected by topic, retrieve better and audit better.

---

## 7. Agent runtime

**The pattern.** Scope, intent routing and capability are separate concerns. Deterministic actions are preferred over free generation for anything countable.

**How it maps here.** An **Agentforce agent** has a defined role and scope. **Topics** group related intents, each with its own scope description, instructions and permitted **actions**. Actions are the agent's capabilities — implemented as Flows, Apex, prompt templates, API-backed calls, or standard actions. A reasoning engine selects the topic and the actions for a given request.

Design guidance:

- **Topic boundaries follow retrieval strategy.** If two intents need different grounding sources or different guardrails, they are different topics. Topics that overlap in scope produce routing errors, which present as the agent using the right data for the wrong question.
- **Write topic scope in terms of what is *out* of scope**, not only what is in. Exclusions route more reliably than inclusions.
- **Prefer a deterministic action over a generative one wherever a number is involved.** A Flow or Apex action returning a typed result is testable and auditable. A prompt template asked to produce a figure is neither.
- **Constrain action parameters.** Enumerated metric identifiers and period grains fail loudly; free-text parameters fail quietly.
- **Give the agent an explicit escalation action.** Handoff must be a capability it can choose, not a fallback that occurs when nothing else matched.
- **Treat instructions as code.** Agent, topic and action configuration should be source-controlled and deployed through the normal release path, not edited in production.

---

## 8. Prompt templates

**The pattern.** Prompts are versioned artefacts with a fixed structure, grounded in retrieved context that carries provenance. See [`../prompts/grounded-answer-template.md`](../prompts/grounded-answer-template.md).

**How it maps here.** **Prompt Builder** provides reusable templates of several types, grounded dynamically at runtime — from record data, related data, canonical objects and insights, retrievers, and the output of Flow or Apex. Templates are managed metadata and deploy like any other component.

Guidance:

- **Ground in the narrowest sufficient source.** A template grounded in a whole related list where two fields were needed enlarges the entitlement surface and dilutes attention.
- **Carry provenance into the template.** If the grounding source does not supply dataset, certification tier and as-of, the answer cannot state them and no downstream check can verify them.
- **Review templates like code.** Two-person review, change log, and an eval run before release. A prompt change is a behaviour change to a production system.
- **Keep the response contract explicit** — citation requirement, abstention rule, no-arithmetic rule, as-of disclosure — so the post-generation checks have something concrete to verify against.
- **Version the template identifier into the audit record**, so any past answer can be tied to the instructions that produced it.

---

## 9. Trust and safety controls

**The pattern.** Controls sit around the model interaction: entitlement before retrieval, minimisation before the provider boundary, checks before the user, and a record of all of it.

**How it maps here.** The **Einstein Trust Layer** is the umbrella for these controls. The concepts most relevant to grounded agents:

| Concept | What it addresses | Practitioner note |
| --- | --- | --- |
| **Secure data retrieval** | Grounding respects the requesting user's permissions | The control that makes entitlement propagation real. Test it explicitly with a low-privilege user — do not assume it. |
| **Dynamic grounding** | Context assembled at runtime from governed sources | Grounding scope is configuration, so it is reviewable and auditable |
| **Data masking** | Sensitive values obscured before leaving the trust boundary | Masking is not entitlement. It reduces exposure at the provider; it does not decide who may ask. |
| **Zero data retention** | Provider does not retain prompts or responses for training | A contractual and architectural control; verify its scope for the specific model you use |
| **Prompt defence** | Mitigates instruction injection | Necessary, not sufficient — retrieved content is untrusted input, and injected instructions can arrive inside a document chunk |
| **Toxicity detection** | Screens generated output | Orthogonal to groundedness. Content can be entirely inoffensive and entirely wrong. |
| **Audit trail and feedback** | Interactions and user feedback captured for review | The evidence base for every audit question in [`../governance/ai-controls-mapping.md`](../governance/ai-controls-mapping.md) |

Two points worth stating plainly:

**Toxicity and groundedness are different problems.** Safety screening on generated output does not detect a fabricated figure or a stale certified value. The checks that catch those are the ones in [`../prompts/guardrail-patterns.md`](../prompts/guardrail-patterns.md), and they are yours to implement.

**Masking is a minimisation control, not an access control.** Masking a value before it crosses a provider boundary limits third-party exposure. It says nothing about whether the requesting user should have been able to trigger the retrieval. Both controls are needed and they are not substitutes.

---

## 10. Testing and evaluation

**The pattern.** Evaluation is a standing control at three levels — retrieval, answer, outcome — not a pre-launch activity.

**How it maps here.** Salesforce provides tooling for testing agents at scale against defined test cases, exercising topic selection and action invocation. Use it for what it is best at: **routing and behaviour regression** — does the agent still pick the right topic and the right action after a configuration change.

Complement it with an offline harness for **answer quality regression**, which is what [`../evaluation/`](../evaluation/) provides. The division of labour:

| Concern | Where |
| --- | --- |
| Did the agent choose the right topic and action? | Platform testing tooling |
| Did the action return the right structured result? | Unit tests on the Flow or Apex |
| Was the answer grounded, cited, numerically consistent, correctly abstaining? | Offline harness, in CI |
| Did retrieval fetch the right context in the first place? | Labelled retrieval set — **build this; it is the one most teams skip** |
| Did users act on, correct or escalate the answer? | Feedback capture and periodic human review |

Keep the answer-quality harness **outside** the platform and in your source repository. It then runs on every pull request, gates deployment, produces artefacts an auditor can read, and remains valid if the platform changes.

---

## What the platform does not give you

Honest boundaries. A capable platform removes plumbing; it does not remove governance work. Everything below remains yours regardless of vendor:

| Not provided | Why it cannot be |
| --- | --- |
| **Your metric definitions** | Only your business knows that active means ninety days |
| **Ownership and accountability** | A platform can store an owner's name; it cannot make someone accountable |
| **Certification decisions** | Fitness for purpose is a judgement, not a computation |
| **Which of two definitions the user meant** | The information exists only in your organisation |
| **Quality thresholds and their consequences** | Business risk appetite |
| **Freshness tolerances** | A business decision per metric and per question type |
| **Groundedness evaluation against your corpus** | Requires your labelled cases |
| **The decision to abstain** | Policy, encoded by you |
| **Correct match and reconciliation rules** | Domain-specific, and the highest-risk configuration in the stack |

The platform is genuinely good at what it is good at: harmonisation, identity resolution, low-latency retrieval, and wrapping model calls in controls that would take a long time to build. None of that substitutes for a certified data foundation and a semantic layer, and an agent built on a capable platform without them will be confidently wrong faster and at greater scale.

---

## Implementation sequence

Order matters. Each step depends on the one before it, and the failure mode of skipping ahead is a rebuild.

1. **Run the readiness assessment** — [`../governance/data-readiness-assessment.md`](../governance/data-readiness-assessment.md). Do not start with the platform.
2. **Decide the data space model.** Structural, hard to change later.
3. **Ingest and map to the canonical model.** Deliberately, not exhaustively. Reconcile against source.
4. **Configure and tune identity resolution.** Conservatively. Test over-matching explicitly.
5. **Register the first twenty terms and metrics** — the ones users actually ask about — with owners, grains, units and exclusions.
6. **Build metric actions** with typed parameters over insights.
7. **Design retrieval per question type.** Structured for definitions and metrics, retrievers for prose. Resist a single retriever for everything.
8. **Build one narrow agent** — one topic, one intent, a small set of actions.
9. **Wire the guardrails** — pre-retrieval gates, in-context contract, post-generation checks.
10. **Stand up evaluation before launch**, including a labelled retrieval set, and gate deployment on it.
11. **Launch to a small, named user group** with feedback capture and a working escalation path.
12. **Grow the certified surface from the resolution-failure log** — it tells you exactly what to define next, in priority order.

Steps 1 and 5 are where the accuracy comes from. Steps 2 through 4 and 6 through 9 are where the effort goes. The temptation is always to start at step 8 because it demonstrates well; agents built that way demonstrate well and then fail in front of users, and the remediation is steps 1 through 7 anyway.
