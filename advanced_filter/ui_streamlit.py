# -*- coding: utf-8 -*-
# --- bootstrap para garantir que 'advanced_filter' seja importável em qualquer ambiente ---
from pathlib import Path
import sys
REPO_ROOT = str(Path(__file__).resolve().parents[1])  # .../filtro_avancado_geral
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
# ------------------------------------------------------------------------------------------

from typing import Optional, List
import streamlit as st


from advanced_filter.logs.loggs import get_logger, bump_render_seq, mark_event, log_state
from advanced_filter.ui.state import ensure_bootstrap
from advanced_filter.ui.help_ui import render_help
from advanced_filter.ui.controller import (
    is_excel_name,
    list_sheets_from_bytes,
    list_columns_from_bytes,
    quick_test_highlight,
)
from advanced_filter.ui.views_profiles import (
    render_sidebar_profile_selector,
    render_profiles_tab,
)
from advanced_filter.ui.result_view import (
    mark_processing,
    render_result_tab,
)

st.set_page_config(page_title="Filtro Avançado", layout="wide")
ensure_bootstrap()

# === LOGS: início de render ===
logger = get_logger("ui")
bump_render_seq(logger)
log_state(logger, prefix="render_state_boot")

# ---------- CSS opcional (visual) ----------
def _inject_css():
    st.markdown(
        """
        <style>
        .hl-pos{ background: rgba(46,125,50,.35); padding: 0 .15em; border-radius: .25rem; }
        .hl-neg{ background: rgba(198,40,40,.35); padding: 0 .15em; border-radius: .25rem; }
        .hl-ctx{ background: rgba(21,101,192,.35); padding: 0 .15em; border-radius: .25rem; }
        .badge{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:600; font-size:.8rem; }
        .badge-inc{ background:#2e7d32; color:#fff; }
        .badge-exc{ background:#c62828; color:#fff; }
        .badge-rev{ background:#616161; color:#fff; }
        .tabs-row{ display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom: .75rem; }
        .tab-btn{ padding:.4rem .7rem; border-radius:999px; border:1px solid #e0e0e0; cursor:pointer; font-weight:600; }
        .tab-btn.active{ background:#0e1117; color:#fff; border-color:#0e1117; }
        </style>
        """,
        unsafe_allow_html=True,
    )
_inject_css()

# ---------- Tab controlado por estado ----------
TABS = ["Teste Rápido", "Perfis", "Resultado", "Ajuda"]
st.session_state.setdefault("__active_tab", TABS[0])

def _tab_selector():
    # Renderiza um “segmented” simples via HTML/CSS (sem depender do DOM interno do Streamlit)
    with st.container():
        cols = st.columns(len(TABS))
        for i, name in enumerate(TABS):
            with cols[i]:
                active = (st.session_state["__active_tab"] == name)
                if st.button(
                    name,
                    key=f"__tab_{i}",
                    use_container_width=True
                ):
                    st.session_state["__active_tab"] = name

# ------------------- SIDEBAR ------------------- #
with st.sidebar:
    st.header("Carregar (dados)")
    uploaded_file = st.file_uploader(
        "Carregue seu arquivo",
        type=["csv", "xlsx", "xlsm"],
        key="__upload_file",
    )

    data_bytes: Optional[bytes] = None
    is_excel = False
    sheets: List[str] = []
    selected_sheet: Optional[str] = None

    if uploaded_file is not None:
        data_bytes = uploaded_file.getvalue()
        is_excel = is_excel_name(uploaded_file.name)
        if is_excel:
            sheets = list_sheets_from_bytes(data_bytes)
            if sheets:
                selected_sheet = st.selectbox("Planilha (sheet)", sheets, index=0, key="__sheet_select")

    # Coluna de texto (apenas com arquivo)
    if uploaded_file is not None and data_bytes:
        preview_sheet = selected_sheet or (sheets[0] if sheets else None)
        sidebar_columns = list_columns_from_bytes(data_bytes, is_excel, preview_sheet)
        if sidebar_columns:
            st.session_state["__text_col"] = st.selectbox(
                "Coluna de texto", sidebar_columns, index=0, key="__text_col_control"
            )
        else:
            st.info("O arquivo não possui colunas detectáveis.")
    else:
        st.session_state.setdefault("__text_col", "texto")

    st.markdown("---")
    st.subheader("Configuração")
    cfg_bytes, cfg_name, cfg_source_label = render_sidebar_profile_selector(
        st.file_uploader("YAML (config)", type=["yaml", "yml"], key="__cfg_upload")
    )
    st.session_state["__cfg_bytes"] = cfg_bytes
    st.session_state["__cfg_name"] = cfg_name
    st.session_state["__cfg_label"] = cfg_source_label

    st.markdown("---")
    st.subheader("Saída")
    st.session_state["__outname"] = st.text_input(
        "Nome do arquivo de saída (.xlsx)",
        value=st.session_state.get("__outname", "resultado_filtrado.xlsx"),
        key="__outname_sidebar"
    )

    # ▶️ Executar filtro
    if st.button("Executar filtro", use_container_width=True, key="__btn_exec_filter"):
        mark_event(logger, "click_execute_filter")
        if uploaded_file is None:
            st.warning("Envie um arquivo CSV/Excel para executar o filtro.")
        elif not cfg_bytes:
            st.warning("Escolha um Perfil ou envie um YAML para executar o filtro.")
        else:
            # Monta snapshot + preserva bytes em memória
            import hashlib as _h
            def _md5(b: Optional[bytes]) -> str:
                return _h.md5(b).hexdigest() if b else ""

            snapshot = {
                "file_hash": _md5(data_bytes),
                "cfg_hash": _md5(cfg_bytes),
                "text_col": st.session_state.get("__text_col", "texto"),
                "sheet": selected_sheet,
                "is_excel": is_excel,
                "outname": st.session_state.get("__outname") or "resultado_filtrado.xlsx",
                "filename": uploaded_file.name if uploaded_file else "",
            }
            st.session_state["__last_data_bytes"] = data_bytes

            # 1) Loga estado antes
            log_state(logger, prefix="before_mark_processing")

            # 2) Marca processamento (LIMPA resultado anterior imediatamente)
            mark_processing(snapshot)

            # 3) Troca de aba — controlada por estado (SEM JS)
            st.session_state["__active_tab"] = "Resultado"
            log_state(logger, prefix="after_mark_processing")

