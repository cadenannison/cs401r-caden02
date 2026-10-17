# Track B — Offer Examples (model-targeted customers, PROMPT_V2)

42 offers were generated for customers in the churn model's top 10% across 2 rounds.
10 audited clean (4 outright, 6 with a tier caveat); 32 are not clean.
Every offer was audited claim by claim against the full policy docs (`northstar-policy-docs/`).

## Five examples

### Example A1 — CUST-10007999 (Silver)

**Profile:** loyalty_tier Silver · total_lifetime_value 646.04 (T-12m 646.04) · churn_probability 0.61 · days_since_last_purchase 56 · avg_order_value 58.73 · category_diversity_score 0.5 · online_to_store_ratio 0.82 · top_categories Beauty, Toys, Electronics

**Offer (verbatim):**
> Earn 1.25× points on your next Beauty purchase and enjoy free standard shipping on orders of $50 or more as a Silver member.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#2-tiers-0`, `loyalty-program-terms.md#5-promotional-offers-0`

**Why it is correct:** Silver earns 1.25× and gets free standard shipping at $50+ (LOY-011 §3, §4; SHP-007 §2), Beauty is a top category, and it makes no claim about expiry, windows or other tiers.

### Example A2 — CUST-10004300 (Silver)

**Profile:** loyalty_tier Silver · total_lifetime_value 671.13 (T-12m 671.13) · churn_probability 0.96 · days_since_last_purchase 218 · avg_order_value 111.86 · category_diversity_score 0.25 · online_to_store_ratio 0.33 · top_categories Electronics, Outdoor

**Offer (verbatim):**
> Earn 1.25x points on your next Outdoor purchase and enjoy free standard shipping on orders of $50 or more as a Silver member.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#5-promotional-offers-0`, `loyalty-program-terms.md#3-points-0`

**Why it is correct:** Silver earns 1.25× and gets free standard shipping at $50+ (LOY-011 §3, §4; SHP-007 §2), Outdoor is a top category, and it makes no claim about expiry, windows or other tiers.

### Example A3 — CUST-10008075 (Silver)

**Profile:** loyalty_tier Silver · total_lifetime_value 844.21 (T-12m 844.21) · churn_probability 0.86 · days_since_last_purchase 150 · avg_order_value 105.53 · category_diversity_score 0.5 · online_to_store_ratio 0.0 · top_categories Home, Footwear, Electronics

**Offer (verbatim):**
> Earn 1.25× points on your next Home purchase and enjoy free standard shipping on orders of $50 or more as a Silver member.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#5-promotional-offers-0`, `loyalty-program-terms.md#2-tiers-0`

**Why it is correct:** Silver earns 1.25× and gets free standard shipping at $50+ (LOY-011 §3, §4; SHP-007 §2), Home is a top category, and it makes no claim about expiry, windows or other tiers.

### Example A4 — CUST-10007974 (Bronze)

**Profile:** loyalty_tier Bronze · total_lifetime_value 135.57 (T-12m 135.57) · churn_probability 0.95 · days_since_last_purchase 245 · avg_order_value 33.89 · category_diversity_score 0.375 · online_to_store_ratio 1.0 · top_categories Outdoor, Footwear, Home

**Offer (verbatim):**
> Earn 1 point per $1 on your next Outdoor purchase and get free standard shipping when you spend $75 or more. As a Bronze member, you'll build points toward $5 rewards while enjoying the convenience of online shopping.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#3-points-0`, `return-policy.md#1-1-extended-window-for-platinum-members-0`

**Why it is correct:** Bronze earns 1 point per $1 and gets free standard shipping at $75+ (LOY-011 §3, §4; SHP-007 §2), 100 points = $5, Outdoor is a top category, and it makes no claim about expiry, windows or other tiers.

### Fifth example — CUST-10001473 (Silver): clean with a tier caveat

**Profile:** loyalty_tier Silver · total_lifetime_value 591.12 (re-summed 591.12) · churn_probability 0.62 · days_since_last_purchase 64 · avg_order_value 49.26 · category_diversity_score 0.375 · online_to_store_ratio 0.42 · top_categories Home, Electronics, Footwear

