
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st

def rerun_safe():
    """Rerun compatível com versões antigas/novas do Streamlit."""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass
