# -*- coding: utf-8 -*-
"""
Carregador de configuração (MODO BÁSICO ÚNICO).

Esquema esperado (YAML):
version: basic-1            # opcional (default basic-1)
normalization:
  lowercase: true
  strip_accents: true
window: 8                   # janela de proximidade (em tokens)
require_context: false      # exige contexto para decidir
negative_wins_ties: true    # em empate, negativo vence
min_pos_to_include: 1
min_neg_to_exclude: 1
positives:                  # lista de strings (palavras ou frases)
  - termo1
negatives:
  - termo2
contexts:
  - termo3
"""
from __future__ import annotations
from typing import Any, Dict, List
import yaml

# -------- Helpers --------
def _as_bool(x, default: bool) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return bool(x)
    return default

def _as_int_pos(x, default: int) -> int:
    try:
        v = int(x)
        return v if v > 0 else default
    except Exception:
        return default

def _as_int_nonneg(x, default: int) -> int:
    try:
        v = int(x)
        return v if v >= 0 else default
    except Exception:
        return default

def _as_list_str(x) -> List[str]:
    out: List[str] = []
    if isinstance(x, list):
        for item in x:
            if item is None:
                continue
            if isinstance(item, (int, float)):
                s = str(item)
            else:
                s = str(item)
            s = s.strip()
            if s:
                out.append(s)
    elif isinstance(x, str):
        s = x.strip()
        if s:
            out = [line.strip() for line in s.splitlines() if line.strip()]
    return out

# -------- Loader --------
def load_config(yaml_bytes: bytes) -> Dict[str, Any]:
    """
    Carrega bytes YAML e normaliza para o dicionário do modo básico.
    Não há suporte a versões antigas; essa é a ÚNICA fonte de verdade.
    """
    try:
        raw = yaml.safe_load(yaml_bytes.decode('utf-8')) if isinstance(yaml_bytes, (bytes, bytearray)) else {}
        if raw is None:
            raw = {}
    except Exception:
        raw = {}

    norm = raw.get('normalization') or {}
    cfg: Dict[str, Any] = {
        "version": "basic-1",
        "normalization": {
            "lowercase": _as_bool(norm.get("lowercase"), True),
            "strip_accents": _as_bool(norm.get("strip_accents"), True),
        },
        "window": _as_int_pos(raw.get("window"), 8),
        "require_context": _as_bool(raw.get("require_context"), False),
        "negative_wins_ties": _as_bool(raw.get("negative_wins_ties"), True),
        "min_pos_to_include": _as_int_pos(raw.get("min_pos_to_include"), 1),
        "min_neg_to_exclude": _as_int_pos(raw.get("min_neg_to_exclude"), 1),
        "positives": _as_list_str(raw.get("positives")),
        "negatives": _as_list_str(raw.get("negatives")),
        "contexts":  _as_list_str(raw.get("contexts")),
        # Campos opcionais
        "name": str(raw.get("name") or "").strip() or None,
        "notes": str(raw.get("notes") or "").strip() or None,
    }
    return cfg

def config_dict_to_yaml_bytes(cfg: Dict[str, Any]) -> bytes:
    """Serializa o dicionário básico para YAML."""
    serial = {
        "version": "basic-1",
        "name": cfg.get("name"),
        "notes": cfg.get("notes"),
        "normalization": {
            "lowercase": bool(cfg.get("normalization", {}).get("lowercase", True)),
            "strip_accents": bool(cfg.get("normalization", {}).get("strip_accents", True)),
        },
        "window": int(cfg.get("window", 8)),
        "require_context": bool(cfg.get("require_context", False)),
        "negative_wins_ties": bool(cfg.get("negative_wins_ties", True)),
        "min_pos_to_include": int(cfg.get("min_pos_to_include", 1)),
        "min_neg_to_exclude": int(cfg.get("min_neg_to_exclude", 1)),
        "positives": list(cfg.get("positives") or []),
        "negatives": list(cfg.get("negatives") or []),
        "contexts":  list(cfg.get("contexts") or []),
    }
    return yaml.safe_dump(serial, allow_unicode=True, sort_keys=False).encode("utf-8")

__all__ = ["load_config", "config_dict_to_yaml_bytes"]
