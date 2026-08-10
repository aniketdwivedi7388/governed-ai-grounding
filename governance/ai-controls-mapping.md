# AI Controls Mapping for Grounded Agents

> Twelve control objectives, what each means when an agent is grounded in enterprise data, how it is implemented in the data layer, and the artefact an auditor will ask you to produce.

The premise of this document is that **most AI controls are data controls wearing a different label**. An organisation with a functioning data governance capability already holds the majority of the evidence an AI assurance review will ask for — ownership records, lineage, quality measurement, access models, change control. What is usually missing is the mapping: showing that the control which governs a dataset also governs the agent grounded in it.

## Contents

- [How to use this](#how-to-use-this)
- [Framework anchoring](#framework-anchoring)
- [Group A — Data foundation controls](#group-a--data-foundation-controls)
- [Group B — Answer integrity controls](#group-b--answer-integrity-controls)
- [Group C — Operational controls](#group-c--operational-controls)
- [Framework cross-reference](#framework-cross-reference)
- [The evidence pack](#the-evidence-pack)
- [AI use-case intake questionnaire](#ai-use-case-intake-questionnaire)
- [Operating cadence](#operating-cadence)

---

## How to use this

Three ways, depending on where you sit:

- **Designing an agent** — read the *implementation* column as a design checklist before build, not after.
- **Reviewing one for approval** — read the *evidence* column. If the artefact does not exist, the control is an intention.
- **Preparing for an audit or assurance review** — assemble the evidence pack. Most of it should already exist as a by-product of running the platform; anything that has to be *created* for the audit is a control that is not actually operating.

A note on proportionality: not every agent needs every control at full strength. An internal agent summarising public policy documents and a customer-facing agent quoting balances warrant very different treatment. The intake questionnaire at the end is designed to establish which you are dealing with **before** anyone argues about controls.

---

## Framework anchoring

Three reference frameworks are used, at a deliberately conceptual level. Clause numbers are omitted on purpose — they change between revisions, and citing them inaccurately is worse than not citing them.

**DAMA-DMBOK** organises data management into knowledge areas — among them Data Governance, Data Quality, Metadata Management, Data Security, Reference and Master Data, and Data Architecture. Its value here is that it names the existing capability each AI control depends on. If Metadata Management is immature, transparency controls for an agent have nothing to stand on.

**NIST AI Risk Management Framework** organises AI risk work into four functions:

| Function | In this context |
| --- | --- |
| **GOVERN** | Accountability, policy, culture, roles — who decides an agent may go live |
| **MAP** | Understanding context, purpose, and who is affected — what the agent is for and what could go wrong |
| **MEASURE** | Analysing and tracking risk — evaluation, quality measurement, monitoring |
| **MANAGE** | Acting on risk — prioritisation, treatment, response, decommissioning |

The functions are continuous and interacting, not a sequence.

**ISO/IEC 42001** specifies requirements for an AI management system — a management-system standard in the same family as ISO 9001 or ISO 27001. Its relevance is structural: it expects a documented policy, defined roles, risk and impact assessment, controls over the AI lifecycle and third parties, monitoring and measurement, internal audit, and management review driving continual improvement. Practically, it asks whether AI governance is a **standing system** or a series of one-off approvals.

The three complement rather than compete. DMBOK tells you which data capability underpins a control; the AI RMF tells you how to reason about the risk; 42001 tells you how to run the whole thing as a managed system.

---

## Group A — Data foundation controls

| Control objective | Why it matters for grounded agents | Implementation in the data layer | Evidence an auditor will ask for |
| --- | --- | --- | --- |
| **Data provenance** | An answer that cannot be traced to a source cannot be defended, corrected or reproduced. Six months later, "where did this number come from" must have an answer that is not a guess. | Column-level lineage from source through transformation to the grounding surface. Every retrieved chunk carries source, dataset, version and as-of. Citations resolve to a governed identifier, not a display name. Tool results embed a provenance reference. | Lineage extract for the datasets grounding the agent; a worked trace from a specific production answer back to source columns; the context schema showing mandatory provenance fields; sample audit records with context identifiers. |
| **Purpose limitation** | Data collected and certified for one purpose is routinely reused for grounding without anyone re-testing whether that use is lawful, consented or appropriate. Reuse is the default failure. | Declared permitted purposes on every certified dataset. Grounding surface assembled from datasets whose permitted purposes include this agent's registered purpose. Purpose recorded on the request and carried into the audit record. Consent and preference state enforced at retrieval for personal data. | Register of datasets with declared purposes; the agent's registered purpose and its approval; the mapping showing every grounding source permits it; evidence that consent state filters retrieval. |
| **Access control propagation** | The retrieval path is the most common way entitlements are bypassed, because access is enforced in the application and then quietly re-implemented — or forgotten — in the index and the cache. | Retrieval executes under the caller's identity. Entitlement evaluated **before** candidate context is fetched, never as a post-generation filter. Derived data inherits the strictest input classification. Vector indexes and caches carry the same model as the source. Per-user cache partitioning. | Architecture evidence that identity reaches the retrieval layer; negative test results with a low-privilege user showing restricted content absent from context, not merely absent from the answer; the index access model; cache partitioning design. |
| **Data minimisation and retention** | Grounding copies data into prompts, logs, caches and indexes. Each copy is a new location for sensitive data with weaker governance than the original, and a new retention obligation nobody scheduled. | Retrieve the narrowest sufficient context; cap chunk counts. Mask or tokenise sensitive attributes before any external boundary. Store context *identifiers* in audit records, not context *content*. Retention schedules applied to prompt logs, transcripts, indexes and caches as data stores in their own right. | Data flow showing every location a prompt or response is persisted; retention schedule covering each; masking configuration and evidence it operates; a sample audit record demonstrating identifiers rather than payloads. |

---

## Group B — Answer integrity controls

| Control objective | Why it matters for grounded agents | Implementation in the data layer | Evidence an auditor will ask for |
| --- | --- | --- | --- |
| **Accuracy and grounding** | The headline risk. A fluent, confident, precisely-formatted wrong answer is harder to detect than an obviously broken one and is acted upon more readily. | Certified datasets only for user-facing grounding, with a named owner and a measured quality SLA. Per-metric freshness tolerance enforced as a gate. Numbers produced by deterministic tools, never generated in prose. Abstention required when context is insufficient, stale or ambiguous. Post-generation groundedness and numeric-consistency checks. | Certification register for grounding sources; current quality measurements against thresholds; evaluation results over a labelled set with a defined pass threshold; the CI gate configuration; a sample of failures and what was done about them. |
| **Transparency and explainability** | Users calibrate trust from what the system shows them. An answer without a source, an as-of date or a certification tier invites uniform trust in output of wildly varying reliability. | Answers cite retrieved context. As-of date stated with every figure. Certification tier disclosed where below the top tier. Certified definitions reproduced verbatim rather than paraphrased. Users can reach the underlying definition and dataset. Interface makes clear they are interacting with an AI system. | The response contract in the prompt template; sample transcripts showing citations and as-of disclosure; user-facing documentation on scope and limitations; evidence of AI disclosure at the interface. |
| **Bias and fairness** | Fairness in a grounded agent is largely inherited from the data layer, not the model: coverage gaps, uneven quality across segments, and unrepresentative retrieval produce systematically worse answers for some groups. | Quality measured **by segment**, not only in aggregate, so a gap is visible. Coverage analysis over the grounding corpus. Retrieval ranking reviewed for systematic skew. Identity resolution match rates monitored by segment — under-matching concentrated in one population is a fairness issue, not just a data issue. Feedback and escalation analysed by segment. | Segment-level quality and coverage analysis; identity-resolution match-rate breakdown; impact assessment for the use case; evidence that segment-level results are reviewed by someone with authority to stop the agent. |
| **Human oversight** | Oversight that is nominal is worse than none, because it transfers accountability to a person who has no realistic ability to exercise it. | Defined escalation triggers: guardrail failure, low confidence, high-consequence topic, explicit user request. Escalation is an action the agent can take, not a fallback. Reviewers see the retrieved context and provenance, not only the answer. Review capacity sized against actual volume. Overrides captured as feedback. | Documented escalation rules with thresholds; escalation and override volumes with outcomes; the reviewer interface showing context is visible; capacity analysis; named accountable owner for the agent. |

---

## Group C — Operational controls

| Control objective | Why it matters for grounded agents | Implementation in the data layer | Evidence an auditor will ask for |
| --- | --- | --- | --- |
| **Logging and auditability** | The question is never "did an interaction occur" — it is "why did *this* answer come out". Reconstruction needs the inputs, the context, the instructions and the checks, not a transcript. | Immutable interaction records: identity and entitlements applied, question, retrieval plan, context identifiers with version and as-of, prompt template version, model and configuration identifiers, response, guardrail verdicts, escalation. Clock synchronisation and tamper evidence. Retention matched to the decision's own retention. | Log schema; a reconstruction walkthrough for a specific historical answer; retention and immutability configuration; access controls on the log estate; evidence logs are actually reviewed, not merely written. |
| **Model and prompt change management** | A prompt edit is a production behaviour change to a system people rely on. Treated as content rather than code, it ships unreviewed and unversioned, and the regression is discovered by users. | Prompts, agent configuration, topics, actions, retriever configuration and semantic definitions in source control. Two-person review. Evaluation suite runs as a merge gate. Versioned deployment with rollback. Model or model-version changes treated as changes requiring re-evaluation. Semantic definition changes trigger notification to dependent consumers. | Repository history showing review on prompt and configuration changes; CI configuration with the eval gate; evaluation results per release; rollback procedure and evidence of a test; change records for model version changes. |
| **Incident response** | AI incidents present differently: not an outage, but a stream of plausible answers that were wrong. Without detection tuned for that shape, discovery comes from a complaint. | Detection on guardrail failure rates, abstention rate shifts, quality threshold breaches, and negative feedback clustering. Defined severity model including "systematically wrong but available". Ability to disable an agent or narrow its grounding surface quickly. Ability to identify all answers affected by a bad dataset or definition — which requires the audit record above. | Incident procedure covering AI-specific failure modes; monitoring and alert configuration; a post-incident review or a documented exercise; demonstration of retrospective impact identification for a given dataset over a date range. |
| **Third-party and model risk** | Model providers, platform vendors and data suppliers each sit in the trust chain. Data leaves your boundary, and provider behaviour changes without your release cycle. | Contractual position on retention, training use and confidentiality, verified against the specific model and deployment. Masking or tokenisation before the boundary. Model and version pinned and recorded; provider-driven changes trigger re-evaluation. Supplier data carries its own certification and licensing terms into the grounding surface. | Contracts and data processing terms; the register of models and versions in use with approval records; evidence masking operates before egress; re-evaluation results after a provider change; supplier data licensing records. |

---

## Framework cross-reference

Which capability each control depends on, which AI RMF function it primarily serves, and the ISO/IEC 42001 theme it evidences.

| Control objective | Primary DMBOK knowledge areas | AI RMF function | ISO/IEC 42001 theme |
| --- | --- | --- | --- |
| Data provenance | Metadata Management; Data Architecture | MAP, MEASURE | Documentation; lifecycle management |
| Purpose limitation | Data Governance; Data Security | GOVERN, MAP | AI policy; data management for AI |
| Access control propagation | Data Security; Reference and Master Data | GOVERN, MANAGE | Operational controls; roles and responsibilities |
| Data minimisation and retention | Data Security; Data Storage and Operations | GOVERN, MANAGE | Data management for AI; lifecycle |
| Accuracy and grounding | Data Quality; Metadata Management | MEASURE | Performance evaluation; monitoring and measurement |
| Transparency and explainability | Metadata Management; Data Governance | MAP, MEASURE | Documentation; information for interested parties |
| Bias and fairness | Data Quality; Reference and Master Data | MAP, MEASURE | Impact assessment; risk treatment |
| Human oversight | Data Governance | GOVERN, MANAGE | Roles and responsibilities; operational controls |
| Logging and auditability | Metadata Management; Data Storage and Operations | MEASURE, MANAGE | Documented information; internal audit |
| Model and prompt change management | Data Governance; Data Architecture | GOVERN, MANAGE | Lifecycle management; change control |
| Incident response | Data Governance; Data Quality | MANAGE | Incident management; continual improvement |
| Third-party and model risk | Data Governance; Data Security | GOVERN, MANAGE | Supplier and third-party relationships |

**Reading the pattern:** ten of twelve controls anchor to Data Governance, Metadata Management, Data Quality or Data Security. That is the argument for placing agent assurance inside the data governance function rather than standing up a parallel one — the capabilities, the people and most of the evidence are already there.

---

## The evidence pack

What to assemble before a review. If an item must be *created* for the review, treat that as a finding in itself.

**Design artefacts**
- [ ] Registered purpose, scope, and named accountable owner for the agent
- [ ] Architecture description showing where each control is enforced
- [ ] Grounding surface inventory: every dataset, retriever and tool the agent can reach
- [ ] Certification status and named owner for each grounding source
- [ ] Data flow showing every location prompts and responses are persisted

**Operating artefacts**
- [ ] Current quality measurements against thresholds for grounding sources
- [ ] Latest evaluation results with the pass threshold and the CI gate configuration
- [ ] Escalation and override volumes with outcomes
- [ ] Guardrail failure rates and trend
- [ ] Feedback summary, including segment-level breakdown

**Change artefacts**
- [ ] Change history for prompts, agent configuration and semantic definitions
- [ ] Evaluation results per release
- [ ] Register of models and versions in use, with approvals
- [ ] Records of definition changes and consumer notification

**Assurance artefacts**
- [ ] Impact assessment for the use case
- [ ] Negative access test results with a low-privilege user
- [ ] A reconstruction walkthrough for one specific historical answer
- [ ] Incident procedure and either a real post-incident review or a documented exercise
- [ ] Third-party terms covering retention and training use

---

## AI use-case intake questionnaire

Questions a governance forum should ask **before** approving an agent. They are ordered to fail fast: a use case that cannot answer section 1 does not need sections 4 through 8 yet.

Answers should be written down. The exercise of writing them is most of the value, and the document becomes the impact assessment.

### 1. Purpose and consequence

1. What decision or task does this agent support, and who acts on its output?
2. What happens if it is confidently wrong? Give a concrete worst realistic case, not a category.
3. Is the user able to detect a wrong answer? If not, what compensating control exists?
4. Is the output customer-facing, or does a professional review it before it leaves?
5. Is this a regulated process, and does any specific obligation attach to the output?
6. What is the intended scope, and — more usefully — what is explicitly out of scope?

### 2. Data foundation

7. Which datasets will ground this agent? List them.
8. Is each certified? If any is not, on what basis is its use acceptable?
9. Who is the named accountable owner of each? Do they know about this use?
10. What is the measured quality of each against its threshold *today*?
11. What is the freshness SLA, and what freshness does this use case actually require?
12. Does the declared purpose of each dataset cover this use?
13. Is any of it personal data, special category, or subject to consent or cross-border restriction?

### 3. Definitions and semantics

14. Which business terms and metrics must the agent resolve?
15. Is each defined in the glossary or metric registry, with an owner?
16. Do any of them have more than one definition in use across the organisation?
17. How will the agent behave when a term is ambiguous?
18. Who arbitrates a definitional dispute, and how quickly?

### 4. Access and entitlement

19. Whose entitlements apply at retrieval — the caller's, or a service identity's?
20. Where is the entitlement check performed relative to context assembly?
21. How are entitlements enforced in the vector index and the cache?
22. Has a negative test been run with a low-privilege user? What were the results?
23. Can the existence of restricted data be inferred from a refusal, and is that acceptable here?

### 5. Grounding and generation

24. Which questions are structured lookups, which are computations, and which need prose retrieval?
25. How are numbers produced — deterministic tool, or generation?
26. What does the agent do when retrieved context is insufficient?
27. Are certified definitions reproduced verbatim or paraphrased?
28. What provenance appears in the answer the user sees?

### 6. Controls and oversight

29. Which pre-retrieval gates are implemented, and in what order?
30. Which post-generation checks run, and what happens when one fails?
31. What triggers escalation to a human, and does that human see the retrieved context?
32. Is review capacity sized against expected volume?
33. Who can disable this agent, and how fast?

### 7. Evaluation

34. Is there a labelled evaluation set? How many cases, and who wrote them?
35. Does it include cases the agent should refuse, and ambiguous cases?
36. Is there a **retrieval** evaluation set, separate from answer evaluation?
37. What is the pass threshold, on what basis was it chosen, and what happens below it?
38. Does evaluation gate deployment, or is it advisory?
39. How will accuracy be monitored after launch, and by whom?

### 8. Lifecycle

40. Who owns this agent operationally once it is live?
41. How are prompt and configuration changes reviewed and deployed?
42. What triggers re-evaluation — model change, definition change, dataset change?
43. What is the review cadence, and what are the criteria for decommissioning?
44. How would you identify every answer affected by a dataset found to be wrong?

### Scoring the intake

| Signal | Interpretation |
| --- | --- |
| Cannot list grounding datasets, or several are uncertified | **Not ready.** Route to the readiness assessment. |
| Cannot name accountable owners | **Not ready.** Ownership precedes everything else. |
| Numbers produced by generation rather than tools | **Redesign required** before approval. |
| Entitlement filtered after retrieval | **Redesign required.** Not a residual risk to accept. |
| No evaluation set, or no abstention cases | **Conditional at best**, with a hard date. |
| No retrieval evaluation | **Common gap.** Approve with a commitment and a date. |
| All answerable, consequences bounded, controls proportionate | **Approve**, with a review date and named owner. |

---

## Operating cadence

Controls that are not exercised on a schedule are documentation.

| Activity | Cadence | Accountable |
| --- | --- | --- |
| Evaluation suite on every change | Per pull request | Engineering |
| Guardrail failure and abstention rate review | Weekly | Agent operational owner |
| Quality threshold review for grounding sources | Weekly or per measurement run | Data stewardship |
| Escalation and override review | Monthly | Agent owner with governance |
| Feedback review including segment breakdown | Monthly | Agent owner |
| Definition and certification review for lapsing terms | Monthly | Term owners |
| Access recertification for the grounding surface | Quarterly | Data owners |
| Full control review against this mapping | Semi-annually | Governance forum |
| Impact assessment refresh | Annually, or on material change | Agent owner |
| Third-party and model register review | Annually, or on provider change | Vendor management with governance |

Two closing observations.

**Most of these already exist.** Access recertification, quality review and definition stewardship are standard data governance activities. The AI-specific additions are the evaluation gate, the guardrail metrics and the abstention-rate review. Extending existing forums is faster, cheaper and more durable than creating a parallel AI governance structure that will struggle for attention.

**Abstention rate is the most underrated metric on this list.** A falling abstention rate looks like improvement and is frequently the opposite — an agent that has quietly started answering questions it should refuse. Track it, alert on movement in either direction, and require an explanation.
