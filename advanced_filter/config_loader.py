# -*- coding: utf-8 -*-
# v2 ONLY loader — mantém o nome público "load_config" para compatibilidade
from __future__ import annotations
from typing import Any, Dict, List
import io
import yaml

# --- helpers simples ---
def _as_bool(x, default: bool) -> bool:
    return bool(x) if isinstance(x, (bool, int)) else default

def _as_int_pos(x, default: int) -> int:
    try:
        v = int(x)
        return v if v > 0 else default
    except Exception:
        return default

def _ensure_dict(x) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}

def _ensure_list(x) -> List[Any]:
    return x if isinstance(x, list) else []

def _require(cond: bool, msg: str):
    if not cond:
        raise ValueError(msg)

def _validate_pattern(p: Dict[str, Any]) -> Dict[str, Any]:
    _require("pattern" in p and isinstance(p["pattern"], str) and p["pattern"].strip(),
             "Cada matcher precisa de 'pattern' (string não vazia).")
    out: Dict[str, Any] = {
        "pattern": p["pattern"].strip(),
        "type": (p.get("type") or "literal").strip(),
    }
    if "weight" in p and p["weight"] is not None and str(p["weight"]).strip() != "":
        try:
            out["weight"] = float(p["weight"])
        except Exception:
            pass
    if "tag" in p and p["tag"] is not None and str(p["tag"]).strip() != "":
        out["tag"] = str(p["tag"]).strip()
    return out

def _validate_contexts(ctxs: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for g, body in (_ensure_dict(ctxs)).items():
        if not isinstance(g, str) or not g.strip():
            continue
        b = _ensure_dict(body)
        cat = b.get("category")
        cat = str(cat).strip() if isinstance(cat, str) else None
        pats = []
        for p in _ensure_list(b.get("patterns")):
            if isinstance(p, dict):
                pats.append(_validate_pattern(p))
        out[g] = {"category": cat, "patterns": pats}
    return out

# --- loader v2 (única fonte) ---
def load_config_v2_from_bytes(yaml_bytes: bytes) -> Dict[str, Any]:
    if not yaml_bytes:
        raise ValueError("YAML vazio.")
    data = yaml.safe_load(io.BytesIO(yaml_bytes).read()) or {}
    _require(isinstance(data, dict), "Estrutura YAML inválida.")

    _require("matchers" in data, "Config YAML deve estar em v2 (com a chave 'matchers').")
    matchers = _ensure_dict(data.get("matchers"))

    norm = _ensure_dict(data.get("normalization"))
    window = _as_int_pos(data.get("window", 8), 8)

    positives = [_validate_pattern(p) for p in _ensure_list(matchers.get("positives")) if isinstance(p, dict)]
    negatives = [_validate_pattern(p) for p in _ensure_list(matchers.get("negatives")) if isinstance(p, dict)]
    contexts  = _validate_contexts(matchers.get("contexts"))

    rules = []
    for r in _ensure_list(data.get("rules")):
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or "").strip()
        eq   = str(r.get("equation") or "").strip()
        dec  = str(r.get("decision") or "").strip().upper()
        if not name or not eq or dec not in {"INCLUI", "REVISA", "EXCLUI"}:
            continue
        rr = {"name": name, "equation": eq, "decision": dec}
        if "min_score" in r and r.get("min_score") not in (None, ""):
            try:
                rr["min_score"] = float(r["min_score"])
            except Exception:
                pass
        if "assign_category" in r and r.get("assign_category"):
            rr["assign_category"] = str(r["assign_category"]).strip()
        rules.append(rr)

    return {
        "normalization": {
            "lowercase": _as_bool(norm.get("lowercase"), True),
            "strip_accents": _as_bool(norm.get("strip_accents"), True),
        },
        "window": window,
        "matchers": {
            "positives": positives,
            "negatives": negatives,
            "contexts": contexts,
        },
        "rules": rules,
    }

# --- alias com o nome esperado pelos módulos existentes ---
def load_config(yaml_bytes: bytes) -> Dict[str, Any]:
    """Alias: mantém nome antigo, carregando SEMPRE em v2."""
    return load_config_v2_from_bytes(yaml_bytes)

# --- util para exportar YAML v2 a partir de um dict já validado ---
def config_dict_to_yaml_bytes(cfg: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False).encode("utf-8")

__all__ = ["load_config_v2_from_bytes", "load_config", "config_dict_to_yaml_bytes"]
