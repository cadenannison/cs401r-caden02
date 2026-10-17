# Track B Evaluation: RAG Offer Generation

**Judge model (all scores):** `us.anthropic.claude-haiku-4-5-20251001-v1:0` w/ Bedrock, with Titan Embeddings v2 for the embedding side of answer relevancy.

## Pipeline choices

- Embeddings, Titan Text Embeddings v2 (1024-dim) via Bedrock; already enabled on the account (Pre-Lab 3 check), no extra service. 
- Vector store- FAISS, in memory, cosine with inner product on normalized vectors; the corpus is 48 chunks, so OpenSearch Serverless would add cost and setup for no benefit.
- Chunking: split on markdown headings so each chunk is one policy section, with the policy ID (POL-XXX-NNN) prepended; cap about 400 tokens with about 50 tokens overlap so a rule is not cut in half. Longest chunk is 245 words, so the cap and overlap never applied: 0 of the 48 chunks have an ID suffix other than -0.
- Generation was with Claude Haiku 4.5 with the Bedrock us. inference profile, temperature 0.2; cheap and fast for a 2 to 3 sentence output. A larger generator was not tested.
- Re-ranking was none. Top 5 of 48 chunks already covers about a tenth of the corpus and a re-ranker is another model call, but retrieval does not filter by tier (the tier name is only added to the query text; a Platinum-only return chunk was retrieved for Bronze and Silver customers), so tier filtered retrieval is the first thing I would add.

## 1. Baseline (PROMPT_V1): 3 runs, 4 cases

**Raw scores:** `rag_eval.csv` (24 rows: 4 cases x 3 runs x 2 prompt versions, with `prompt_version`, `run` and `judge_model` columns). No case scored NaN, so nothing was re-run or dropped.
**Caveat:** four test cases is a tiny sample, and an LLM-judged score is an estimate, not a measurement. Run-to-run movement of 0.1 to 0.2 on a single case is normal here.

Each cell is faithfulness / answer relevancy / context recall.

| Case (tier) | Run 1 | Run 2 | Run 3 | Case mean |
|---|---|---|---|---|
| CUST-10000317 (Gold) | 0.375 / 0.569 / 1.000 | 0.429 / 0.339 / 1.000 | 0.375 / 0.362 / 1.000 | 0.393 / 0.423 / 1.000 |
| CUST-10000904 (Bronze) | 0.333 / 0.309 / 0.400 | 0.333 / 0.309 / 0.400 | 0.167 / 0.309 / 0.400 | 0.278 / 0.309 / 0.400 |
| CUST-10000122 (Platinum) | 0.400 / 0.352 / 0.333 | 0.400 / 0.352 / 0.333 | 0.600 / 0.352 / 0.333 | 0.467 / 0.352 / 0.333 |
| CUST-10000588 (Silver) | 0.857 / 0.252 / 0.500 | 0.714 / 0.272 / 0.500 | 0.714 / 0.272 / 0.500 | 0.762 / 0.265 / 0.500 |
| **Run mean** | 0.491 / 0.370 / 0.558 | 0.469 / 0.318 / 0.558 | 0.464 / 0.324 / 0.558 | |

| Metric | Mean over 3 runs | Range of run means |
|---|---|---|
| Faithfulness | 0.475 | 0.464 to 0.491 |
| Answer relevancy | 0.337 | 0.318 to 0.370 |
| Context recall | 0.558 | 0.558 (identical) |

## 2. What limits each metric

**Faithfulness (0.475).** The judge counts every claim the contexts do not support - CUST-10000904 (Bronze, 0.28) was promised "1.25x points", the Silver rate (POL-LOY-011 section 3/4), CUST-10000588 (Silver) was told "you're $15 away" from Gold (tier is trailing 12 month spend, our feature is lifetime value), and CUST-10000122 (Platinum) was offered "shop new arrivals" although policy grants early access to sales. Welcome back openers are also unsupported claims, and part of the score is judge noise (Platinum 0.40 to 0.60; Bronze 0.33 to 0.17).

**Answer relevancy (0.337).* The metric reverse generates questions from the answer, and our "question" is an instruction while the answer is marketing copy, so even a good pair scores below 1. The weakest case is CUST-10000588 (0.25 to 0.27), whose offer spends its words on Gold benefits a Silver customer does not have. CUST-10000317 swung from 0.569 to 0.339 between two runs, so the metric is noisy on a single case.

**Context recall (0.558).** Identical in every run because retrieval is deterministic, so it measures retrieval plus the reference, not generation. The lab says the ground truths contain commentary found nowhere in the corpus, which caps a full corpus judge at 0.61 to 0.67. Retrieval does not filter by tier. For CUST-10000904 (Bronze) and CUST-10000588 (Silver) the top five included `return-policy.md#1-1-extended-window-for-platinum-members-0`, a Platinum-only chunk. Gold CUST-10000317 reached 1.000; Bronze, Platinum and Silver scored 0.33 to 0.50.

## 3. The one measured change: PROMPT_V1 to PROMPT_V2

Only the system prompt changed (same model, temperature, top-k, chunks and retrieval query). V2 adds three rules. 1. the offer starts with the offer itself, with no greeting or welcome-back opener, two no validity period, deadline, multiplier, hours, count or dollar figure unless that exact figure is in the retrieved text for the customer's tier, and three never state spend gaps or progress toward a tier threshold. 

| Case | Faithfulness V1 | Faithfulness V2 | Relevancy V1 | Relevancy V2 | Recall (both) |
|---|---|---|---|---|---|
| Gold 317 | 0.393 | 0.667 (0.60 to 0.80) | 0.423 | 0.515 | 1.000 |
| Bronze 904 | 0.278 | 0.250 | 0.309 | 0.461 | 0.400 |
| Platinum 122 | 0.467 | 0.590 (0.40 to 0.80) | 0.352 | 0.325 (0.294 to 0.340) | 0.333 |
| Silver 588 | 0.762 | 0.767 (0.75 to 0.80) | 0.265 | 0.362 | 0.500 |
| **Overall mean (range of run means)** | **0.475 (0.464 to 0.491)** | **0.568 (0.550 to 0.600)** | **0.337 (0.318 to 0.370)** | **0.416 (0.410 to 0.418)** | **0.558** |

*Judgement:* V2 raised faithfulness and relevancy modestly (the run mean ranges do not overlap) but unevenly (Bronze faithfulness and Platinum relevancy fell). Offers still break V2's own rules (welcome back openers, "free returns on all orders"), so prompt rules do not enforce policy.
