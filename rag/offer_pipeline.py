"""Track B RAG offer pipeline: chunk -> embed (Titan v2) -> FAISS cosine -> Haiku 4.5.

Entry point: ``rag_offer_fn(customer_context, question)`` returns
``{"answer": str, "contexts": list[str]}``. Chunk IDs of the most recent call are
available via ``last_retrieved_chunk_ids()`` or ``retrieve_chunk_ids(...)``.
"""
import hashlib
import json
import os
import re
from pathlib import Path

import boto3
import faiss
import numpy as np

REGION = "us-east-1"
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIM = 1024
GEN_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
TEMPERATURE = 0.2
TOP_K = 5

# Token budget is approximated as words / 0.75 (~1.33 tokens per English word).
MAX_TOKENS = 400
OVERLAP_TOKENS = 50
MAX_WORDS = int(MAX_TOKENS * 0.75)       # 300
OVERLAP_WORDS = int(OVERLAP_TOKENS * 0.75)  # 37

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "northstar-policy-docs"
CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "embeddings.json"

# ── Prompt ─────────────────────────────────────────────────────────────────────
#
# Tier guidelines adapted from prompt_templates/offer_generation_prompts.md
# (Template 3). Three planted errors were corrected against POL-LOY-011 s2/s4 and
# POL-SHP-007 / KB-FAQ-022:
#
#   Original (WRONG)                                     Corrected
#   1. Gold ($2,000 - $9,999.99)                         Gold ($2,000 - $4,999.99)
#   2. Platinum ($10,000+)                               Platinum ($5,000 and above)
#   3. Gold: "... free expedited shipping on orders      Removed: no tier gets free
#      over $200"                                        expedited shipping.
#
# Original block, kept for citation:
#
#   Gold ($2,000 - $9,999.99):
#   - Entitled to: 1.5x points, free standard shipping at any amount, free return
#     shipping, 24-hour early access, 2 free gear repairs per year, free expedited
#     shipping on orders over $200
#   ...
#   Platinum ($10,000+):
#
TIER_GUIDELINES = """\
## Offer Guidelines by Loyalty Tier
Tier thresholds are based on trailing 12-month spend (POL-LOY-011 section 2):

Bronze (under $500):
- Entitled to: 1x points, free standard shipping at $75+, $5 birthday reward
- NOT entitled to: free return shipping, early sale access, gear repair

Silver ($500 - $1,999.99):
- Entitled to: 1.25x points, free standard shipping at $50+, $10 birthday reward,
  12-hour early sale access
- NOT entitled to: free return shipping, gear repair

Gold ($2,000 - $4,999.99):
- Entitled to: 1.5x points, free standard shipping at any amount, free return
  shipping, 24-hour early access, 2 free gear repairs per year
- NOT entitled to: the 60-day return window (Platinum only)

Platinum ($5,000 and above):
- Entitled to: 2x points, 60-day return window, free return shipping, 48-hour
  early access, unlimited gear repair, dedicated support line, $100 annual gear credit
- Prefer recognition and exclusivity over leading with a discount percentage

Applies to every tier:
- No tier receives free expedited shipping.
- Final sale merchandise is never returnable. Do not imply otherwise.
"""

PROMPT_V1 = """\
You are a retention marketing assistant for NorthStar Retail. Write a retention \
offer of 2-3 sentences for an at-risk customer.

Rules:
- Ground every claim only in the retrieved policy text and the customer profile.
- Recommend exactly one specific product category, chosen from the customer's \
top_categories.
- Do not open with a greeting or warm-up line; begin directly with the offer.
- Do not invent terms, deadlines, discounts, codes, prices, or products.
- State tier-dependent benefits conditionally (for example "as a Gold member, you \
get...") and only if the retrieved text supports that benefit for that tier. Never \
claim a benefit of a higher tier.
- Never promise free expedited shipping or returns on final sale items.

{tier_guidelines}
## Retrieved Policy Context
{retrieved_context}
"""

# V2 = V1 plus three rules appended to the Rules list; nothing else differs.
_V2_RULES = """\
- The offer's first words must be the offer itself: no greeting, welcome-back or \
appreciation opener.
- State no validity period, deadline, multiplier, hours, count or dollar figure \
unless that exact figure appears in the retrieved policy text for the customer's tier.
- Never state spend gaps or progress toward a tier threshold; mention tier benefits \
only as "Gold members get ..." style statements and only when the retrieved text \
lists them for that tier.
"""
PROMPT_V2 = PROMPT_V1.replace("\n{tier_guidelines}", _V2_RULES + "\n{tier_guidelines}", 1)

PROMPTS = {"V1": PROMPT_V1, "V2": PROMPT_V2}


def prompt_version() -> str:
    """Selected via env var RAG_PROMPT_VERSION (V1 or V2); defaults to V2."""
    v = os.environ.get("RAG_PROMPT_VERSION", "V2").strip().upper()
    if v not in PROMPTS:
        raise ValueError(f"RAG_PROMPT_VERSION must be one of {sorted(PROMPTS)}, got {v!r}")
    return v

