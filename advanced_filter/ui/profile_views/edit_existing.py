# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from ..profiles import get_profiles, set_profile, profile_to_yaml_bytes

def _rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def _textarea_lines(label: str, value_list, key: str):
    txt = "\n".join(value_list or [])
    out = st.text_area(label, value=txt, height=140, key=key)
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    return lines

def render_edit_existing_tab():
    st.session_state.setdefault("__existing_open", False)
    st.session_state.setdefault("__existing_name", "")

    profiles = get_profiles()
    names = sorted(profiles.keys())

    if not names:
        st.info("Nenhum perfil salvo. Crie um na aba *Criar* ou importe um arquivo na aba *Arquivo YAML*.")
        return

    if not st.session_state["__existing_open"]:
        name = st.selectbox("Escolha um perfil para editar", names, index=0, key="sel_existing_name_basic")
        c1, c2, _ = st.columns([1,1,2])
        with c1:
            if st.button("Editar", use_container_width=True, key="btn_existing_open_basic"):
                st.session_state["__existing_open"] = True
                st.session_state["__existing_name"] = name
                _rerun()
        with c2:
            st.download_button(
                "Baixar YAML",
                profile_to_yaml_bytes(profiles[name]),
                file_name=f"{name}.yaml",
                use_container_width=True,
                key="btn_existing_download_yaml_basic"
            )
        return

    editing_name = st.session_state["__existing_name"]
    draft = dict(profiles.get(editing_name) or {})
    st.markdown(f"#### Editando: **{editing_name}**")

    with st.form("form_edit_existing_basic", clear_on_submit=False):
        c1, c2 = st.columns([2,1])
        with c1:
            draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or editing_name, key="edit_name")
        with c2:
            draft["window"] = st.number_input("Janela (tokens)", min_value=1, value=int(draft.get("window", 8)), step=1, key="edit_window")

        st.markdown("#### Opções")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key="edit_lower"
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key="edit_strip"
            )
        with c3:
            draft["require_context"] = st.checkbox(
                "Exigir contexto", value=bool(draft.get("require_context", False)), key="edit_reqctx"
            )
        with c4:
            draft["negative_wins_ties"] = st.checkbox(
                "Negativo vence empate", value=bool(draft.get("negative_wins_ties", True)), key="edit_negwins"
            )

        c1, c2 = st.columns(2)
        with c1:
            draft["min_pos_to_include"] = st.number_input(
                "Mín. positivos p/ incluir", min_value=1,
                value=int(draft.get("min_pos_to_include", 1)), key="edit_minpos"
            )
        with c2:
            draft["min_neg_to_exclude"] = st.number_input(
                "Mín. negativos p/ excluir", min_value=1,
                value=int(draft.get("min_neg_to_exclude", 1)), key="edit_minneg"
            )

        st.markdown("#### Vocabulário")
        draft["positives"] = _textarea_lines("Positivas (1 por linha)", draft.get("positives"), key="edit_pos")
        draft["negatives"] = _textarea_lines("Negativas (1 por linha)", draft.get("negatives"), key="edit_neg")
        draft["contexts"]  = _textarea_lines("Contextos (1 por linha)",  draft.get("contexts"),  key="edit_ctx")

        saved = st.form_submit_button("Salvar alterações", use_container_width=True)
        canceled = st.form_submit_button("Cancelar edição", use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "Baixar YAML do rascunho",
            profile_to_yaml_bytes(draft),
            file_name=f"{draft['name']}.yaml",
            use_container_width=True,
            key="btn_existing_download_draft_basic"
        )
    with c2:
        if st.button("Excluir perfil", use_container_width=True, key="btn_existing_delete_basic"):
            if editing_name in profiles:
                del profiles[editing_name]
            st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
            st.warning(f"Perfil '{editing_name}' excluído.")
            st.session_state["__existing_open"] = False
            _rerun()
    with c3:
        if st.button("Fechar editor", use_container_width=True, key="btn_existing_close_basic"):
            st.session_state["__existing_open"] = False
            _rerun()

    if saved:
        new_name = draft["name"]
        set_profile(new_name, draft)
        st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
        if editing_name != new_name and editing_name in profiles:
            del profiles[editing_name]
        st.success(f"Perfil salvo: {new_name}")
        st.session_state["__existing_open"] = False
        _rerun()

    if canceled:
        st.info("Edição cancelada.")
        st.session_state["__existing_open"] = False
        _rerun()
