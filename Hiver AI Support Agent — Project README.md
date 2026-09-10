# Hiver AI Support Agent

## 1. Project Overview

This project is an AI-powered customer support agent built for the Hiver SDE Intern Open Challenge.

The system is designed around real customer-support conversations between customers and brands on Twitter. The goal is to select one brand from the dataset and build an end-to-end support agent that can:

1. Understand the customer's intent.
2. Retrieve relevant historical support conversations.
3. Generate a response grounded in how the brand historically handled similar issues.
4. Decide whether the request can be handled automatically or should be escalated to a human.
5. Evaluate the quality and reliability of every stage of the system.

The central principle of the project is:

> Building the AI system is only half of the problem. The system must also provide credible evidence that its outputs are reliable.

The evaluation system is therefore treated as a first-class component rather than an afterthought.

---

# 2. Problem Statement

Hiver provides a real-world customer-support dataset containing approximately three million tweets and multi-turn conversations between customers and brands.

The dataset is noisy, contains incomplete conversations, and represents multiple brands.

For this project, one brand will be selected and used to build a specialized AI support agent.

The system must solve three core problems:

### Intent Classification

Determine what the customer is trying to accomplish.

Example:

```text
Customer:
"I've been waiting five days for my refund."

Intent:
refund_status
```

### Grounded Response Generation

Generate a response using historical conversations from the selected brand as evidence.

The response should reflect how the brand has historically resolved similar issues rather than relying solely on generic LLM knowledge.

### Human Escalation

Determine whether the AI should respond automatically or whether the conversation should be transferred to a human agent.

Example:

```text
Customer:
"My account was hacked and someone transferred money."

Decision:
ESCALATE

Reason:
Potential account compromise and financial loss require human intervention.
```

---

# 3. Project Goals

The project focuses on building a reliable and measurable AI support pipeline.

The primary goals are:

- Build a working end-to-end support agent.
- Discover a practical intent taxonomy from real support data.
- Use historical conversations as retrieval evidence.
- Generate grounded responses.
- Make explicit AI-vs-human decisions.
- Provide a reason for every escalation decision.
- Build a manually labelled golden evaluation dataset.
- Evaluate intent classification independently.
- Evaluate retrieval quality.
- Evaluate generated response quality.
- Evaluate escalation decisions.
- Validate the LLM-as-a-judge against human evaluation.
- Perform detailed failure analysis.
- Establish meaningful baselines.
- Document important engineering decisions.

---

# 4. What the System Does

The complete system follows this flow:

```text
Customer Message
       |
       v
Intent Classification
       |
       v
Intent + Confidence
       |
       v
Historical Conversation Retrieval
       |
       v
Evidence Validation
       |
       v
LLM Response Generation
       |
       v
Risk / Decision Engine
       |
       +----------------------+
       |                      |
       v                      v
   AUTO-HANDLE             ESCALATE
       |                      |
       v                      v
   AI Response           Human Agent
       |
       v
Evaluation
```

The evaluation layer operates around the complete pipeline rather than evaluating only the final decision.

---

# 5. High-Level Architecture

```text
                         CUSTOMER MESSAGE
                                |
                                v
                  +--------------------------+
                  |    Intent Classifier     |
                  |                          |
                  | NLP / ML / LLM based     |
                  +------------+-------------+
                               |
                    Intent + Confidence
                               |
                               v
                  +--------------------------+
                  |      RAG Retrieval       |
                  |                          |
                  | Historical conversations |
                  +------------+-------------+
                               |
                      Retrieved Evidence
                               |
                               v
                  +--------------------------+
                  |   Evidence Validation    |
                  |                          |
                  | Retrieval confidence     |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  |   LLM Response Generator |
                  |                          |
                  | Grounded support reply   |
                  +------------+-------------+
                               |
                        Draft Response
                               |
                               v
                  +--------------------------+
                  |     Decision Engine      |
                  |                          |
                  | AUTO-HANDLE / ESCALATE   |
                  +------------+-------------+
                               |
                  +------------+------------+
                  |                         |
                  v                         v
              AI RESPONSE              HUMAN AGENT
                                          |
                                          v
                              +--------------------------+
                              |     EVALUATION ENGINE    |
                              |                          |
                              | Intent metrics           |
                              | Retrieval metrics        |
                              | Response quality         |
                              | Decision metrics         |
                              | LLM-as-judge             |
                              | Human agreement          |
                              +--------------------------+
```

