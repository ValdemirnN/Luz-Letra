"""Tema visual "Palco & Neon" do Luz & Letras.

Só apresentação (CSS): não mexe em nenhuma regra de negócio.
Uso no app.py, logo depois do login (antes da sidebar):

    from modulos.tema import aplicar_tema
    aplicar_tema()

Funciona em todos os módulos (Dashboard, Agendamento, Estoque, Compras, Faturamento...)
porque estiliza os componentes do Streamlit (métricas, expanders, abas, botões, campos, menu).
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap');

:root {
    --ll-ouro: #FFC107;
    --ll-ouro-2: #FF9F1C;
    --ll-ouro-suave: rgba(255,193,7,.14);
    --ll-fundo: #0B0B0D;
    --ll-card: rgba(255,255,255,.045);
    --ll-card-forte: rgba(255,255,255,.075);
    --ll-borda: rgba(255,255,255,.10);
    --ll-borda-ouro: rgba(255,193,7,.45);
    --ll-texto: #F4F4F5;
    --ll-texto-2: #A1A1AA;
    --ll-raio: 16px;
}

html, body, .stApp, [data-testid="stAppViewContainer"] { font-family: 'Inter', system-ui, sans-serif !important; }
h1, h2, h3, [data-testid="stHeading"] { font-family: 'Outfit', 'Inter', sans-serif !important; letter-spacing: -.01em; }

/* ---------- Fundo: halos dourados no lugar da marca d'água ---------- */
.stApp { background: var(--ll-fundo) !important; }
.stApp::before {
    background-image:
        radial-gradient(55% 38% at 85% -5%, rgba(255,193,7,.20) 0%, rgba(255,193,7,0) 70%),
        radial-gradient(45% 35% at 0% 100%, rgba(255,120,0,.10) 0%, rgba(255,120,0,0) 70%),
        radial-gradient(rgba(255,255,255,.055) 1px, transparent 1px) !important;
    background-size: 100% 100%, 100% 100%, 26px 26px !important;
    background-position: center !important;
    background-repeat: no-repeat, no-repeat, repeat !important;
    opacity: 1 !important; animation: none !important; filter: none !important;
}

/* ---------- Cabeçalho da página ---------- */
[data-testid="stHeader"] { background: transparent !important; }
/* Esconde Share / estrela / lápis / GitHub / menu ⋮ e o rodapé do Streamlit */
[data-testid="stToolbar"], [data-testid="stToolbarActions"], [data-testid="stAppToolbar"],
[data-testid="stActionElements"], [data-testid="stAppDeployButton"],
[data-testid="stMainMenu"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, .stAppToolbar, .stToolbarActions,
header [data-testid="stToolbar"] *, #MainMenu, footer,
a[href*="github.com"][target="_blank"][class*="Toolbar"],
[class*="ToolbarActions"], [class*="stToolbar"] { display: none !important; visibility: hidden !important; }
[data-testid="stMainBlockContainer"] h1 {
    font-weight: 800 !important; font-size: clamp(1.7rem, 5vw, 2.4rem) !important;
    background: linear-gradient(92deg, #FFFFFF 0%, #FFE082 55%, var(--ll-ouro) 100%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    padding-bottom: .15rem !important; margin-bottom: .2rem !important;
}
[data-testid="stMainBlockContainer"] h1::after {
    content: ""; display: block; width: 64px; height: 4px; border-radius: 4px; margin-top: 10px;
    background: linear-gradient(90deg, var(--ll-ouro), var(--ll-ouro-2));
    box-shadow: 0 0 14px rgba(255,193,7,.7);
}
[data-testid="stMainBlockContainer"] h4, [data-testid="stMainBlockContainer"] h3 {
    margin-top: .6rem !important; font-weight: 700 !important; color: var(--ll-texto) !important;
}
hr { border: none !important; height: 1px !important; margin: 1.6rem 0 !important;
     background: linear-gradient(90deg, transparent, var(--ll-borda-ouro), transparent) !important; }

/* ---------- Métricas viram cartões ---------- */
[data-testid="stMetric"] {
    position: relative; overflow: hidden; padding: 16px 18px !important;
    background: linear-gradient(145deg, var(--ll-card-forte), var(--ll-card));
    border: 1px solid var(--ll-borda); border-radius: var(--ll-raio);
    box-shadow: 0 8px 24px rgba(0,0,0,.35); backdrop-filter: blur(8px);
    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
[data-testid="stMetric"]::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    background: linear-gradient(180deg, var(--ll-ouro), var(--ll-ouro-2)); box-shadow: 0 0 12px rgba(255,193,7,.6);
}
[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: var(--ll-borda-ouro); box-shadow: 0 14px 30px rgba(0,0,0,.5), 0 0 0 1px rgba(255,193,7,.12); }
[data-testid="stMetricLabel"] { color: var(--ll-texto-2) !important; font-size: .82rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: .04em; }
[data-testid="stMetricValue"] { font-family: 'Outfit', sans-serif !important; font-weight: 800 !important; font-size: clamp(1.8rem, 6vw, 2.5rem) !important; color: #fff !important; }
[data-testid="stMetricDelta"] { border-radius: 999px; padding: 1px 8px; width: fit-content; }

/* ---------- Expanders (cards de evento, histórico, cadastro) ---------- */
[data-testid="stExpander"] {
    background: var(--ll-card) !important; border: 1px solid var(--ll-borda) !important;
    border-radius: var(--ll-raio) !important; overflow: hidden; margin-bottom: .55rem;
    transition: border-color .18s ease, box-shadow .18s ease;
}
[data-testid="stExpander"]:hover { border-color: var(--ll-borda-ouro) !important; box-shadow: 0 10px 26px rgba(0,0,0,.4); }
[data-testid="stExpander"] details { border: none !important; background: transparent !important; }
[data-testid="stExpander"] summary { padding: .85rem 1rem !important; font-weight: 600; }
[data-testid="stExpander"] summary:hover { background: var(--ll-ouro-suave) !important; }
[data-testid="stExpander"] summary svg { color: var(--ll-ouro) !important; }

/* ---------- Cartão de evento (HTML gerado em agendamento.py) ---------- */
.ev-card { display: flex; gap: 14px; align-items: center; padding: 14px 16px;
    background: linear-gradient(135deg, var(--ll-card-forte), var(--ll-card));
    border: 1px solid var(--ll-borda); border-bottom: none; border-radius: var(--ll-raio) var(--ll-raio) 0 0;
    position: relative; overflow: hidden; margin-top: .55rem; }
.ev-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 5px; background: var(--ev-cor, var(--ll-ouro)); box-shadow: 0 0 14px var(--ev-cor, var(--ll-ouro)); }
.ev-data { flex: 0 0 58px; text-align: center; border-radius: 14px; padding: 7px 0 6px; margin-left: 6px;
    background: rgba(0,0,0,.45); border: 1px solid var(--ll-borda); line-height: 1; }
.ev-data b { display: block; font: 800 1.55rem 'Outfit', sans-serif; color: #fff; }
.ev-data span { font-size: .68rem; font-weight: 700; letter-spacing: .12em; color: var(--ev-cor, var(--ll-ouro)); text-transform: uppercase; }
.ev-info { flex: 1; min-width: 0; }
.ev-titulo { font: 700 1.02rem 'Outfit', sans-serif; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ev-sub { color: var(--ll-texto-2); font-size: .82rem; margin-top: 3px; display: flex; flex-wrap: wrap; gap: 4px 12px; }
.ev-chip { flex: 0 0 auto; align-self: flex-start; font-size: .68rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
    padding: 4px 10px; border-radius: 999px; color: var(--ev-cor, var(--ll-ouro));
    background: color-mix(in srgb, var(--ev-cor, var(--ll-ouro)) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--ev-cor, var(--ll-ouro)) 50%, transparent); }
/* o expander logo abaixo do cartão "gruda" nele */
[data-testid="stElementContainer"]:has(.ev-card) + [data-testid="stElementContainer"] [data-testid="stExpander"] {
    border-radius: 0 0 var(--ll-raio) var(--ll-raio) !important; border-top: 1px dashed var(--ll-borda) !important; margin-top: -1rem; }

.ev-vazio { text-align: center; padding: 34px 18px; border: 1.5px dashed var(--ll-borda-ouro); border-radius: var(--ll-raio);
    background: radial-gradient(80% 120% at 50% 0%, var(--ll-ouro-suave), transparent); }
.ev-vazio .ic { font-size: 2.2rem; filter: drop-shadow(0 0 12px rgba(255,193,7,.7)); }
.ev-vazio b { display: block; margin-top: 6px; font: 700 1.05rem 'Outfit', sans-serif; }
.ev-vazio small { color: var(--ll-texto-2); }

/* ---------- Campos ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"] {
    background: rgba(255,255,255,.055) !important; border: 1px solid var(--ll-borda) !important; border-radius: 12px !important; transition: all .15s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
    border-color: var(--ll-ouro) !important; box-shadow: 0 0 0 3px rgba(255,193,7,.20) !important; background: rgba(255,193,7,.05) !important;
}
[data-testid="stWidgetLabel"] p { color: var(--ll-texto-2) !important; font-size: .82rem !important; font-weight: 600 !important; }
[data-baseweb="tag"] { border-radius: 999px !important; background: linear-gradient(135deg, var(--ll-ouro), var(--ll-ouro-2)) !important; color: #1a1200 !important; font-weight: 700; }
[data-baseweb="tag"] span { color: #1a1200 !important; }

/* ---------- Botões ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 12px !important; font-weight: 700 !important; min-height: 44px; border: 1px solid var(--ll-borda) !important;
    background: var(--ll-card-forte) !important; color: var(--ll-texto) !important; transition: all .16s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
    border-color: var(--ll-ouro) !important; color: var(--ll-ouro) !important; transform: translateY(-1px); box-shadow: 0 6px 18px rgba(255,193,7,.18);
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"], [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--ll-ouro), var(--ll-ouro-2)) !important; color: #1a1200 !important; border: none !important;
    box-shadow: 0 8px 22px rgba(255,160,0,.35);
}
.stButton > button[kind="primary"]:hover { color: #000 !important; filter: brightness(1.08); box-shadow: 0 10px 28px rgba(255,160,0,.5); }

/* ---------- Abas em formato de pílula ---------- */
[data-baseweb="tab-list"] { gap: 6px; background: rgba(255,255,255,.04); padding: 5px; border-radius: 14px; border: 1px solid var(--ll-borda); overflow-x: auto; scrollbar-width: none; }
[data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
[data-baseweb="tab"] { border-radius: 10px !important; padding: 8px 14px !important; height: auto !important; white-space: nowrap; font-weight: 600; color: var(--ll-texto-2) !important; }
[data-baseweb="tab"][aria-selected="true"] { background: linear-gradient(135deg, var(--ll-ouro), var(--ll-ouro-2)) !important; color: #1a1200 !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none !important; }

/* ---------- Alertas, tabelas, gráficos ---------- */
[data-testid="stAlert"] { border-radius: var(--ll-raio) !important; border: 1px solid var(--ll-borda) !important; backdrop-filter: blur(6px); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 14px; overflow: hidden; border: 1px solid var(--ll-borda); }
[data-testid="stPlotlyChart"] { background: var(--ll-card); border: 1px solid var(--ll-borda); border-radius: var(--ll-raio); padding: 8px; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { border-radius: var(--ll-raio); }

/* ---------- Menu lateral ---------- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #131315 0%, #0B0B0D 100%) !important; border-right: 1px solid var(--ll-borda); }
[data-testid="stSidebar"] img { border-radius: 18px; }
[data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
[data-testid="stSidebar"] [role="radiogroup"] > div { width: 100%; }
[data-testid="stSidebar"] [data-testid="stRadioOption"], [data-testid="stSidebar"] [role="radiogroup"] > label {
    width: 100%; padding: 11px 14px; border-radius: 12px; border: 1px solid transparent; cursor: pointer; transition: all .15s ease; }
/* esconde a bolinha (Streamlit novo e antigo) */
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child,
[data-testid="stSidebar"] [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child { display: none !important; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover, [data-testid="stSidebar"] [role="radiogroup"] > label:hover { background: var(--ll-card-forte); }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked), [data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, rgba(255,193,7,.22), rgba(255,159,28,.08)); border-color: var(--ll-borda-ouro);
    box-shadow: inset 3px 0 0 var(--ll-ouro), 0 0 18px rgba(255,193,7,.12); }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) p, [data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p { color: var(--ll-ouro) !important; font-weight: 700; }
[data-testid="stSidebar"] .stButton > button { width: 100%; }
[data-testid="stSidebar"] [data-testid="stAlert"] { padding: .5rem .75rem; font-weight: 600; }

/* ---------- Sem rolagem horizontal / faixa vazia no fim da página ---------- */
html, body, .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { overflow-x: hidden !important; max-width: 100vw; }
[data-testid="stMain"]::-webkit-scrollbar:horizontal, section.main::-webkit-scrollbar:horizontal { display: none; height: 0; }
[data-testid="stBottom"]:not(:has(textarea)):not(:has(input)):not(:has(button)) { display: none !important; }
[data-testid="stMainBlockContainer"] { padding-bottom: 3rem !important; }

/* ---------- Detalhes ---------- */
* { scrollbar-width: thin; scrollbar-color: rgba(255,193,7,.35) transparent; }
::selection { background: rgba(255,193,7,.35); }
[data-testid="stMainBlockContainer"] { animation: ll-entrada .35s ease both; }
@keyframes ll-entrada { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* ---------- CELULAR ---------- */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"], .block-container { padding: 4.4rem .85rem 3rem !important; }  /* topo livra o menu/Share; rodapé sem faixa vazia */
    /* 4 métricas em grade 2x2 em vez de empilhadas */
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap: wrap !important; gap: .6rem !important; }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div[data-testid="column"] {
        flex: 1 1 calc(50% - .4rem) !important; min-width: calc(50% - .4rem) !important; width: calc(50% - .4rem) !important; }
    [data-testid="stMetric"] { padding: 12px 14px !important; }
    [data-testid="stMetricLabel"] { font-size: .70rem !important; }
    .ev-card { padding: 12px; gap: 10px; flex-wrap: wrap; }
    .ev-chip { order: 3; margin-left: 74px; }
    .ev-data { flex-basis: 52px; }
    /* campos e botões maiores para o polegar */
    .stButton > button, [data-testid="stFormSubmitButton"] > button { min-height: 48px; width: 100%; }
    [data-baseweb="input"] input, [data-baseweb="select"] input, textarea { font-size: 16px !important; } /* evita zoom do iPhone */
    [data-baseweb="tab"] { padding: 8px 12px !important; font-size: .85rem; }
}
@media (min-width: 641px) and (max-width: 1000px) {
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] { flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important; }
}
</style>
"""


