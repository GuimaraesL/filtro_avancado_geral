# -*- coding: utf-8 -*-
import os
import hashlib
import tempfile
from io import BytesIO
from typing import Optional, List

import pandas as pd
import streamlit as st

# Imports absolutos do pacote (sem relativos)
from advanced_filter.engine import run_filter
from advanced_filter.ui.controller import (
    is_excel_name,
    list_sheets_from_bytes,
    list_columns_from_bytes,
    read_table_compat,
    quick_test_highlight,
)
from advanced_filter.ui.state import ensure_bootstrap
from advanced_filter.ui.views_profiles import (
    render_sidebar_profile_selector,
    render_profiles_tab,
)

# --------------------------------------------------------------------
# Config da página e bootstrap de estado
# --------------------------------------------------------------------
st.set_page_config(page_title="Filtro Avançado por Contexto (Config)", layout="wide")
ensure_bootstrap()

def inject_highlight_css():
    st.markdown(
        """
        <style>
        /* Destaques no texto */
        .hl-pos{ background: rgba(46,125,50,.35); padding: 0 .15em; border-radius: .25rem; }
        .hl-neg{ background: rgba(198,40,40,.35); padding: 0 .15em; border-radius: .25rem; }
        .hl-ctx{ background: rgba(21,101,192,.35); padding: 0 .15em; border-radius: .25rem; }

        /* Badges de decisão */
        .badge{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:600; font-size:.8rem; }
        .badge-inc{ background:#2e7d32; color:#fff; }
        .badge-exc{ background:#c62828; color:#fff; }
        .badge-rev{ background:#616161; color:#fff; }
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_highlight_css()

def _md5(b: Optional[bytes]) -> str:
    if not b:
        return ""
    return hashlib.md5(b).hexdigest()

# --------------------------------------------------------------------
# SIDEBAR — Upload de dados, sheet/coluna, fonte da configuração e botão Executar
# --------------------------------------------------------------------
with st.sidebar:
    st.header("Carregar (dados)")
    uploaded_file = st.file_uploader(
        "CSV/Excel (opcional p/ Teste Rápido)",
        type=["csv", "xlsx", "xls", "xlsm"],
        key="__upload_file"
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
        else:
            selected_sheet = None  # CSV não tem sheets

    # ↓↓↓ Coluna de texto (apenas se houver arquivo carregado)
    sidebar_columns = []
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

    # ▶️ Botão Executar filtro
    if st.button("Executar filtro", use_container_width=True, key="__btn_exec_filter"):
        if uploaded_file is None:
            st.warning("Envie um arquivo CSV/Excel para executar o filtro.")
        elif not cfg_bytes:
            st.warning("Escolha um Perfil ou envie um YAML para executar o filtro.")
        else:
            st.session_state["__exec_requested"] = True
            st.session_state["__exec_snapshot"] = {
                "file_hash": _md5(data_bytes),
                "cfg_hash": _md5(cfg_bytes),
                "text_col": st.session_state.get("__text_col", "texto"),
                "sheet": selected_sheet,
                "is_excel": is_excel,
                "outname": st.session_state.get("__outname") or "resultado_filtrado.xlsx",
                "filename": uploaded_file.name if uploaded_file else "",
            }
            st.session_state["__last_data_bytes"] = data_bytes
            # marcar para trocar de aba no fim do render
            st.session_state["__go_result"] = True

# --------------------------------------------------------------------
# TABS (main)
# --------------------------------------------------------------------
tab_quick, tab_profiles, tab_result, tab_help = st.tabs(["Teste Rápido", "Perfis", "Resultado", "Ajuda"])

# ============================================================
# TESTE RÁPIDO
# ============================================================
with tab_quick:
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

    # Quick test — roda quando necessário
    def _md5_bytes(b: Optional[bytes]) -> str:
        return hashlib.md5(b).hexdigest() if b else ""

    cfg_hash = _md5_bytes(cfg_bytes)
    prev_hash = st.session_state.get("prev_cfg_hash")
    prev_text = st.session_state.get("prev_sample_text") or ""
    current_text = st.session_state.get("sample_text") or ""
    profiles_version = st.session_state.get("__profiles_version", 0)
    prev_profiles_version = st.session_state.get("prev_profiles_version", 0)
    text_col = st.session_state.get("__text_col", "texto")

    should_run_quick = False
    if cfg_bytes and current_text.strip():
        if st.session_state.get("__quick_dirty"):
            should_run_quick = True
        elif prev_hash != cfg_hash:
            should_run_quick = True
        elif prev_text != current_text:
            should_run_quick = True
        elif prev_profiles_version != profiles_version:
            should_run_quick = True

    if should_run_quick:
        st.session_state["__quick_dirty"] = False
        st.session_state["prev_cfg_hash"] = cfg_hash
        st.session_state["prev_sample_text"] = current_text
        st.session_state["prev_profiles_version"] = profiles_version
        try:
            row, full_df, html_orig, html_norm, counts, _ = quick_test_highlight(
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
            with st.expander("Ver texto normalizado (para depuração)"):
                st.markdown(html_norm, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Positivos", counts.get("positivos", 0))
            c2.metric("Negativos", counts.get("negativos", 0))
            c3.metric("Contextos", counts.get("contextos", 0))
        except Exception as e:
            st.error(f"Erro no Teste Rápido: {e}")
    elif not cfg_bytes:
        st.info("Escolha **Perfil** ou envie um **YAML** na barra lateral para usar no Teste Rápido.")

# ============================================================
# PERFIS (edição/criação)
# ============================================================
with tab_profiles:
    render_profiles_tab()

# ============================================================
# RESULTADO — processa o arquivo completo (somente após botão)
# ============================================================
with tab_result:
    st.markdown("### Resultado")

    exec_requested = st.session_state.get("__exec_requested", False)
    snapshot = st.session_state.get("__exec_snapshot") or {}

    if not exec_requested and "last_result_df" not in st.session_state:
        st.info("Use **Executar filtro** na barra lateral para processar o arquivo.")
        st.stop()

    cfg_bytes = st.session_state.get("__cfg_bytes")
    text_col = snapshot.get("text_col") or st.session_state.get("__text_col", "texto")
    selected_sheet = snapshot.get("sheet")
    out_name = snapshot.get("outname") or (st.session_state.get("__outname") or "resultado_filtrado.xlsx")

    data_bytes = st.session_state.get("__last_data_bytes")
    if not data_bytes or not cfg_bytes:
        st.warning("Arquivo ou configuração ausentes. Clique novamente em **Executar filtro**.")
        st.stop()

    # gravar temp e ler com util compatível
    suffix = os.path.splitext(snapshot.get("filename", "data.xlsx"))[-1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data_bytes or b"")
        tmp.flush()
        data_path = tmp.name

    try:
        df = read_table_compat(data_path, sheet=selected_sheet)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        st.stop()

    try:
        result = run_filter(df, text_col, cfg_bytes)
    except Exception as e:
        st.error(f"Erro ao executar filtro: {e}")
        st.stop()

    st.session_state["last_result_df"] = result.copy()
    st.session_state["__exec_requested"] = False  # consumido

    st.success("Filtro executado com sucesso.")
    st.dataframe(result.head(200), use_container_width=True)

    # Download como .xlsx
    try:
        out_buf = BytesIO()
        with pd.ExcelWriter(out_buf, engine="xlsxwriter") as writer:
            result.to_excel(writer, index=False, sheet_name="Resultado")
        out_buf.seek(0)
        st.download_button(
            "Baixar resultado (.xlsx)",
            out_buf.getvalue(),
            file_name=out_name,
            use_container_width=True,
            key="__download_result_xlsx"
        )
    except Exception as e:
        st.error(f"Falha ao preparar download: {e}")

# ============================================================
# AJUDA
# ============================================================
with tab_help:
    st.markdown(
        """
        **Dicas rápidas**
        - A **fonte da configuração** (Perfil/YAML) fica na **barra lateral**.
        - A **Coluna de texto** também fica na barra lateral e aparece após carregar um arquivo.
        - O **Teste Rápido** roda quando você altera o texto, muda a config ou salva/edita/exclui um perfil.
        - Para processar o arquivo inteiro, use **Executar filtro** na barra lateral; a tela muda para **Resultado** automaticamente.
        """
    )

# ============================================================
# Troca automática para a aba Resultado (robusta)
# ============================================================
if st.session_state.get("__go_result"):
    st.markdown(
        """
        <script>
        (function clickResultTab(){
          const tryClick = () => {
            try {
              const root = parent.document;
              const tabs = Array.from(root.querySelectorAll('button[role="tab"]'));
              const t = tabs.find(el => el.innerText.trim().startsWith('Resultado'));
              if (t) { t.click(); }
              else { setTimeout(tryClick, 60); }
            } catch (e) {
              setTimeout(tryClick, 60);
            }
          };
          tryClick();
        })();
        </script>
        """,
        unsafe_allow_html=True
    )
    st.session_state["__go_result"] = False
