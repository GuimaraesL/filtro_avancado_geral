# -*- coding: utf-8 -*-
# advanced_filter/ui/profiles.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import io, math
import yaml

# ----------------- utilitários robustos -----------------
def _is_nan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)

def _as_str(x, default: str = "") -> str:
    if x is None or _is_nan(x):
        return default
    s = str(x)
    return s

def _as_stripped(x, default: str = "") -> str:
    return _as_str(x, default).strip()

def _as_upper(x, default: str = "") -> str:
    return _as_str(x, default).upper().strip()

def _as_float_or_none(x):
    if x is None or _is_nan(x):
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    try:
        xs = str(x).strip()
        if xs == "":
            return None
        return float(xs.replace(",", "."))  # tolera vírgula
    except Exception:
        return None

# -------- Helpers de parsing/serialização --------
def _split_multivalue(s) -> List[str]:
    """
    Divide por quebras de linha, ponto-e-vírgula ou vírgula.
    Aceita valores não-string (converte com segurança).
    """
    text = _as_str(s, "")
    if not text:
        return []
    parts = []
    for line in text.replace(";", "\n").replace(",", "\n").splitlines():
        t = line.strip()
        if t:
            parts.append(t)
    return parts

def parse_pattern_str(s) -> Dict[str, Any]:
    """
    Converte uma linha de padrão em dict PatternSpec.
    Sintaxes aceitas (pipe ou :: como separador):
      - padrao
      - padrao | type
      - padrao | type | weight
      - padrao | type | weight | tag
    type ∈ {literal, phrase, regex}; weight = float opcional; tag = str opcional.
    Tolerante a NaN/None/numéricos.
    """
    raw = _as_str(s, "")
    if not raw:
        return {}
    parts = [p.strip() for p in raw.replace("::", "|").split("|")]
    parts += ["", "", "", ""]  # padding
    pattern, ptype, weight, tag = parts[:4]

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
    """Converte textarea (linhas) em lista de PatternSpec dicts (robusto a NaN/None)."""
    items = []
    for s in _split_multivalue(text):
        d = parse_pattern_str(s)
        if d.get("pattern"):
            items.append(d)
    return items

def parse_context_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Converte linhas do data_editor em dict de contexts:
      { group: {category: str?, patterns: [PatternSpec, ...]} }
    Espera colunas: group, category, patterns (string multivalor).
    Robusto a NaN/None.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows or []:
        group = _as_stripped(r.get("group"), "")
        if not group:
            continue
        cat = _as_stripped(r.get("category"), "")
        patt_str = r.get("patterns")  # pode ser NaN/None
        patt_list = []
        for s in _split_multivalue(patt_str):
            d = parse_pattern_str(s)
            if d.get("pattern"):
                patt_list.append(d)
        out[group] = {"category": cat or None, "patterns": patt_list}
    return out

def parse_rules_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converte linhas do data_editor em lista de regras.
    Espera colunas: name, equation, decision, min_score, assign_category
    Robusto a NaN/None; ignora linhas inválidas.
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

