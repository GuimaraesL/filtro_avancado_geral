# -*- coding: utf-8 -*-
# advanced_filter/engine.py
from __future__ import annotations
from typing import Dict, Any, List
import os
import io
import re
import unicodedata
import yaml
import pandas as pd

# Loader v2 (única fonte). Mantém o código robusto caso o módulo não esteja disponível.
try:
    from .config_loader import load_config_v2_from_bytes  # v2 somente
except Exception:
    def load_config_v2_from_bytes(yaml_bytes: bytes) -> Dict[str, Any]:
        """Fallback mínimo: exige 'matchers' no YAML."""
        if not yaml_bytes:
            raise ValueError("YAML vazio.")
        data = yaml.safe_load(io.BytesIO(yaml_bytes).read()) or {}
        if "matchers" not in data:
            raise ValueError("Config YAML deve estar em v2 (com 'matchers').")
        return data


# -------------------------------------------------------------------
# Util: aceitar bytes/str/dict como cfg_yaml e sempre devolver bytes
# -------------------------------------------------------------------
def _to_yaml_bytes(cfg_in) -> bytes:
    """
    Aceita:
      - bytes/bytearray -> retorna como está
      - dict            -> serializa para YAML (utf-8)
      - str             -> se for caminho existente, lê em modo 'rb'; senão, trata como YAML em texto
    Retorna sempre bytes (utf-8).
    """
    if isinstance(cfg_in, (bytes, bytearray)):
        return bytes(cfg_in)

    if isinstance(cfg_in, dict):
        return yaml.safe_dump(cfg_in, allow_unicode=True, sort_keys=False).encode("utf-8")

    if isinstance(cfg_in, str):
        path = cfg_in.strip()
        if path and os.path.exists(path) and os.path.isfile(path):
            with open(path, "rb") as f:
                return f.read()
        # trata como YAML em texto
        return cfg_in.encode("utf-8")

    raise TypeError(f"Config inválida: esperado bytes/str/dict, recebi {type(cfg_in)}")


# -------------------------------------------------------------------
# Normalização e tokenização
# -------------------------------------------------------------------
def _normalize_text(s: str, lowercase: bool = True, strip_accents: bool = True) -> str:
    if s is None:
        return ""
    t = str(s)
    if lowercase:
        t = t.lower()
    if strip_accents:
        t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return t

def _tokenize(s: str) -> List[tuple]:
    """Retorna [(token, start_char_pos), ...]"""
    return [(m.group(0), m.start()) for m in re.finditer(r"\w+|[^\w\s]", s, flags=re.UNICODE)]


# -------------------------------------------------------------------
# Matching
# -------------------------------------------------------------------
def _match_positions(text_norm: str, patterns: List[Dict[str, Any]]) -> List[tuple]:
    """
    Retorna [(start_char, pattern_dict), ...] para cada match.
    type:
      - literal -> \b...\b (se não tiver espaço). Se tiver espaço, vira 'phrase'.
      - phrase  -> substring (escape)
      - regex   -> regex bruto
    """
    hits: List[tuple] = []
    for p in patterns or []:
        pat = (p.get("pattern") or "").strip()
        if not pat:
            continue
        ptype = (p.get("type") or "literal").strip().lower()
        if ptype == "literal" and re.search(r"\s", pat):
            ptype = "phrase"

        try:
            if ptype == "literal":
                rgx = re.compile(r"\b" + re.escape(pat) + r"\b")
                for m in rgx.finditer(text_norm):
                    hits.append((m.start(), p))
            elif ptype == "phrase":
                rgx = re.compile(re.escape(pat))
                for m in rgx.finditer(text_norm):
                    hits.append((m.start(), p))
            elif ptype == "regex":
                rgx = re.compile(pat)
                for m in rgx.finditer(text_norm):
                    hits.append((m.start(), p))
            else:
                # default: literal
                rgx = re.compile(r"\b" + re.escape(pat) + r"\b")
                for m in rgx.finditer(text_norm):
                    hits.append((m.start(), p))
        except re.error:
            # padrão inválido: ignora
            continue
    return hits


def _within_window(tokens: List[tuple], posA: List[tuple], posB: List[tuple], window_tokens: int) -> bool:
    """Retorna True se existe A/B com distância em tokens <= window_tokens."""
    starts = [s for _, s in tokens]

    import bisect
    def char_to_tok_idx(ch):
        i = bisect.bisect_right(starts, ch) - 1
        return max(0, i)

    for a in posA:
        ia = char_to_tok_idx(a[0])
        for b in posB:
            ib = char_to_tok_idx(b[0])
            if abs(ia - ib) <= window_tokens:
                return True
    return False


# -------------------------------------------------------------------
# Avaliação de regras
# -------------------------------------------------------------------
class _HitSet:
    def __init__(self, hits: List[tuple]):
        self.hits = hits or []
    def __bool__(self):
        return bool(self.hits)
    def __repr__(self):
        return f"HitSet({len(self.hits)})"


