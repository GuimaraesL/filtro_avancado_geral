# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from ..profiles import yaml_bytes_to_profile, profile_to_yaml_bytes, set_profile, make_default_profile

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

def render_edit_file_tab():
    st.session_state.setdefault("__file_open", False)
    st.session_state.setdefault("__file_draft", None)

    if not st.session_state["__file_open"]:
        up = st.file_uploader("Enviar YAML (modo básico)", type=["yaml", "yml"], key="upload_yaml_file_basic")
        if up is None:
            st.info("Envie um arquivo YAML (basic-1) para editar/importar.")
            return
        data = up.getvalue()
        try:
            prof = yaml_bytes_to_profile(data)
        except Exception as e:
            st.error(f"YAML inválido: {e}")
            return
        st.session_state["__file_open"] = True
        st.session_state["__file_draft"] = prof
        _rerun()
        return

    draft = dict(st.session_state["__file_draft"] or make_default_profile("Perfil_importado"))

    with st.form("form_edit_file_basic", clear_on_submit=False):
        c1, c2 = st.columns([2,1])
        with c1:
            draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or "Perfil_importado", key="file_name")
        with c2:
            draft["window"] = st.number_input("Janela (tokens)", min_value=1, value=int(draft.get("window", 8)), step=1, key="file_window")

        st.markdown("#### Opções")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key="file_lower"
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key="file_strip"
            )
        with c3:
            draft["require_context"] = st.checkbox(
                "Exigir contexto", value=bool(draft.get("require_context", False)), key="file_reqctx"
            )
        with c4:
            draft["negative_wins_ties"] = st.checkbox(
                "Negativo vence empate", value=bool(draft.get("negative_wins_ties", True)), key="file_negwins"
            )

        c1, c2 = st.columns(2)
        with c1:
            draft["min_pos_to_include"] = st.number_input(
                "Mín. positivos p/ incluir", min_value=1,
                value=int(draft.get("min_pos_to_include", 1)), key="file_minpos"
            )
        with c2:
            draft["min_neg_to_exclude"] = st.number_input(
                "Mín. negativos p/ excluir", min_value=1,
                value=int(draft.get("min_neg_to_exclude", 1)), key="file_minneg"
            )

        st.markdown("#### Vocabulário")
        draft["positives"] = _textarea_lines("Positivas (1 por linha)", draft.get("positives"), key="file_pos")
        draft["negatives"] = _textarea_lines("Negativas (1 por linha)", draft.get("negatives"), key="file_neg")
        draft["contexts"]  = _textarea_lines("Contextos (1 por linha)",  draft.get("contexts"),  key="file_ctx")

        saved_as_profile = st.form_submit_button("Salvar como Perfil", use_container_width=True)
        canceled = st.form_submit_button("Cancelar", use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Baixar YAML do rascunho",
            profile_to_yaml_bytes(draft),
            file_name=f"{draft['name']}.yaml",
            use_container_width=True,
            key="btn_file_download_yaml_basic"
        )
    with c2:
        if st.button("Fechar editor", use_container_width=True, key="btn_file_close_basic"):
            st.session_state["__file_open"] = False
            st.session_state["__file_draft"] = None
            _rerun()

    if saved_as_profile:
        name = draft["name"] or "Perfil_importado"
        set_profile(name, draft)
        st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
        st.success(f"Perfil salvo: {name}")

    if canceled:
        st.info("Edição cancelada.")
        st.session_state["__file_open"] = False
        st.session_state["__file_draft"] = None
        _rerun()
