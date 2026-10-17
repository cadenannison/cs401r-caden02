**Track declaration: Track B (Offer Generation, RAG over the policy corpus).**

# Lab 3 Model Design

## 1. Why gradient boosting for churn

NorthStar has 9,999 customers, 11 tabular input features in the graded run, and a retention team that must understand why a customer is flagged. Gradient boosting fits, it handles mixed scale features and nonlinear interactions without scaling, tolerates missing values, and exposes gain based importance the team can read. A neural network has little to offer on roughly 7,000 training rows and costs interpretability. Logistic regression is the real alternative and is easier to read coefficient by coefficient. I didnt train one, so my preference for boosting is a design argument, not a measured result. I would switch to logistic regression if the retention team needed a auditable scorecard.

## 2. What the features bought

The recency only baseline scores AUC 0.7232; the full model scores 0.7820 (XGBoost 3.4.1). The lift is +0.0587 with a paired bootstrap 95% CI of [0.0408, 0.0776], which excludes zero, so the engineered features did measurable work. The lift is modest because recency is already the strongest single feature (gain about 93), so the baseline alone reaches 0.72; the frequency and basket features supply the rest.

`churn_risk_score`, a recency heuristic, added only +0.004 AUC at default settings, within noise, and hyperparameter changes moved AUC only between 0.776 and 0.782, so the features, not tuning, carried the lift. By gain, `days_since_last_purchase` leads (about 93), followed by `purchase_frequency_30d` (~67), `avg_basket_size_6m` (~53) and `purchase_frequency_180d` (~48). The category-diversity and channel-mix features that Lab 2 emphasized (`category_diversity_score`, `online_to_store_ratio`) and `customer_tenure_days` carry the least (about 13 to 15), so they look closest to decorative, though I did not run a drop-feature test.

## 3. RAG over fine-tuning, and the main risk

Policy text changes (tier thresholds, return windows). With RAG we fix a document and reindex, with no retraining, and every offer carries retrieved chunk IDs for audit. Fine tuning would put today's policy into the weights, could not cite a source, and a 48-chunk is too small to justify it.

The primary production risk is confident policy violations. I audited 42 offers generated for top-decile customers against the full policy corpus. I saw only 10 were clean, only 4 were clean without a tier caveat, and none of the 9 Gold and Platinum offers passed. The most common failure was "points never expire" (12 offers, policy says 18 months). Prompt V2 raised RAGAS faithfulness from 0.475 to 0.568 but did'nt remove the failures. I would not ship this without deterministic controls: a per-tier benefits table, tier-filtered retrieval, a post-generation claim check, and human review of early batches.

The pipeline uses the feature-store tier as given and does not verify it. That tier is derived from lifetime value, while the policy defines tier by trailing 12-month spend. Of the 10 clean offers, six sat within 20% of the Bronze/Silver floor. For one (CUST-10004453), readding spend gives Bronze instead of Silver, which would invalidate its Silver benefits.

## 4. With 10x the time or data

First, change the architecture of the offer step and let the model choose from a catalog of approved, tier offers and use the LLM only to phrase the chosen one, so the incentive and its terms cannot be made up. Second, replace the four case RAGAS check with a few hundred offers where each labeled by an automatic claim validator against structured policy and checked by a human, and track the clean rate as the primary metric.
