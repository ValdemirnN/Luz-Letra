"""Canto superior direito de todas as páginas: avatar do usuário + menu (Meu Perfil / Sair).

- Se o usuário tiver foto, o avatar mostra a foto; senão, mostra a inicial do nome.
- A foto é salva (já reduzida) na coluna `foto_perfil` da tabela `usuarios`.
  Para ativar, rode UMA vez no Supabase (SQL Editor):
      alter table usuarios add column if not exists foto_perfil text;
"""
import base64
import io

import streamlit as st

from modulos.log import registrar_erro

SQL_COLUNA_FOTO = "alter table usuarios add column if not exists foto_perfil text;"

_CSS_BASE = """
/* ---------- Avatar fixo no canto superior direito ---------- */
.st-key-ll_topbar {
    position: fixed !important; top: 10px; right: 18px; z-index: 1000002;
    width: auto !important; min-width: 0 !important;
}
.st-key-ll_topbar { pointer-events: auto !important; }
.st-key-ll_topbar [data-testid="stPopover"] { width: auto !important; }

/* O cabeçalho transparente do Streamlit cobre o topo todo e bloqueava o clique no avatar:
   ele deixa o clique passar, e só os botões dele (abrir/fechar menu lateral) continuam clicáveis. */
[data-testid="stHeader"], [data-testid="stHeader"] *,
[data-testid="stToolbar"], [data-testid="stToolbar"] *,
[data-testid="stAppToolbar"], [data-testid="stAppToolbar"] * { pointer-events: none !important; }
[data-testid="stHeader"] button, [data-testid="stHeader"] a,
[data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapsedControl"] *,
[data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapseButton"] * { pointer-events: auto !important; }
/* o avatar (e o painel que ele abre) ficam acima de qualquer camada do cabeçalho */
.st-key-ll_topbar, .st-key-ll_topbar * { pointer-events: auto !important; }
[data-testid="stPopoverBody"], [data-baseweb="popover"] { z-index: 1000010 !important; pointer-events: auto !important; }
.st-key-ll_topbar [data-testid="stPopover"] > button,
.st-key-ll_topbar button[data-testid="stPopoverButton"] {
    width: 44px !important; height: 44px !important; min-height: 44px !important;
    padding: 0 !important; border-radius: 50% !important;
    border: 2px solid #FFC107 !important;
    background-color: #1B1B1D !important;
    background-size: cover !important; background-position: center !important;
    box-shadow: 0 0 0 3px rgba(255,193,7,.18), 0 4px 14px rgba(0,0,0,.45) !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
    transition: transform .15s ease, box-shadow .15s ease;
}
.st-key-ll_topbar [data-testid="stPopover"] > button:hover,
.st-key-ll_topbar button[data-testid="stPopoverButton"]:hover {
    transform: scale(1.06);
    box-shadow: 0 0 0 4px rgba(255,193,7,.30), 0 4px 14px rgba(0,0,0,.45) !important;
}
/* inicial do nome, centralizada (sem a seta do popover e sem o espaço que ela reserva) */
.st-key-ll_topbar button[data-testid="stPopoverButton"] [aria-hidden="true"],
.st-key-ll_topbar [data-testid="stPopover"] button [aria-hidden="true"] { display: none !important; }
.st-key-ll_topbar button[data-testid="stPopoverButton"] div,
.st-key-ll_topbar button[data-testid="stPopoverButton"] span {
    margin: 0 !important; padding: 0 !important; gap: 0 !important;
    justify-content: center !important; align-items: center !important;
    max-width: 100% !important;
}
.st-key-ll_topbar button[data-testid="stPopoverButton"] > div { width: 100% !important; height: 100% !important; }
.st-key-ll_topbar button[data-testid="stPopoverButton"] p {
    font-weight: 800 !important; font-size: 18px !important; color: #FFC107 !important;
    margin: 0 !important; padding: 0 !important; line-height: 1 !important; text-align: center !important;
}

/* ---------- Painel que abre ao clicar ---------- */
[data-testid="stPopoverBody"] { min-width: 230px; }
.ll-user-head { display:flex; align-items:center; gap:12px; padding: 2px 2px 8px 2px; }
.ll-user-head .av { width:46px; height:46px; border-radius:50%; flex:0 0 46px; background:#1B1B1D center/cover no-repeat;
    border:2px solid #FFC107; display:flex; align-items:center; justify-content:center;
    color:#FFC107; font-weight:800; font-size:19px; }
.ll-user-head .nm { font-weight:700; color:#F5F5F5; line-height:1.2; word-break:break-word; }
.ll-user-head .sub { font-size:12px; color:#9A9A9A; margin-top:2px; }
"""


