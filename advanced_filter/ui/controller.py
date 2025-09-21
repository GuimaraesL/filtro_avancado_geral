# -*- coding: utf-8 -*-
# advanced_filter/ui/controller.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any
import os
import re
from io import BytesIO
import html

import pandas as pd
from unidecode import unidecode

# Camada de negócio
from ..excel_io import read_table
from ..engine import run_filter                     # v2: retorna __decision/__category/...
from ..config_loader import load_config             # v2: recebe BYTES e retorna dict
from ..preprocessor import normalize                # normalização simples (lower/accents)

# --------- Helpers básicos ---------
def is_excel_name(name: str) -> bool:
    return isinstance(name, str) and name.lower().endswith((".xls", ".xlsx", ".xlsm"))

def list_sheets_from_bytes(data_bytes: Optional[bytes]) -> List[str]:
    if not data_bytes:
        return []
    try:
        xls = pd.ExcelFile(BytesIO(data_bytes))
        return list(xls.sheet_names)
    except Exception:
        return []

def list_columns_from_bytes(data_bytes: Optional[bytes], is_excel: bool, sheet: Optional[str]) -> List[str]:
    if not data_bytes:
        return []
    try:
        bio = BytesIO(data_bytes)
        if is_excel:
            head = pd.read_excel(bio, sheet_name=sheet, nrows=0) if sheet else pd.read_excel(bio, nrows=0)
        else:
            head = pd.read_csv(bio, nrows=0)
        return list(map(str, head.columns))
    except Exception:
        return []

# --------- Compat para read_table (com ou sem 'sheet') ---------
def read_table_compat(path_or_buf, sheet: Optional[str] = None) -> pd.DataFrame:
    import inspect
    try:
        sig = inspect.signature(read_table)  # type: ignore
        if "sheet" in sig.parameters:
            return read_table(path_or_buf, sheet=sheet)  # type: ignore
    except Exception:
        pass

    def _is_excel_path(p):
        return isinstance(p, str) and p.lower().endswith((".xls", ".xlsx", ".xlsm"))

    if sheet:
        try:
            if isinstance(path_or_buf, (bytes, bytearray)):
                bio = BytesIO(path_or_buf)
                return pd.read_excel(bio, sheet_name=sheet)
            elif _is_excel_path(path_or_buf):
                return pd.read_excel(path_or_buf, sheet_name=sheet)
        except Exception:
            pass

    return read_table(path_or_buf)  # type: ignore

# --------- Autodetectar sheet pela coluna ---------
def autodetect_sheet_by_column(data_path: str, sheets: List[str], text_col: str) -> Tuple[Optional[str], Optional[str]]:
    found: List[str] = []
    for sn in sheets:
        try:
            head = pd.read_excel(data_path, sheet_name=sn, nrows=5)
            if text_col in head.columns:
                found.append(sn)
        except Exception:
            pass

    if len(found) == 1:
        return found[0], f"Aba detectada automaticamente: {found[0]} (coluna '{text_col}')."
    if len(found) > 1:
        return None, "ambiguidade"
    return None, "nao_encontrada"

# --------- YAML em memória ---------
def ensure_cfg_bytes(cfg_file) -> Tuple[Optional[bytes], str]:
    if cfg_file is None:
        return None, "config.yaml"
    return cfg_file.getvalue(), getattr(cfg_file, "name", "config.yaml")

# --------- Teste rápido (1 linha) ---------
def quick_test(sample_text: str, text_col: str, cfg_bytes: bytes, cfg_name: str):
    """
    Executa o engine v2 em 1 linha e mapeia para o formato esperado pela UI.
    """
    df_test = pd.DataFrame([{text_col: (sample_text or "").strip()}])

    # roda o engine v2 — retorna colunas __decision/__category/__score/__rule/...
    result = run_filter(df_test, text_col, cfg_bytes)

    r0 = result.iloc[0]
    row = {
        "decision":    str(r0.get("__decision", "") or "").upper(),
        "categoria":   r0.get("__category", "") or "",
        "score_total": float(r0.get("__score", 0.0) or 0.0),
        "rule_fired":  r0.get("__rule", "") or "",
        "audit": (
            f"POS={len(r0.get('__pos_hits', []) or [])}, "
            f"NEG={len(r0.get('__neg_hits', []) or [])}, "
            f"CTX_grupos={len((r0.get('__ctx_hits', {}) or {}).keys())}"
        ),
    }
    return row, result  # (full_df agora é o próprio result)