# ── Chunking ───────────────────────────────────────────────────────────────────

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def _doc_id(text: str, fallback: str) -> str:
    m = re.search(r"\*\*Document ID:\*\*\s*([A-Z]+-[A-Z]+-\d+)", text)
    return m.group(1) if m else fallback


def _split_words(body: str):
    words = body.split()
    if len(words) <= MAX_WORDS:
        yield body
        return
    step = MAX_WORDS - OVERLAP_WORDS
    for start in range(0, len(words), step):
        yield " ".join(words[start:start + MAX_WORDS])
        if start + MAX_WORDS >= len(words):
            break


def chunk_documents(docs_dir: Path = DOCS_DIR) -> list[dict]:
    """Split each file on markdown headings, then cap sections at ~400 tokens.

    Returns [{"id", "text", "doc_id", "file"}]. Chunk text is prefixed with
    "[<policy id>] <heading>" so the POL-XXX-NNN id travels with every chunk.
    """
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        doc_id = _doc_id(raw, path.stem)
        sections, heading, buf = [], path.stem, []
        for line in raw.splitlines():
            m = _HEADING.match(line)
            if m:
                sections.append((heading, "\n".join(buf)))
                heading, buf = m.group(2), []
            else:
                buf.append(line)
        sections.append((heading, "\n".join(buf)))

        counts: dict[str, int] = {}
        for heading, body in sections:
            body = body.strip()
            if not body or body == "---":
                continue
            slug = _slug(heading)
            for piece in _split_words(body):
                n = counts.get(slug, 0)
                counts[slug] = n + 1
                chunks.append({
                    "id": f"{path.name}#{slug}-{n}",
                    "doc_id": doc_id,
                    "file": path.name,
                    "text": f"[{doc_id}] {heading}\n{piece}",
                })
    return chunks


# ── Embeddings + index ─────────────────────────────────────────────────────────

_client = None
_runtime = None
_cache: dict | None = None
_index = None
_chunks: list[dict] | None = None
_last_ids: list[str] = []


def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    return _cache


def _embed(text: str) -> np.ndarray:
    """Titan v2 embedding (1024-d, normalized), cached on disk by text hash."""
    cache = _load_cache()
    key = hashlib.sha256(f"{EMBED_MODEL_ID}:{EMBED_DIM}:{text}".encode()).hexdigest()
    if key not in cache:
        resp = _bedrock().invoke_model(
            modelId=EMBED_MODEL_ID,
            body=json.dumps({"inputText": text, "dimensions": EMBED_DIM, "normalize": True}),
        )
        cache[key] = json.loads(resp["body"].read())["embedding"]
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
    return np.asarray(cache[key], dtype="float32")


def _build_index():
    global _index, _chunks
    if _index is None:
        _chunks = chunk_documents()
        mat = np.vstack([_embed(c["text"]) for c in _chunks])
        faiss.normalize_L2(mat)
        _index = faiss.IndexFlatIP(EMBED_DIM)  # inner product on unit vectors = cosine
        _index.add(mat)
    return _index, _chunks


def _build_query(customer_context: dict, question: str) -> str:
    tier = customer_context.get("loyalty_tier", "")
    return (f"{question} Loyalty tier {tier} benefits, points earn rate, free shipping, "
            f"return window, early access, retention offer terms")


def retrieve(customer_context: dict, question: str, k: int = TOP_K) -> list[dict]:
    index, chunks = _build_index()
    q = _embed(_build_query(customer_context, question)).reshape(1, -1).copy()
    faiss.normalize_L2(q)
    _, idx = index.search(q, k)
    return [chunks[i] for i in idx[0] if i >= 0]


def retrieve_chunk_ids(customer_context: dict, question: str, k: int = TOP_K) -> list[str]:
    return [c["id"] for c in retrieve(customer_context, question, k)]


def last_retrieved_chunk_ids() -> list[str]:
    """Chunk IDs retrieved by the most recent rag_offer_fn call."""
    return list(_last_ids)


# ── Generation ─────────────────────────────────────────────────────────────────


def _profile_line(ctx: dict) -> str:
    return (f"Customer profile: loyalty_tier={ctx.get('loyalty_tier')}; "
            f"total_lifetime_value={ctx.get('total_lifetime_value')}; "
            f"top_categories={', '.join(ctx.get('top_categories', []))}")


def rag_offer_fn(customer_context: dict, question: str) -> dict:
    global _last_ids, _runtime
    hits = retrieve(customer_context, question)
    _last_ids = [h["id"] for h in hits]
    texts = [h["text"] for h in hits]
    profile = _profile_line(customer_context)

    system = PROMPTS[prompt_version()].format(
        tier_guidelines=TIER_GUIDELINES,
        retrieved_context="\n\n".join(texts),
    )
    user = (f"{question}\n\n{profile}\n"
            f"Churn probability: {customer_context.get('churn_probability')}; "
            f"days since last purchase: {customer_context.get('days_since_last_purchase')}; "
            f"average order value: {customer_context.get('avg_order_value')}")
    resp = _bedrock().converse(
        modelId=GEN_MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"temperature": TEMPERATURE, "maxTokens": 300},
    )
    answer = resp["output"]["message"]["content"][0]["text"].strip()
    return {"answer": answer, "contexts": texts + [profile]}