---

# 6. Component 1: Intent Classification

The first stage determines the intent of the incoming customer message.

The intent taxonomy will not simply be taken from an existing dataset. It should be derived from the selected brand's historical conversations.

Possible intents could include:

```text
refund_request
refund_status
payment_failed
payment_reversed
account_issue
card_not_received
transaction_dispute
password_issue
billing_question
general_question
account_security
```

The final taxonomy depends on the selected brand and the actual distribution of its conversations.

## Important Design Principle

The taxonomy should be:

- Small enough to classify reliably.
- Distinct enough to avoid excessive overlap.
- Meaningful for customer support.
- Supported by sufficient training and evaluation examples.

A very large taxonomy may look sophisticated but can produce poor classification quality and severe class imbalance.

---

# 7. Intent Classification Output

The classifier should ideally produce structured output:

```json
{
  "intent": "refund_status",
  "confidence": 0.94
}
```

The confidence value can later be used by the decision engine.

For example:

```text
High intent confidence
+
Strong retrieval evidence
+
Low-risk intent
=
Potential AUTO-HANDLE
```

Whereas:

```text
Low intent confidence
+
Weak retrieval evidence
+
High-risk intent
=
ESCALATE
```

---

# 8. Component 2: RAG-Based Historical Retrieval

The second stage retrieves relevant historical customer-support conversations from the selected brand.

The purpose is to ground the generated response in real historical support behavior.

The conceptual pipeline is:

```text
Customer Message
       |
       v
Embedding
       |
       v
Vector Search
       |
       v
Top-K Historical Conversations
       |
       v
Relevant Evidence
```

Instead of generating a generic response, the LLM receives relevant examples of how the brand historically handled similar situations.

---

# 9. Why RAG Is Important

A generic LLM may produce a response that sounds professional but does not accurately represent the selected brand's support practices.

Historical retrieval provides:

- Brand-specific context.
- Real examples of previous resolutions.
- Real customer language.
- Historical support patterns.
- Evidence for response generation.

The objective is not to blindly copy previous responses.

The objective is to identify relevant historical resolution patterns and generate an appropriate response based on them.

---

# 10. Retrieval Output

The retrieval layer can return something similar to:

```json
{
  "query": "My payment failed but money was deducted",
  "results": [
    {
      "conversation_id": "123",
      "similarity": 0.91,
      "customer_message": "...",
      "brand_response": "..."
    },
    {
      "conversation_id": "456",
      "similarity": 0.87,
      "customer_message": "...",
      "brand_response": "..."
    }
  ]
}
```

The system should preferably retain the source conversation identifiers so that generated responses can be traced back to their evidence.

---

# 11. Evidence Validation

An additional layer can be placed between retrieval and generation.

```text
Intent
  |
  v
RAG
  |
  v
Evidence Validation
  |
  v
LLM
```

The purpose is to determine whether the retrieved evidence is sufficiently relevant.

Potential signals include:

```text
intent_confidence
retrieval_confidence
similarity_score
number_of_relevant_examples
risk_level
```

This is important because a retrieval system can return results even when there is insufficient evidence.

The LLM should not confidently generate a response simply because the retrieval system returned documents.

---

# 12. Component 3: LLM Response Generator

The response generator receives:

- Customer message.
- Predicted intent.
- Retrieved historical examples.
- Evidence/confidence information.
- Relevant support instructions.

It then produces the final draft.

Conceptually:

```text
Customer Message
       +
Intent
       +
Historical Evidence
       +
Risk / Evidence Information
       |
       v
      LLM
       |
       v
Generated Response
```

The response should be:

- Relevant.
- Correct.
- Helpful.
- Grounded in retrieved evidence.
- Consistent with the brand's historical behavior.
- Safe.
- Appropriate for customer support.