def _apply_rules_to_text(text: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    norm = cfg.get("normalization", {})
    window = int(cfg.get("window", 8))
    M = cfg.get("matchers", {})
    positives = M.get("positives", [])
    negatives = M.get("negatives", [])
    contexts  = M.get("contexts", {})
    rules     = cfg.get("rules", [])

    # normaliza texto e padrões
    t = _normalize_text(text,
                        lowercase=bool(norm.get("lowercase", True)),
                        strip_accents=bool(norm.get("strip_accents", True)))
    toks = _tokenize(t)

    def _norm_patterns(lst):
        out = []
        for d in lst or []:
            q = dict(d)
            q["pattern"] = _normalize_text(q.get("pattern") or "",
                                           lowercase=bool(norm.get("lowercase", True)),
                                           strip_accents=bool(norm.get("strip_accents", True)))
            if not q["pattern"]:
                continue
            if "weight" in q:
                try:
                    q["weight"] = float(q["weight"])
                except Exception:
                    q.pop("weight", None)
            out.append(q)
        return out

    pos_pats = _norm_patterns(positives)
    neg_pats = _norm_patterns(negatives)
    ctx_pats = {
        g: {
            "category": (info or {}).get("category"),
            "patterns": _norm_patterns((info or {}).get("patterns") or []),
        }
        for g, info in (contexts or {}).items()
    }

    pos_hits = _match_positions(t, pos_pats)
    neg_hits = _match_positions(t, neg_pats)
    ctx_hits_map = {g: _match_positions(t, info["patterns"]) for g, info in ctx_pats.items()}

    # score simples: soma dos pesos positivos encontrados (default 1.0)
    score = sum(p.get("weight", 1.0) for _, p in pos_hits)

    def POS(): return _HitSet(pos_hits)
    def NEG(): return _HitSet(neg_hits)
    def CTX(group): return _HitSet(ctx_hits_map.get(group, []))
    def WITHIN(n, A, B): return _within_window(toks, A.hits, B.hits, int(n))

    env = {"POS": POS, "NEG": NEG, "CTX": CTX, "WITHIN": WITHIN}

    decision = "REVISA"
    category = ""
    rule_name = ""

    for r in rules or []:
        eq = (r.get("equation") or "").strip()
        if not eq:
            continue
        try:
            res = eval(eq, {"__builtins__": {}}, env)  # expressão controlada via YAML
        except Exception:
            res = False
        if res:
            ms = r.get("min_score", None)
            if ms is None or score >= float(ms):
                decision = (r.get("decision") or "REVISA").upper()
                category = (r.get("assign_category") or "").strip()
                rule_name = (r.get("name") or "").strip()
                break

    return {
        "decision": decision,
        "category": category,
        "score": score,
        "rule": rule_name,
        "pos_hits": [p for _, p in pos_hits],
        "neg_hits": [p for _, p in neg_hits],
        "ctx_hits": {g: [p for _, p in hits] for g, hits in ctx_hits_map.items()},
    }


# -------------------------------------------------------------------
# API pública
# -------------------------------------------------------------------
def run_filter(df: pd.DataFrame, text_col: str, cfg_yaml, **kwargs) -> pd.DataFrame:
    """
    Aplica o filtro do YAML v2 (única fonte) sobre df[text_col].

    Parâmetro cfg_yaml pode ser:
      - bytes (YAML)
      - str   (caminho de arquivo .yaml ou YAML em texto)
      - dict  (já carregado; será serializado p/ YAML antes de validar)

    Retorna df com colunas adicionais:
       __decision, __category, __score, __rule, __pos_hits, __neg_hits, __ctx_hits
    """
    cfg_bytes = _to_yaml_bytes(cfg_yaml)
    cfg = load_config_v2_from_bytes(cfg_bytes)  # valida/normaliza estrutura v2

    vals = df[text_col].fillna("").astype(str).tolist()
    decisions: List[str] = []
    categories: List[str] = []
    scores: List[float] = []
    rules: List[str] = []
    pos_hits_list: List[Any] = []
    neg_hits_list: List[Any] = []
    ctx_hits_list: List[Any] = []

    for s in vals:
        res = _apply_rules_to_text(s, cfg)
        decisions.append(res["decision"])
        categories.append(res["category"])
        scores.append(res["score"])
        rules.append(res["rule"])
        pos_hits_list.append(res["pos_hits"])
        neg_hits_list.append(res["neg_hits"])
        ctx_hits_list.append(res["ctx_hits"])

    out = df.copy()
    out["__decision"] = decisions
    out["__category"] = categories
    out["__score"] = scores
    out["__rule"] = rules
    out["__pos_hits"] = pos_hits_list
    out["__neg_hits"] = neg_hits_list
    out["__ctx_hits"] = ctx_hits_list
    return out
