# Data Readiness Assessment for Agent Grounding

> A scored assessment you can actually run in a day, before anyone builds anything. Eight dimensions, a concrete 0–4 rubric for each, a scoring sheet, and a dependency-ordered guide to what to fix first.

The purpose is not to produce a number. It is to make an honest, evidenced statement about whether a specific set of data can support a specific agent — and, where it cannot, to identify the shortest path to where it can.

## Contents

- [How to run this](#how-to-run-this)
- [Scoring conventions](#scoring-conventions)
- [Dimension 1 — Ownership and stewardship](#dimension-1--ownership-and-stewardship)
- [Dimension 2 — Definitional clarity](#dimension-2--definitional-clarity)
- [Dimension 3 — Data quality](#dimension-3--data-quality)
- [Dimension 4 — Freshness and SLA](#dimension-4--freshness-and-sla)
- [Dimension 5 — Lineage and provenance](#dimension-5--lineage-and-provenance)
- [Dimension 6 — Access control model](#dimension-6--access-control-model)
- [Dimension 7 — Documentation and metadata coverage](#dimension-7--documentation-and-metadata-coverage)
- [Dimension 8 — Historical and temporal handling](#dimension-8--historical-and-temporal-handling)
- [Scoring sheet](#scoring-sheet)
- [Hard gates](#hard-gates)
- [Interpreting the result](#interpreting-the-result)
- [What to fix first](#what-to-fix-first)
- [Reassessment](#reassessment)

---

## How to run this

**Scope it narrowly.** Assess *the data that will ground one specific agent*, not the enterprise estate. "Are we ready for AI" is unanswerable. "Can these six datasets ground an agent that answers questions about client holdings for relationship managers" is answerable in a day.

**Timebox it.** Half a day of preparation, a two-to-three hour workshop, half a day to write up. An assessment that takes six weeks will describe an estate that has already changed.

**Who is in the room.** The data owner or steward for each in-scope dataset; the engineer who actually maintains the pipelines; someone from access management; the person who wants the agent. That last one matters — the assessment is only useful if the requester hears the answer directly rather than receiving it as a document.

**Bring evidence, not opinions.** Every score should point at something: a catalogue entry, a measurement result, a lineage extract, a ticket. A score with no evidence is a 0 for [Documentation](#dimension-7--documentation-and-metadata-coverage) regardless of what anyone believes.

**Expect low scores the first time.** Most estates score 1–2 on first assessment. That is the normal starting point, not a failure — and a fully honest 1 is far more useful than an aspirational 3.

---

## Scoring conventions

| Convention | Rule |
| --- | --- |
| **Score what is true today** | Not what is planned, in flight, or true for a different domain. If it ships next quarter it scores today's reality. |
| **Score the weakest in-scope source** | An agent is as groundable as its worst grounding source. Averaging hides the one that will cause the incident. |
| **Half points are allowed** | 2.5 is a legitimate score. Precision beyond that is false. |
| **Evidence or it did not happen** | Each score cites an artefact. "The team knows this" is level 0 or 1. |
| **Different agents, different assessments** | The same data can be ready for an internal summarisation agent and not ready for a customer-facing one. |

**The general shape of the levels**, consistent across all eight dimensions:

| Level | Meaning |
| --- | --- |
| **0** | Absent. Nobody has done this. |
| **1** | Informal. It exists in people's heads or in scattered artefacts. Depends on individuals. |
| **2** | Documented. Written down somewhere findable, but not enforced or systematically maintained. |
| **3** | Managed. Systematic, maintained, and machine-readable. Sufficient for agent grounding. |
| **4** | Optimised. Automated, monitored, self-correcting, with consequences on breach. |

**Level 3 is the target.** Level 4 is worth reaching only where the consequence justifies it — it is a genuine step up in cost and should be a deliberate choice, not a default aspiration.

---

## Dimension 1 — Ownership and stewardship

*Is there a named human accountable for this data being right?*

| Level | What you would observe |
| --- | --- |
| **0** | No owner. If the data is wrong, there is a discussion about whose problem it is. Escalations go to whoever built the pipeline. |
| **1** | An owner is understood informally — usually a team, sometimes a person who left. Not written down anywhere authoritative. |
| **2** | Ownership is recorded in a catalogue or register. The named person may not know they hold it, and there is no defined obligation attached. |
| **3** | A named individual is accountable, knows it, and has accepted a defined obligation. A delegated steward handles day-to-day matters. Both are recorded, current, and reachable through a known escalation path. |
| **4** | As level 3, plus: ownership is reviewed on a cadence and on organisational change; vacancy triggers automatic escalation; owners receive quality and usage reporting for their data; a dataset without a current owner is automatically demoted out of the certified surface. |

**Evidence.** Catalogue entry with a named individual; a stewardship charter or role description; an escalation path with a tested response time; evidence the owner has acted at least once.

**Test it in ten minutes.** Pick the most important in-scope dataset. Ask three different people who owns it. Three different answers means level 1 at best. Then ask the named owner — unprompted — what their obligation is. Hesitation means level 2.

**Cheapest move up.** Level 1 → 2 is an afternoon in the catalogue. Level 2 → 3 requires a conversation in which someone actually accepts the obligation, which is a management task rather than a data task, and is the step most commonly skipped.

---

## Dimension 2 — Definitional clarity

*Does everyone mean the same thing by the same word, and is that written down in a form a machine can read?*

| Level | What you would observe |
| --- | --- |
| **0** | No glossary. Definitions live in report titles and SQL. Two teams produce different numbers for the same metric and both are confident. |
| **1** | A glossary exists — usually a spreadsheet or wiki page — with prose definitions, no owners, and no link to physical data. Frequently out of date. |
| **2** | Definitions are documented with owners and reviewed occasionally. Exclusions are inconsistently captured. Mapping to physical columns is partial or done by inspection. |
| **3** | Terms and metrics are registered as structured objects with definition, owner, grain, unit, **explicit exclusions**, physical mapping, version and status. Known conflicts between definitions are recorded. The registry is queryable by a system, not just readable by a human. |
| **4** | As level 3, plus: aliases and synonyms are registered and maintained; ambiguity is detected automatically at resolution time; definitions carry review intervals and demote automatically when lapsed; changes are versioned and notified to dependent consumers. |

**Evidence.** The registry itself; a term with populated exclusions and a physical mapping; a change log showing a definition version bump; a documented conflict between two definitions.

**Test it in twenty minutes.** Take the three terms the agent must answer about. For each, ask: where is it defined, who owns it, what does it *exclude*, and which column implements it. Then ask a second team the same question. Divergence on exclusions is the reliable early signal — inclusions rarely differ, exclusions almost always do.

**Cheapest move up.** Do not attempt the whole estate. Take the twenty terms that appear in the questions users actually ask and take those to level 3. That is a few weeks of stewardship time and it unblocks the agent.

> **This dimension has the highest leverage of the eight.** It is the one most directly responsible for confidently-different answers, and the one least fixable by anything downstream.

---

## Dimension 3 — Data quality

*Is quality measured against thresholds, with a consequence when breached?*

| Level | What you would observe |
| --- | --- |
| **0** | Not measured. Quality is assessed by whether anyone has complained recently. |
| **1** | Ad hoc checks — a pipeline null check, a reconciliation someone runs manually before month end. No thresholds, no history. |
| **2** | Quality is measured on a schedule for key datasets across recognised dimensions. Results are visible on a dashboard. No agreed thresholds, or thresholds with no consequence. |
| **3** | Measured against **agreed thresholds** with a named owner per rule. Current status is machine-readable and available at retrieval time. Breach raises an issue with an owner and a due date. History is retained for trend analysis. |
| **4** | As level 3, plus: breach **automatically demotes** the dataset out of the agent-facing surface without human intervention; quality is measured by segment as well as in aggregate; trend degradation alerts before the threshold is crossed; the measurement service is itself retrievable so the agent can answer questions about data quality honestly. |

**Evidence.** Rule definitions with thresholds and owners; measurement history; an example breach with its issue and resolution; the API or table exposing current status.

**Test it in fifteen minutes.** Ask: what is the completeness of this dataset right now? Level 3 answers with a number from a system in under a minute. Level 2 finds a dashboard. Level 1 offers to run a query. Level 0 asks what you mean by completeness. Then ask what happens if it falls below threshold — if the answer is "someone would notice", the score is 2 regardless of the measurement in place.

**Cheapest move up.** Level 2 → 3 is mostly a governance step, not an engineering one: agree thresholds with owners and attach a consequence. The measurement usually already exists.

---

## Dimension 4 — Freshness and SLA

*Do you know how old the data is, and is that visible where it matters?*

| Level | What you would observe |
| --- | --- |
| **0** | No freshness tracking. Nobody can say when a table last updated without querying it. |
| **1** | Pipeline run times are logged. Freshness is inferred from job success, which conflates "the job ran" with "the data is current". |
| **2** | Publication timestamps are recorded and visible. A documented refresh schedule exists. Event time, ingestion time and as-of are not clearly separated. |
| **3** | Event time, ingestion time, publication time and **as-of** are distinguished and available per record or per partition. A freshness SLA is declared per dataset. As-of is carried into retrieval and reaches the answer. Late or missed delivery raises an alert. |
| **4** | As level 3, plus: freshness **tolerance is declared per metric and per question type**, not per dataset; stale data is automatically excluded from grounding; restatement policy is declared and enforced; consumers are notified of late delivery before they ask. |

**Evidence.** Timestamp columns or partition metadata; declared SLAs; a missed-delivery alert and its response; a context block or answer showing as-of.

**Test it in ten minutes.** Ask what the as-of date of the current data is, and — separately — what the maximum acceptable age is *for the question the agent will answer*. Most estates answer the first and not the second. Being unable to answer the second caps this dimension at 3.

**Cheapest move up.** Separating as-of from publication time is usually a schema and documentation change rather than a re-engineering effort, and it is the single change that most improves answer honesty.

---

## Dimension 5 — Lineage and provenance

*Can you trace a value back to its source, and defend it months later?*

| Level | What you would observe |
| --- | --- |
| **0** | No lineage. Tracing a value means reading pipeline code and asking whoever wrote it. |
| **1** | Lineage exists in architecture diagrams and tribal knowledge. Accurate when drawn, drifting since. |
| **2** | Table-level lineage is captured, automatically or manually. You can see which tables feed which, but not which column came from where, nor what was transformed. |
| **3** | **Column-level** lineage is captured automatically from pipeline execution, including transformation logic. It is queryable by a system, retained for the required period, and current — it updates when pipelines change. |
| **4** | As level 3, plus: lineage extends **through the retrieval layer to the answer**, so a specific production response can be traced to specific source columns; impact analysis is automated ("which agent answers used this dataset in this window"); lineage is captured for the semantic layer and the index, not only the warehouse. |

**Evidence.** A column-level lineage extract; evidence it is generated rather than drawn; a completed trace from a value back to source; retention configuration.

**Test it in twenty minutes.** Pick a specific field the agent will surface. Ask where it comes from and what was done to it. Level 3 produces a lineage view in minutes. Level 2 names the source table but not the transformation. Level 1 finds the person who wrote the job. Then ask the harder question: *which answers given last month used this field?* Only level 4 can answer, and most organisations discover the gap here.

**Cheapest move up.** Level 2 → 3 usually means enabling column-level capture in tooling you already run. The blocker is typically that lineage was never wired for the curated layer, only for ingestion.

---

## Dimension 6 — Access control model

*Can entitlements be evaluated for a caller, before retrieval, consistently across every copy?*

| Level | What you would observe |
| --- | --- |
| **0** | Access is granted at platform or schema level. Anyone who can query can see everything in scope. |
| **1** | Access is managed per system with different models in each. Row and column restrictions exist in some places, implemented differently, and are not comparable. |
| **2** | A consistent model exists for the main platform — roles or attributes, documented, with periodic recertification. Copies (extracts, indexes, caches) are governed separately or not at all. |
| **3** | Entitlements are evaluated **for a specific caller against a specific resource, by a service, before data is returned**. The same model governs the warehouse, the semantic layer, the index and the cache. Derived data inherits the strictest input classification. Decisions are logged. |
| **4** | As level 3, plus: purpose and consent are evaluated alongside identity; entitlement decisions are traceable per interaction; negative testing with low-privilege identities runs automatically in CI; existence-disclosure behaviour is a deliberate, documented choice per sensitivity tier. |

**Evidence.** The access model documentation; the entitlement service interface; negative test results with a low-privilege user; recertification records; the index and cache access design.

**Test it in fifteen minutes.** Ask how the vector index enforces the access rules that govern the source. Silence, or "it's internal-only", is level 2 at best — the index is a copy, and a copy with a weaker access model is the copy that will leak. Then ask whether a low-privilege user has ever been tested end to end. If not, the effective score is 2 whatever the design says.

**Cheapest move up.** There is no cheap route from 2 to 3 — this is the most expensive dimension to improve and the one where shortcuts are least survivable. Plan it properly, and scope the agent to a sensitivity tier the current model genuinely supports rather than deferring the problem.

---

## Dimension 7 — Documentation and metadata coverage

*Is there enough machine-readable metadata for a system — not just a person — to make decisions about this data?*

| Level | What you would observe |
| --- | --- |
| **0** | No catalogue. Discovery is by asking colleagues. |
| **1** | A catalogue exists with partial, stale coverage. Populated once during a project and not since. Table descriptions like "customer data". |
| **2** | Key datasets are catalogued with descriptions, owners and classifications. Column-level documentation is patchy. Updates are manual and lag reality. |
| **3** | In-scope datasets have complete, current, **machine-readable** metadata: description, owner, classification, certification tier, quality status, freshness SLA, permitted purposes. Technical metadata is harvested automatically; business metadata is maintained by stewards. Coverage is measured. |
| **4** | As level 3, plus: metadata is a **runtime dependency**, queried by retrieval to make certification, freshness and entitlement decisions; coverage and staleness are monitored with owners accountable; undocumented datasets cannot enter the grounding surface at all. |

**Evidence.** Catalogue coverage metrics for the in-scope datasets; a fully populated entry; the API retrieval uses; evidence of maintenance in the last quarter.

**Test it in ten minutes.** Pull the catalogue entry for one in-scope dataset. Is certification tier there? Freshness SLA? Permitted purposes? Quality status? If a human can read the entry but a retrieval service cannot query those fields, the score is 2 — level 3 is specifically about machine-readability.

**Cheapest move up.** Prioritise ruthlessly by scope. Complete metadata for six datasets beats 40% coverage across four hundred, and it is what actually unblocks the build.

---

## Dimension 8 — Historical and temporal handling

*Can you answer a question about the past correctly, and explain why an answer changed?*

| Level | What you would observe |
| --- | --- |
| **0** | Current state only. History is overwritten. "What was it in March" is unanswerable. |
| **1** | History exists in backups or snapshots not designed for query. Reconstructing a past state is a project. |
| **2** | History is retained and queryable for key datasets. Slowly-changing dimensions are handled inconsistently — some attributes versioned, some overwritten, no documented rule. |
| **3** | Temporal handling is explicit and documented: which attributes are versioned, effective-dating on reference data, a stated restatement policy. Point-in-time queries are supported and correct. Definition changes are recorded with their effective dates. |
| **4** | As level 3, plus: **bitemporal** where the domain requires it, separating "as at" from "as known at"; definition version is bound to the data so a historical answer uses the definition in force at the time; the agent can explain why the same question returns a different answer than it did last quarter. |

**Evidence.** Effective-dating on reference tables; a documented restatement policy; a point-in-time query returning a defensible historical value; a definition change log with effective dates.

**Test it in fifteen minutes.** Ask for the value of an in-scope metric as at a date six months ago, then ask whether that value could have changed since it was first published, and how you would know. Level 3 answers both. Level 2 answers the first. Then ask the killer question: *if the definition changed in that period, which definition does the historical figure use?* Anything below level 4 typically cannot say — which is exactly how an agent produces a trend that is an artefact of a definition change.

**Cheapest move up.** Documenting the restatement policy costs a conversation and prevents a class of unexplainable discrepancy. Do that before investing in bitemporal modelling, which is expensive and only justified in specific domains.

---

## Scoring sheet

Copy this into the assessment record. Weights reflect impact on agent accuracy and are a sensible default — adjust deliberately and record why.

| # | Dimension | Weight | Score (0–4) | Weighted | Evidence reference | Owner | Gap to 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Ownership and stewardship | 1.5 | | | | | |
| 2 | Definitional clarity | 2.0 | | | | | |
| 3 | Data quality | 1.5 | | | | | |
| 4 | Freshness and SLA | 1.0 | | | | | |
| 5 | Lineage and provenance | 1.0 | | | | | |
| 6 | Access control model | 2.0 | | | | | |
| 7 | Documentation and metadata coverage | 1.0 | | | | | |
| 8 | Historical and temporal handling | 1.0 | | | | | |
| | **Total** | **11.0** | | **/ 44** | | | |

**Readiness score** = weighted total ÷ 44, expressed as a percentage.

Why definitional clarity and access control carry the highest weight: definitional clarity is the direct cause of the confidently-different-answers failure and nothing downstream can compensate for it, and access control failures are the only ones on this list that are potentially unrecoverable. The others degrade answer quality; those two produce incidents.

---

## Hard gates

Independent of the total. A high average must not disguise a disqualifying weakness.

| Gate | Threshold | Consequence |
| --- | --- | --- |
| **Ownership** below 2 | No accountable owner | **Stop.** Nothing else is meaningful without someone accountable. |
| **Access control** below 3 for anything beyond public data | Entitlements not evaluable pre-retrieval | **Stop** for user-facing. Sandbox only, on non-sensitive data. |
| **Definitional clarity** below 2 for any term the agent must answer about | Definitions not documented | **Stop** for that scope. Define first; it is measured in weeks. |
| **Data quality** below 2 | Not measured | **Stop** for decision-support. Quality cannot be asserted. |
| **Freshness** below 2 | As-of unknown | **Stop** for any current-state question. Definitional questions may proceed. |
| Any dimension at **0** | Absent | **Stop.** Fix before scoping the agent at all. |

A gate is not a veto on the idea, only on the current scope. The usual and correct response is to **narrow the agent** — fewer datasets, fewer question types, a lower-consequence audience — until the in-scope data clears the gates.

---

## Interpreting the result

| Readiness | Band | What it means |
| --- | --- | --- |
| **80–100%** | Ready | Build. Focus effort on evaluation and monitoring rather than more foundation work. |
| **60–79%** | Ready with conditions | Build a narrow first agent on the strongest subset. Fix the two lowest dimensions in parallel with a hard date. |
| **40–59%** | Foundation first | An agent built now will be demonstrable and not trustworthy. Three to six months of focused foundation work, then reassess. Build a proof of concept on synthetic data meanwhile if momentum needs protecting. |
| **20–39%** | Not ready | The agent is not the problem to solve. Ownership and definitions first. Do not let a deadline convert this into a build. |
| **0–19%** | Start with governance | No data governance capability to build on. This is an eighteen-month programme, and framing it as an AI project will fail on both fronts. |

**A caution on the 40–59% band.** This is where the most damage is done, because the data is good enough to produce impressive demonstrations and not good enough to be trusted in production. The demonstration creates commitment; the production failure arrives months later and is attributed to the technology rather than to the foundation. If you are in this band, be explicit with stakeholders about the distinction between a demonstration and a system.

---

## What to fix first

Fix in dependency order. Later dimensions genuinely depend on earlier ones, and working out of order wastes effort.

```
1. Ownership          -> nothing else is maintainable without an accountable human
2. Documentation      -> ownership needs somewhere authoritative to live
3. Definitional       -> definitions need owners and a home
   clarity
4. Data quality       -> thresholds need owners to agree them and definitions to measure against
5. Freshness          -> SLAs need owners and a measurement capability
6. Lineage            -> most valuable once there are definitions to trace to
7. Temporal handling  -> refines correctness once the basics hold
8. Access control     -> runs in PARALLEL from day one; long lead time, hard dependency
```

**Access control is the exception to the sequence.** It has the longest lead time, the hardest dependencies on other teams, and it is a hard gate. Start it immediately and in parallel; do not schedule it after lineage.

### Sequenced first moves

| Order | Action | Typical effort | Unblocks |
| --- | --- | --- | --- |
| 1 | Name an accountable owner per in-scope dataset and get explicit acceptance | Days | Everything |
| 2 | Complete catalogue entries for in-scope datasets, machine-readable | 1–2 weeks | Retrieval-time decisions |
| 3 | Register the 20 terms users actually ask about, with exclusions and mappings | 2–4 weeks | The largest accuracy gain available |
| 4 | Agree quality thresholds with owners, attach a consequence | 1–2 weeks | Certification |
| 5 | Separate as-of from publication time; declare freshness tolerances | 1–2 weeks | Honest current-state answers |
| 6 | Enable column-level lineage on the curated layer | 2–6 weeks | Defensibility |
| 7 | Document the restatement policy | Days | Explainable change |
| — | *In parallel:* entitlement evaluation before retrieval, consistent across index and cache | 1–2 quarters | User-facing deployment |

**Item 3 is where the accuracy is.** If only one thing gets funded, fund that — and scope it to the terms users actually ask about rather than the terms that exist.

---

## Reassessment

| Trigger | Action |
| --- | --- |
| Before each new agent | Full assessment, scoped to that agent's data |
| Quarterly while an agent is live | Dimensions 3, 4 and 7 — the ones that decay |
| On material change to a grounding source | Reassess dimensions 2, 3, 5 |
| On an accuracy incident | Reassess fully; the failing dimension is usually one that was scored optimistically |
| Annually | Full reassessment for all live agents |

Keep every assessment. The trend across assessments is more informative than any single score, and it is the most credible evidence available that the governance investment is working — which is, in most organisations, the argument that has to be won repeatedly.

Two habits worth building:

**Record the evidence reference, not just the score.** A year later nobody remembers why dimension 5 was a 2, and the next assessment either repeats the work or copies the number forward without checking.

**Score honestly even when it is inconvenient.** The assessment's only value is as an input to a decision. An assessment written to justify a decision already taken costs the effort of running it and returns nothing.