# -------- Perfil <-> YAML --------
def profile_to_config_dict(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte o dicionário de perfil (UI) em config YAML (dict) para o engine.
    Campos esperados no perfil:
      - name (str)
      - normalization: {lowercase: bool, strip_accents: bool}
      - window (int)   [opcional]
      - positives_text (str)
      - negatives_text (str)
      - contexts_rows (list[dict])
      - rules_rows (list[dict])
    """
    cfg: Dict[str, Any] = {}
    norm = (profile.get("normalization") or {})
    cfg["normalization"] = {
        "lowercase": bool(norm.get("lowercase", True)),
        "strip_accents": bool(norm.get("strip_accents", True)),
    }

    win = _as_float_or_none(profile.get("window"))
    if win is not None:
        try:
            cfg["window"] = int(win)
        except Exception:
            pass

    cfg["positives"] = parse_patterns_area(profile.get("positives_text"))
    cfg["negatives"] = parse_patterns_area(profile.get("negatives_text"))
    cfg["contexts"]  = parse_context_rows(profile.get("contexts_rows") or [])
    cfg["rules"]     = parse_rules_rows(profile.get("rules_rows") or [])
    return cfg

def config_dict_to_yaml_bytes(cfg: Dict[str, Any]) -> bytes:
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False).encode("utf-8")

def profile_to_yaml_bytes(profile: Dict[str, Any]) -> bytes:
    return config_dict_to_yaml_bytes(profile_to_config_dict(profile))

def yaml_bytes_to_profile(yaml_bytes: bytes) -> Dict[str, Any]:
    """
    Converte um YAML (bytes) em um dicionário de perfil (UI).
    """
    cfg = yaml.safe_load(io.BytesIO(yaml_bytes).read()) or {}
    profile: Dict[str, Any] = {
        "name": _as_stripped(cfg.get("name"), ""),
        "normalization": {
            "lowercase": bool((cfg.get("normalization", {}) or {}).get("lowercase", True)),
            "strip_accents": bool((cfg.get("normalization", {}) or {}).get("strip_accents", True)),
        },
        "window": cfg.get("window", None),
        "positives_text": "",
        "negatives_text": "",
        "contexts_rows": [],
        "rules_rows": [],
    }

    def patt_to_line(p: Dict[str, Any]) -> str:
        parts = [ _as_str(p.get("pattern"), "") ]
        ptype = _as_stripped(p.get("type"), "")
        if ptype: parts.append(ptype)
        w = _as_float_or_none(p.get("weight"))
        if w is not None: parts.append(str(w))
        tag = _as_stripped(p.get("tag"), "")
        if tag: parts.append(tag)
        return " | ".join([x for x in parts if x != ""])

    if cfg.get("positives"):
        profile["positives_text"] = "\n".join([patt_to_line(p) for p in cfg["positives"] if p])
    if cfg.get("negatives"):
        profile["negatives_text"] = "\n".join([patt_to_line(p) for p in cfg["negatives"] if p])

    ctx_rows: List[Dict[str, Any]] = []
    for g, obj in (cfg.get("contexts") or {}).items():
        lines = []
        for p in (obj or {}).get("patterns", []):
            lines.append(patt_to_line(p))
        ctx_rows.append({
            "group": _as_stripped(g, ""),
            "category": _as_stripped((obj or {}).get("category"), ""),
            "patterns": "\n".join(lines)
        })
    profile["contexts_rows"] = ctx_rows

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

# -------- Perfil inicial --------
def make_default_profile(name: str = "Novo Perfil") -> Dict[str, Any]:
    return {
        "name": name,
        "normalization": {"lowercase": True, "strip_accents": True},
        "window": 8,
        "positives_text": "luva | literal | 2.0\nalicate | literal | 1.5\nmartelo | literal | 1.0",
        "negatives_text": "contramão | phrase | 2.0\ncontra mao | phrase | 2.0\nmoinho de martelos | phrase | 2.0",
        "contexts_rows": [
            {"group": "MAOS", "category": "Proteção das Mãos", "patterns": "mãos | literal\nmao | literal\ndedos | literal"},
            {"group": "EQUIPAMENTOS_BLOQUEIO", "category": "Equipamento (Bloqueio)", "patterns": "moinho de martelos | phrase"},
        ],
        "rules_rows": [
            {
                "name": "incluir_maos_ferramenta",
                "equation": "WITHIN(8, POS(), CTX('MAOS')) and not CTX('EQUIPAMENTOS_BLOQUEIO')",
                "decision": "INCLUI",
                "min_score": 1.0,
                "assign_category": "Segurança > Proteção das Mãos",
            },
            {
                "name": "excluir_negativos",
                "equation": "NEG() or CTX('EQUIPAMENTOS_BLOQUEIO')",
                "decision": "EXCLUI"
            },
            {
                "name": "revisar_padrao",
                "equation": "POS() or CTX('MAOS')",
                "decision": "REVISA"
            },
        ],
    }