# ---------- Render do "tab controlado" ----------
_tab_selector()
active = st.session_state["__active_tab"]

if active == "Teste Rápido":
    st.markdown("### Teste Rápido")
    cfg_bytes = st.session_state.get("__cfg_bytes")
    cfg_name = st.session_state.get("__cfg_name")
    cfg_source_label = st.session_state.get("__cfg_label")

    if cfg_bytes:
        st.caption(f"Usando configuração: **{cfg_source_label}** — {cfg_name}")
    else:
        st.caption("Sem configuração carregada.")

    st.session_state.setdefault("__quick_dirty", False)
    st.session_state.setdefault("prev_cfg_hash", None)
    st.session_state.setdefault("prev_sample_text", "")
    st.session_state.setdefault("prev_profiles_version", 0)

    def _mark_quick_dirty():
        st.session_state["__quick_dirty"] = True

    st.text_area(
        "Cole um relato para testar:",
        height=160,
        key="sample_text",
        on_change=_mark_quick_dirty,
    )

    def _md5_bytes(b: Optional[bytes]) -> str:
        import hashlib as _h
        return _h.md5(b).hexdigest() if b else ""

    cfg_hash = _md5_bytes(cfg_bytes)
    prev_hash = st.session_state.get("prev_cfg_hash")
    prev_text = st.session_state.get("prev_sample_text") or ""
    current_text = st.session_state.get("sample_text") or ""
    profiles_version = st.session_state.get("__profiles_version", 0)
    prev_profiles_version = st.session_state.get("prev_profiles_version", 0)
    text_col = st.session_state.get("__text_col", "texto")

    should_run_quick = False
    if cfg_bytes and current_text.strip():
        if st.session_state.get("__quick_dirty"): should_run_quick = True
        elif prev_hash != cfg_hash: should_run_quick = True
        elif prev_text != current_text: should_run_quick = True
        elif prev_profiles_version != profiles_version: should_run_quick = True

    if should_run_quick:
        st.session_state["__quick_dirty"] = False
        st.session_state["prev_cfg_hash"] = cfg_hash
        st.session_state["prev_sample_text"] = current_text
        st.session_state["prev_profiles_version"] = profiles_version
        try:
            row, _df, html_orig, _html_norm, counts, _ = quick_test_highlight(
                current_text, text_col, cfg_bytes, cfg_name
            )
            decision = (row.get("decision") or "").upper()
            badge_cls = "badge-exc"
            if decision == "INCLUI": badge_cls = "badge-inc"
            elif decision == "REVISA": badge_cls = "badge-rev"

            st.markdown(
                f"""
                <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
                  <span class="badge {badge_cls}">{decision or "-"}</span>
                  <span><b>Score:</b> {row.get("score_total"):.2f}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("### Texto com realce (original)")
            st.markdown(html_orig, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Positivos", counts.get("positivos", 0))
            c2.metric("Negativos", counts.get("negativos", 0))
            c3.metric("Contextos", counts.get("contextos", 0))
        except Exception as e:
            st.error(f"Erro no Teste Rápido: {e}")
    elif not cfg_bytes:
        st.info("Escolha **Perfil** ou envie um **YAML** na barra lateral para usar no Teste Rápido.")

elif active == "Perfis":
    render_profiles_tab()

elif active == "Resultado":
    render_result_tab()

else:  # "Ajuda"
 render_help()
