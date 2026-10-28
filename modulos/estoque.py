"""Módulo: 📦 Estoque.

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
Visual: navegação por seções (pílulas), resumo com anel de disponibilidade e cartões de produto.
Todas as funcionalidades continuam as mesmas; só a apresentação mudou.
"""
from html import escape
from modulos.log import registrar_erro
import json
from datetime import datetime

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

_CSS = """
<style>
/* ===== Estoque: painel de disponibilidade ===== */
.es-sub { color:#A1A1AA; font-size:.95rem; margin:-.2rem 0 1rem; }
.es-chip-titulo { display:flex; align-items:center; gap:8px; margin:0 0 .5rem; font:700 1.05rem 'Outfit',sans-serif; color:#fff; }
.es-titulo { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:1.6rem 0 .7rem; font:800 1.3rem 'Outfit',sans-serif; color:#fff; }
.es-titulo em { white-space:nowrap; flex:0 0 auto; font-style:normal; font:700 .76rem 'Inter',sans-serif; color:#1a1200; background:#FFC107; padding:3px 10px; border-radius:999px; }

/* navegação por seções (pílulas) */
.st-key-estoque_secao, .st-key-estoque_secao [data-testid="stRadio"] { width:100% !important; }
.st-key-estoque_secao [role="radiogroup"] { gap:8px; flex-wrap:wrap; padding:2px 2px 8px; }
.st-key-estoque_secao [role="radiogroup"]::-webkit-scrollbar { display:none; }
.st-key-estoque_secao [role="radiogroup"] > div { flex:0 0 auto; }
.st-key-estoque_secao [data-testid="stRadioOption"], .st-key-estoque_secao [role="radiogroup"] > label {
    padding:9px 16px; border-radius:999px; cursor:pointer; white-space:nowrap; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); transition:all .15s ease; }
.st-key-estoque_secao [data-testid="stRadioOption"] p { white-space:nowrap; margin:0; }
.st-key-estoque_secao [data-testid="stRadioOption"] > div > div:first-child,
.st-key-estoque_secao [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child { display:none !important; }
.st-key-estoque_secao [data-testid="stRadioOption"]:hover { border-color:rgba(255,193,7,.5); }
.st-key-estoque_secao [data-testid="stRadioOption"]:has(input:checked), .st-key-estoque_secao [role="radiogroup"] > label:has(input:checked) {
    background:linear-gradient(135deg,#FFC107,#FF9F1C); border-color:transparent; box-shadow:0 8px 22px rgba(255,160,0,.35); }
.st-key-estoque_secao [data-testid="stRadioOption"]:has(input:checked) p { color:#1a1200 !important; font-weight:800; }

/* cartões / formulários */
[class*="st-key-es_box"], [data-testid="stForm"] {
    position:relative; border:1px solid rgba(255,255,255,.10) !important; border-radius:20px !important; padding:1.1rem 1.15rem .6rem !important;
    background:linear-gradient(160deg,rgba(255,255,255,.065),rgba(255,255,255,.02)) !important; box-shadow:0 12px 32px rgba(0,0,0,.35); margin-bottom:.9rem; }
[class*="st-key-es_box"]::before, [data-testid="stForm"]::before { content:""; position:absolute; left:22px; right:22px; top:-1px; height:2px; border-radius:2px;
    background:linear-gradient(90deg,transparent,#FFC107,transparent); box-shadow:0 0 12px rgba(255,193,7,.7); }
[data-testid="stFormSubmitButton"] button { width:100%; min-height:50px; background:linear-gradient(135deg,#FFC107,#FF9F1C) !important; color:#1a1200 !important; border:none !important; box-shadow:0 10px 26px rgba(255,160,0,.40); }

/* pílulas: tipo de cadastro e tipo de remoção */
.st-key-es_tipo_cadastro [role="radiogroup"], .st-key-radio_tipo_remocao [role="radiogroup"] { gap:10px; flex-wrap:wrap; }
.st-key-es_tipo_cadastro [data-testid="stRadioOption"], .st-key-radio_tipo_remocao [data-testid="stRadioOption"] { padding:10px 16px; border-radius:14px; cursor:pointer; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); }
.st-key-es_tipo_cadastro [data-testid="stRadioOption"] > div > div:first-child, .st-key-radio_tipo_remocao [data-testid="stRadioOption"] > div > div:first-child { display:none !important; }
.st-key-es_tipo_cadastro [data-testid="stRadioOption"]:has(input:checked), .st-key-radio_tipo_remocao [data-testid="stRadioOption"]:has(input:checked) {
    background:linear-gradient(135deg,rgba(255,193,7,.28),rgba(255,159,28,.10)); border-color:#FFC107; box-shadow:0 0 18px rgba(255,193,7,.25); }
.st-key-es_tipo_cadastro [data-testid="stRadioOption"]:has(input:checked) p, .st-key-radio_tipo_remocao [data-testid="stRadioOption"]:has(input:checked) p { color:#FFC107 !important; font-weight:800; }

/* resumo geral com anel */
.es-hero { --cor:#34D399; display:flex; align-items:center; gap:24px; padding:20px 24px; border-radius:22px; margin:.4rem 0 1.2rem;
    background:radial-gradient(90% 140% at 0% 0%,color-mix(in srgb,var(--cor) 18%,transparent),transparent 60%),linear-gradient(160deg,rgba(255,255,255,.08),rgba(255,255,255,.02));
    border:1px solid color-mix(in srgb,var(--cor) 40%,transparent); box-shadow:0 14px 36px rgba(0,0,0,.4); }
.es-ring { flex:0 0 118px; width:118px; height:118px; border-radius:50%; display:grid; place-items:center;
    background:conic-gradient(var(--cor) calc(var(--p) * 1%), rgba(255,255,255,.09) 0); box-shadow:0 0 28px color-mix(in srgb,var(--cor) 35%,transparent); }
.es-ring > div { width:92px; height:92px; border-radius:50%; background:#111113; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.es-ring b { font:800 1.55rem 'Outfit',sans-serif; color:#fff; line-height:1; } .es-ring small { color:#A1A1AA; font-size:.68rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin-top:3px; }
.es-hero-stats { flex:1; display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.es-hero-stats div { padding:12px 14px; border-radius:16px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); }
.es-hero-stats small { display:block; color:#A1A1AA; font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.es-hero-stats b { display:block; margin-top:4px; font:800 1.9rem 'Outfit',sans-serif; color:#fff; line-height:1; }
.es-hero-stats .res b { color:#FFC107; } .es-hero-stats .liv b { color:var(--cor); }

/* categorias e produtos */
.es-cat { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; margin:1.6rem 0 .7rem; }
.es-cat-nome { font:800 1.12rem 'Outfit',sans-serif; color:#fff; letter-spacing:.02em; }
.es-cat-chips { display:flex; flex-wrap:wrap; gap:6px; }
.es-cat-chips span { font-size:.74rem; font-weight:600; padding:4px 11px; border-radius:999px; color:#D4D4D8; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.10); }
.es-cat-chips b { color:#fff; font-weight:800; } .es-cat-chips .r b { color:#FFC107; } .es-cat-chips .l b { color:#34D399; } .es-cat-chips .l.zero b { color:#F87171; }
.es-prods { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr)); gap:12px; margin-bottom:.8rem; }
.es-prod { --cor:#34D399; padding:14px 16px 13px; border-radius:18px; background:linear-gradient(145deg,rgba(255,255,255,.075),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.09);
    box-shadow:0 8px 22px rgba(0,0,0,.3); transition:transform .18s ease,border-color .18s ease; }
.es-prod:hover { transform:translateY(-2px); border-color:color-mix(in srgb,var(--cor) 55%,transparent); }
.es-prod-top { display:flex; align-items:center; gap:10px; margin-bottom:11px; }
.es-ic { flex:0 0 38px; height:38px; display:grid; place-items:center; font-size:1.2rem; border-radius:12px; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.08); }
.es-nome { flex:1; min-width:0; font:700 .98rem 'Outfit',sans-serif; color:#fff; overflow-wrap:anywhere; line-height:1.2; }
.es-st { flex:0 0 auto; font-size:.7rem; font-weight:700; color:#D4D4D8; padding:3px 9px; border-radius:999px; background:rgba(255,255,255,.07); white-space:nowrap; }
.es-bar { height:9px; border-radius:999px; background:rgba(255,255,255,.09); overflow:hidden; }
.es-bar i { display:block; height:100%; border-radius:999px; box-shadow:0 0 10px currentColor; }
.es-nums { display:flex; justify-content:space-between; gap:8px; margin-top:9px; font-size:.78rem; color:#A1A1AA; }
.es-nums b { color:#fff; font-weight:800; } .es-nums .liv b { color:var(--cor); }

/* peças de kit (letras / números) */
.es-kit { display:grid; grid-template-columns:repeat(auto-fill,minmax(62px,1fr)); gap:8px; margin:.3rem 0 .6rem; }
.es-peca { text-align:center; padding:8px 2px; border-radius:12px; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08); }
.es-peca b { display:block; font:800 1rem 'Outfit',sans-serif; color:#fff; } .es-peca span { font-size:.74rem; font-weight:700; color:#34D399; }
.es-peca.zero { border-color:rgba(248,113,113,.4); } .es-peca.zero span { color:#F87171; }

/* manutenção e quebrados */
.es-mcard { --cor:#38BDF8; display:flex; gap:14px; padding:14px 16px; margin:.5rem 0 .3rem; border-radius:18px; position:relative; overflow:hidden;
    background:linear-gradient(145deg,rgba(255,255,255,.075),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.10); }
.es-mcard::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--cor); box-shadow:0 0 12px var(--cor); }
.es-mcard.atrasado { --cor:#F87171; } .es-mcard.ok { --cor:#34D399; }
.es-mcard .es-ic { background:color-mix(in srgb,var(--cor) 15%,transparent); border-color:color-mix(in srgb,var(--cor) 45%,transparent); }
.es-minfo { flex:1; min-width:0; }
.es-mtop { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.es-mtop b { font:700 1.02rem 'Outfit',sans-serif; color:#fff; overflow-wrap:anywhere; }
.es-qtd { flex:0 0 auto; font:800 1rem 'Outfit',sans-serif; color:var(--cor); white-space:nowrap; }
.es-msub { color:#A1A1AA; font-size:.8rem; margin-top:3px; overflow-wrap:anywhere; }
.es-mchips { display:flex; flex-wrap:wrap; gap:6px; margin-top:9px; }
.es-mchips span { font-size:.7rem; font-weight:700; padding:4px 10px; border-radius:999px; color:#D4D4D8; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); }
.es-mchips .late { color:var(--cor); background:color-mix(in srgb,var(--cor) 14%,transparent); border-color:color-mix(in srgb,var(--cor) 55%,transparent); }
.es-motivo { margin-top:8px; color:#A1A1AA; font-size:.78rem; font-style:italic; overflow-wrap:anywhere; }
.es-kpis2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:.2rem 0 1rem; }
.es-kpi { padding:15px 18px; border-radius:18px; background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.10); }
.es-kpi small { display:block; color:#A1A1AA; font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.es-kpi b { display:block; margin-top:4px; font:800 1.7rem 'Outfit',sans-serif; color:#F87171; }


/* conteúdo das abas vira cartão; botões principais em dourado */
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] [data-baseweb="tab-panel"] { padding-top:1rem; }
[data-baseweb="tab-panel"] { position:relative; }
[data-testid="stMain"] button[kind="primary"]:not([data-testid="stFormSubmitButton"] button) { min-height:50px; }
@media (max-width:640px) { [data-testid="stMain"] button[kind="primary"] { width:100%; } }

/* campos de kit em grade (várias colunas viram grade no celular) */
@media (max-width:900px) {
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(5)) { flex-wrap:wrap !important; gap:.5rem !important; }
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(5)) > [data-testid="stColumn"] { flex:1 1 calc(33.33% - .5rem) !important; min-width:calc(33.33% - .5rem) !important; width:auto !important; }
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(5)):not(:has([data-testid="stNumberInput"])) > [data-testid="stColumn"] { flex:1 1 calc(50% - .5rem) !important; min-width:calc(50% - .5rem) !important; }
}
@media (max-width:640px) {
    .st-key-estoque_secao [role="radiogroup"] { gap:6px; }
    .st-key-estoque_secao [data-testid="stRadioOption"] { padding:7px 12px; } .st-key-estoque_secao [data-testid="stRadioOption"] p { font-size:.84rem; }
    .es-hero { flex-direction:column; align-items:stretch; gap:16px; padding:18px 16px; }
    .es-ring { align-self:center; } .es-hero-stats { gap:8px; } .es-hero-stats div { padding:10px; } .es-hero-stats b { font-size:1.45rem; }
    [class*="st-key-es_box"], [data-testid="stForm"] { padding:1rem .9rem .4rem !important; border-radius:18px !important; }
    .es-mcard { padding:12px 13px; gap:11px; }
}
</style>
"""


