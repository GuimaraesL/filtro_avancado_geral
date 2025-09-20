# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st

from ..profiles import make_default_profile, profile_to_yaml_bytes
from ..state import set_profile
from .common import rerun_safe

def render_create_tab():
    """Fluxo de criação de perfil. Editor só aparece após clicar."""
    st.session_state.setdefault("__creating", False)
    st.session_state.setdefault("__create_draft", None)

    if not st.session_state["__creating"]:
        st.info("Clique no botão abaixo para iniciar a criação de um novo perfil.")
        if st.button("➕ Criar perfil", key="__btn_create_start"):
            st.session_state["__creating"] = True
            st.session_state["__create_draft"] = make_default_profile("Novo Perfil")
            try: st.toast("Criando novo perfil…", icon="✨")
            except Exception: pass
            rerun_safe()
        return

    # Editor de criação
    draft = st.session_state["__create_draft"] or make_default_profile("Novo Perfil")
    st.markdown("### Novo perfil")

    with st.form("create_form"):
        draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or "Novo Perfil")
        c1, c2, c3 = st.columns(3)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True))
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True))
            )
        with c3:
            draft["window"] = st.number_input(
                "window (janela tokens)", value=int(draft.get("window") or 8), min_value=1, step=1
            )

        st.markdown("#### Positivos")
        draft["positives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("positives_text") or "", height=120
        )

        st.markdown("#### Negativos")
        draft["negatives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("negatives_text") or "", height=100
        )

        st.markdown("#### Grupos de Contexto")
        st.caption("Colunas: group, category, patterns (múltiplos por linha, vírgula ou ';').")
        ctx_df = pd.DataFrame(draft.get("contexts_rows") or [{"group":"","category":"","patterns":""}])
        ctx_df = st.data_editor(ctx_df, num_rows="dynamic", use_container_width=True, key="create_ctx_editor")
        draft["contexts_rows"] = ctx_df.to_dict(orient="records")

        st.markdown("#### Regras")
        st.caption("Decisão ∈ {INCLUI, REVISA, EXCLUI}. min_score e assign_category são opcionais.")
        rules_df = pd.DataFrame(draft.get("rules_rows") or [{"name":"","equation":"","decision":"REVISA","min_score":None,"assign_category":""}])
        rules_df = st.data_editor(rules_df, num_rows="dynamic", use_container_width=True, key="create_rules_editor")
        draft["rules_rows"] = rules_df.to_dict(orient="records")

        csave, ccancel = st.columns([1,1])
        saved   = csave.form_submit_button("Salvar")
        canceled= ccancel.form_submit_button("Cancelar")

    st.download_button(
        "Baixar YAML do rascunho",
        profile_to_yaml_bytes(draft),
        file_name=f"{draft['name']}.yaml",
        use_container_width=True,
        key="__dl_create_draft"
    )

    if saved:
        name = draft["name"]
        set_profile(name, draft)
        st.success(f"Perfil criado: {name}")
        st.session_state["__creating"] = False
        st.session_state["__create_draft"] = None
        rerun_safe()

    if canceled:
        st.session_state["__creating"] = False
        st.session_state["__create_draft"] = None
        st.info("Criação cancelada.")
        rerun_safe()