# ----------------------------------------------------------------------------------
# Foto de perfil (carrega 1x por usuário e guarda em sessão)
# ----------------------------------------------------------------------------------
def _carregar_foto(supabase, uid):
    cache = st.session_state.get('_foto_perfil_cache')
    if cache and cache[0] == uid:
        return cache[1]
    foto = None
    try:
        r = supabase.table("usuarios").select("foto_perfil").eq("id", uid).execute()
        if r.data:
            foto = r.data[0].get("foto_perfil") or None
    except Exception:
        registrar_erro("topo_usuario.py:carregar_foto")  # coluna ainda não criada, etc.
    st.session_state['_foto_perfil_cache'] = (uid, foto)
    return foto


def _inicial(nome):
    nome = (nome or "").strip()
    return nome[0].upper() if nome else "U"


def _processar_imagem(arquivo, lado=200):
    """Recorta em quadrado, reduz e devolve base64 (JPEG leve, ~10–20 KB)."""
    from PIL import Image, ImageOps
    img = Image.open(arquivo)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (lado, lado), method=Image.LANCZOS, centering=(0.5, 0.4))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _avatar_html(foto, inicial, tamanho=46):
    if foto:
        estilo = f"background-image:url(data:image/jpeg;base64,{foto});"
        miolo = ""
    else:
        estilo, miolo = "", inicial
    return (f'<div class="av" style="width:{tamanho}px;height:{tamanho}px;flex:0 0 {tamanho}px;{estilo}">{miolo}</div>')


# ----------------------------------------------------------------------------------
# Avatar + menu no topo (chamar 1x logo depois de aplicar_tema())
# ----------------------------------------------------------------------------------
def render_topo(supabase, fazer_logout, plano_txt=""):
    uid = st.session_state.get('usuario_id')
    nome = st.session_state.get('nome_usuario') or ""
    foto = _carregar_foto(supabase, uid) if uid else None
    inicial = _inicial(nome)

    css = _CSS_BASE
    if foto:
        # com foto: esconde a letra e usa a imagem como fundo do botão
        css += f"""
.st-key-ll_topbar [data-testid="stPopover"] > button,
.st-key-ll_topbar button[data-testid="stPopoverButton"] {{
    background-image: url(data:image/jpeg;base64,{foto}) !important;
}}
.st-key-ll_topbar [data-testid="stPopover"] > button p,
.st-key-ll_topbar button[data-testid="stPopoverButton"] p {{ color: transparent !important; }}
"""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    def _ir_perfil():
        st.session_state['ver_perfil'] = not st.session_state.get('ver_perfil', False)
        st.session_state['_fechar_sidebar'] = True

    with st.container(key="ll_topbar"):
        with st.popover(inicial):
            from html import escape
            st.markdown(
                f'<div class="ll-user-head">{_avatar_html(foto, inicial)}'
                f'<div><div class="nm">{escape(nome or "Minha conta")}</div>'
                f'<div class="sub">{escape(plano_txt)}</div></div></div>',
                unsafe_allow_html=True,
            )
            st.button("Meu Perfil", icon=":material/person:", key="topo_btn_perfil",
                      use_container_width=True, on_click=_ir_perfil)
            st.button("Sair", icon=":material/logout:", key="topo_btn_sair",
                      use_container_width=True, on_click=fazer_logout)


