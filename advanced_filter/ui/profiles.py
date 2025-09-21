# -*- coding: utf-8 -*-
# advanced_filter/ui/profiles.py
from __future__ import annotations
from typing import Dict, List, Optional, Any
import io
import math
import yaml

# ----------------- utilitários -----------------
def _is_nan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)

def _as_str(x, default: str = "") -> str:
    if x is None or _is_nan(x):
        return default
    try:
        return str(x)
    except Exception:
        return default

def _as_stripped(x, default: str = "") -> str:
    s = _as_str(x, default)
    return s.strip()

def _as_upper(x, default: str = "") -> str:
    return _as_stripped(x, default).upper()

def _as_float_or_none(x) -> Optional[float]:
    if x is None or _is_nan(x):
        return None
    xs = _as_stripped(x, "")
    if xs == "":
        return None
    try:
        return float(xs)
    except Exception:
        return None

def _split_multivalue(s) -> List[str]:
    """
    Divide por quebras de linha, ';' ou ',' e retorna entradas não vazias, com strip().
    Linhas iniciadas por '#' são ignoradas.
    """
    text = _as_str(s, "")
    if not text:
        return []
    out: List[str] = []
    for line in text.replace(";", "\n").replace(",", "\n").splitlines():
        t = line.strip()
        if t and not t.startswith("#"):
            out.append(t)
    return out

# ----------------- parsing de padrões/áreas -----------------
def parse_pattern_str(s) -> Dict[str, Any]:
    """
    Converte 1 linha em PatternSpec:
      pattern [| type] [| weight] [| tag]
    - aceita '::' como separador alternativo a '|'
    - type default: 'literal'
    - weight vazio -> ignora (engine assume 1.0)
    """
    raw = _as_str(s, "")
    if not raw:
        return {}
    parts = [p.strip() for p in raw.replace("::", "|").split("|")]
    parts += ["", "", "", ""]
    pattern, ptype, weight, tag = parts[:4]

    if not pattern:
        return {}

    out: Dict[str, Any] = {"pattern": pattern}
    out["type"] = ptype if ptype else "literal"

    w = _as_float_or_none(weight)
    if w is not None:
        out["weight"] = w

    tag_s = _as_stripped(tag, "")
    if tag_s:
        out["tag"] = tag_s
    return out

def parse_patterns_area(text) -> List[Dict[str, Any]]:
    """
    Converte o textarea (linhas múltiplas) em lista de PatternSpec.
    Tolera espaços, vírgulas e ';' como separadores de linha.
    """
    items: List[Dict[str, Any]] = []
    for s in _split_multivalue(text):
        d = parse_pattern_str(s)
        if d.get("pattern"):
            items.append(d)
    return items

# ----------------- parsing de contextos e regras -----------------
def parse_context_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Converte linhas (data_editor) em:
      { group: { category: str|None, patterns: [PatternSpec, ...] } }
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows or []:
        group = _as_stripped(r.get("group"), "")
        if not group:
            continue
        cat = _as_stripped(r.get("category"), "")
        patt_str = r.get("patterns")
        patt_list: List[Dict[str, Any]] = []
        for s in _split_multivalue(patt_str):
            d = parse_pattern_str(s)
            if d.get("pattern"):
                patt_list.append(d)
        out[group] = {"category": (cat or None), "patterns": patt_list}
    return out

def parse_rules_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converte linhas (data_editor) em lista de regras válidas.
    Campos: name, equation, decision, min_score, assign_category
    """
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        name = _as_stripped(r.get("name"), "")
        eq = _as_stripped(r.get("equation"), "")
        dec = _as_upper(r.get("decision"), "")
        if not name or not eq or dec not in {"INCLUI", "REVISA", "EXCLUI"}:
            continue

        row: Dict[str, Any] = {"name": name, "equation": eq, "decision": dec}

        ms = _as_float_or_none(r.get("min_score"))
        if ms is not None:
            row["min_score"] = ms

        ac = _as_stripped(r.get("assign_category"), "")
        if ac:
            row["assign_category"] = ac

        out.append(row)
    return out

# ----------------- conversões perfil <-> config YAML v2 -----------------
def profile_to_config_dict(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte o dicionário de perfil (UI) em config **v2** para o engine.
    """
    norm = (profile.get("normalization") or {})
    window = profile.get("window") or 8

    positives = parse_patterns_area(profile.get("positives_text"))
    negatives = parse_patterns_area(profile.get("negatives_text"))
    contexts  = parse_context_rows(profile.get("contexts_rows") or [])
    rules     = parse_rules_rows(profile.get("rules_rows") or [])

    return {
        "normalization": {
            "lowercase": bool(norm.get("lowercase", True)),
            "strip_accents": bool(norm.get("strip_accents", True)),
        },
        "window": int(window) if window else 8,
        "matchers": {
            "positives": positives,
            "negatives": negatives,
            "contexts":  contexts,
        },
        "rules": rules,
    }