---

# 13. Structured LLM Output

The system should preferably use structured output rather than relying on free-form text.

Example:

```json
{
  "reply": "We're sorry about the issue. If the payment failed but the amount was deducted, it may be reversed automatically. Please...",
  "evidence_used": [
    "conversation_123",
    "conversation_456"
  ]
}
```

This makes the system easier to evaluate and debug.

---

# 14. Component 4: Decision Engine

The decision engine determines whether the generated response should be sent automatically or whether the conversation should be escalated.

The two possible decisions are:

```text
AUTO-HANDLE
ESCALATE
```

The decision should not be based solely on whether the LLM generated a response.

The engine should consider:

- Intent confidence.
- Retrieval confidence.
- Risk level.
- Type of customer issue.
- Availability of historical evidence.
- Potential consequences of an incorrect response.

---

# 15. Example Decision Logic

A simplified conceptual policy could be:

```text
IF risk is HIGH
    -> ESCALATE

ELSE IF intent confidence is LOW
    -> ESCALATE

ELSE IF retrieval confidence is LOW
    -> ESCALATE

ELSE
    -> AUTO-HANDLE
```

The actual thresholds should be determined experimentally rather than arbitrarily.

---

# 16. Why Risk Matters

Not every incorrect answer has the same cost.

For example:

```text
Question:
"What are your support hours?"

Incorrect answer:
Low impact.
```

Versus:

```text
Question:
"Someone accessed my account and transferred money."

Incorrect automatic response:
Potentially serious.
```

Therefore, the decision engine should be designed to minimize dangerous false auto-handling.

A useful metric is:

```text
False Auto-Handle Rate
```

This measures cases where the system chose AUTO-HANDLE when a human should have handled the case.

This can be more important than raw decision accuracy.

---

# 17. Complete Production Pipeline

The production pipeline should look like:

```text
Input Message
      |
      v
Intent Classifier
      |
      +--> Intent
      +--> Confidence
      |
      v
RAG Retriever
      |
      +--> Historical Evidence
      +--> Retrieval Score
      |
      v
Evidence Validation
      |
      +--> Evidence Confidence
      |
      v
LLM Response Generator
      |
      +--> Draft Reply
      |
      v
Decision Engine
      |
      +----------------------+
      |                      |
      v                      v
AUTO-HANDLE              ESCALATE
      |                      |
      v                      v
Final Reply             Human Review
```

---

# 18. Evaluation Engine

Evaluation is a core part of this project.

The evaluation engine should evaluate multiple components independently.

It should not only answer:

```text
"Did the final decision match?"
```

It should answer:

```text
Did the classifier understand the customer?
Did retrieval find useful evidence?
Was the generated reply correct?
Was it grounded?
Was the reply helpful?
Was the AI/human decision appropriate?
Can the automated evaluator itself be trusted?
```

---

# 19. Golden Evaluation Set

A manually labelled golden set containing approximately:

```text
150–250 examples
```

should be created.

These examples should come from the selected brand's real conversations.

Each example should contain appropriate ground-truth labels.

For example:

```json
{
  "message": "My card hasn't arrived yet",
  "intent": "card_delivery",
  "expected_decision": "AUTO-HANDLE"
}
```

Where appropriate, the golden set can also contain a reference resolution or expected support behavior.

---

# 20. Sampling Strategy

The golden set should not simply be the first 200 rows of the dataset.

A better approach is stratified sampling.

For example:

```text
1. Discover candidate intents.
2. Estimate their frequency.
3. Sample across the major intents.
4. Include difficult and ambiguous examples.
5. Include rare but high-risk cases.
6. Manually label all selected examples.
```

The README/report should explain the sampling procedure.

---

# 21. Manual Labelling

A clear labelling policy should be defined before creating the golden set.

For example:

```text
account_security:
Customer reports unauthorized access, suspicious activity,
or potential account compromise.

refund_status:
Customer is asking about the status of money expected to be refunded.

payment_failed:
Customer reports that a payment attempt failed.

card_delivery:
Customer asks about the delivery or non-arrival of a physical card.
```

