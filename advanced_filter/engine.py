# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Iterable, Optional, Union
import re
import pandas as pd

try:
    from .config_loader import load_config
except Exception:
    from config_loader import load_config

# ---------- Normalização ----------
def _strip_accents(s: str) -> str:
    try:
        from unidecode import unidecode
        return unidecode(s)
    except Exception:
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def normalize_text(s: str, lowercase: bool = True, strip_accents: bool = True) -> str:
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    if lowercase:
        s = s.lower()
    if strip_accents:
        s = _strip_accents(s)
    return s

# ---------- Compilação de padrões ----------
def _compile_term(term: str) -> re.Pattern:
    t = term.strip()
    if not t:
        return re.compile(r"$^")
    if " " in t:
        return re.compile(re.escape(t))
    else:
        return re.compile(r"\b" + re.escape(t) + r"\b")

def compile_terms(terms: Iterable[str]) -> List[re.Pattern]:
    return [_compile_term(t) for t in (terms or []) if isinstance(t, str) and t.strip()]

# ---------- Indexação de tokens ----------
_word_re = re.compile(r"\w+")

def _word_starts(text: str) -> List[int]:
    return [m.start() for m in _word_re.finditer(text)]

def _char_to_token_index(char_idx: int, word_starts: List[int]) -> int:
    import bisect
    return bisect.bisect_right(word_starts, char_idx)

def _token_distance(a_char: int, b_char: int, word_starts: List[int]) -> int:
    ai = _char_to_token_index(a_char, word_starts)
    bi = _char_to_token_index(b_char, word_starts)
    return abs(ai - bi)

# ---------- Matching ----------
def find_matches(text_norm: str, patterns: List[re.Pattern]) -> List[Tuple[int, int, str]]:
    out: List[Tuple[int, int, str]] = []
    for rgx in patterns:
        for m in rgx.finditer(text_norm):
            out.append((m.start(), m.end(), m.group(0)))
    out.sort(key=lambda x: x[0])
    return out

def any_near(a_matches: List[Tuple[int, int, str]], b_matches: List[Tuple[int, int, str]], k_tokens: int, word_starts: List[int]) -> bool:
    if not a_matches or not b_matches:
        return False
    for sa, ea, _ in a_matches:
        for sb, eb, _ in b_matches:
            if _token_distance(sa, sb, word_starts) <= k_tokens:
                return True
    return False

def _unique_terms(matches: List[Tuple[int, int, str]], limit: int = 50) -> str:
    """Retorna termos únicos (normalizados) separados por ' | ' para auditoria."""
    seen = []
    seen_set = set()
    for _, _, t in matches:
        if t not in seen_set:
            seen.append(t)
            seen_set.add(t)
        if len(seen) >= limit:
            break
    return " | ".join(seen)

# ---------- Decisão básica (com motivo) ----------
def decide_basic(P: int, N: int, Cpos: bool, Cneg: bool, cfg: Dict[str, Any]) -> Tuple[str, str]:
    """
    Retorna (decision, reason_code).
    Opção A aplicada: se P==0 e N==0 => EXCLUI (NO_SIGNALS).
    """
    require_ctx = bool(cfg.get("require_context", False))
    neg_wins = bool(cfg.get("negative_wins_ties", True))
    minP = int(cfg.get("min_pos_to_include", 1))
    minN = int(cfg.get("min_neg_to_exclude", 1))

    # 🔴 Opção A: sem sinais => EXCLUI
    if P == 0 and N == 0:
        return "EXCLUI", "NO_SIGNALS"

    if require_ctx:
        pos_ok = P >= minP
        neg_ok = N >= minN
        if Cpos and pos_ok and not Cneg:
            return "INCLUI", "REQ_CTX_POS_ONLY"
        if Cneg and neg_ok and not Cpos:
            return "EXCLUI", "REQ_CTX_NEG_ONLY"
        # não atendeu exclusividade de contexto
        if pos_ok and not Cpos:
            return "REVISA", "REQ_CTX_POS_NO_CTX"
        if neg_ok and not Cneg:
            return "REVISA", "REQ_CTX_NEG_NO_CTX"
        if pos_ok and neg_ok:
            return "REVISA", "REQ_CTX_TIE_OR_NO_EXCLUSIVE"
        return "REVISA", "REQ_CTX_UNMET"

    # contexto não exigido
    pos_ok = P >= minP
    neg_ok = N >= minN

    if neg_ok and not pos_ok:
        return "EXCLUI", "NEG_ONLY"
    if pos_ok and not neg_ok:
        return "INCLUI", "POS_ONLY"
    if pos_ok and neg_ok:
        if neg_wins:
            if Cpos and not Cneg:
                return "INCLUI", "TIE_POS_CTX"
            if Cneg and not Cpos:
                return "EXCLUI", "TIE_NEG_CTX"
            return "REVISA", "TIE_NO_CTX"
        else:
            if Cpos and not Cneg:
                return "INCLUI", "TIE_POS_CTX"
            return "REVISA", "TIE_NO_CTX"

    # abaixo dos limiares (mas não zero-zerado, já tratado)
    if (P > 0 and P < minP) and (N == 0):
        return "REVISA", "POS_BELOW_MIN"
    if (N > 0 and N < minN) and (P == 0):
        return "REVISA", "NEG_BELOW_MIN"
    return "REVISA", "WEAK_SIGNALS"

