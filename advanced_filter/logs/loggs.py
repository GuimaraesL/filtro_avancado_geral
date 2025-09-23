# logs/loggs.py
# -*- coding: utf-8 -*-
"""
Lightweight logging utilities for Streamlit apps:
- RotatingFileHandler -> logs/app.log
- Session and render sequence context (to trace reruns)
- Helpers: mark_event, log_state, trace, safe_rerun
"""

from __future__ import annotations
import logging
import os
import sys
import time
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Iterable, Optional

# ---------- Global logger config ----------
_LOGGERS: Dict[str, logging.Logger] = {}
_LOG_DIR = os.path.join(os.getcwd(), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_MAX_BYTES = 1_000_000  # ~1MB
_BACKUP_COUNT = 5

def _ensure_handlers(level: int = logging.DEBUG) -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    if getattr(root, "__streamlit_handlers_configured__", False):
        return
    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(_LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.setLevel(level)

    root.addHandler(fh)
    root.addHandler(ch)
    root.__streamlit_handlers_configured__ = True  # type: ignore[attr-defined]

def get_logger(name: str = "app") -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]
    _ensure_handlers()
    lg = logging.getLogger(name)
    lg.propagate = True
    _LOGGERS[name] = lg
    return lg

# ---------- Session / render context ----------
try:
    import streamlit as st  # type: ignore
except Exception:
    st = None  # type: ignore

SESSION_ID_KEY = "__log_session_id"
RENDER_SEQ_KEY  = "__log_render_seq"
RENDER_TS_KEY   = "__log_render_ts"

def _ss_get(key: str, default: Any = None) -> Any:
    if st is None:
        return default
    return st.session_state.get(key, default)

def _ss_set(key: str, value: Any) -> None:
    if st is None:
        return
    st.session_state[key] = value

def get_session_id() -> str:
    sid = _ss_get(SESSION_ID_KEY)
    if not sid:
        sid = str(uuid.uuid4())
        _ss_set(SESSION_ID_KEY, sid)
    return sid

def bump_render_seq(logger: Optional[logging.Logger] = None) -> int:
    seq = int(_ss_get(RENDER_SEQ_KEY, 0)) + 1
    _ss_set(RENDER_SEQ_KEY, seq)
    _ss_set(RENDER_TS_KEY, time.time())
    if logger:
        logger.debug(f"render_start seq={seq} sid={get_session_id()}")
    return seq

def get_render_seq() -> int:
    return int(_ss_get(RENDER_SEQ_KEY, 0))

# ---------- Helpers ----------
def _fmt(d: Dict[str, Any]) -> str:
    parts = []
    for k, v in d.items():
        try:
            s = str(v)
        except Exception:
            s = "<unrepr>"
        parts.append(f"{k}={s}")
    return " | " + " | ".join(parts)

def mark_event(logger: logging.Logger, event: str, **kwargs: Any) -> None:
    sid = get_session_id()
    seq = get_render_seq()
    payload = {"event": event, "sid": sid, "seq": seq, **kwargs}
    logger.info(_fmt(payload))

def log_state(logger: logging.Logger, keys: Optional[Iterable[str]] = None, prefix: str = "state") -> None:
    if st is None:
        return
    if keys is None:
        keys = [
            "__processing", "__result_ready", "__exec_requested", "__go_result",
            "__cfg_name", "__cfg_label", "__text_col", "__sheet_select",
            "__outname", "__upload_file", "__last_data_bytes", "__cfg_bytes"
        ]
    snapshot: Dict[str, Any] = {}
    for k in keys:
        v = st.session_state.get(k, None)
        if isinstance(v, (bytes, bytearray)) and len(v) > 32:
            snapshot[k] = f"<bytes:{len(v)}>"
        else:
            snapshot[k] = v
    mark_event(logger, prefix, **snapshot)

def trace(logger: logging.Logger, name: str):
    def _decor(fn):
        def _wrap(*args, **kwargs):
            sid = get_session_id()
            seq = get_render_seq()
            t0 = time.time()
            logger.debug(_fmt({"event": f"{name}:start", "sid": sid, "seq": seq}))
            try:
                return fn(*args, **kwargs)
            finally:
                dt = (time.time() - t0) * 1000
                logger.debug(_fmt({"event": f"{name}:end", "sid": sid, "seq": seq, "ms": round(dt, 2)}))
        return _wrap
    return _decor

def safe_rerun(logger: logging.Logger, reason: str = "") -> None:
    mark_event(logger, "request_rerun", reason=reason)
    if st is not None:
        st.rerun()