The definitions should be written down to make the evaluation reproducible.

---

# 22. Intent Evaluation

The intent classifier should be evaluated using:

- Accuracy.
- Precision.
- Recall.
- Macro F1.
- Confusion matrix.

Macro F1 is particularly useful when the intent classes are imbalanced.

Example result format:

```text
Intent Classification

Accuracy:  XX.X%
Macro F1:  XX.X%
```

Per-intent results should also be available.

---

# 23. Retrieval Evaluation

The retrieval component should also be evaluated.

Potential metrics include:

```text
Recall@K
Precision@K
MRR
```

For example:

```text
Recall@5 = XX.X%
MRR       = 0.XX
```

The evaluation should determine whether useful historical support examples are actually being retrieved.

---

# 24. Response Evaluation

Generated responses should be evaluated on multiple dimensions.

Recommended dimensions:

```text
Correctness
Groundedness
Relevance
Helpfulness
Brand Consistency
Safety
```

A five-point scale can be used:

```text
1 = Very Poor
2 = Poor
3 = Acceptable
4 = Good
5 = Excellent
```

---

# 25. LLM-as-a-Judge

An LLM can be used to automatically evaluate generated responses.

For each response, the evaluator receives:

- Customer message.
- Historical evidence.
- Generated response.
- Expected intent or reference information.

It then scores the response.

Example:

```json
{
  "correctness": 4,
  "groundedness": 5,
  "relevance": 5,
  "helpfulness": 4,
  "brand_consistency": 4,
  "safety": 5
}
```

An overall score can then be calculated.

The weighting scheme should be justified in the report.

---

# 26. Human Validation of the LLM Judge

The LLM-as-a-judge cannot simply be treated as ground truth.

A subset of responses should be evaluated manually by humans.

For example:

```text
50 generated responses

Human evaluation
        |
        +----------------+
                         |
LLM evaluation ---------+
                         |
                         v
              Agreement Analysis
```

Possible measurements include:

- Correlation.
- Rank correlation.
- Agreement on categorical ratings.
- Mean absolute difference between human and LLM scores.

Example:

```text
Human-LLM Spearman correlation = 0.XX
```

The actual result should be calculated from the experiment.

This demonstrates that the automated evaluator has been validated rather than blindly trusted.

---

# 27. Decision Engine Evaluation

The decision engine should be evaluated independently.

Useful metrics include:

```text
Decision Accuracy
Precision
Recall
F1
False Auto-Handle Rate
Escalation Recall
```

The most important distinction is between:

```text
Correct AUTO-HANDLE
Correct ESCALATE
False AUTO-HANDLE
Unnecessary ESCALATE
```

Example:

```text
                    Actual
                 Auto     Human
Pred Auto         TP       FP
Pred Escalate     FN       TN
```

The system should pay particular attention to false auto-handling because automatically answering a sensitive customer issue can be significantly worse than unnecessarily escalating a safe issue.

---

# 28. End-to-End Evaluation

The final evaluation should combine the component-level metrics into an overall picture.

For each golden example:

```text
Input
  |
  +--> Intent prediction
  |
  +--> Retrieved evidence
  |
  +--> Generated response
  |
  +--> AI/Human decision
```

The evaluator should preserve all intermediate outputs.

This allows individual failures to be traced.

---

# 29. Example Evaluation Record

```json
{
  "message": "My payment failed but money was deducted",
  "actual_intent": "payment_failed",
  "predicted_intent": "payment_failed",
  "intent_confidence": 0.94,
  "retrieved_conversations": [
    "conversation_123",
    "conversation_456"
  ],
  "retrieval_confidence": 0.88,
  "generated_response": "...",
  "decision": "AUTO-HANDLE",
  "expected_decision": "AUTO-HANDLE",
  "decision_correct": true,
  "llm_judge": {
    "correctness": 5,
    "groundedness": 5,
    "relevance": 4,
    "helpfulness": 5,
    "brand_consistency": 4,
    "safety": 5
  }
}
```

