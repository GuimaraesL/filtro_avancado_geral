# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from ..profiles import make_default_profile, profile_to_yaml_bytes, set_profile
from .common import rerun_safe

def _textarea_lines(label: str, value_list, key: str):
    txt = "\n".join(value_list or [])
    out = st.text_area(label, value=txt, height=140, key=key)
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    return lines

def render_create_tab():
    st.session_state.setdefault("__creating", False)
    st.session_state.setdefault("__create_draft", None)

    if not st.session_state["__creating"]:
        st.info("Clique no botão abaixo para iniciar a criação de um novo perfil (modo básico).")
        if st.button("Criar novo perfil", use_container_width=True, key="btn_create_open_basic"):
            st.session_state["__creating"] = True
            st.session_state["__create_draft"] = make_default_profile("Novo Perfil")
            rerun_safe()
        return

    draft = dict(st.session_state["__create_draft"] or make_default_profile("Novo Perfil"))

    with st.form("form_create_basic", clear_on_submit=False):
        c1, c2 = st.columns([2,1])
        with c1:
            draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or "Novo Perfil", key="create_name")
        with c2:
            draft["window"] = st.number_input(
                "Janela de proximidade (tokens)",
                min_value=1, value=int(draft.get("window", 8)), step=1, key="create_window"
            )

        st.markdown("#### Opções")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key="create_lower"
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key="create_strip"
            )
        with c3:
            draft["require_context"] = st.checkbox(
                "Exigir contexto", value=bool(draft.get("require_context", False)), key="create_reqctx"
            )
        with c4:
            draft["negative_wins_ties"] = st.checkbox(
                "Negativo vence empate", value=bool(draft.get("negative_wins_ties", True)), key="create_negwins"
            )

        c1, c2 = st.columns(2)
        with c1:
            draft["min_pos_to_include"] = st.number_input(
                "Mín. positivos p/ incluir", min_value=1,
                value=int(draft.get("min_pos_to_include", 1)), key="create_minpos"
            )
        with c2:
            draft["min_neg_to_exclude"] = st.number_input(
                "Mín. negativos p/ excluir", min_value=1,
                value=int(draft.get("min_neg_to_exclude", 1)), key="create_minneg"
            )

        st.markdown("#### Vocabulário")
        draft["positives"] = _textarea_lines("Positivas (1 por linha)", draft.get("positives"), key="create_pos")
        draft["negatives"] = _textarea_lines("Negativas (1 por linha)", draft.get("negatives"), key="create_neg")
        draft["contexts"]  = _textarea_lines("Contextos (1 por linha)",  draft.get("contexts"),  key="create_ctx")

        # mantém o rascunho atualizado durante a sessão (útil para baixar antes de salvar)
        st.session_state["__create_draft"] = draft

        saved = st.form_submit_button("Salvar perfil", use_container_width=True)
        canceled = st.form_submit_button("Cancelar", use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Baixar YAML do rascunho",
            profile_to_yaml_bytes(draft),
            file_name=f"{draft['name']}.yaml",
            use_container_width=True,
            key="btn_create_download_yaml_basic"
        )
    with c2:
        if st.button("Fechar editor", use_container_width=True, key="btn_create_close_basic"):
            st.session_state["__creating"] = False
            st.session_state["__create_draft"] = None
            rerun_safe()

    if saved:
        set_profile(draft["name"], draft)
        st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
        st.success(f"Perfil criado: {draft['name']}")
        st.session_state["__creating"] = False
        st.session_state["__create_draft"] = None
        rerun_safe()

    if canceled:
        st.info("Criação cancelada.")
        st.session_state["__creating"] = False
        st.session_state["__create_draft"] = None
        rerun_safe()
