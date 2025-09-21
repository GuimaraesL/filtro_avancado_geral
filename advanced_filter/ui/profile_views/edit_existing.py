# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st

from ..profiles import profile_to_yaml_bytes
from ..state import get_profiles, set_profile

def _rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def render_edit_existing_tab():
    st.session_state.setdefault("__existing_open", False)
    st.session_state.setdefault("__existing_name", "")

    profiles = get_profiles()
    names = sorted(profiles.keys())

    if not names:
        st.info("Nenhum perfil salvo. Crie um na aba *Criar* ou importe um arquivo na aba *Arquivo YAML*.")
        return

    if not st.session_state["__existing_open"]:
        name = st.selectbox("Escolha um perfil para editar", names, index=0, key="sel_existing_name")
        c1, c2, _ = st.columns([1,1,2])
        with c1:
            if st.button("Editar", use_container_width=True, key="btn_existing_open"):
                st.session_state["__existing_open"] = True
                st.session_state["__existing_name"] = name
                _rerun()
        with c2:
            st.download_button(
                "Baixar YAML",
                profile_to_yaml_bytes(profiles[name]),
                file_name=f"{name}.yaml",
                use_container_width=True,
                key="btn_existing_download_yaml"
            )
        return

    # Editor aberto
    editing_name = st.session_state["__existing_name"]
    draft = dict(profiles.get(editing_name) or {})
    st.markdown(f"#### Editando: **{editing_name}**")

    # ====== FORM (sem download_button dentro) ======
    with st.form("form_edit_existing", clear_on_submit=False):
        c1, c2 = st.columns([2,1])
        with c1:
            draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or editing_name, key="edit_name")
        with c2:
            st.write(" ")

        st.markdown("#### Normalização e janela")
        c1, c2, c3 = st.columns(3)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key="edit_lowercase"
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key="edit_strip"
            )
        with c3:
            draft["window"] = st.number_input(
                "window (janela tokens)", value=int(draft.get("window") or 8), min_value=1, step=1, key="edit_window"
            )

        st.markdown("#### Positivos")
        draft["positives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("positives_text") or "", height=120, key="edit_pos"
        )

        st.markdown("#### Negativos")
        draft["negatives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("negatives_text") or "", height=100, key="edit_neg"
        )

        st.markdown("#### Grupos de Contexto")
        st.caption("Colunas: group, category, patterns (múltiplos por linha, vírgula ou ';').")
        ctx_df = pd.DataFrame(draft.get("contexts_rows") or [{"group":"","category":"","patterns":""}])
        ctx_df = st.data_editor(ctx_df, num_rows="dynamic", use_container_width=True, key="edit_ctx")
        draft["contexts_rows"] = ctx_df.to_dict(orient="records")

        st.markdown("#### Regras")
        st.caption("Decisão ∈ {INCLUI, REVISA, EXCLUI}. min_score e assign_category são opcionais.")
        rules_df = pd.DataFrame(draft.get("rules_rows") or [{
            "name":"","equation":"","decision":"REVISA","min_score":None,"assign_category":""
        }])
        rules_df = st.data_editor(rules_df, num_rows="dynamic", use_container_width=True, key="edit_rules")
        draft["rules_rows"] = rules_df.to_dict(orient="records")

        # ⚠️ sem 'key' (compat Streamlit)
        saved = st.form_submit_button("Salvar alterações", use_container_width=True)
        canceled = st.form_submit_button("Cancelar edição", use_container_width=True)

    # ====== AÇÕES FORA DO FORM ======
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.download_button(
            "Baixar YAML do rascunho",
            profile_to_yaml_bytes(draft),
            file_name=f"{draft['name']}.yaml",
            use_container_width=True,
            key="btn_existing_download_draft"
        )
    with c2:
        if st.button("Excluir perfil", use_container_width=True, key="btn_existing_delete"):
            if editing_name in profiles:
                del profiles[editing_name]
            st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
            st.warning(f"Perfil '{editing_name}' excluído.")
            st.session_state["__existing_open"] = False
            _rerun()
    with c3:
        if st.button("Fechar editor", use_container_width=True, key="btn_existing_close"):
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
