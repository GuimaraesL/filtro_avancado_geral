# -*- coding: utf-8 -*-
import streamlit as st

def rerun_safe():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass
