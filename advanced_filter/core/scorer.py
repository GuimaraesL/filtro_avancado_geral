from __future__ import annotations
from typing import Tuple, Dict, Any

Span = Tuple[int,int]

def score_matches(pos_hits, neg_hits, ctx_hits_by_group, cfg):
    pos_score = sum(h[1].get("weight") or cfg.scoring.default_positive_weight for h in pos_hits)
    neg_score = sum(h[1].get("weight") or cfg.scoring.default_negative_weight for h in neg_hits)
    ctx_score = 0.0
    for g, hits in ctx_hits_by_group.items():
        if hits:
            ctx_score += cfg.scoring.context_weight
    total = pos_score + ctx_score - neg_score
    details = {
        "pos_score": pos_score,
        "neg_score": neg_score,
        "ctx_score": ctx_score,
        "total": total,
    }
    return total, details
