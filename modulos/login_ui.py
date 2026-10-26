"""Visual da tela de login do Luz & Letras.

Só apresentação: nenhuma regra de autenticação passa por aqui.
Uso no app.py (dentro do `if not st.session_state['logado']:`):

    from modulos.login_ui import aplicar_estilo_login, cabecalho_login, rodape_login
    aplicar_estilo_login()
    cabecalho_login()
    ... (formulário) ...
    rodape_login()
"""
import base64
import streamlit as st


@st.cache_data(show_spinner=False)
def _logo_base64(caminho="logo.jpg"):
    """Logo recortada (sem a margem preta) para ocupar melhor o espaço."""
    try:
        import io
        from PIL import Image
        im = Image.open(caminho).convert("RGB")
        w, h = im.size
        im = im.crop((int(w * 0.04), int(h * 0.19), int(w * 0.97), int(h * 0.76)))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        try:
            with open(caminho, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            return ""


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---------- Esconde a sidebar (a logo agora fica no topo do card) ---------- */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ---------- Fundo: halo dourado suave no lugar da marca d'água ---------- */
.stApp::before {
    background-image:
        radial-gradient(60% 45% at 50% 0%, rgba(255,193,7,0.16) 0%, rgba(255,193,7,0) 70%),
        radial-gradient(50% 40% at 50% 100%, rgba(255,193,7,0.07) 0%, rgba(255,193,7,0) 70%) !important;
    background-size: 100% 100% !important;
    background-position: center !important;
    opacity: 1 !important;
    animation: none !important;
    filter: none !important;
}

/* ---------- Coluna central estreita ---------- */
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 480px !important;
    padding: 4.5rem 1rem 2rem 1rem !important;
    margin: 0 auto;
}
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp button, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3, .stApp summary { font-family: 'Inter', 'Source Sans Pro', sans-serif; }
/* mantém a fonte de ícones do Streamlit (setas, olho da senha etc.) */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

