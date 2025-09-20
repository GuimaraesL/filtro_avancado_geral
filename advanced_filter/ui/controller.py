# -*- coding: utf-8 -*-
# advanced_filter/ui/controller.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any
import os
import tempfile
from io import BytesIO
import html

import pandas as pd
from unidecode import unidecode

# Camada de negócio
from ..excel_io import read_table
from ..engine import run_filter
from ..config_loader import load_config
from ..matcher import build_indices
from ..preprocessor import normalize

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
    df_test = pd.DataFrame([{text_col: (sample_text or "").strip()}])
    with tempfile.TemporaryDirectory() as tdir:
        cfg_path = os.path.join(tdir, cfg_name or "config.yaml")
        with open(cfg_path, "wb") as f:
            f.write(cfg_bytes)

        result = run_filter(df_test, text_col, cfg_path)
        row = result["full"].iloc[0].to_dict()
        return row, result["full"]

# --------- Normalização com mapeamento (norm_idx -> orig_idx) ---------
def normalize_with_map(text: str, lowercase: bool = True, strip_accents: bool = True) -> Tuple[str, List[int]]:
    """
    Retorna (texto_normalizado, map_norm_to_orig).
    Cada posição i do texto normalizado aponta para o índice do caractere original que o gerou.
    """
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

# --------- Coleta de spans (POS/NEG/CTX) ---------
def _collect_hits(sample_text: str, cfg_bytes: bytes, cfg_name: str):
    """
    Retorna:
      norm_text, pos_hits, neg_hits, ctx_hits_by_group, cfg (para saber flags de normalização)
    hits: [((start,end), spec_dict), ...]
    """
    with tempfile.TemporaryDirectory() as tdir:
        cfg_path = os.path.join(tdir, cfg_name or "config.yaml")
        with open(cfg_path, "wb") as f:
            f.write(cfg_bytes)

        cfg = load_config(cfg_path)
        norm = normalize(sample_text, lowercase=cfg.normalization.lowercase, strip_accents=cfg.normalization.strip_accents)
        indices = build_indices(cfg)

        pos_hits = indices["positives"].findall(norm)
        neg_hits = indices["negatives"].findall(norm)
        ctx_hits_by_group: Dict[str, List] = {name: idx.findall(norm) for name, idx in indices["contexts"].items()}
        return norm, pos_hits, neg_hits, ctx_hits_by_group, cfg

# --------- HTML high-contrast para highlight ---------
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
    # Resultado do pipeline
    row, full_df = quick_test(sample_text, text_col, cfg_bytes, cfg_name)

    # Coleta de hits em TEXTO NORMALIZADO
    norm_text, pos_hits, neg_hits, ctx_hits_by_group, cfg = _collect_hits(sample_text, cfg_bytes, cfg_name)
    labels_norm = _labels_from_hits(len(norm_text), pos_hits, neg_hits, ctx_hits_by_group)
    html_norm = _html_from_labels(norm_text, labels_norm)

    # Mapeia para o ORIGINAL para realce também no texto original
    orig_text = sample_text or ""
    norm_text2, norm2orig = normalize_with_map(orig_text, lowercase=cfg.normalization.lowercase, strip_accents=cfg.normalization.strip_accents)
    # (norm_text2 deve ser igual a norm_text; se não for, usamos norm_text como referência mesmo assim)
    labels_orig = _project_labels_to_original(labels_norm, norm2orig, len(orig_text))
    html_orig = _html_from_labels(orig_text, labels_orig)

    counts = {
        "positivos": len(pos_hits),
        "negativos": len(neg_hits),
        "contextos": sum(len(v) for v in ctx_hits_by_group.values()),
    }
    return row, full_df, html_orig, html_norm, counts, norm_text
