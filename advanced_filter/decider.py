from __future__ import annotations
from typing import Dict, Any
from .dsl import DSLContext, eval_equation

def apply_rules(equations, scores, ctx: DSLContext, cfg):
    for rule in equations:
        ok = eval_equation(rule["equation"], ctx)
        if ok:
            if rule.get("min_score") is not None and scores["total"] < float(rule["min_score"]):
                continue
            return {
                "rule_fired": rule["name"],
                "decision": rule["decision"],
                "category": rule.get("assign_category"),
            }
    return {
        "rule_fired": "",
        "decision": "EXCLUI",
        "category": None,
    }