def aplicar_tema():
    st.markdown(_CSS, unsafe_allow_html=True)


MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
COR_STATUS = {
    "Agendado": "#FFC107",
    "Em Andamento": "#38BDF8",
    "Concluído": "#34D399",
    "Cancelado": "#F87171",
}


def cartao_evento_html(titulo, cliente, data_ini_iso, data_ini_br, data_fim_br, hora_ini, hora_fim, status, valor_txt=""):
    """HTML do cartão de evento (selo de data + título + cliente + status)."""
    from html import escape
    cor = COR_STATUS.get(status, "#FFC107")
    try:
        dia = data_ini_iso[8:10]
        mes = MESES_ABREV[int(data_ini_iso[5:7]) - 1]
    except Exception:
        dia, mes = "--", "---"
    periodo = data_ini_br if data_ini_br == data_fim_br else f"{data_ini_br} → {data_fim_br}"
    valor = f"<span>💰 R$ {escape(valor_txt)}</span>" if valor_txt else ""
    return (
        f'<div class="ev-card" style="--ev-cor:{cor}">'
        f'<div class="ev-data"><b>{dia}</b><span>{mes}</span></div>'
        f'<div class="ev-info"><div class="ev-titulo">{escape(str(titulo))}</div>'
        f'<div class="ev-sub"><span>👤 {escape(str(cliente))}</span><span>🕒 {escape(hora_ini)}–{escape(hora_fim)}</span>'
        f'<span>📆 {escape(periodo)}</span>{valor}</div></div>'
        f'<div class="ev-chip">{escape(str(status))}</div></div>'
    )


def estado_vazio_html(icone="🎪", titulo="Nenhum evento por aqui", subtitulo="Ajuste os filtros ou cadastre um novo evento abaixo."):
    return f'<div class="ev-vazio"><div class="ic">{icone}</div><b>{titulo}</b><small>{subtitulo}</small></div>'
