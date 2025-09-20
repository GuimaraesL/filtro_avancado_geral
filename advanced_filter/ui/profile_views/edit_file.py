# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st

from ..profiles import profile_to_yaml_bytes, yaml_bytes_to_profile, make_default_profile
from ..state import set_profile
from .common import rerun_safe

# ---------- helpers de estado/flash ----------
def _flash_file(msg: str, kind: str = "info"):
    st.session_state["__file_flash"] = (kind, msg)

def _show_flash_file():
    kind_msg = st.session_state.pop("__file_flash", None)
    if not kind_msg:
        return
    kind, msg = kind_msg
    if kind == "success":
        st.success(msg)
    elif kind == "warning":
        st.warning(msg)
    else:
        st.info(msg)

def _clear_file_editor_state(reset_uploader: bool = True):
    for k in list(st.session_state.keys()):
        if k.startswith("file_"):
            del st.session_state[k]
    st.session_state["__file_bytes"] = None
    st.session_state["__file_name"]  = None
    st.session_state["__file_draft"] = None
    st.session_state["__file_mode_active"] = False
    st.session_state["__file_form_nonce"] = st.session_state.get("__file_form_nonce", 0) + 1
    if reset_uploader:
        st.session_state["__file_upload_nonce"] = st.session_state.get("__file_upload_nonce", 0) + 1

def render_edit_file_tab():
    """
    Editar um ARQUIVO YAML:
    - Upload (uploader some após sucesso).
    - Baixar YAML atualizado (rascunho).
    - Salvar como novo perfil (opcional).
    - Cancelar edição (fecha editor e retorna ao uploader).
    """
    # Estado base
    st.session_state.setdefault("__file_bytes", None)
    st.session_state.setdefault("__file_name", None)
    st.session_state.setdefault("__file_draft", None)
    st.session_state.setdefault("__file_mode_active", False)
    st.session_state.setdefault("__file_form_nonce", 0)
    st.session_state.setdefault("__file_upload_nonce", 0)

    # Mostra flash (feedback pós-rerun)
    _show_flash_file()

    # ---- Estado inicial: sem editor, mostrar uploader ----
    if not st.session_state["__file_mode_active"]:
        up_key = f"__yaml_import_file_{st.session_state['__file_upload_nonce']}"
        up = st.file_uploader("Carregar YAML", type=["yaml", "yml"], key=up_key)
        if up is None:
            st.info("Envie um arquivo YAML para abrir no editor. Depois você poderá **Baixar** ou **Salvar como perfil**.")
            return
        # ao enviar, liga editor
        try:
            by = up.getvalue()
            nm = up.name or "config.yaml"
            prof = yaml_bytes_to_profile(by)
            prof["name"] = prof.get("name") or "Perfil_importado"

            st.session_state["__file_bytes"] = by
            st.session_state["__file_name"]  = nm
            st.session_state["__file_draft"] = prof
            st.session_state["__file_form_nonce"] += 1
            st.session_state["__file_mode_active"] = True
            st.success(f"YAML carregado: {nm}")
            rerun_safe(); st.stop()
        except Exception as e:
            st.error(f"Falha ao abrir YAML: {e}")
            return

    # ------- Editor ativo -------
    draft = st.session_state["__file_draft"] or make_default_profile("Perfil_importado")
    nonce = st.session_state["__file_form_nonce"]

    def k(suffix: str) -> str:
        return f"file_{suffix}_{nonce}"

    top = st.columns([3, 1])
    top[0].success(f"YAML carregado: {st.session_state.get('__file_name') or 'config.yaml'}")
    if top[1].button("Trocar arquivo YAML", key="__btn_swap_yaml"):
        _flash_file("Arquivo trocado.", "info")
        _clear_file_editor_state(reset_uploader=True)
        rerun_safe(); st.stop()

    with st.form(f"edit_form_from_file_{nonce}"):
        draft["name"] = st.text_input(
            "Nome (opcional, para salvar como perfil)",
            value=draft.get("name") or "Perfil_importado",
            key=k("name"),
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key=k("lower")
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key=k("strip")
            )
        with c3:
            draft["window"] = st.number_input(
                "window (janela tokens)", value=int(draft.get("window") or 8), min_value=1, step=1, key=k("window")
            )

        st.markdown("#### Positivos")
        draft["positives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("positives_text") or "",
            height=120,
            key=k("pos"),
        )

        st.markdown("#### Negativos")
        draft["negatives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("negatives_text") or "",
            height=100,
            key=k("neg"),
        )

        st.markdown("#### Grupos de Contexto")
        st.caption("Colunas: group, category, patterns (múltiplos por linha, vírgula ou ';').")
        ctx_df = pd.DataFrame(draft.get("contexts_rows") or [{"group":"","category":"","patterns":""}])
        ctx_df = st.data_editor(ctx_df, num_rows="dynamic", use_container_width=True, key=k("ctx_editor"))
        draft["contexts_rows"] = ctx_df.to_dict(orient="records")

        st.markdown("#### Regras")
        st.caption("Decisão ∈ {INCLUI, REVISA, EXCLUI}. min_score e assign_category são opcionais.")
        rules_df = pd.DataFrame(draft.get("rules_rows") or [{
            "name":"","equation":"","decision":"REVISA","min_score":None,"assign_category":""
        }])
        rules_df = st.data_editor(rules_df, num_rows="dynamic", use_container_width=True, key=k("rules_editor"))
        draft["rules_rows"] = rules_df.to_dict(orient="records")

        csave_as_profile, ccancel = st.columns([1, 1])
        saved_as_profile = csave_as_profile.form_submit_button(
            "Salvar como novo perfil", use_container_width=True, key=k("btn_save_as_profile")
        )
        canceled = ccancel.form_submit_button(
            "Cancelar edição", use_container_width=True, key=k("btn_cancel")
        )

    # Ações fora do form
    st.download_button(
        "Baixar YAML atualizado",
        profile_to_yaml_bytes(draft),
        file_name=(st.session_state.get("__file_name") or f"{draft['name']}.yaml"),
        use_container_width=True,
        key=k("dl"),
    )

    if saved_as_profile:
        name = draft["name"] or "Perfil_importado"
        set_profile(name, draft)
        try: st.toast("✅ Perfil salvo", icon="👍")
        except Exception: pass
        _flash_file(f"Perfil salvo: {name}", "success")

    if canceled:
        _flash_file("Edição cancelada.", "info")
        _clear_file_editor_state(reset_uploader=True)
        rerun_safe(); st.stop()