This makes every individual prediction auditable.

---

# 30. Baselines

The project must compare the proposed system against at least two baselines.

## Baseline 1: Trivial Baseline

A simple majority-class classifier.

Example:

```text
Always predict the most frequent intent.
```

This provides a minimum benchmark.

---

## Baseline 2: Simple ML Baseline

A classical NLP classifier can be used.

One practical option is:

```text
TF-IDF
   |
   v
Logistic Regression
   |
   v
Intent
```

This provides a meaningful comparison against a simple machine-learning approach.

Other simple approaches can be considered, but the baseline should remain significantly simpler than the final system.

---

# 31. Example Comparison

The final report can contain a table similar to:

```text
| System                  | Accuracy | Macro F1 |
|-------------------------|----------|----------|
| Majority Class Baseline | XX.X%    | XX.X%    |
| TF-IDF + Logistic Reg.  | XX.X%    | XX.X%    |
| Proposed System         | XX.X%    | XX.X%    |
```

These are placeholders. Actual results must be generated from the experiment.

---

# 32. Failure Analysis

The project should identify the top five failure modes.

Possible categories include:

### 1. Ambiguous messages

Example:

```text
"Still waiting."
```

The message may lack sufficient context.

### 2. Multiple intents

Example:

```text
"My payment failed and now I also can't access my account."
```

The customer may be describing multiple issues.

### 3. Very short messages

Example:

```text
"Help"
"Still no refund"
"Why?"
```

These provide insufficient context.

### 4. Rare intents

There may not be enough historical examples for unusual problems.

### 5. Incorrect retrieval

The retriever may return superficially similar but semantically incorrect conversations.

Other failure modes may be discovered during evaluation.

---

# 33. Failure Analysis Format

Each failure mode should contain:

```text
Failure Mode:
Ambiguous Customer Messages

Example:
"Still waiting."

Predicted Intent:
refund_status

Actual Intent:
unknown / account issue

Hypothesis:
The message lacks enough context and the retrieval system
overweights previous refund-related conversations.

Potential Improvement:
Use conversation history and confidence-aware escalation.
```

The report should use actual examples from the evaluation set.

---

# 34. "What Is Misleading About My Headline Number?"

This is a mandatory section of the report.

If the system achieves:

```text
87% accuracy
```

that does not automatically mean the system is reliable.

Potential reasons include:

- Class imbalance.
- Easy examples dominating the dataset.
- Rare intents performing poorly.
- Duplicate or related conversations.
- Dataset noise.
- Historical Twitter support not representing modern support traffic.
- LLM judge limitations.
- Accuracy hiding dangerous false auto-handling.
- Evaluation set not fully representing production traffic.

The report should explicitly discuss what the headline metric fails to capture.

---

# 35. Important Evaluation Principle

A high overall score is not sufficient.

For example:

```text
Overall Decision Accuracy = 95%
```

could still be problematic if:

```text
High-risk false auto-handling = 8%
```

Therefore, the evaluation should report both:

```text
Overall Performance
```

and

```text
Safety / Risk Performance
```

This provides a more realistic picture of whether the system should be trusted.

---

# 36. What the Project Is Not Trying to Build

The project should remain focused.

It does not need to become:

- A complete customer-support SaaS platform.
- A full Gmail integration.
- A production CRM.
- A complex frontend.
- A transactional banking system.
- A system capable of actually issuing refunds.
- A complete autonomous customer-support replacement.

The assignment is primarily evaluating the AI pipeline and, especially, its evaluation methodology.

A command-line interface or lightweight API is sufficient if the entire system runs reliably.

---

# 37. Reproducibility

The repository should allow the headline results to be reproduced in under 15 minutes.

The README should contain clear commands such as:

```bash
git clone <repository-url>

cd hiver-ai-support-agent

pip install -r requirements.txt

python scripts/download_data.py

python scripts/prepare_data.py

python scripts/build_index.py

python scripts/run_pipeline.py

python evaluation/evaluate.py
```

The actual commands depend on the final implementation.

The evaluation should avoid requiring the evaluator to manually configure many steps.

