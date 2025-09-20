# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import tempfile
import hashlib
from io import BytesIO

# Fallbacks (pacote ou script)
try:
    from .excel_io import read_table, write_output
    from .engine import run_filter
    from .ui.controller import (
        is_excel_name, list_sheets_from_bytes, list_columns_from_bytes,
        read_table_compat, autodetect_sheet_by_column,
        quick_test_highlight
    )
    from .ui.state import ensure_bootstrap
    from .ui.views_profiles import render_sidebar_profile_selector, render_profiles_tab
except Exception:
    from advanced_filter.excel_io import read_table, write_output
    from advanced_filter.engine import run_filter
    from advanced_filter.ui.controller import (
        is_excel_name, list_sheets_from_bytes, list_columns_from_bytes,
        read_table_compat, autodetect_sheet_by_column,
        quick_test_highlight
    )
    from advanced_filter.ui.state import ensure_bootstrap
    from advanced_filter.ui.views_profiles import render_sidebar_profile_selector, render_profiles_tab

# ---- rerun seguro (compatível com versões antigas/novas) ----
def _rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

st.set_page_config(page_title="Filtro Avançado por Contexto (Config)", layout="wide")
st.title("🧠 Filtro Avançado por Contexto (Config)")

# Estado básico
ensure_bootstrap(auto_load_from_disk=False)
st.session_state.setdefault("__prefer_results_first", False)
st.session_state.setdefault("__run_clicked", False)

with st.sidebar:
    st.header("Carregar (dados)")
    uploaded_file = st.file_uploader(
        "CSV/Excel (opcional p/ Teste Rápido)",
        type=["csv", "xlsx", "xls", "xlsm"]
    )

    selected_sheet, sheets, data_bytes, is_excel = None, [], None, False
    if uploaded_file is not None:
        data_bytes = uploaded_file.getvalue()
        is_excel = is_excel_name(uploaded_file.name)
        if is_excel:
            sheets = list_sheets_from_bytes(data_bytes)
        if sheets:
            selected_sheet = st.selectbox("Planilha (sheet)", sheets, index=0)

    # Colunas (dropdown ou input)
    columns = []
    if uploaded_file is not None:
        if is_excel and len(sheets) > 1 and not selected_sheet:
            st.info("Selecione a planilha (sheet) para listar as colunas corretas.")
        else:
            preview_sheet = selected_sheet or (sheets[0] if sheets else None)
            columns = list_columns_from_bytes(data_bytes, is_excel, preview_sheet)

    if columns:
        default_idx = columns.index("texto") if "texto" in columns else 0
        text_col = st.selectbox("Coluna de texto", columns, index=default_idx)
    else:
        text_col = st.text_input("Coluna de texto", value="texto")

    # ---------- Configuração (fonte única) ----------
    st.header("Configuração")
    cfg_file = st.file_uploader(
        "YAML (opcional — use se escolher 'YAML' como fonte)",
        type=["yaml", "yml"]
    )
    cfg_bytes, cfg_name, cfg_source_label = render_sidebar_profile_selector(cfg_file)

    out_name = st.text_input("Nome do arquivo de saída", value="saida.xlsx")

    # Botão: Executar filtro (e ir para Resultado)
    if st.button("Executar filtro"):
        st.session_state["__run_clicked"] = True
        st.session_state["__prefer_results_first"] = True
        _rerun()

# ------------- Tabs (ordem muda para priorizar Resultado após rodar) -------------
def build_tabs():
    if st.session_state.get("__prefer_results_first"):
        tabs = st.tabs(["Resultado", "Teste Rápido", "Perfis", "Ajuda"])
        return {"result": tabs[0], "quick": tabs[1], "profiles": tabs[2], "help": tabs[3]}
    else:
        tabs = st.tabs(["Teste Rápido", "Perfis", "Resultado", "Ajuda"])
        return {"quick": tabs[0], "profiles": tabs[1], "result": tabs[2], "help": tabs[3]}

tabs = build_tabs()

