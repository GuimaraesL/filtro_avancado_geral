# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Tuple, Dict, Any, Optional
import io
import unicodedata
import pandas as pd

try:
    from ..engine import run_filter, compile_terms, normalize_text, find_matches
    from ..config_loader import load_config
    from ..excel_io import read_table
except Exception:
    from engine import run_filter, compile_terms, normalize_text, find_matches  # type: ignore
    from config_loader import load_config  # type: ignore

    def read_table(path: str, sheet: Optional[str] = None) -> pd.DataFrame:  # type: ignore
        import pandas as _pd
        if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
            return _pd.read_excel(path, sheet_name=sheet)
        return _pd.read_csv(path)

# ---------------- Excel helpers ----------------
def is_excel_name(name: str) -> bool:
    return str(name).lower().endswith((".xlsx", ".xlsm", ".xls"))

def list_sheets_from_bytes(data_bytes: bytes) -> List[str]:
    import pandas as _pd
    with io.BytesIO(data_bytes) as bio:
        try:
            xls = _pd.ExcelFile(bio)
            return list(xls.sheet_names)
        except Exception:
            return []

def list_columns_from_bytes(data_bytes: bytes, is_excel: bool, sheet: Optional[str]) -> List[str]:
    import pandas as _pd
    with io.BytesIO(data_bytes) as bio:
        try:
            if is_excel:
                df = _pd.read_excel(bio, sheet_name=sheet)
            else:
                df = _pd.read_csv(bio, nrows=200)
            return list(df.columns)
        except Exception:
            return []

def read_table_compat(path: str, sheet: Optional[str] = None) -> pd.DataFrame:
    try:
        return read_table(path, sheet_name=sheet)  # type: ignore
    except TypeError:
        return read_table(path, sheet)  # type: ignore

# --------------- Normalização com MAPA p/ voltar ao original ---------------
def _strip_accents_char(ch: str) -> str:
    # Remove apenas marcas combinantes (NFKD), evitando expandir em 2+ chars.
    decomp = unicodedata.normalize("NFKD", ch)
    base = "".join(c for c in decomp if not unicodedata.combining(c))
    return base or ch  # se esvaziar, mantém original