# ----------------------------------------------------------------------------------
# Seção "Foto de perfil" (usar dentro da tela Meu Perfil)
# ----------------------------------------------------------------------------------
def secao_foto_perfil(supabase, em_expander=True):
    """Foto de perfil em dois estados:
    - COM foto salva (modo normal): mostra aviso de "foto salva" + botões Alterar foto / Remover foto.
    - SEM foto, ou depois de clicar em Alterar foto (modo edição): mostra o campo de anexo
      + botões Salvar foto / Remover foto.
    """
    uid = st.session_state.get('usuario_id')
    nome = st.session_state.get('nome_usuario') or ""
    foto = _carregar_foto(supabase, uid)

    contexto = st.expander("📸 Foto de perfil", expanded=False) if em_expander else st.container()
    if not em_expander:
        st.markdown("#### Foto de perfil")

    # sem foto salva => sempre em edição; com foto => só edita se clicou em "Alterar foto"
    editando = bool(st.session_state.get('_foto_editando', False)) or not foto
    _n_up = st.session_state.get('_foto_up_n', 0)  # trocar a chave do uploader limpa o anexo

    with contexto:
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(f'<div class="ll-user-head">{_avatar_html(foto, _inicial(nome), 84)}</div>', unsafe_allow_html=True)
        with c2:
            _msg = st.session_state.pop('_foto_msg_ok', None)
            if _msg:
                st.toast(_msg, icon="✅")

            if not editando:
                # ---------------- modo normal: foto já salva ----------------
                st.success(_msg or "Foto de perfil salva. Ela aparece no canto superior direito de todas as páginas.", icon="✅")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✏️ Alterar foto", key="btn_alterar_foto", use_container_width=True):
                        st.session_state['_foto_editando'] = True
                        st.session_state['_foto_up_n'] = _n_up + 1
                        st.rerun()
                with b2:
                    if st.button("🗑️ Remover foto", key="btn_remover_foto", use_container_width=True):
                        if _remover_foto(supabase, uid, _n_up):
                            st.rerun()
                return

            # ---------------- modo edição: anexar / salvar / remover ----------------
            st.caption("Opcional. A foto aparece no canto superior direito de todas as páginas. "
                       "Sem foto, mostramos a inicial do seu nome.")
            arq = st.file_uploader("Escolher imagem", type=["png", "jpg", "jpeg", "webp"],
                                   key=f"up_foto_perfil_{_n_up}", label_visibility="collapsed")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 Salvar foto", key="btn_salvar_foto", type="primary",
                             use_container_width=True, disabled=(arq is None)):
                    salvou = False
                    try:
                        b64 = _processar_imagem(arq)
                        supabase.table("usuarios").update({"foto_perfil": b64}).eq("id", uid).execute()
                        st.session_state['_foto_perfil_cache'] = (uid, b64)
                        st.session_state['_foto_up_n'] = _n_up + 1
                        st.session_state['_foto_editando'] = False
                        st.session_state['_foto_msg_ok'] = "Foto salva com sucesso!"
                        salvou = True
                    except Exception:
                        registrar_erro("topo_usuario.py:salvar_foto")
                        st.error("Não foi possível salvar a foto. Se for a primeira vez, crie a coluna no Supabase "
                                 "(SQL Editor) e tente de novo:")
                        st.code(SQL_COLUNA_FOTO, language="sql")
                    if salvou:
                        st.rerun()
            with b2:
                # remove a foto salva; se não houver foto salva, só descarta o anexo escolhido
                if st.button("🗑️ Remover foto", key="btn_remover_foto_edit", use_container_width=True,
                             disabled=(not foto and arq is None)):
                    if foto:
                        if _remover_foto(supabase, uid, _n_up):
                            st.rerun()
                    else:
                        st.session_state['_foto_up_n'] = _n_up + 1
                        st.rerun()
            if foto:
                if st.button("Cancelar alteração", key="btn_cancelar_foto", type="tertiary"):
                    st.session_state['_foto_editando'] = False
                    st.session_state['_foto_up_n'] = _n_up + 1
                    st.rerun()


def _remover_foto(supabase, uid, n_up):
    """Apaga a foto salva. Devolve True se deu certo."""
    try:
        supabase.table("usuarios").update({"foto_perfil": None}).eq("id", uid).execute()
        st.session_state['_foto_perfil_cache'] = (uid, None)
        st.session_state['_foto_up_n'] = n_up + 1
        st.session_state['_foto_editando'] = False
        st.session_state['_foto_msg_ok'] = "Foto removida."
        return True
    except Exception:
        registrar_erro("topo_usuario.py:remover_foto")
        st.error("Não foi possível remover a foto.")
        return False