# ==========================
# TESTE RÁPIDO (auto ao digitar/colar e quando a config muda)
# ==========================
with tabs["quick"]:
    st.subheader("Teste Rápido")
    st.caption(f"Usando configuração: **{cfg_source_label}** — {cfg_name}")

    # flags
    st.session_state.setdefault("__quick_dirty", False)
    st.session_state.setdefault("prev_cfg_hash", None)
    st.session_state.setdefault("prev_sample_text", "")

    # callback para marcar sujo quando texto muda
    def _mark_quick_dirty():
        st.session_state["__quick_dirty"] = True

    sample = st.text_area(
        "Cole um relato para testar:",
        height=140,
        key="sample_text",
        on_change=_mark_quick_dirty,
    )

    def render_quick(sample_text: str):
        row, full_df, html_orig, html_norm, counts, _ = quick_test_highlight(
            sample_text, text_col, cfg_bytes, cfg_name
        )
        decision = (row.get("decision") or "").upper()
        badge_cls = "badge-exc"
        if decision == "INCLUI": badge_cls = "badge-inc"
        elif decision == "REVISA": badge_cls = "badge-rev"

        st.markdown(
            f"""
            <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
              <span class="badge {badge_cls}">{decision or "-"}</span>
              <span><b>Categoria:</b> {row.get("categoria") or "-"}</span>
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
        with st.expander("Auditoria e regra aplicada", expanded=True):
            st.write("**Regra disparada:**", row.get("rule_fired", "") or "-")
            st.write("**Motivo (auditoria):**"); st.info(row.get("audit", ""))
        with st.expander("Registro completo (linha processada)"):
            st.dataframe(full_df)

    # decidir quando rodar
    cfg_hash = hashlib.sha1(cfg_bytes or b"").hexdigest() if cfg_bytes else None
    config_changed = cfg_hash != st.session_state["prev_cfg_hash"]
    sample_changed  = (st.session_state.get("sample_text") or "") != st.session_state["prev_sample_text"]

    should_run = cfg_bytes is not None and (
        st.session_state["__quick_dirty"] or
        config_changed or
        sample_changed
    ) and (st.session_state.get("sample_text") or "").strip() != ""

    if should_run:
        st.session_state["__quick_dirty"] = False
        st.session_state["prev_cfg_hash"]  = cfg_hash
        st.session_state["prev_sample_text"] = st.session_state.get("sample_text") or ""
        try:
            render_quick(st.session_state["sample_text"])
        except Exception as e:
            st.error(f"Erro no Teste Rápido: {e}")
    elif not cfg_bytes:
        st.info("Escolha **Perfil** ou envie um **YAML** na barra lateral para usar no Teste Rápido.")

# ==========================
# PERFIS
# ==========================
with tabs["profiles"]:
    render_profiles_tab()

# ==========================
# RESULTADO (processamento do arquivo)
# ==========================
with tabs["result"]:
    st.subheader("Saída")
    if st.session_state.pop("__run_clicked", False):
        if uploaded_file and cfg_bytes:
            with tempfile.TemporaryDirectory() as tdir:
                data_path = os.path.join(tdir, uploaded_file.name)
                with open(data_path, "wb") as f:
                    f.write(data_bytes if data_bytes is not None else uploaded_file.read())

                cfg_path = os.path.join(tdir, cfg_name or "config.yaml")
                with open(cfg_path, "wb") as f:
                    f.write(cfg_bytes)

                if is_excel and not selected_sheet:
                    tmp_sheets = sheets or list_sheets_from_bytes(data_bytes)
                    det, msg = autodetect_sheet_by_column(data_path, tmp_sheets, text_col)
                    if det:
                        selected_sheet = det
                        st.info(msg)
                    elif msg == "ambiguidade":
                        st.warning(f"Mais de uma aba possui a coluna '{text_col}'. Selecione a planilha correta na barra lateral.")
                        st.stop()
                    else:
                        st.error(f"Nenhuma aba contém a coluna '{text_col}'. Verifique o nome da coluna ou selecione outra planilha.")
                        st.stop()

                df = read_table_compat(data_path, sheet=selected_sheet)
                if text_col not in df.columns:
                    st.error(f"A coluna '{text_col}' não foi encontrada na planilha selecionada.")
                    st.stop()

                result = run_filter(df, text_col, cfg_path)

                st.success("Processado!")
                st.write("**Incluídos**"); st.dataframe(result["incluidos"].head(200))
                st.write("**Revisar**");   st.dataframe(result["revisar"].head(200))
                st.write("**Excluídos**"); st.dataframe(result["excluidos"].head(200))

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as xw:
                    result["incluidos"].to_excel(xw, index=False, sheet_name="Incluidos")
                    result["revisar"].to_excel(xw, index=False, sheet_name="Revisar")
                    result["excluidos"].to_excel(xw, index=False, sheet_name="Excluidos_do_Filtro")
                st.download_button("Baixar Excel", buffer.getvalue(), file_name=out_name)
        else:
            if not uploaded_file:
                st.error("Nenhum CSV/Excel carregado.")
            if not cfg_bytes:
                st.error("Nenhuma configuração ativa (Perfil/YAML).")

    # após exibir resultado, voltamos à ordem normal
    st.session_state["__prefer_results_first"] = False

# ==========================
# AJUDA
# ==========================
with tabs["help"]:
    st.markdown(
        '''
        **Dicas rápidas**
        - Sidebar: escolha **uma única fonte** (Perfil ou YAML). Sem perfis → usamos **YAML** automaticamente.
        - **Teste Rápido** roda quando você cola/edita o texto e quando a configuração muda.
        - **Executar filtro** processa o arquivo e abre a aba **Resultado** automaticamente.
        - Na aba **Perfis**, o editor só aparece durante criação/edição. **Cancelar** fecha na hora.
        '''
    )