**Offer (verbatim):**
> Earn 1.25× points on your next Home purchase and enjoy free standard shipping on orders of $50 or more as a Silver member.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#5-promotional-offers-0`, `loyalty-program-terms.md#2-tiers-0`

**Why it is correct:** same two Silver claims as A1-A3 (LOY-011 §3, §4; SHP-007 §2), Home is a top category. Caveat: $91.12 above the $500 Silver floor; the data does not say whether order_value includes tax or refunds.

Tier note: six of the clean offers (CUST-10006212, CUST-10000655, CUST-10001473, CUST-10001708, CUST-10002695, CUST-10004453) sit within 20% of the Bronze/Silver floor, and for CUST-10004453 re-summing spend gives Bronze, not Silver, which would invalidate its Silver claims.

## Two failures

### Failure A — CUST-10007173 (Bronze): offers a Gold-tier multiplier

**Profile:** loyalty_tier Bronze · total_lifetime_value 192.88 (T-12m 192.88) · churn_probability 0.95 · days_since_last_purchase 225 · avg_order_value 38.58 · category_diversity_score 0.125 · online_to_store_ratio 0.6 · top_categories Footwear

**Offer (verbatim):**
> We're offering you 1.5x points on your next Footwear purchase to help you earn rewards faster on the styles you love. As a Bronze member, you'll earn 1 point per $1 spent, and with this bonus you'll get an extra 50% more points toward your next $5 reward—redeem 100 points anytime in our online store.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `loyalty-program-terms.md#3-points-0`, `return-policy.md#1-1-extended-window-for-platinum-members-0`

**Problem:** "1.5x points" is the Gold rate; Bronze earns 1× (LOY-011 §3, §4). LOY-011 §5.1 makes an offer promising a higher tier's benefit invalid.

**Proposed fix (deterministic):**
1. Inject a per-tier benefits table from the system-of-record tier, with tier-filtered retrieval, so the generator only sees that tier's row.
2. Post-generation claim validator: extract every multiplier, dollar amount and day count and reject any not allowed for the tier.
3. Incentives come only from an approved offer catalog; the model phrases the chosen item and cannot invent bonuses.

### Failure B — CUST-10000728 (Gold): "free returns on all orders"

**Profile:** loyalty_tier Gold · total_lifetime_value 3,362.70 (T-12m 3,362.70) · churn_probability 0.86 · days_since_last_purchase 159 · avg_order_value 210.17 · category_diversity_score 0.875 · online_to_store_ratio 0.31 · top_categories Toys, Footwear, Electronics

**Offer (verbatim):**
> We're offering you free return shipping on your next Footwear purchase—as a Gold member, you get free returns on all orders, so you can shop with confidence and send back anything that doesn't work without worrying about the cost.

**Retrieved chunk IDs:**
`loyalty-program-terms.md#4-tier-benefits-0`, `loyalty-program-terms.md#5-1-retention-offers-0`, `customer-faq.md#loyalty-0`, `loyalty-program-terms.md#3-points-0`, `loyalty-program-terms.md#2-3-tier-protection-0`

**Problem:** The Gold benefit is free return *shipping* on mail returns (RET-004 §6.2), not free returns of everything. Final-sale items cannot be returned (RET-004 §4), and the §3 conditions and 30-day window still apply.

**Proposed fix (deterministic):**
1. Use a fixed benefit phrase per tier ("free return shipping on mail returns") from a table; the model never rewrites it.
2. Banned-pattern validator rejects universal quantifiers near return, shipping or points terms ("all orders", "every order", "anything", "never expire").
3. Generate offers as [catalog incentive] + [fixed tier benefit lines].

## Audit of all 42

Rows 1–12 are round 1, rows 13–42 round 2. "Clean*" means clean with a tier caveat (within 20% of a threshold).