---

# 38. Dataset

The primary dataset is:

```text
Customer Support on Twitter
Kaggle:
thoughtvector/customer-support-on-twitter
```

The dataset contains approximately three million tweets and conversations across multiple brands.

The project should select one brand.

The repository should include either:

- The relevant dataset/subsample, where permitted.
- Or a script that downloads/fetches/generates the required dataset subset.

The README should explain:

- Dataset source.
- Selected brand.
- Number of records used.
- Filtering process.
- Cleaning process.
- Conversation reconstruction process.
- Train/evaluation split.

---

# 39. Data Processing

The raw Twitter dataset is noisy.

The preprocessing pipeline may include:

```text
Raw Tweets
    |
    v
Filter Selected Brand
    |
    v
Remove Invalid Records
    |
    v
Reconstruct Conversations
    |
    v
Identify Customer / Brand Messages
    |
    v
Normalize Text
    |
    v
Create Training / Retrieval Data
```

The exact preprocessing decisions should be documented.

---

# 40. Data Leakage Prevention

The evaluation set should not leak into the retrieval or training data.

A critical principle is:

```text
Training / Retrieval Data
          |
          X
     Golden Set
```

The same customer example should not be used as retrieval evidence when evaluating that exact example.

Otherwise, the system may appear much better than it actually is.

The report should explicitly describe how evaluation leakage was avoided.

---

# 41. Decision Log

The project should contain a decision log containing approximately 10–15 non-obvious decisions.

Example:

```text
1. Selected the brand based on sufficient conversation volume.
2. Limited the intent taxonomy to a manageable number of classes.
3. Used stratified sampling for the golden evaluation set.
4. Kept the golden set isolated from retrieval data.
5. Used a classical ML classifier as a baseline.
6. Used semantic retrieval for historical support examples.
7. Limited retrieval to top-K examples.
8. Added evidence confidence before response generation.
9. Used structured LLM output.
10. Added explicit escalation reasoning.
11. Treated high-risk issues differently from low-risk issues.
12. Evaluated false auto-handling separately.
13. Used an LLM as a response-quality judge.
14. Validated the LLM judge against human ratings.
15. Included failure analysis rather than reporting only aggregate metrics.
```

These decisions should be adapted to the actual implementation.

---

# 42. Suggested Repository Structure

A possible repository structure is:

```text
hiver-ai-support-agent/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── golden/
│
├── src/
│   ├── preprocessing/
│   │   ├── clean.py
│   │   └── conversations.py
│   │
│   ├── intent/
│   │   ├── classifier.py
│   │   └── taxonomy.py
│   │
│   ├── retrieval/
│   │   ├── index.py
│   │   └── retriever.py
│   │
│   ├── generation/
│   │   └── generator.py
│   │
│   ├── decision/
│   │   └── decision_engine.py
│   │
│   └── pipeline.py
│
├── evaluation/
│   ├── golden_set.json
│   ├── evaluate_intent.py
│   ├── evaluate_retrieval.py
│   ├── evaluate_response.py
│   ├── evaluate_decision.py
│   ├── llm_judge.py
│   └── human_agreement.py
│
├── baselines/
│   ├── majority.py
│   └── tfidf_classifier.py
│
├── scripts/
│   ├── download_data.py
│   ├── prepare_data.py
│   └── run_pipeline.py
│
├── results/
│
├── report/
│
├── requirements.txt
├── .env.example
├── README.md
└── decision_log.md
```

This is a suggested structure rather than a requirement.

---

# 43. Example End-to-End Input and Output

### Input

```text
"My payment failed but the amount was deducted from my account."
```

### Intent

```json
{
  "intent": "payment_failed",
  "confidence": 0.94
}
```

### Retrieved Evidence

```text
Conversation 123:
Customer: Payment failed but money was deducted.
Brand: ...

Conversation 456:
Customer: Failed transaction but amount deducted.
Brand: ...
```

### Generated Response

```text
We're sorry about the issue. If the payment failed but the
amount was deducted, the transaction may be reversed automatically.
Please check your transaction status, and if the amount does not
return within the expected period, contact support for further
assistance.
```