def normalize_with_map(text: str, lowercase: bool = True, strip_accents: bool = True) -> Tuple[str, List[int]]:
    """
    Retorna (texto_normalizado, map_norm_to_orig).
    Para cada posição i do texto normalizado, map_norm_to_orig[i] = índice do caractere no texto ORIGINAL
    que gerou esse caractere normalizado. Assim conseguimos pintar o original.
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    norm_chars: List[str] = []
    norm_to_orig: List[int] = []

    for i, ch in enumerate(text):
        ch2 = ch
        if lowercase:
            ch2 = ch2.lower()
        if strip_accents:
            ch2 = _strip_accents_char(ch2)

        # ch2 pode ter 0 ou 1+ chars; normalmente 0 ou 1 para PT-BR após NFKD
        if ch2:
            for _ in ch2:
                norm_chars.append(_)
                norm_to_orig.append(i)

    return "".join(norm_chars), norm_to_orig

# --------------- Highlight ---------------
def _apply_spans_on_original(original_text: str, spans: List[Tuple[int, int, str]]) -> str:
    """
    Aplica spans (em índices DO ORIGINAL) ao texto original.
    'spans' = lista de (start, end, class) com 0 <= start < end <= len(original_text).
    Se houver sobreposição, usa prioridade: ctx(1) < neg(2) < pos(3).
    """
    if not spans:
        # escapar mínimo para segurança
        html = (
            original_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return html

    n = len(original_text)
    priority = {"hl-ctx": 1, "hl-neg": 2, "hl-pos": 3}

    mask = [0] * n  # 0 = sem classe
    cls_at = ["" for _ in range(n)]
    for s, e, cls in spans:
        s = max(0, min(n, s))
        e = max(0, min(n, e))
        if e <= s:
            continue
        pr = priority.get(cls, 1)
        for i in range(s, e):
            if pr >= mask[i]:
                mask[i] = pr
                cls_at[i] = cls

    # gera HTML caminhando char a char, escapando e abrindo/fechando <span>
    out = []
    current = ""
    def esc(ch: str) -> str:
        if ch == "&": return "&amp;"
        if ch == "<": return "&lt;"
        if ch == ">": return "&gt;"
        return ch

    for i, ch in enumerate(original_text):
        cls = cls_at[i]
        if cls != current:
            if current:
                out.append("</span>")
            if cls:
                out.append(f'<span class="{cls}">')
            current = cls
        out.append(esc(ch))
    if current:
        out.append("</span>")
    return "".join(out)

def build_highlight_html(original_text: str, cfg: Dict[str, Any]) -> Tuple[str, str, Dict[str, int]]:
    """
    Retorna (html_original_com_realce, html_normalizado_com_realce, contagens).
    """
    norm = cfg.get("normalization", {}) or {}
    lower = bool(norm.get("lowercase", True))
    strip = bool(norm.get("strip_accents", True))

    # Texto normalizado + mapa para original
    text_norm, map_norm_to_orig = normalize_with_map(
        original_text, lowercase=lower, strip_accents=strip
    )

    # Normalizar termos antes de compilar (igual ao engine)
    def _norm_terms(terms):
        return [normalize_text(t, lowercase=lower, strip_accents=strip) for t in (terms or [])]

    pos_rgx = compile_terms(_norm_terms(cfg.get("positives")))
    neg_rgx = compile_terms(_norm_terms(cfg.get("negatives")))
    ctx_rgx = compile_terms(_norm_terms(cfg.get("contexts")))

    pos = find_matches(text_norm, pos_rgx)
    neg = find_matches(text_norm, neg_rgx)
    ctx = find_matches(text_norm, ctx_rgx)

    counts = {"positivos": len(pos), "negativos": len(neg), "contextos": len(ctx)}

    # -------- pintar NORMALIZADO (para o painel de depuração) --------
    def _paint(matches, cls: str, base: str) -> str:
        if not matches:
            return base
        out, last = [], 0
        for s, e, _ in matches:
            if s > last:
                out.append(base[last:s])
            out.append(f'<span class="{cls}">' + base[s:e] + '</span>')
            last = e
        if last < len(base):
            out.append(base[last:])
        return ''.join(out)

    html_norm = text_norm
    html_norm = _paint(ctx, "hl-ctx", html_norm)
    html_norm = _paint(neg, "hl-neg", html_norm)
    html_norm = _paint(pos, "hl-pos", html_norm)

    # -------- pintar ORIGINAL (convertendo offsets do normalizado -> original) --------
    spans_original: List[Tuple[int, int, str]] = []

    def _normspan_to_origspan(s: int, e: int) -> Tuple[int, int]:
        # converte [s,e) do normalizado para [s_o,e_o) no original
        s = max(0, min(len(map_norm_to_orig), s))
        e = max(s, min(len(map_norm_to_orig), e))
        if e <= s:
            return (0, 0)
        s_o = map_norm_to_orig[s]
        e_o = map_norm_to_orig[e - 1] + 1  # inclui último char
        return (s_o, e_o)

    for s, e, _ in ctx:
        s_o, e_o = _normspan_to_origspan(s, e)
        if e_o > s_o:
            spans_original.append((s_o, e_o, "hl-ctx"))
    for s, e, _ in neg:
        s_o, e_o = _normspan_to_origspan(s, e)
        if e_o > s_o:
            spans_original.append((s_o, e_o, "hl-neg"))
    for s, e, _ in pos:
        s_o, e_o = _normspan_to_origspan(s, e)
        if e_o > s_o:
            spans_original.append((s_o, e_o, "hl-pos"))

    html_orig = _apply_spans_on_original(original_text, spans_original)
    return html_orig, html_norm, counts

# --------------- Teste rápido ---------------
def quick_test_highlight(sample_text: str, text_col: str, cfg_bytes: bytes, cfg_name: Optional[str]):
    cfg = load_config(cfg_bytes)
    df = pd.DataFrame([{text_col: sample_text}])
    result = run_filter(df, text_col, cfg)
    row = result.iloc[0].to_dict()
    html_orig, html_norm, counts = build_highlight_html(sample_text, cfg)
    debug = {
        "require_context": cfg.get("require_context", False),
        "negative_wins_ties": cfg.get("negative_wins_ties", True),
        "min_pos_to_include": cfg.get("min_pos_to_include", 1),
        "min_neg_to_exclude": cfg.get("min_neg_to_exclude", 1),
        "window": cfg.get("window", 8),
    }
    return row, result, html_orig, html_norm, counts, debug
