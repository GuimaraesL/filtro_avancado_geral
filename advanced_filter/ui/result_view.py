# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import tempfile
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st

# === LOGS ===
from advanced_filter.logs.loggs import get_logger, bump_render_seq, mark_event,trace log_state
_logger = get_logger("result_view")

from advanced_filter.ui.controller import read_table_compat
from advanced_filter.engine import run_filter

# ---- state keys ----
RESULT_BYTES_KEY = "__result_bytes"
RESULT_NAME_KEY  = "__result_filename"
RESULT_READY_KEY = "__result_ready"
PROCESSING_KEY   = "__processing"
EXEC_REQ_KEY     = "__exec_requested"
RUNNING_KEY      = "__engine_running"    # NEW: lock anti-reentrance
SNAPSHOT_KEY     = "__exec_snapshot"
LAST_DF_KEY      = "last_result_df"

def _clear_previous_result() -> None:
    """Drop any previous artifacts (bytes, df, flags)."""
    mark_event(_logger, "clear_previous_result")
    st.session_state.pop(RESULT_BYTES_KEY, None)
    st.session_state.pop(RESULT_NAME_KEY, None)
    st.session_state.pop(LAST_DF_KEY, None)
    st.session_state[RESULT_READY_KEY] = False

def mark_processing(snapshot: Dict[str, Any]) -> None:
    """Start processing and wipe previous visual/bytes."""
    mark_event(_logger, "mark_processing:start")
    log_state(_logger, prefix="mp_before")
    _clear_previous_result()
    st.session_state[PROCESSING_KEY] = True
    st.session_state[EXEC_REQ_KEY] = True
    st.session_state[RUNNING_KEY] = False  # ensure unlocked before starting
    st.session_state[SNAPSHOT_KEY] = snapshot
    mark_event(_logger, "mark_processing:end")
    log_state(_logger, prefix="mp_after")

def finish_processing(success: bool) -> None:
    """Finish processing flags."""
    mark_event(_logger, "finish_processing", success=bool(success))
    st.session_state[PROCESSING_KEY] = False
    st.session_state[EXEC_REQ_KEY] = False
    st.session_state[RUNNING_KEY] = False
    st.session_state[RESULT_READY_KEY] = bool(success)

def _start_engine_once() -> None:
    """
    Transition from 'requested' -> 'running' exactly once.
    This function sets the lock and calls the runner.
    """
    # Set lock and consume the request atomically for this render
    st.session_state[RUNNING_KEY] = True
    st.session_state[EXEC_REQ_KEY] = False
    mark_event(_logger, "engine_start_once")

    # Run synchronously; rerun will be requested inside the function
    _run_and_prepare_download_silent()

def render_result_tab() -> None:
    """
    Result tab UI:
      1) PROCESSING: show only spinner (no old grid/download)
      2) READY:      grid + download
      3) EMPTY:      instructions
    """
    st.markdown("### Resultado")

    processing = bool(st.session_state.get(PROCESSING_KEY, False))
    exec_requested = bool(st.session_state.get(EXEC_REQ_KEY, False))
    running = bool(st.session_state.get(RUNNING_KEY, False))

    has_prev = (
        bool(st.session_state.get(RESULT_READY_KEY, False))
        and st.session_state.get(RESULT_BYTES_KEY) is not None
        and st.session_state.get(LAST_DF_KEY) is not None
    )

    mark_event(
        _logger,
        "render_result_tab",
        processing=processing,
        has_prev=has_prev,
        exec_requested=exec_requested,
        running=running,
    )

    # If there is a queued request and engine is not started, start it ONCE.
    if processing and exec_requested and not running:
        mark_event(_logger, "render_result_tab:arming_engine")
        _start_engine_once()
        # after starting, keep spinner and stop rendering the rest in this run
        st.stop()

    # 1) PROCESSING -> spinner only
    if processing:
        mark_event(_logger, "render_result_tab:processing_spinner")
        with st.spinner("Processando… o conteúdo anterior foi ocultado até a conclusão."):
            pass
        st.stop()

    # 2) READY -> show result
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

    # 3) EMPTY
    st.info("Use **Executar filtro** na barra lateral para processar o arquivo.")

@trace(_logger, "run_and_prepare")
def _run_and_prepare_download_silent() -> None:
    """
    Run the filter and prepare the Excel output.
    At the end, request a rerun so the next render shows the fresh result.
    """
    mark_event(_logger, "run_and_prepare:start")
    log_state(_logger, prefix="run_ctx")

    try:
        snapshot = st.session_state.get(SNAPSHOT_KEY) or {}
        cfg_bytes = st.session_state.get("__cfg_bytes")
        data_bytes = st.session_state.get("__last_data_bytes")
        if not data_bytes or not cfg_bytes:
            finish_processing(False)
            safe_rerun(_logger, reason="missing-inputs")
            return

        text_col = snapshot.get("text_col") or st.session_state.get("__text_col", "texto")
        selected_sheet = snapshot.get("sheet")
        out_name = snapshot.get("outname") or (st.session_state.get("__outname") or "resultado_filtrado.xlsx")

        suffix = os.path.splitext(snapshot.get("filename", "data.xlsx"))[-1] or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data_bytes or b"")
            tmp.flush()
            data_path = tmp.name

        # Read input
        try:
            df = read_table_compat(data_path, sheet=selected_sheet)
        except Exception as e:
            mark_event(_logger, "read_table_compat:error", err=str(e))
            finish_processing(False)
            safe_rerun(_logger, reason="read-error")
            return

        # Engine
        try:
            result = run_filter(df, text_col, cfg_bytes)
        except Exception as e:
            mark_event(_logger, "run_filter:error", err=str(e))
            finish_processing(False)
            safe_rerun(_logger, reason="engine-error")
            return

        # Save DF and bytes
        st.session_state[LAST_DF_KEY] = result.copy()
        try:
            out_buf = BytesIO()
            with pd.ExcelWriter(out_buf, engine="xlsxwriter") as writer:
                result.to_excel(writer, index=False, sheet_name="Resultado")
            out_buf.seek(0)
            st.session_state[RESULT_BYTES_KEY] = out_buf.getvalue()
            st.session_state[RESULT_NAME_KEY] = out_name
            finish_processing(True)
        except Exception as e:
            mark_event(_logger, "xlsx_write:error", err=str(e))
            st.session_state.pop(RESULT_BYTES_KEY, None)
            st.session_state[RESULT_NAME_KEY] = out_name
            finish_processing(False)

        safe_rerun(_logger, reason="processing-finished")

    except Exception as e:
        mark_event(_logger, "run_and_prepare:unhandled", err=str(e))
        finish_processing(False)
        safe_rerun(_logger, reason="processing-exception")