# ---------- API principal ----------
CfgSource = Union[bytes, Dict[str, Any]]

def run_filter(df: pd.DataFrame, text_col: str, cfg_source: CfgSource) -> pd.DataFrame:
    """
    Aplica o filtro básico a um DataFrame, retornando um novo DataFrame com colunas extras.
    - df: tabela de entrada
    - text_col: nome da coluna texto
    - cfg_source: bytes YAML ou dicionário já carregado
    """
    if isinstance(cfg_source, (bytes, bytearray)):
        cfg = load_config(cfg_source)
    elif isinstance(cfg_source, dict):
        cfg = cfg_source
    else:
        raise ValueError("cfg_source deve ser bytes (YAML) ou dict.")

    norm_opts = cfg.get("normalization", {}) or {}
    lowercase = bool(norm_opts.get("lowercase", True))
    strip_acc = bool(norm_opts.get("strip_accents", True))
    window = int(cfg.get("window", 8))

    # Normalizar termos antes de compilar (casa com o texto normalizado)
    def _norm_terms(terms):
        return [normalize_text(t, lowercase=lowercase, strip_accents=strip_acc) for t in (terms or [])]

    pos_patterns = compile_terms(_norm_terms(cfg.get("positives")))
    neg_patterns = compile_terms(_norm_terms(cfg.get("negatives")))
    ctx_patterns = compile_terms(_norm_terms(cfg.get("contexts")))

    out_rows = []
    for _, row in df.iterrows():
        text = row.get(text_col, "")
        text = "" if text is None else str(text)
        text_norm = normalize_text(text, lowercase=lowercase, strip_accents=strip_acc)
        words_idx = _word_starts(text_norm)

        pos_matches = find_matches(text_norm, pos_patterns)
        neg_matches = find_matches(text_norm, neg_patterns)
        ctx_matches = find_matches(text_norm, ctx_patterns)

        P = len(pos_matches)
        N = len(neg_matches)
        Cpos = any_near(pos_matches, ctx_matches, window, words_idx) if ctx_patterns else False
        Cneg = any_near(neg_matches, ctx_matches, window, words_idx) if ctx_patterns else False

        decision, reason_code = decide_basic(P, N, Cpos, Cneg, cfg)
        score = P - N

        # Auditoria amigável
        minP = int(cfg.get("min_pos_to_include", 1))
        minN = int(cfg.get("min_neg_to_exclude", 1))
        reason_detail = (
            f"P={P} (min {minP}), N={N} (min {minN}), "
            f"Cpos={'1' if Cpos else '0'}, Cneg={'1' if Cneg else '0'}, janela={window}, "
            f"require_ctx={'1' if cfg.get('require_context', False) else '0'}, "
            f"neg_wins={'1' if cfg.get('negative_wins_ties', True) else '0'} → {reason_code}"
        )

        new_row = dict(row)
        new_row["decision"] = decision
        new_row["decision_reason_code"] = reason_code
        new_row["decision_reason"] = reason_detail
        new_row["p_count"] = P
        new_row["n_count"] = N
        new_row["ctx_count"] = len(ctx_matches)
        new_row["near_pos_ctx"] = bool(Cpos)
        new_row["near_neg_ctx"] = bool(Cneg)
        new_row["score_total"] = float(score)
        # termos que dispararam (para auditoria)
        new_row["pos_terms"] = _unique_terms(pos_matches)
        new_row["neg_terms"] = _unique_terms(neg_matches)
        new_row["ctx_terms"] = _unique_terms(ctx_matches)

        out_rows.append(new_row)

    return pd.DataFrame(out_rows)
