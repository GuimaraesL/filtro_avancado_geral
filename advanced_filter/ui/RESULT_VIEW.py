# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import tempfile
from io import BytesIO
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st

# Dependências internas do app
from advanced_filter.ui.controller import read_table_compat
from advanced_filter.engine import run_filter


# ------------------ Helpers de estado ------------------ #
RESULT_BYTES_KEY = "__result_bytes"
RESULT_NAME_KEY = "__result_filename"
RESULT_READY_KEY = "__result_ready"
PROCESSING_KEY = "__processing"
EXEC_REQ_KEY = "__exec_requested"
SNAPSHOT_KEY = "__exec_snapshot"
LAST_DF_KEY = "last_result_df"

def _clear_previous_result() -> None:
    """Remove qualquer artefato de resultados anteriores (bytes, df, flags)."""
    st.session_state.pop(RESULT_BYTES_KEY, None)
    st.session_state.pop(RESULT_NAME_KEY, None)
    st.session_state.pop(LAST_DF_KEY, None)
    st.session_state[RESULT_READY_KEY] = False

def mark_processing(snapshot: Dict[str, Any]) -> None:
    """Marca início de processamento e apaga visuais/bytes antigos."""
    _clear_previous_result()
    st.session_state[PROCESSING_KEY] = True
    st.session_state[EXEC_REQ_KEY] = True
    st.session_state[SNAPSHOT_KEY] = snapshot

def finish_processing(success: bool) -> None:
    """Finaliza flags de processamento."""
    st.session_state[PROCESSING_KEY] = False
    st.session_state[EXEC_REQ_KEY] = False
    st.session_state[RESULT_READY_KEY] = bool(success)


# ------------------ Render da aba Resultado ------------------ #
def render_result_tab() -> None:
    """
    UI da aba Resultado. Controla três estados:
      1) PROCESSANDO         -> mostra spinner e oculta conteúdos antigos
      2) RESULTADO DISPONÍVEL-> mostra grid + botão download (com bytes prontos)
      3) SEM RESULTADO       -> instrução para executar filtro
    E executa o filtro quando EXEC_REQ_KEY=True, gerando bytes de download
    de forma atômica (só habilita botão quando terminar).
    """
    st.markdown("### Resultado")

    processing = st.session_state.get(PROCESSING_KEY, False)
    exec_requested = st.session_state.get(EXEC_REQ_KEY, False)
    has_prev = (st.session_state.get(RESULT_READY_KEY, False)
                and st.session_state.get(RESULT_BYTES_KEY) is not None
                and st.session_state.get(LAST_DF_KEY) is not None)

    # Se estamos processando, NÃO exibe nada antigo
    if processing:
        with st.spinner("Processando… O conteúdo anterior foi ocultado até a conclusão."):
            # Se também foi sinalizado para executar agora, roda aqui
            if exec_requested:
                _run_once_and_prepare_download()
        # Após _run_once..., o flag processing cai para False.
        return

    # Se não está processando e temos resultado anterior pronto
    if has_prev:
        result = st.session_state[LAST_DF_KEY]
        st.success("Mostrando o último resultado gerado.")
        st.dataframe(result.head(200), use_container_width=True)
        st.download_button(
            "Baixar resultado (.xlsx)",
            st.session_state[RESULT_BYTES_KEY],
            file_name=st.session_state.get(RESULT_NAME_KEY, "resultado_filtrado.xlsx"),
            use_container_width=True,
            key="__download_result_ready"
        )
        return

    # Caso não haja nada ainda
    st.info("Use **Executar filtro** na barra lateral para processar o arquivo.")


def _run_once_and_prepare_download() -> None:
    """
    Executa o filtro UMA vez usando o snapshot salvo na sessão e prepara
    o Excel para download. Em caso de erro, limpa flags e não habilita o botão.
    """
    try:
        snapshot = st.session_state.get(SNAPSHOT_KEY) or {}
        cfg_bytes = st.session_state.get("__cfg_bytes")
        data_bytes = st.session_state.get("__last_data_bytes")
        if not data_bytes or not cfg_bytes:
            finish_processing(False)
            st.warning("Arquivo ou configuração ausentes. Clique novamente em **Executar filtro**.")
            return

        text_col = snapshot.get("text_col") or st.session_state.get("__text_col", "texto")
        selected_sheet = snapshot.get("sheet")
        out_name = snapshot.get("outname") or (st.session_state.get("__outname") or "resultado_filtrado.xlsx")

        # Grava o upload temporariamente e lê com compat util (suporta CSV/Excel)
        suffix = os.path.splitext(snapshot.get("filename", "data.xlsx"))[-1] or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data_bytes or b"")
            tmp.flush()
            data_path = tmp.name

        try:
            df = read_table_compat(data_path, sheet=selected_sheet)
        except Exception as e:
            finish_processing(False)
            st.error(f"Erro ao ler arquivo: {e}")
            return

        try:
            result = run_filter(df, text_col, cfg_bytes)
        except Exception as e:
            finish_processing(False)
            st.error(f"Erro ao executar filtro: {e}")
            return

        # Guarda DataFrame no estado
        st.session_state[LAST_DF_KEY] = result.copy()

        # Gera bytes de Excel
        try:
            out_buf = BytesIO()
            with pd.ExcelWriter(out_buf, engine="xlsxwriter") as writer:
                result.to_excel(writer, index=False, sheet_name="Resultado")
            out_buf.seek(0)
            st.session_state[RESULT_BYTES_KEY] = out_buf.getvalue()
            st.session_state[RESULT_NAME_KEY] = out_name
            finish_processing(True)
            st.success("Filtro executado com sucesso.")
            st.dataframe(result.head(200), use_container_width=True)
            st.download_button(
                "Baixar resultado (.xlsx)",
                st.session_state[RESULT_BYTES_KEY],
                file_name=out_name,
                use_container_width=True,
                key="__download_result_fresh"
            )
        except Exception as e:
            finish_processing(False)
            st.warning(f"Resultado exibido, mas não foi possível preparar o arquivo para download: {e}")
            st.dataframe(result.head(200), use_container_width=True)

    except Exception as e:
        # Falha inesperada: encerra processamento e não mostra artefatos antigos
        finish_processing(False)
        st.error(f"Falha inesperada: {e}")
