from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional

Span = Tuple[int,int]

def make_audit_row(rule_name: str, decision: str, category: Optional[str], matches: Dict[str, Any], extra_reason: str=""):
    reason = f"Regra: {rule_name}; Decision: {decision}"
    if category:
        reason += f"; Categoria: {category}"
    if extra_reason:
        reason += f"; Detalhes: {extra_reason}"
    return {
        "rule_fired": rule_name,
        "decision": decision,
        "category": category or "",
        "reason": reason,
        "matches": matches,
    }