### Decision

```json
{
  "decision": "AUTO-HANDLE",
  "reason": "High-confidence intent with strong historical evidence and low-risk resolution."
}
```

---

# 44. Example Escalation

### Input

```text
"Someone hacked my account and transferred money without my permission."
```

### Intent

```text
account_security
```

### Decision

```json
{
  "decision": "ESCALATE",
  "reason": "Potential account compromise and unauthorized financial activity require human investigation."
}
```

The system may still generate a draft response for the human agent, but it should not automatically send it.

---

# 45. Recommended Final System Philosophy

The system should follow this principle:

```text
High confidence
+
Strong evidence
+
Low risk
=
AUTO-HANDLE
```

And:

```text
Low confidence
OR
Weak evidence
OR
High risk
=
ESCALATE
```

This makes the system more conservative and appropriate for customer support.

---

# 46. What Makes This Project Strong

The project is stronger if it demonstrates all of the following:

```text
Real data
    +
Meaningful intent taxonomy
    +
Historical evidence retrieval
    +
Grounded generation
    +
Risk-aware decisions
    +
Strong evaluation
    +
Human validation
    +
Failure analysis
```

The most important differentiator is not necessarily the sophistication of the LLM.

It is the ability to demonstrate:

> "Here is what the system does, here is how we measured it, here is where it fails, and here is why we believe the evaluation itself is trustworthy."

---

# 47. Assignment Deliverables

The final submission should contain:

## 1. GitHub Repository

Contains:

```text
Code
Dataset / data-generation script
Pipeline
Evaluation harness
Golden set
Baselines
README
Report
Decision log
```

## 2. Golden Evaluation Set

```text
150–250 manually labelled examples
```

with documented sampling and labelling methodology.

## 3. Evaluation Harness

Should include:

```text
Intent metrics
Retrieval metrics
Response quality metrics
Decision metrics
LLM-as-judge
Human-vs-LLM judge agreement
```

## 4. Report

Maximum six pages or an equivalent README section.

Must cover:

```text
Problem framing
Baselines
Results
Failure analysis
"What is misleading about my headline number?"
One-week improvement plan
```

## 5. Decision Log

Approximately 10–15 non-obvious engineering decisions and their reasoning.

---

# 48. Submission Process

The project should be submitted through the Hiver-provided submission form:

https://intelligent-bar-256.notion.site/39492cbf0da2800682cfc78a600a745f

The submission should include the repository URL and required report/submission information.

The assignment explicitly states that submissions should not be sent by email.

---

# 49. Time Constraint

The challenge provides:

```text
100 minutes
```

The clock starts when the challenge is started.

The primary objective should therefore be:

```text
Working system
>
Strong evaluation
>
Clear documentation
>
Additional sophistication
```

A simple system that runs end-to-end and has credible evaluation is preferable to a highly sophisticated system that is incomplete.

A frontend should not be prioritized over the core pipeline and evaluation.

---

# 50. Recommended Development Priority

During the 100-minute challenge, prioritize approximately in this order:

```text
1. Working end-to-end pipeline
2. Golden evaluation set
3. Evaluation harness
4. Intent classifier
5. Historical retrieval
6. LLM response generation
7. Decision engine
8. Baselines
9. Failure analysis
10. README/report
11. UI / additional polish
```

The exact allocation will depend on implementation speed, but the evaluation component should receive substantial attention.

---

# 51. Core Project Definition

The project can be summarized as:

```text
Customer Message
        |
        v
     INTENT
        |
        v
     EVIDENCE
        |
        v
     RESPONSE
        |
        v
      RISK
        |
        v
AI HANDLE / HUMAN ESCALATE
        |
        v
   EVALUATION
```

The central engineering idea is:

> **Understand the customer, retrieve evidence from the brand's history, generate a grounded response, make a risk-aware automation decision, and measure every stage with a trustworthy evaluation system.**

The evaluation engine is not merely a final scoring script. It is a core part of the system that determines whether the AI support agent is actually reliable enough to trust.