| # | Customer | Tier | Verdict | Main reason |
|---|---|---|---|---|
| 1 | CUST-10002887 | Platinum | Not clean | "60-day window on every order" overstates (RET-004 §1.1, §4). |
| 2 | CUST-10003089 | Platinum | Not clean | Points reset framed as a Platinum perk (LOY-011 §3.1). |
| 3 | CUST-10007912 | Platinum | Not clean | Invented "fresh inventory" and "upcoming sale"; welcome-back opener. |
| 4 | CUST-10000728 | Gold | Not clean | "free returns on all orders" (RET-004 §4, §6.2). Failure B. |
| 5 | CUST-10009047 | Gold | Not clean | "1.5× points on every dollar" ignores exclusions (LOY-011 §2, §3). |
| 6 | CUST-10009826 | Gold | Not clean | "every transaction" overstates scope, same as row 5. |
| 7 | CUST-10000795 | Silver | Not clean | "points never expire" (LOY-011 §3.1). |
| 8 | CUST-10006212 | Silver | Clean* | LTV +2.6% over the Silver floor. |
| 9 | CUST-10007999 | Silver | **Clean** | Example A1. |
| 10 | CUST-10004918 | Bronze | Not clean | Birthday reward tied to purchase (LOY-011 §4); banned opener. |
| 11 | CUST-10007173 | Bronze | Not clean | 1.5× points offered to Bronze (Gold rate). Failure A. |
| 12 | CUST-10009733 | Bronze | Not clean | "build toward rewards faster" implies base-rate boost (borderline). |
| 13 | CUST-10003666 | Gold | Not clean | "risk-free" returns and "every dollar" overstate (RET-004, LOY-011). |
| 14 | CUST-10005570 | Gold | Not clean | Return shipping "on all" purchases ignores final sale (RET-004 §4). |
| 15 | CUST-10009715 | Gold | Not clean | "all orders" free returns, "every dollar", invented 45-day condition. |
| 16 | CUST-10000533 | Silver | Not clean | "points never expire". |
| 17 | CUST-10000655 | Silver | Clean* | LTV +6.9% over the Silver floor. |
| 18 | CUST-10001473 | Silver | Clean* | LTV +18.2% over the Silver floor. |
| 19 | CUST-10001708 | Silver | Clean* | LTV +14.3% over the Silver floor. |
| 20 | CUST-10002310 | Silver | Not clean | "points never expire". |
| 21 | CUST-10002695 | Silver | Clean* | LTV +1.5% over the Silver floor. |
| 22 | CUST-10003012 | Silver | Not clean | "points never expire". |
| 23 | CUST-10004166 | Silver | Not clean | "every purchase" scope, birthday misframed, welcome-back opener, tier progress. |
| 24 | CUST-10004300 | Silver | **Clean** | Example A2. |
| 25 | CUST-10004453 | Silver | Clean* | LTV +1.1% over the Silver floor. |
| 26 | CUST-10006686 | Silver | Not clean | "points never expire". |
| 27 | CUST-10008075 | Silver | **Clean** | Example A3. |
| 28 | CUST-10008970 | Silver | Not clean | Invented "extra 0.25×"; 1.5× is the Gold rate (LOY-011). |
| 29 | CUST-10009640 | Silver | Not clean | "points never expire". |
| 30 | CUST-10000079 | Bronze | Not clean | 1.5× points offered to Bronze (Gold rate). |
| 31 | CUST-10000303 | Bronze | Not clean | "points never expire"; "$5 in store credit" misdescribed. |
| 32 | CUST-10002534 | Bronze | Not clean | 1.25× points offered to Bronze (Silver rate). |
| 33 | CUST-10002808 | Bronze | Not clean | 1.25× points offered to Bronze ("25% more rewards"). |
| 34 | CUST-10003758 | Bronze | Not clean | "points never expire". |
| 35 | CUST-10003784 | Bronze | Not clean | Invented "extra 0.25×" to reach the Silver rate. |
| 36 | CUST-10003793 | Bronze | Not clean | "points never expire"; "$5 in store credit". |
| 37 | CUST-10004021 | Bronze | Not clean | "points never expire". |
| 38 | CUST-10004943 | Bronze | Not clean | 1.5× points offered to Bronze (Gold rate). |
| 39 | CUST-10007974 | Bronze | **Clean** | Example A4. |
| 40 | CUST-10008131 | Bronze | Not clean | "points never expire"; "every dollar counts". |
| 41 | CUST-10009385 | Bronze | Not clean | "points never expire"; "$5 in store credit". |
| 42 | CUST-10009985 | Bronze | Not clean | "every pair" implies base-rate boost (borderline, as row 12). |