def _s(v):
    return "" if v is None else str(v)


def _data_br(d):
    try: return datetime.strptime(_s(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception: return _s(d) or "-"


def _grade(n):
    """Devolve uma função idx -> coluna. A cada n itens abre uma nova linha de n colunas,
    para a ordem de leitura (A, B, C...) ficar certa também no celular."""
    estado = {"cols": None}
    def pegar(i):
        if i % n == 0: estado["cols"] = st.columns(n)
        return estado["cols"][i % n]
    return pegar


def _pecas_txt(js):
    try:
        dk = json.loads(js) if isinstance(js, str) else (js or {})
        return ", ".join(f"{k}: {v}x" for k, v in dk.items())
    except Exception:
        return ""


SECOES = ["📊 Disponibilidade", "➕ Novo item", "📥 Ajustar estoque", "🔧 Manutenção", "💥 Quebrados"]


def render(supabase, emp_id, formatar_moeda, mostrar_popup, safe_json_load, calcular_detalhamento_periodo_produto, calcular_disponibilidade_periodo, definir_categoria, formatar_telefone_br, prever_icone, status_cor, popup_confirmacao_estoque):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("Controle de Estoque Inteligente")
    st.markdown('<div class="es-sub">Veja o que está livre, cadastre itens e acompanhe manutenção e perdas.</div>', unsafe_allow_html=True)
    produtos_lista = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).order("nome").execute()

    secao = st.radio("Seção", SECOES, horizontal=True, key="estoque_secao", label_visibility="collapsed")

    if secao == SECOES[0]:
        with st.container(key="es_box_datas"):
            st.markdown('<div class="es-chip-titulo">🗓️ Período para verificar</div>', unsafe_allow_html=True)
            col_d1, col_d2 = st.columns(2)
            with col_d1: data_inicio_f = st.date_input("De (Data Inicial)", format="DD/MM/YYYY")
            with col_d2: data_fim_f = st.date_input("Até (Data Final)", value=data_inicio_f, format="DD/MM/YYYY")
        if produtos_lista.data:
            df_produtos = pd.DataFrame(produtos_lista.data)
            df_produtos['Categoria'] = df_produtos['nome'].apply(definir_categoria)
            df_produtos['Ícone'] = df_produtos['nome'].apply(prever_icone)
            df_produtos['Estoque Total'] = df_produtos['quantidade_estoque']
            try: qtd_alugada, detalhe_alugado = calcular_disponibilidade_periodo(data_inicio_f, data_fim_f)
            except Exception as e:
                registrar_erro("estoque.py:29")
                st.exception(e)
                qtd_alugada, detalhe_alugado = {}, {}
            def calcular_disponivel(row): return row['quantidade_estoque'] - qtd_alugada.get(row['id'],0)
            df_produtos['Reservado na Data'] = df_produtos['id'].map(lambda x: qtd_alugada.get(x,0))
            df_produtos['Disponível Livre'] = df_produtos.apply(calcular_disponivel, axis=1)
            total_geral_estoque = int(df_produtos['Estoque Total'].sum())
            total_geral_reservado = int(df_produtos['Reservado na Data'].sum())
            total_geral_livre = int(df_produtos['Disponível Livre'].sum())
            pct_livre_geral = (total_geral_livre / total_geral_estoque * 100) if total_geral_estoque > 0 else 0
            cor_hero = "#34D399" if pct_livre_geral >= 50 else ("#FFC107" if pct_livre_geral > 20 else "#F87171")
            st.markdown(
                f'<div class="es-hero" style="--cor:{cor_hero}"><div class="es-ring" style="--p:{pct_livre_geral:.0f}"><div><b>{pct_livre_geral:.0f}%</b><small>livre</small></div></div>'
                f'<div class="es-hero-stats"><div><small>📦 Estoque total</small><b>{total_geral_estoque}</b></div>'
                f'<div class="res"><small>🔒 Reservado</small><b>{total_geral_reservado}</b></div>'
                f'<div class="liv"><small>✅ Disponível</small><b>{total_geral_livre}</b></div></div></div>', unsafe_allow_html=True)

            def _cor_barra(disponivel, total):
                if total <= 0: return "#555"
                pct_livre = disponivel / total
                if pct_livre >= 0.5: return "#34D399"
                if pct_livre > 0.2: return "#FFC107"
                return "#F87171"

            categorias = sorted(df_produtos['Categoria'].unique())
            for cat in categorias:
                df_cat = df_produtos[df_produtos['Categoria'] == cat]
                total_fisico = int(df_cat['Estoque Total'].sum())
                total_reservado_cat = int(df_cat['Reservado na Data'].sum())
                total_livre = int(df_cat['Disponível Livre'].sum())
                cartoes_prod = []
                for _, prod_row in df_cat.iterrows():
                    total_p = int(prod_row['Estoque Total'])
                    reservado_p = int(prod_row['Reservado na Data'])
                    livre_p = int(prod_row['Disponível Livre'])
                    pct_reservado = min(100, (reservado_p / total_p * 100) if total_p > 0 else 0)
                    cor_barra = _cor_barra(livre_p, total_p)
                    status_label = status_cor(prod_row['quantidade_estoque'])
                    cartoes_prod.append(
                        f'<div class="es-prod" style="--cor:{cor_barra}"><div class="es-prod-top"><span class="es-ic">{prod_row["Ícone"]}</span>'
                        f'<span class="es-nome">{escape(str(prod_row["nome"]))}</span><span class="es-st">{escape(str(status_label))}</span></div>'
                        f'<div class="es-bar"><i style="width:{max(pct_reservado, 2) if reservado_p > 0 else 0:.1f}%;background:{cor_barra};color:{cor_barra}"></i></div>'
                        f'<div class="es-nums"><span>📦 Total <b>{total_p}</b></span><span>🔒 Reservado <b>{reservado_p}</b></span><span class="liv">✅ Livre <b>{livre_p}</b></span></div></div>')
                st.markdown(
                    f'<div class="es-cat"><div class="es-cat-nome">{escape(str(cat))}</div><div class="es-cat-chips">'
                    f'<span>Físico <b>{total_fisico}</b></span><span class="r">Reservado <b>{total_reservado_cat}</b></span>'
                    f'<span class="l{" zero" if total_livre <= 0 else ""}">Livres <b>{total_livre}</b></span></div></div>'
                    f'<div class="es-prods">{"".join(cartoes_prod)}</div>', unsafe_allow_html=True)

                for _, prod_row in df_cat.iterrows():
                    total_p = int(prod_row['Estoque Total'])
                    reservado_p = int(prod_row['Reservado na Data'])
                    js_kit = safe_json_load(prod_row.get('observacao'))

                    if js_kit:
                        alugados_kit = detalhe_alugado.get(prod_row['id'], {})
                        with st.expander(f"Ver detalhamento de {prod_row['nome']} ({len(js_kit)} peças)", expanded=False):
                            itens_kit_ordenados = sorted(js_kit.items())
                            pecas_html = []
                            for k, max_v in itens_kit_ordenados:
                                livre_k = max(0, max_v - alugados_kit.get(k, 0))
                                pecas_html.append(f'<div class="es-peca{"" if livre_k > 0 else " zero"}"><b>{escape(str(k))}</b><span>{livre_k}/{max_v}</span></div>')
                            st.markdown(f'<div class="es-kit">{"".join(pecas_html)}</div>', unsafe_allow_html=True)

                    if reservado_p > 0:
                        linhas_detalhe = calcular_detalhamento_periodo_produto(data_inicio_f, data_fim_f, prod_row['id'], total_p)
                        if linhas_detalhe:
                            with st.expander(f"🕐 Detalhamento por dia e horário — {prod_row['nome']}", expanded=False):
                                st.dataframe(pd.DataFrame(linhas_detalhe), use_container_width=True, hide_index=True)
        else: st.info("Nenhum produto cadastrado no estoque ainda.")

    elif secao == SECOES[1]:
        tipo_cadastro = st.radio("O que você vai cadastrar?", ["Produto Normal","🔠 Kit Letras (A-Z)","🔢 Kit Números (0 a 9)"], horizontal=True, key="es_tipo_cadastro")
        with st.form("form_estoque_add"):
            if tipo_cadastro == "Produto Normal":
                nome_prod = st.text_input("Nome do Item")
                qtd_prod = st.number_input("Quantidade Total Físico", min_value=0, value=None)
                valor_locacao_prod = st.number_input("Valor de Locação por Unidade (R$)", min_value=0.0, value=None, format="%.2f")
                obs_prod = st.text_input("Observação Simples (Opcional)")
                if st.form_submit_button("Salvar Produto Normal"):
                    if nome_prod.strip():
                        supabase.table("produtos").insert({"empresa_id": emp_id,"nome": nome_prod.upper(),"quantidade_estoque": (qtd_prod or 0),"valor_locacao": (valor_locacao_prod or 0),"observacao": obs_prod}).execute()
                        mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                        st.rerun()
            elif tipo_cadastro == "🔠 Kit Letras (A-Z)":
                nome_prod = st.text_input("Nome do Kit", value="LETRAS ILUMINADAS")
                valor_locacao_letras = st.number_input("Valor de Locação por Peça (R$)", min_value=0.0, value=None, format="%.2f")
                letras = [f"🔠 {l}" for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
                cols_l = _grade(6)
                qtd_letras = {}
                for i, l in enumerate(letras): qtd_letras[l] = cols_l(i).number_input(l, min_value=0, value=None)
                if st.form_submit_button("Salvar Kit Letras"):
                    total_letras = sum((v or 0) for v in qtd_letras.values())
                    if total_letras == 0: mostrar_popup("Coloque pelo menos 1 letra!", tipo="erro")
                    else:
                        obs_json = json.dumps({k: (v or 0) for k,v in qtd_letras.items() if (v or 0) > 0})
                        supabase.table("produtos").insert({"empresa_id": emp_id,"nome": nome_prod.upper(),"quantidade_estoque": total_letras,"valor_locacao": (valor_locacao_letras or 0),"observacao": obs_json}).execute()
                        mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                        st.rerun()
            elif tipo_cadastro == "🔢 Kit Números (0 a 9)":
                nome_prod = st.text_input("Nome do Kit", value="NÚMEROS ILUMINADOS")
                valor_locacao_numeros = st.number_input("Valor de Locação por Peça (R$)", min_value=0.0, value=None, format="%.2f")
                numeros = ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]
                cols_n = _grade(10)
                qtd_numeros = {}
                for i, num in enumerate(numeros): qtd_numeros[num] = cols_n(i).number_input(num, min_value=0, value=None)
                if st.form_submit_button("Salvar Kit Números"):
                    total_numeros = sum((v or 0) for v in qtd_numeros.values())
                    if total_numeros == 0: mostrar_popup("Coloque pelo menos 1 número!", tipo="erro")
                    else:
                        obs_json = json.dumps({k: (v or 0) for k,v in qtd_numeros.items() if (v or 0) > 0})
                        supabase.table("produtos").insert({"empresa_id": emp_id,"nome": nome_prod.upper(),"quantidade_estoque": total_numeros,"valor_locacao": (valor_locacao_numeros or 0),"observacao": obs_json}).execute()
                        mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                        st.rerun()
    elif secao == SECOES[2]:
        tab_entrada, tab_valor, tab_baixa = st.tabs(["⬆️ Entrada de estoque", "💲 Valor de locação", "🗑️ Baixa / exclusão"])
        with tab_entrada:
            if produtos_lista.data:
                opcoes_add = {f"{p['nome']} (Estoque Atual: {p['quantidade_estoque']})": p for p in produtos_lista.data}
                prod_selecionado_add = st.selectbox("Selecione o produto para aumentar o estoque", list(opcoes_add.keys()), key="select_add_qtd")
                prod_alvo_add = opcoes_add[prod_selecionado_add]
                js_estoque_add = safe_json_load(prod_alvo_add.get('observacao'))
                if js_estoque_add:
                    st.markdown(f"**Especifique a quantidade recebida para cada item de {prod_alvo_add['nome']}:**")
                    cols_add_kit = _grade(10)
                    idx_add = 0
                    qtds_adicionar_kit = {}
                    for k, v_atual in js_estoque_add.items():
                        val_add_k = cols_add_kit(idx_add).number_input(f"{k} (Tem: {v_atual})", min_value=0, value=None, placeholder="0", key=f"add_kit_{prod_alvo_add['id']}_{k}") or 0
                        if val_add_k > 0: qtds_adicionar_kit[k] = val_add_k
                        idx_add += 1
                    if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_kit_estoque", type="primary"):
                        if not qtds_adicionar_kit: mostrar_popup("Adicione quantidade em pelo menos um item.", tipo="erro")
                        else:
                            novo_json_add = dict(js_estoque_add)
                            total_adicionado = 0
                            for k, v in qtds_adicionar_kit.items():
                                novo_json_add[k] = novo_json_add.get(k,0) + v
                                total_adicionado += v
                            qtd_final = prod_alvo_add['quantidade_estoque'] + total_adicionado
                            supabase.table("produtos").update({"quantidade_estoque": qtd_final,"observacao": json.dumps(novo_json_add)}).eq("id", prod_alvo_add['id']).execute()
                            mostrar_popup("Estoque atualizado com sucesso!")
                            st.rerun()
                else:
                    nova_qtd_add = st.number_input("Quantidade de peças adquiridas/adicionadas", min_value=1, step=1, key="num_add_qtd_normal")
                    if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_normal_estoque", type="primary"):
                        qtd_final = prod_alvo_add['quantidade_estoque'] + nova_qtd_add
                        supabase.table("produtos").update({"quantidade_estoque": qtd_final}).eq("id", prod_alvo_add['id']).execute()
                        mostrar_popup("Estoque atualizado com sucesso!")
                        st.rerun()
        with tab_valor:
            if produtos_lista.data:
                opcoes_val = {p['nome']: p for p in produtos_lista.data}
                prod_val_nome = st.selectbox("Produto", list(opcoes_val.keys()), key="sel_editar_valor")
                prod_val = opcoes_val[prod_val_nome]
                valor_atual_salvo = float(prod_val.get('valor_locacao') or 0)
                if valor_atual_salvo > 0: st.caption(f"💾 Valor atual salvo: **R$ {formatar_moeda(valor_atual_salvo)}**")
                else: st.caption("Nenhum valor cadastrado ainda.")
                novo_valor_ref = st.number_input("Novo Valor de Locação por Unidade (R$)", min_value=0.0, value=None, placeholder="Ex: 15,00", format="%.2f", key="input_editar_valor")
                if st.button("💾 Salvar Valor de Referência", key="btn_editar_valor_ref", type="primary"):
                    if novo_valor_ref is None: mostrar_popup("Digite um valor antes de salvar.", tipo="erro")
                    else:
                        supabase.table("produtos").update({"valor_locacao": novo_valor_ref}).eq("id", prod_val['id']).execute()
                        mostrar_popup("VALOR ATUALIZADO COM SUCESSO!")
                        st.rerun()
            else: st.info("Nenhum produto cadastrado ainda.")
        with tab_baixa:
            if produtos_lista.data:
                opcoes_produtos_excluir = {f"{p['nome']} (ID {p['id']}, Estoque: {p['quantidade_estoque']})": p['id'] for p in produtos_lista.data}
                dict_produtos_lista = {p['id']: p for p in produtos_lista.data}
                produto_escolhido_label = st.selectbox("Selecione o produto", list(opcoes_produtos_excluir.keys()), key="select_excluir_produto")
                produto_id_excluir = opcoes_produtos_excluir[produto_escolhido_label]
                produto_selecionado_info = dict_produtos_lista[produto_id_excluir]
                tipo_remocao = st.radio("O que você quer fazer?", ["Remover quantidade parcial (ex: quebrou 5 cadeiras)","Excluir o produto inteiro do estoque"], key="radio_tipo_remocao")
                if tipo_remocao.startswith("Remover quantidade parcial"):
                    js_prod_excluir = safe_json_load(produto_selecionado_info.get('observacao'))
                    if js_prod_excluir:
                        cols_pex = _grade(6)
                        qtds_remover_parcial = {}
                        idxpex = 0
                        for k, max_v in js_prod_excluir.items():
                            if max_v > 0:
                                val_pex = cols_pex(idxpex).number_input(f"{k} (Tem: {max_v})", min_value=0, max_value=max_v, value=None, key=f"pex_{produto_id_excluir}_{k}")
                                if (val_pex or 0) > 0: qtds_remover_parcial[k] = val_pex
                                idxpex += 1
                        motivo_pex = st.text_input("Motivo da remoção", key=f"motivo_pex_{produto_id_excluir}")
                        total_remover_pex = sum(qtds_remover_parcial.values())
                        if st.button("➖ Solicitar Remoção", key=f"btn_solicita_pex_{produto_id_excluir}"):
                            if total_remover_pex > 0 and motivo_pex.strip(): popup_confirmacao_estoque(produto_selecionado_info, "parcial", total_remover=total_remover_pex, qtds_json=qtds_remover_parcial, motivo=motivo_pex)
                            else: mostrar_popup("Preencha a quantidade e o motivo da remoção.", tipo="erro")
                    else:
                        qtd_disponivel_pex = produto_selecionado_info['quantidade_estoque']
                        qtd_remover_normal = st.number_input(f"Quanto deseja remover? (Tem: {qtd_disponivel_pex})", min_value=0, max_value=qtd_disponivel_pex, value=None, key=f"pex_normal_{produto_id_excluir}")
                        motivo_pex_normal = st.text_input("Motivo da remoção", key=f"motivo_pex_normal_{produto_id_excluir}")
                        if st.button("➖ Solicitar Remoção", key=f"btn_solicita_pex_normal_{produto_id_excluir}"):
                            if (qtd_remover_normal or 0) > 0 and motivo_pex_normal.strip(): popup_confirmacao_estoque(produto_selecionado_info, "parcial", total_remover=qtd_remover_normal, motivo=motivo_pex_normal)
                            else: mostrar_popup("Preencha a quantidade e o motivo da remoção.", tipo="erro")
                else:
                    if st.button("🗑️ Solicitar Exclusão", key="btn_solicita_excluir_produto"):
                        popup_confirmacao_estoque(produto_selecionado_info, "total")
            else: st.info("Nenhum produto cadastrado para excluir.")

    elif secao == SECOES[3]:
        tab_enviar_manut, tab_extrato_manut = st.tabs(["Enviar para Manutenção", "📋 Histórico de Manutenção"])

        with tab_enviar_manut:
            if produtos_lista.data:
                opcoes_manut = {p['nome']: p for p in produtos_lista.data}
                prod_manut_nome = st.selectbox("Selecione o Produto", list(opcoes_manut.keys()), key="sel_manut")
                prod_manut = opcoes_manut[prod_manut_nome]

                js_manut = safe_json_load(prod_manut.get('observacao'))

                if js_manut:
                    st.markdown(f"**Especifique quais peças de {prod_manut['nome']} vão para manutenção:**")
                    cols_mkit = _grade(6)
                    idx_mkit = 0
                    qtds_manut_kit = {}
                    for k, max_v in js_manut.items():
                        if max_v > 0:
                            v_mk = cols_mkit(idx_mkit).number_input(
                                f"{k} (Tem: {max_v})", min_value=0, max_value=max_v,
                                value=None, key=f"manut_kit_{prod_manut['id']}_{k}"
                            )
                            if (v_mk or 0) > 0:
                                qtds_manut_kit[k] = v_mk
                            idx_mkit += 1
                    qtd_manut = sum(qtds_manut_kit.values())
                else:
                    qtd_manut = st.number_input(
                        "Qtd para Manutenção",
                        min_value=1, max_value=prod_manut['quantidade_estoque'], step=1,
                        key="qtd_manut_normal"
                    )
                    qtds_manut_kit = {}

                motivo_manut = st.text_input("Motivo / Defeito", key="motivo_manut")

                st.markdown("**📍 Onde vai ficar para manutenção?**")
                col_loc1, col_loc2, col_loc3, col_loc4, col_loc5 = st.columns(5)
                with col_loc1: local_nome_manut = st.text_input("Nome do Local / Oficina", key="manut_local_nome", placeholder="Ex: Oficina do João")
                with col_loc2: local_rua_manut = st.text_input("Rua", key="manut_local_rua", placeholder="Ex: Rua das Flores")
                with col_loc3: local_numero_manut = st.text_input("Número", key="manut_local_numero", placeholder="Ex: 123")
                with col_loc4: local_bairro_manut = st.text_input("Bairro / Referência", key="manut_local_bairro", placeholder="Ex: Centro")
                with col_loc5: contato_manut = st.text_input("Telefone/Contato", key="manut_contato", placeholder="(84) 99999-9999")

                st.markdown("**📅 Previsão de Retorno da Manutenção:**")
                data_prev_retorno = st.date_input(
                    "Data prevista para o item voltar ao estoque",
                    value=datetime.now().date() + relativedelta(days=7),
                    format="DD/MM/YYYY",
                    key="data_prev_manut"
                )
                st.caption("O item ficará fora do estoque até você confirmar manualmente o retorno. Esta data é apenas uma referência.")

                if st.button("🔧 Registrar Manutenção", key="btn_reg_manut", type="primary"):
                    if not motivo_manut.strip():
                        mostrar_popup("Informe o motivo da manutenção.", tipo="erro")
                    elif (qtd_manut or 0) <= 0:
                        mostrar_popup("Informe a quantidade a enviar.", tipo="erro")
                    else:
                        local_completo = f"{local_nome_manut} — {local_rua_manut}, {local_numero_manut} — {local_bairro_manut}".strip(" —,")
                        contato_manut_formatado = formatar_telefone_br(contato_manut) if contato_manut.strip() else None
                        novo_estoque_manut = prod_manut['quantidade_estoque'] - qtd_manut

                        if js_manut and qtds_manut_kit:
                            novo_json_manut = dict(js_manut)
                            for k, v in qtds_manut_kit.items():
                                novo_json_manut[k] = max(0, novo_json_manut.get(k, 0) - v)
                            supabase.table("produtos").update({
                                "quantidade_estoque": max(0, novo_estoque_manut),
                                "observacao": json.dumps(novo_json_manut)
                            }).eq("id", prod_manut['id']).execute()
                        else:
                            supabase.table("produtos").update({
                                "quantidade_estoque": max(0, novo_estoque_manut)
                            }).eq("id", prod_manut['id']).execute()

                        supabase.table("manutencao").insert({
                            "empresa_id": emp_id,
                            "produto_id": prod_manut['id'],
                            "quantidade": qtd_manut,
                            "motivo": motivo_manut,
                            "status": "Em Manutenção",
                            "data_envio": str(datetime.now().date()),
                            "data_prevista_retorno": str(data_prev_retorno),
                            "detalhes_kit": json.dumps(qtds_manut_kit) if qtds_manut_kit else None,
                            "local_manutencao": local_completo if local_completo else None,
                            "contato_manutencao": contato_manut_formatado
                        }).execute()

                        mostrar_popup("Produto enviado para manutenção!")
                        st.rerun()
            else:
                st.info("Nenhum produto cadastrado.")

        with tab_extrato_manut:
                try:
                    manut_lista = supabase.table("manutencao").select("*, produtos(nome)").eq("empresa_id", emp_id).order("data_envio", desc=True).execute()
    
                    if manut_lista.data:
                        hoje_manut = datetime.now().date()
                        em_manut = [m for m in manut_lista.data if m['status'] == "Em Manutenção"]
                        concluidos = [m for m in manut_lista.data if m['status'] == "Concluído"]
    
                        if em_manut:
                            st.markdown("#### 🔴 Em Manutenção (itens fora de circulação)")
                            for m in em_manut:
                                nome_p = m['produtos']['nome'] if m.get('produtos') else f"Produto #{m['produto_id']}"
                                data_envio_m = m.get('data_envio', '-')
                                data_prev_m = m.get('data_prevista_retorno', '-')
                                local_m = m.get('local_manutencao') or 'Local não informado'
    
                                prazo_vencido = False
                                dias_atraso = 0
                                if data_prev_m and data_prev_m != '-':
                                    try:
                                        dt_prev = datetime.strptime(data_prev_m, "%Y-%m-%d").date()
                                        if hoje_manut > dt_prev:
                                            prazo_vencido = True
                                            dias_atraso = (hoje_manut - dt_prev).days
                                    except Exception:
                                        registrar_erro("estoque.py:366")
                                        pass
    
                                detalhes_kit_m = ""
                                if m.get('detalhes_kit'):
                                    try:
                                        dk = json.loads(m['detalhes_kit'])
                                        detalhes_kit_m = " | Peças: " + ", ".join([f"{k}: {v}x" for k, v in dk.items()])
                                    except Exception:
                                        registrar_erro("estoque.py:375")
                                        pass
    
                                icone_m = "⚠️" if prazo_vencido else "🔧"
                                atraso_txt = f" — ATRASADO {dias_atraso} dia(s)" if prazo_vencido else ""

                                pecas_m = _pecas_txt(m.get('detalhes_kit')) if m.get('detalhes_kit') else ""
                                chip_atraso = f'<span class="late">⏰ Atrasado {dias_atraso} dia(s)</span>' if prazo_vencido else ""
                                linha_pecas = f'<div class="es-msub">🧩 {escape(pecas_m)}</div>' if pecas_m else ""
                                classe_card = "atrasado" if prazo_vencido else ""
                                st.markdown(
                                    f'<div class="es-mcard {classe_card}"><div class="es-ic">{icone_m}</div><div class="es-minfo">'
                                    f'<div class="es-mtop"><b>{escape(str(nome_p))}</b><span class="es-qtd">{m["quantidade"]} un.</span></div>'
                                    f'<div class="es-msub">📍 {escape(str(local_m))}</div>'
                                    f'<div class="es-mchips"><span>📤 Enviado {_data_br(data_envio_m)}</span><span>📅 Retorno {_data_br(data_prev_m)}</span>{chip_atraso}</div>'
                                    f'{linha_pecas}<div class="es-motivo">Motivo: {escape(str(m["motivo"]))}</div></div></div>', unsafe_allow_html=True)

                                with st.expander("⚙️ Gerenciar este item", expanded=False):
                                    if m.get('local_manutencao'):
                                        st.info(f"📍 **Local:** {m['local_manutencao']}")
                                    if m.get('contato_manutencao'):
                                        st.info(f"📞 **Contato:** {m['contato_manutencao']}")

                                    if st.button(
                                        "✅ Confirmar Retorno ao Estoque",
                                        key=f"ret_manut_{m['id']}",
                                        use_container_width=True,
                                        type="primary"
                                    ):
                                        prod_ret = supabase.table("produtos").select("quantidade_estoque, observacao").eq("id", m['produto_id']).execute()
                                        if prod_ret.data:
                                            estq_novo_ret = prod_ret.data[0]['quantidade_estoque'] + m['quantidade']
                                            if m.get('detalhes_kit'):
                                                try:
                                                    dk_ret = json.loads(m['detalhes_kit'])
                                                    obs_ret = safe_json_load(prod_ret.data[0].get('observacao'))
                                                    if obs_ret and dk_ret:
                                                        for k, v in dk_ret.items():
                                                            obs_ret[k] = obs_ret.get(k, 0) + v
                                                        supabase.table("produtos").update({
                                                            "quantidade_estoque": estq_novo_ret,
                                                            "observacao": json.dumps(obs_ret)
                                                        }).eq("id", m['produto_id']).execute()
                                                    else:
                                                        supabase.table("produtos").update({"quantidade_estoque": estq_novo_ret}).eq("id", m['produto_id']).execute()
                                                except Exception:
                                                    registrar_erro("estoque.py:464")
                                                    supabase.table("produtos").update({"quantidade_estoque": estq_novo_ret}).eq("id", m['produto_id']).execute()
                                            else:
                                                supabase.table("produtos").update({"quantidade_estoque": estq_novo_ret}).eq("id", m['produto_id']).execute()
    
                                            supabase.table("manutencao").update({
                                                "status": "Concluído",
                                                "data_retorno_real": str(datetime.now().date())
                                            }).eq("id", m['id']).execute()
                                            mostrar_popup("Produto devolvido ao estoque com sucesso!")
                                            st.rerun()

                                    tab_prazo, tab_quebra_m, tab_rem_m = st.tabs(["📅 Atualizar prazo", "💀 Mover para Quebrados", "🗑️ Remover do Histórico"])
                                    with tab_prazo:
                                        nova_data_prev = st.date_input(
                                            "Nova previsão",
                                            value=datetime.strptime(data_prev_m, "%Y-%m-%d").date() if data_prev_m and data_prev_m != '-' else hoje_manut,
                                            format="DD/MM/YYYY",
                                            key=f"nova_data_prev_{m['id']}"
                                        )
                                        if st.button("💾 Salvar data", key=f"btn_nova_data_{m['id']}"):
                                            supabase.table("manutencao").update({
                                                "data_prevista_retorno": str(nova_data_prev),
                                                "motivo": m['motivo'] + f" [Prazo atualizado em {datetime.now().strftime('%d/%m/%Y')}]"
                                            }).eq("id", m['id']).execute()
                                            mostrar_popup("Data de retorno atualizada!")
                                            st.rerun()
                                    with tab_quebra_m:
                                        st.caption("Use se o item não tiver mais conserto.")
                                        motivo_quebra_manut = st.text_input(
                                            "Motivo da quebra/perda",
                                            key=f"motivo_quebra_manut_{m['id']}",
                                            placeholder="Ex: sem conserto, perda total..."
                                        )
                                        if st.button("💀 Confirmar Quebra", key=f"mover_quebrado_{m['id']}"):
                                            if not motivo_quebra_manut.strip():
                                                mostrar_popup("Informe o motivo antes de confirmar.", tipo="erro")
                                            else:
                                                supabase.table("itens_quebrados").insert({
                                                    "empresa_id": emp_id,
                                                    "produto_id": m['produto_id'],
                                                    "quantidade": m['quantidade'],
                                                    "motivo": f"[Veio da manutenção — {local_m}] {motivo_quebra_manut}",
                                                    "data_registro": str(datetime.now().date()),
                                                    "detalhes_kit": m.get('detalhes_kit')
                                                }).execute()
                                                supabase.table("manutencao").delete().eq("id", m['id']).execute()
                                                mostrar_popup("Item movido para o histórico de quebrados!")
                                                st.rerun()
                                    with tab_rem_m:
                                        st.caption("Remove apenas o registro. O estoque não é alterado.")
                                        if st.button("🗑️ Confirmar Remoção", key=f"del_manut_ativo_{m['id']}"):
                                            supabase.table("manutencao").delete().eq("id", m['id']).execute()
                                            mostrar_popup("Registro removido do histórico.")
                                            st.rerun()
                        else:
                            st.success("✅ Nenhum item em manutenção no momento.")
                        if concluidos:
                            st.markdown(f"#### 📜 Histórico de Manutenções Concluídas ({len(concluidos)})")
                        for mc in concluidos:
                            nome_pc = mc['produtos']['nome'] if mc.get('produtos') else f"Produto #{mc['produto_id']}"
                            detalhes_kit_c = ""
                            if mc.get('detalhes_kit'):
                                try:
                                    dkc = json.loads(mc['detalhes_kit'])
                                    detalhes_kit_c = " | Peças: " + ", ".join([f"{k}: {v}x" for k, v in dkc.items()])
                                except Exception:
                                    registrar_erro("estoque.py:487")
                                    pass
                            data_retorno_real = mc.get('data_retorno_real', '-')
                        
                            with st.expander(
                                f"✅ {nome_pc} — {mc['quantidade']} un. | "
                                    f"Enviado: {_data_br(mc.get('data_envio','-'))} | "
                                    f"Retornou: {_data_br(data_retorno_real)}{detalhes_kit_c}",
                                expanded=False
                            ):
                                st.caption(f"Motivo: {mc['motivo']}")
                                st.write(f"📍 **Local:** {mc.get('local_manutencao') or 'Não informado'}")
                                if mc.get('contato_manutencao'):
                                    st.write(f"📞 **Contato:** {mc['contato_manutencao']}")
                        
                                col_btn_mc1, col_btn_mc2 = st.columns(2)
                                with col_btn_mc1:
                                    if st.button("✏️ Editar Registro", key=f"toggle_edit_mc_{mc['id']}"):
                                        chave = f"editando_mc_{mc['id']}"
                                        st.session_state[chave] = not st.session_state.get(chave, False)
                                        st.rerun()
                                with col_btn_mc2:
                                    if st.button("🗑️ Excluir do Histórico", key=f"excluir_hist_concluido_{mc['id']}"):
                                        supabase.table("manutencao").delete().eq("id", mc['id']).execute()
                                        mostrar_popup("Registro excluído do histórico.")
                                        st.rerun()
                        
                                if st.session_state.get(f"editando_mc_{mc['id']}", False):
                                    st.markdown("---")
                                    col_ec1, col_ec2, col_ec3 = st.columns(3)
                                    with col_ec1:
                                        novo_motivo_mc = st.text_input(
                                            "Motivo",
                                            value=mc['motivo'],
                                            key=f"edit_motivo_mc_{mc['id']}"
                                        )
                                    with col_ec2:
                                        try:
                                            val_data_envio = datetime.strptime(mc.get('data_envio', '2024-01-01'), "%Y-%m-%d").date()
                                        except Exception:
                                            registrar_erro("estoque.py:527")
                                            val_data_envio = datetime.now().date()
                                        nova_data_envio_mc = st.date_input(
                                            "Data de Envio",
                                            value=val_data_envio,
                                            format="DD/MM/YYYY",
                                            key=f"edit_envio_mc_{mc['id']}"
                                        )
                                    with col_ec3:
                                        try:
                                            val_data_ret = datetime.strptime(mc.get('data_retorno_real', '2024-01-01'), "%Y-%m-%d").date()
                                        except Exception:
                                            registrar_erro("estoque.py:539")
                                            val_data_ret = datetime.now().date()
                                        nova_data_retorno_mc = st.date_input(
                                            "Data de Retorno Real",
                                            value=val_data_ret,
                                            format="DD/MM/YYYY",
                                            key=f"edit_retorno_mc_{mc['id']}"
                                        )
                        
                                    col_ec4, col_ec5 = st.columns(2)
                                    with col_ec4:
                                        novo_local_mc = st.text_input(
                                            "Local da Manutenção",
                                            value=mc.get('local_manutencao') or "",
                                            key=f"edit_local_mc_{mc['id']}"
                                        )
                                    with col_ec5:
                                        novo_contato_mc = st.text_input(
                                            "Contato",
                                            value=mc.get('contato_manutencao') or "",
                                            key=f"edit_contato_mc_{mc['id']}"
                                        )
                        
                                    if st.button("💾 Salvar Edição", key=f"salvar_edit_mc_{mc['id']}"):
                                        supabase.table("manutencao").update({
                                            "motivo": novo_motivo_mc,
                                            "data_envio": str(nova_data_envio_mc),
                                            "data_retorno_real": str(nova_data_retorno_mc),
                                            "local_manutencao": novo_local_mc,
                                            "contato_manutencao": novo_contato_mc
                                        }).eq("id", mc['id']).execute()
                                        st.session_state[f"editando_mc_{mc['id']}"] = False
                                        mostrar_popup("Registro atualizado com sucesso!")
                                        st.rerun()
                    else:
                        st.info("Nenhum registro de manutenção ainda.")
                except Exception as e:
                    registrar_erro("estoque.py:576")
                    st.error(f"Erro ao carregar manutenção: {e}")
    elif secao == SECOES[4]:
        tab_reg_quebrado, tab_lista_quebrados = st.tabs(["Registrar Quebra", "📋 Histórico de Quebrados"])

        with tab_reg_quebrado:
            if produtos_lista.data:
                opcoes_quebrado = {p['nome']: p for p in produtos_lista.data}
                prod_quebra_nome = st.selectbox("Selecione o Produto", list(opcoes_quebrado.keys()), key="sel_quebrado")
                prod_quebrado = opcoes_quebrado[prod_quebra_nome]

                js_quebrado = safe_json_load(prod_quebrado.get('observacao'))

                col_q1, col_q2 = st.columns(2)
                with col_q1:
                    if js_quebrado:
                        st.markdown(f"**Especifique quais peças de {prod_quebrado['nome']} foram quebradas/perdidas:**")
                        cols_qkit = _grade(6)
                        idx_qkit = 0
                        qtds_quebra_kit = {}
                        for k, max_v in js_quebrado.items():
                            if max_v > 0:
                                v_qk = cols_qkit(idx_qkit).number_input(
                                    f"{k} (Tem: {max_v})", min_value=0, max_value=max_v,
                                    value=None, key=f"quebra_kit_{prod_quebrado['id']}_{k}"
                                )
                                if (v_qk or 0) > 0:
                                    qtds_quebra_kit[k] = v_qk
                                idx_qkit += 1
                        qtd_quebrada = sum(qtds_quebra_kit.values())
                    else:
                        qtd_quebrada = st.number_input(
                            "Quantidade Quebrada/Perdida",
                            min_value=1, max_value=prod_quebrado['quantidade_estoque'], step=1,
                            key="qtd_quebrada_normal"
                        )
                        qtds_quebra_kit = {}

                with col_q2:
                    motivo_quebra = st.text_input("Detalhes (Ex: Quebrou na festa X)", key="motivo_quebra")

                st.error("⚠️ **Atenção:** Itens quebrados são **removidos permanentemente** do estoque. Esta ação não pode ser desfeita.")

                if st.button("🗑️ Registrar Quebra / Perda Definitiva", key="btn_reg_quebra", type="primary"):
                    if not motivo_quebra.strip():
                        mostrar_popup("Informe os detalhes da quebra.", tipo="erro")
                    elif (qtd_quebrada or 0) <= 0:
                        mostrar_popup("Informe a quantidade quebrada.", tipo="erro")
                    else:
                        # Remove permanentemente do estoque
                        novo_estoque_q = prod_quebrado['quantidade_estoque'] - qtd_quebrada

                        if js_quebrado and qtds_quebra_kit:
                            novo_json_q = dict(js_quebrado)
                            for k, v in qtds_quebra_kit.items():
                                novo_json_q[k] = max(0, novo_json_q.get(k, 0) - v)
                            supabase.table("produtos").update({
                                "quantidade_estoque": max(0, novo_estoque_q),
                                "observacao": json.dumps(novo_json_q)
                            }).eq("id", prod_quebrado['id']).execute()
                        else:
                            supabase.table("produtos").update({
                                "quantidade_estoque": max(0, novo_estoque_q)
                            }).eq("id", prod_quebrado['id']).execute()

                        supabase.table("itens_quebrados").insert({
                            "empresa_id": emp_id,
                            "produto_id": prod_quebrado['id'],
                            "quantidade": qtd_quebrada,
                            "motivo": motivo_quebra,
                            "data_registro": str(datetime.now().date()),
                            "detalhes_kit": json.dumps(qtds_quebra_kit) if qtds_quebra_kit else None
                        }).execute()

                        mostrar_popup("Baixa de estoque registrada permanentemente.")
                        st.rerun()
            else:
                st.info("Nenhum produto cadastrado.")

        with tab_lista_quebrados:
            try:
                quebrados_lista = supabase.table("itens_quebrados").select("*, produtos(nome)").eq("empresa_id", emp_id).order("data_registro", desc=True).execute()

                if quebrados_lista.data:
                    total_quebrados = len(quebrados_lista.data)
                    total_pecas_perdidas = sum(q['quantidade'] for q in quebrados_lista.data)
                    st.markdown(
                        f'<div class="es-kpis2"><div class="es-kpi"><small>📋 Total de registros</small><b>{total_quebrados}</b></div>'
                        f'<div class="es-kpi"><small>📦 Peças perdidas</small><b>{total_pecas_perdidas}</b></div></div>', unsafe_allow_html=True)

                    for q in quebrados_lista.data:
                        nome_pq = q['produtos']['nome'] if q.get('produtos') else f"Produto #{q['produto_id']}"
                        pecas_q = _pecas_txt(q.get('detalhes_kit')) if q.get('detalhes_kit') else ""
                        st.markdown(
                            f'<div class="es-mcard atrasado"><div class="es-ic">❌</div><div class="es-minfo">'
                            f'<div class="es-mtop"><b>{escape(str(nome_pq))}</b><span class="es-qtd">− {q["quantidade"]} un.</span></div>'
                            f'<div class="es-msub">📆 {_data_br(q["data_registro"])}' + (f' · 🧩 {escape(pecas_q)}' if pecas_q else '') + '</div>'
                            f'<div class="es-motivo">Motivo: {escape(str(q["motivo"]))}</div></div></div>', unsafe_allow_html=True)
                else:
                    st.info("Nenhum item quebrado registrado.")
            except Exception as e:
                registrar_erro("estoque.py:687")
                st.error(f"Erro ao carregar itens quebrados: {e}")