def config_dict_to_yaml_bytes(cfg: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False).encode("utf-8")

def profile_to_yaml_bytes(profile: Dict[str, Any]) -> bytes:
    """Serializa um perfil (UI) como YAML v2 (única fonte)."""
    return config_dict_to_yaml_bytes(profile_to_config_dict(profile))

def yaml_bytes_to_profile(yaml_bytes: bytes) -> Dict[str, Any]:
    """
    Converte YAML v2 (bytes) -> perfil (UI).
    Lança erro se o YAML não possuir 'matchers'.
    """
    cfg = yaml.safe_load(io.BytesIO(yaml_bytes).read()) or {}
    if "matchers" not in cfg:
        raise ValueError("Este editor aceita apenas YAML v2 (com a chave 'matchers').")

    profile: Dict[str, Any] = {
        "name": _as_stripped(cfg.get("name"), ""),
        "normalization": {
            "lowercase": bool((cfg.get("normalization", {}) or {}).get("lowercase", True)),
            "strip_accents": bool((cfg.get("normalization", {}) or {}).get("strip_accents", True)),
        },
        "window": cfg.get("window", 8),
        "positives_text": "",
        "negatives_text": "",
        "contexts_rows": [],
        "rules_rows": [],
    }

    # reidrata positivos/negativos em formato texto (1 por linha)
    pos_lines: List[str] = []
    for p in ((cfg.get("matchers", {}) or {}).get("positives") or []):
        line = f"{_as_stripped(p.get('pattern'))} | {_as_stripped(p.get('type'),'literal')}"
        w = _as_float_or_none(p.get("weight"))
        if w is not None:
            line += f" | {w}"
        t = _as_stripped(p.get("tag"), "")
        if t:
            line += f" | {t}"
        pos_lines.append(line)
    profile["positives_text"] = "\n".join(pos_lines)

    neg_lines: List[str] = []
    for p in ((cfg.get("matchers", {}) or {}).get("negatives") or []):
        line = f"{_as_stripped(p.get('pattern'))} | {_as_stripped(p.get('type'),'literal')}"
        w = _as_float_or_none(p.get("weight"))
        if w is not None:
            line += f" | {w}"
        t = _as_stripped(p.get("tag"), "")
        if t:
            line += f" | {t}"
        neg_lines.append(line)
    profile["negatives_text"] = "\n".join(neg_lines)

    # contextos -> rows
    ctx_rows: List[Dict[str, Any]] = []
    for group, cinfo in (((cfg.get("matchers", {}) or {}).get("contexts")) or {}).items():
        cat = _as_stripped((cinfo or {}).get("category"), "")
        patt_lines: List[str] = []
        for p in ((cinfo or {}).get("patterns") or []):
            line = f"{_as_stripped(p.get('pattern'))} | {_as_stripped(p.get('type'), 'literal')}"
            w = _as_float_or_none(p.get("weight"))
            if w is not None:
                line += f" | {w}"
            t = _as_stripped(p.get('tag'), "")
            if t:
                line += f" | {t}"
            patt_lines.append(line)
        ctx_rows.append({"group": group, "category": cat, "patterns": "\n".join(patt_lines)})
    profile["contexts_rows"] = ctx_rows

    # regras -> rows
    rules_rows: List[Dict[str, Any]] = []
    for r in (cfg.get("rules") or []):
        rules_rows.append({
            "name": _as_stripped(r.get("name"), ""),
            "equation": _as_stripped(r.get("equation"), ""),
            "decision": _as_upper(r.get("decision"), "REVISA"),
            "min_score": _as_float_or_none(r.get("min_score")),
            "assign_category": _as_stripped(r.get("assign_category"), ""),
        })
    profile["rules_rows"] = rules_rows
    return profile

# ----------------- perfil default -----------------
def make_default_profile(name: str = "Novo Perfil") -> Dict[str, Any]:
    return {
        "name": name,
        "normalization": {"lowercase": True, "strip_accents": True},
        "window": 8,
        "positives_text": "luva | literal | 2.0\nalicate | literal | 1.5\nmartelo | literal | 1.0",
        "negatives_text": "moinho de martelos | phrase | 2.0",
        "contexts_rows": [
            {"group": "MAOS", "category": "Proteção das Mãos", "patterns": "mãos | literal\nmao | literal\ndedos | literal"},
        ],
        "rules_rows": [
            {
                "name": "incluir_maos_ferramenta",
                "equation": "WITHIN(8, POS(), CTX('MAOS'))",
                "decision": "INCLUI",
                "min_score": 1.0,
                "assign_category": "Segurança > Proteção das Mãos",
            },
            {
                "name": "excluir_negativos",
                "equation": "NEG()",
                "decision": "EXCLUI"
            },
            {
                "name": "revisar_padrao",
                "equation": "POS() or CTX('MAOS')",
                "decision": "REVISA"
            },
        ],
    }
