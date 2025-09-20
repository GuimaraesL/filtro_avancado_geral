from __future__ import annotations
from typing import Dict, Any, List, Tuple
import pandas as pd
from .config_loader import load_config
from .preprocessor import normalize
from .matcher import build_indices
from .scorer import score_matches
from .dsl import DSLContext
from .decider import apply_rules
from .auditor import make_audit_row

def _collect_spans(text: str, indices):
    pos_hits = indices["positives"].findall(text)
    neg_hits = indices["negatives"].findall(text)
    ctx_hits_by_group = {}
    for name, idx in indices["contexts"].items():
        ctx_hits_by_group[name] = idx.findall(text)
    pos_spans = [h[0] for h in pos_hits]
    neg_spans = [h[0] for h in neg_hits]
    ctx_spans = {g: [h[0] for h in hits] for g, hits in ctx_hits_by_group.items()}
    return pos_hits, neg_hits, ctx_hits_by_group, pos_spans, neg_spans, ctx_spans

def run_filter(df: pd.DataFrame, text_col: str, config_path: str):
    cfg = load_config(config_path)
    idx = build_indices(cfg)

    registros = []
    for i, row in df.iterrows():
        text = str(row[text_col])
        norm = normalize(text, lowercase=cfg.normalization.lowercase, strip_accents=cfg.normalization.strip_accents)

        pos_hits, neg_hits, ctx_hits_by_group, pos_spans, neg_spans, ctx_spans = _collect_spans(norm, idx)
        total_score, score_details = score_matches(pos_hits, neg_hits, ctx_hits_by_group, cfg)

        eqs = [{
            "name": r.name,
            "equation": r.equation,
            "min_score": r.min_score,
            "decision": r.decision,
            "assign_category": r.assign_category,
        } for r in cfg.rules]

        dsl_ctx = DSLContext(norm, pos_spans, neg_spans, ctx_spans)
        decision = apply_rules(eqs, {"total": total_score, **score_details}, dsl_ctx, cfg)
        audit = make_audit_row(decision["rule_fired"], decision["decision"], decision["category"], {
            "positives": pos_hits,
            "negatives": neg_hits,
            "contexts": {k: v for k, v in ctx_hits_by_group.items() if v},
            "score": score_details
        })

        registros.append({
            **row.to_dict(),
            "norm_text": norm,
            "score_total": total_score,
            "decision": decision["decision"],
            "categoria": decision["category"] or "",
            "rule_fired": decision["rule_fired"],
            "audit": audit["reason"],
        })

    out_df = pd.DataFrame(registros)
    incluidos = out_df[out_df["decision"]=="INCLUI"].copy()
    revisar = out_df[out_df["decision"]=="REVISA"].copy()
    excluidos = out_df[out_df["decision"]=="EXCLUI"].copy()

    return {
        "incluidos": incluidos,
        "revisar": revisar,
        "excluidos": excluidos,
        "full": out_df,
    }