# --------- Normalização com mapeamento (norm_idx -> orig_idx) ---------
def normalize_with_map(text: str, lowercase: bool = True, strip_accents: bool = True) -> Tuple[str, List[int]]:
    out_chars: List[str] = []
    map_norm_to_orig: List[int] = []
    for i, ch in enumerate(text):
        tmp = ch
        if strip_accents:
            tmp = unidecode(tmp)
        if lowercase:
            tmp = tmp.lower()
        for _c in tmp:
            out_chars.append(_c)
            map_norm_to_orig.append(i)
    return "".join(out_chars), map_norm_to_orig

# --------- Mini-matcher local (alinhado ao engine v2) ---------
def _compile_pattern(normalized_pat: str, ptype: str) -> re.Pattern:
    # Se 'literal' mas tem espaço, vira 'phrase' (mesma regra do engine)
    t = (ptype or "literal").strip().lower()
    if t == "literal" and re.search(r"\s", normalized_pat):
        t = "phrase"
    if t == "literal":
        return re.compile(r"\b" + re.escape(normalized_pat) + r"\b")
    elif t == "phrase":
        return re.compile(re.escape(normalized_pat))
    elif t == "regex":
        return re.compile(normalized_pat)
    else:
        return re.compile(r"\b" + re.escape(normalized_pat) + r"\b")

def _find_spans(text_norm: str, patterns: List[Dict[str, Any]],
                lowercase: bool, strip_accents: bool) -> List[Tuple[Tuple[int,int], Dict[str, Any]]]:
    hits: List[Tuple[Tuple[int,int], Dict[str, Any]]] = []
    for spec in patterns or []:
        raw = (spec.get("pattern") or "").strip()
        if not raw:
            continue
        # 🔑 normaliza o padrão com as mesmas flags do texto
        pat = normalize(raw, lowercase=lowercase, strip_accents=strip_accents)
        try:
            rgx = _compile_pattern(pat, (spec.get("type") or "literal"))
            for m in rgx.finditer(text_norm):
                hits.append(((m.start(), m.end()), spec))
        except re.error:
            continue
    return hits

# --------- Coleta de spans (POS/NEG/CTX) ---------
def _collect_hits(sample_text: str, cfg_bytes: bytes, cfg_name: str):
    """
    Retorna: norm_text, pos_hits, neg_hits, ctx_hits_by_group, cfg_dict
    """
    cfg = load_config(cfg_bytes)  # dict v2 (normalization/window/matchers/regras)
    norm_flags = (cfg.get("normalization") or {})
    lc = bool(norm_flags.get("lowercase", True))
    sa = bool(norm_flags.get("strip_accents", True))

    # Texto normalizado
    norm = normalize(sample_text, lowercase=lc, strip_accents=sa)

    M = cfg.get("matchers", {}) or {}
    positives = M.get("positives") or []
    negatives = M.get("negatives") or []
    contexts  = M.get("contexts")  or {}

    pos_hits = _find_spans(norm, positives, lc, sa)
    neg_hits = _find_spans(norm, negatives, lc, sa)
    ctx_hits_by_group: Dict[str, List] = {
        g: _find_spans(norm, (info or {}).get("patterns") or [], lc, sa)
        for g, info in contexts.items()
    }
    return norm, pos_hits, neg_hits, ctx_hits_by_group, cfg

# --------- HTML para highlight ---------
CSS_HIGHLIGHT = """
<style>
:root{
  --pos-bg: #d1fae5; --pos-fg: #065f46; --pos-bd: #10b981;
  --neg-bg: #fee2e2; --neg-fg: #7f1d1d; --neg-bd: #ef4444;
  --ctx-bg: #dbeafe; --ctx-fg: #1e3a8a; --ctx-bd: #3b82f6;
  --badge-inc-bg:#16a34a; --badge-inc-fg:#ffffff;
  --badge-rev-bg:#f59e0b; --badge-rev-fg:#111827;
  --badge-exc-bg:#ef4444; --badge-exc-fg:#ffffff;
}
@media (prefers-color-scheme: dark){
  :root{
    --pos-bg: #064e3b66; --pos-fg: #d1fae5; --pos-bd: #10b981;
    --neg-bg: #7f1d1d66; --neg-fg: #fee2e2; --neg-bd: #ef4444;
    --ctx-bg: #1e3a8a66; --ctx-fg: #bfdbfe; --ctx-bd: #3b82f6;
  }
}
.mark { border:1px solid; border-radius:6px; padding:0 4px; margin:0 1px; font-weight:600 }
.mark-pos{ background:var(--pos-bg); color:var(--pos-fg); border-color:var(--pos-bd); }
.mark-neg{ background:var(--neg-bg); color:var(--neg-fg); border-color:var(--neg-bd); }
.mark-ctx{ background:var(--ctx-bg); color:var(--ctx-fg); border-color:var(--ctx-bd); }
.hl-legend{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:6px 0 10px; }
.hl-legend .chip{ border:1px solid #374151; padding:2px 8px; border-radius:999px; font-size:12px; opacity:.9 }
.hl-text{ white-space:pre-wrap; line-height:1.6; font-family: ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; }
.badge{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; font-size:13px; }
.badge-inc{ background: var(--badge-inc-bg); color: var(--badge-inc-fg); }
.badge-rev{ background: var(--badge-rev-bg); color: var(--badge-rev-fg); }
.badge-exc{ background: var(--badge-exc-bg); color: var(--badge-exc-fg); }
.section-title{ margin:10px 0 6px; font-weight:700; font-size:15px; }
</style>
""".strip()