/* ---------- Cabeçalho da marca ---------- */
.ll-brand { text-align: center; margin-bottom: 1.4rem; }
.ll-logo {
    width: 230px; max-width: 70%; height: auto; border-radius: 20px;
    box-shadow: 0 0 0 1px rgba(255,193,7,.35), 0 10px 40px rgba(255,193,7,.28);
    animation: ll-glow 3.5s ease-in-out infinite;
}
@keyframes ll-glow {
    0%,100% { box-shadow: 0 0 0 1px rgba(255,193,7,.30), 0 8px 30px rgba(255,193,7,.20); }
    50%     { box-shadow: 0 0 0 1px rgba(255,193,7,.55), 0 12px 48px rgba(255,193,7,.40); }
}
.ll-brand h1 {
    font-size: 1.65rem; font-weight: 800; letter-spacing: -.02em;
    margin: 1.1rem 0 .25rem 0; padding: 0; color: #F5F5F5;
}
.ll-brand p { margin: 0; color: #9A9A9A; font-size: .95rem; }

/* ---------- Card do formulário ---------- */
[data-testid="stForm"] {
    background: linear-gradient(180deg, rgba(30,30,30,.92), rgba(20,20,20,.92));
    border: 1px solid rgba(255,255,255,.08) !important;
    border-top: 2px solid #FFC107 !important;
    border-radius: 16px !important;
    padding: 1.5rem 1.4rem 1.3rem 1.4rem !important;
    box-shadow: 0 20px 60px rgba(0,0,0,.55);
}

/* ---------- Campos ---------- */
[data-testid="stTextInput"] label p, [data-testid="stTextArea"] label p {
    font-size: .82rem !important; font-weight: 600 !important; color: #C9C9C9 !important;
}
[data-testid="stTextInput"] input {
    background: #121212 !important; border-radius: 10px !important;
    min-height: 46px; font-size: 1rem;
}
[data-baseweb="input"], [data-baseweb="base-input"] {
    background: #121212 !important; border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    transition: border-color .15s, box-shadow .15s;
}
[data-baseweb="input"]:focus-within, [data-baseweb="base-input"]:focus-within {
    border-color: #FFC107 !important; box-shadow: 0 0 0 3px rgba(255,193,7,.18);
}

/* olho da senha com o mesmo fundo do campo */
[data-testid="stTextInput"] [data-baseweb="input"] > div,
[data-testid="stTextInput"] [data-baseweb="input"] button { background: transparent !important; }

/* ---------- Botões ---------- */
[data-testid="stFormSubmitButton"] button, [data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stBaseButton-primaryFormSubmit"] {
    width: 100%; min-height: 48px; border-radius: 10px; font-weight: 700; font-size: 1rem;
    transition: transform .08s, box-shadow .15s, filter .15s;
}
[data-testid="stBaseButton-primaryFormSubmit"] {
    background: linear-gradient(135deg, #FFD54F 0%, #FFC107 55%, #FFB300 100%) !important;
    color: #1A1400 !important; border: none !important;
    box-shadow: 0 6px 20px rgba(255,193,7,.30);
}
[data-testid="stBaseButton-primaryFormSubmit"]:hover { filter: brightness(1.06); box-shadow: 0 8px 26px rgba(255,193,7,.42); }
[data-testid="stBaseButton-primaryFormSubmit"]:active { transform: translateY(1px); }

/* ---------- Expanders (esqueci a senha / criar conta) ---------- */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,.08) !important; border-radius: 12px !important;
    background: rgba(255,255,255,.02); margin-bottom: .6rem;
}
[data-testid="stExpander"] summary { padding: .7rem 1rem; }
[data-testid="stExpander"] summary:hover { color: #FFC107; }
[data-testid="stExpander"] summary p { font-size: .92rem; font-weight: 500; }

/* ---------- Divisor, destaques e rodapé ---------- */
hr { border-color: rgba(255,255,255,.08) !important; margin: 1.4rem 0 !important; }
.ll-chips { display: flex; flex-wrap: wrap; justify-content: center; gap: .45rem; margin: 1.2rem 0 .4rem 0; }
.ll-chip {
    font-size: .76rem; color: #BDBDBD; padding: .3rem .7rem; border-radius: 999px;
    border: 1px solid rgba(255,193,7,.25); background: rgba(255,193,7,.06);
}
.ll-foot { text-align: center; color: #7A7A7A; font-size: .76rem; margin-top: 1rem; line-height: 1.5; }
.ll-foot a { color: #9A9A9A; text-decoration: underline; }

/* ---------- Celular ---------- */
@media (max-width: 600px) {
    [data-testid="stMainBlockContainer"], .block-container {
        padding-top: 3.8rem !important;
    }
    .ll-logo { width: 200px; border-radius: 18px; }
    .ll-brand h1 { font-size: 1.45rem; }
    [data-testid="stForm"] { padding: 1.2rem 1rem 1.1rem 1rem !important; }
    /* 16px evita o zoom automático do iPhone ao tocar no campo */
    [data-testid="stTextInput"] input { font-size: 16px !important; }
}
</style>
"""


def aplicar_estilo_login():
    """Injeta o CSS da tela de login (chamar só quando o usuário NÃO está logado)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def cabecalho_login(titulo="Bem-vindo de volta", subtitulo="Gestão completa para a sua locadora de eventos"):
    logo = _logo_base64()
    img = f'<img class="ll-logo" src="data:image/jpeg;base64,{logo}" alt="Luz &amp; Letras">' if logo else ""
    st.markdown(
        f'<div class="ll-brand">{img}<h1>{titulo}</h1><p>{subtitulo}</p></div>',
        unsafe_allow_html=True,
    )


def rodape_login():
    """Destaques do sistema + rodapé discreto (chamar no fim da tela de login)."""
    st.markdown(
        """
        <div class="ll-chips">
            <span class="ll-chip">📦 Estoque</span>
            <span class="ll-chip">📅 Agenda de eventos</span>
            <span class="ll-chip">📄 Orçamentos em PDF</span>
            <span class="ll-chip">💰 Faturamento</span>
        </div>
        <div class="ll-foot">
            🔒 Acesso protegido por senha criptografada<br>
            © Luz &amp; Letras · <a href="?privacidade=1" target="_self">Política de Privacidade</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