def _labels_from_hits(n: int,
                      pos_hits: List[Tuple[Tuple[int,int], Dict[str,Any]]],
                      neg_hits: List[Tuple[Tuple[int,int], Dict[str,Any]]],
                      ctx_hits_by_group: Dict[str, List[Tuple[Tuple[int,int], Dict[str,Any]]]]) -> List[Optional[str]]:
    labels: List[Optional[str]] = [None] * n
    PRIORITY = {"neg": 3, "pos": 2, "ctx": 1}

    def paint(span: Tuple[int,int], tag: str):
        s, e = span
        s = max(0, min(n, s)); e = max(s, min(n, e))
        for i in range(s, e):
            cur = labels[i]
            if cur is None or PRIORITY[tag] > PRIORITY.get(cur, 0):
                labels[i] = tag

    for (s,e), _ in neg_hits:
        paint((s,e), "neg")
    for (s,e), _ in pos_hits:
        paint((s,e), "pos")
    for _, hits in ctx_hits_by_group.items():
        for (s,e), _ in hits:
            paint((s,e), "ctx")

    return labels

def _html_from_labels(text: str, labels: List[Optional[str]]) -> str:
    n = len(text)
    out: List[str] = []
    i = 0
    while i < n:
        tag = labels[i]
        if tag is None:
            out.append(html.escape(text[i]))
            i += 1
            continue
        j = i
        while j < n and labels[j] == tag:
            j += 1
        seg = html.escape(text[i:j])
        out.append(f'<span class="mark mark-{tag}">{seg}</span>')
        i = j
    legend = (
        '<div class="hl-legend">'
        '<span class="chip">positivos</span>'
        '<span class="chip">negativos</span>'
        '<span class="chip">contexto</span>'
        '</div>'
    )
    return f'{CSS_HIGHLIGHT}{legend}<div class="hl-text">{"".join(out)}</div>'

def _project_labels_to_original(labels_norm: List[Optional[str]], map_norm_to_orig: List[int], orig_len: int) -> List[Optional[str]]:
    PRIORITY = {"neg": 3, "pos": 2, "ctx": 1}
    labels_orig: List[Optional[str]] = [None] * orig_len
    for i_norm, tag in enumerate(labels_norm):
        if tag is None:
            continue
        i_orig = map_norm_to_orig[i_norm]
        prev = labels_orig[i_orig]
        if prev is None or PRIORITY[tag] > PRIORITY.get(prev, 0):
            labels_orig[i_orig] = tag
    return labels_orig

# --------- Pipeline de highlight (normalizado + original) ---------
def quick_test_highlight(sample_text: str, text_col: str, cfg_bytes: bytes, cfg_name: str):
    row, full_df = quick_test(sample_text, text_col, cfg_bytes, cfg_name)

    norm_text, pos_hits, neg_hits, ctx_hits_by_group, cfg = _collect_hits(sample_text, cfg_bytes, cfg_name)
    labels_norm = _labels_from_hits(len(norm_text), pos_hits, neg_hits, ctx_hits_by_group)
    html_norm = _html_from_labels(norm_text, labels_norm)

    norm_flags = (cfg.get("normalization") or {})
    lc = bool(norm_flags.get("lowercase", True))
    sa = bool(norm_flags.get("strip_accents", True))

    orig_text = sample_text or ""
    _, norm2orig = normalize_with_map(orig_text, lowercase=lc, strip_accents=sa)
    labels_orig = _project_labels_to_original(labels_norm, norm2orig, len(orig_text))
    html_orig = _html_from_labels(orig_text, labels_orig)

    counts = {
        "positivos": len(pos_hits),
        "negativos": len(neg_hits),
        "contextos": sum(len(v) for v in ctx_hits_by_group.values()),
    }
    return row, full_df, html_orig, html_norm, counts, norm_text
