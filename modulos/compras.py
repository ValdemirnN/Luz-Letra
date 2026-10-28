"""Módulo: 🛒 Compras.

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
Visual: formulário em etapas, resumo no topo e histórico em cartões (estilo "ingresso").
As regras de negócio (inserir / atualizar / editar / excluir no Supabase) continuam as mesmas.
"""
from html import escape
from modulos.log import registrar_erro
from datetime import datetime, date

import pandas as pd
import streamlit as st

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
CHAVES_FORM = ["compra_nome_produto", "compra_nome_site", "compra_tipo_aquisicao", "compra_qtd", "compra_vunit"]

_CSS = """
<style>
/* ===== Compras: visual "ingresso neon" ===== */
.cp-sub { color:#A1A1AA; font-size:.95rem; margin:-.2rem 0 1.1rem; }

/* resumo */
.cp-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:.4rem 0 1.4rem; }
.cp-kpi { position:relative; overflow:hidden; padding:16px 18px; border-radius:18px;
    background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.10);
    box-shadow:0 10px 28px rgba(0,0,0,.35); }
.cp-kpi small { display:block; color:#A1A1AA; font-size:.72rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
.cp-kpi b { display:block; margin-top:6px; font:800 1.55rem 'Outfit',sans-serif; color:#fff; line-height:1.1; }
.cp-kpi span { display:block; margin-top:4px; color:#A1A1AA; font-size:.8rem; }
.cp-kpi .ic { position:absolute; right:14px; top:12px; font-size:1.5rem; opacity:.9; filter:drop-shadow(0 0 10px rgba(255,193,7,.6)); }
.cp-kpi-hero { background:linear-gradient(135deg,#FFC107 0%,#FF9F1C 100%); border:none; box-shadow:0 14px 34px rgba(255,160,0,.32); }
.cp-kpi-hero small, .cp-kpi-hero span { color:rgba(26,18,0,.75); }
.cp-kpi-hero b { color:#1a1200; font-size:1.95rem; }
.cp-kpi-hero::after { content:""; position:absolute; right:-30px; bottom:-40px; width:130px; height:130px; border-radius:50%;
    background:radial-gradient(circle,rgba(255,255,255,.55),transparent 70%); }
.cp-kpi .alerta { color:#F87171; font-weight:700; }

/* etapas do formulário */
.cp-step { display:flex; align-items:center; gap:10px; margin:0 0 .6rem; }
.cp-step i { flex:0 0 30px; height:30px; border-radius:50%; display:grid; place-items:center; font:800 .95rem 'Outfit',sans-serif; font-style:normal;
    color:#1a1200; background:linear-gradient(135deg,#FFC107,#FF9F1C); box-shadow:0 0 16px rgba(255,193,7,.55); }
.cp-step b { font:700 1.08rem 'Outfit',sans-serif; color:#fff; }
.cp-step small { color:#A1A1AA; margin-left:auto; font-size:.75rem; }

[class*="st-key-cp_box"], [data-testid="stForm"] {
    position:relative; border:1px solid rgba(255,255,255,.10) !important; border-radius:20px !important; padding:1.15rem 1.15rem .6rem !important;
    background:linear-gradient(160deg,rgba(255,255,255,.065),rgba(255,255,255,.02)) !important; box-shadow:0 12px 32px rgba(0,0,0,.35); margin-bottom:.9rem; }
[class*="st-key-cp_box"]::before, [data-testid="stForm"]::before {
    content:""; position:absolute; left:22px; right:22px; top:-1px; height:2px; border-radius:2px;
    background:linear-gradient(90deg,transparent,#FFC107,transparent); box-shadow:0 0 12px rgba(255,193,7,.7); }

/* "Comprado onde?" vira seletor em pílulas (funciona nas versões nova e antiga do Streamlit) */
.st-key-compra_tipo_aquisicao, .st-key-compra_tipo_aquisicao [data-testid="stRadio"] { width:100% !important; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"] p { white-space:nowrap; margin:0; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"] > div { flex-direction:row; align-items:center; }
.st-key-compra_tipo_aquisicao [role="radiogroup"] { gap:10px; width:100%; flex-wrap:nowrap; }
.st-key-compra_tipo_aquisicao [role="radiogroup"] > div { flex:1; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"], .st-key-compra_tipo_aquisicao [role="radiogroup"] > label {
    width:100%; justify-content:center; padding:11px 8px; border-radius:14px; cursor:pointer;
    background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); transition:all .15s ease; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"] > div > div:first-child,
.st-key-compra_tipo_aquisicao [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child { display:none !important; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"] > div { margin:0 auto; }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"]:has(input:checked), .st-key-compra_tipo_aquisicao [role="radiogroup"] > label:has(input:checked) {
    background:linear-gradient(135deg,rgba(255,193,7,.28),rgba(255,159,28,.10)); border-color:#FFC107; box-shadow:0 0 18px rgba(255,193,7,.25); }
.st-key-compra_tipo_aquisicao [data-testid="stRadioOption"]:has(input:checked) p { color:#FFC107 !important; font-weight:800; }

/* total ao vivo */
.cp-total { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; margin:.2rem 0 .9rem; border-radius:16px;
    background:radial-gradient(120% 160% at 0% 0%,rgba(255,193,7,.20),rgba(255,193,7,.04)); border:1.5px dashed rgba(255,193,7,.55); }
.cp-total small { display:block; color:#A1A1AA; font-size:.72rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
.cp-total span { color:#D4D4D8; font-size:.85rem; }
.cp-total b { font:800 1.7rem 'Outfit',sans-serif; color:#FFC107; text-shadow:0 0 18px rgba(255,193,7,.55); white-space:nowrap; }

/* botão de registrar */
[data-testid="stFormSubmitButton"] button { width:100%; min-height:52px; font-size:1.02rem; letter-spacing:.02em;
    background:linear-gradient(135deg,#FFC107,#FF9F1C) !important; color:#1a1200 !important; border:none !important; box-shadow:0 10px 26px rgba(255,160,0,.40); }
[data-testid="stFormSubmitButton"] button:hover { filter:brightness(1.08); color:#000 !important; transform:translateY(-1px); }

/* histórico */
.cp-titulo { display:flex; align-items:center; gap:10px; margin:2rem 0 .8rem; font:800 1.45rem 'Outfit',sans-serif; color:#fff; }
.cp-titulo em { font-style:normal; font:700 .78rem 'Inter',sans-serif; color:#1a1200; background:#FFC107; padding:3px 10px; border-radius:999px; }
.st-key-compras_filtro [role="radiogroup"] { gap:8px; flex-wrap:wrap; }
.st-key-compras_filtro [data-testid="stRadioOption"], .st-key-compras_filtro [role="radiogroup"] > label {
    padding:7px 16px; border-radius:999px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); cursor:pointer; }
.st-key-compras_filtro [data-testid="stRadioOption"] > div > div:first-child,
.st-key-compras_filtro [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child { display:none !important; }
.st-key-compras_filtro [data-testid="stRadioOption"]:has(input:checked), .st-key-compras_filtro [role="radiogroup"] > label:has(input:checked) { background:#FFC107; border-color:#FFC107; }
.st-key-compras_filtro [data-testid="stRadioOption"]:has(input:checked) p { color:#1a1200 !important; font-weight:800; }

.cp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,370px),1fr)); gap:14px; margin:.8rem 0 1rem; }
.cp-card { --cor:#FFC107; display:flex; position:relative; min-height:128px; border-radius:18px; overflow:hidden;
    background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.10);
    box-shadow:0 10px 26px rgba(0,0,0,.38); transition:transform .18s ease,box-shadow .18s ease;
    -webkit-mask:radial-gradient(circle 9px at 84px 0,#0000 97%,#000) top/100% 51% no-repeat,radial-gradient(circle 9px at 84px 100%,#0000 97%,#000) bottom/100% 51% no-repeat;
            mask:radial-gradient(circle 9px at 84px 0,#0000 97%,#000) top/100% 51% no-repeat,radial-gradient(circle 9px at 84px 100%,#0000 97%,#000) bottom/100% 51% no-repeat; }
.cp-card:hover { transform:translateY(-3px); box-shadow:0 16px 34px rgba(0,0,0,.5); }
.cp-card.chegou { --cor:#34D399; } .cp-card.atrasado { --cor:#F87171; }
.cp-stub { flex:0 0 84px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; text-align:center;
    background:linear-gradient(180deg,color-mix(in srgb,var(--cor) 24%,transparent),color-mix(in srgb,var(--cor) 6%,transparent)); border-right:2px dashed rgba(255,255,255,.18); }
.cp-stub b { font:800 1.9rem 'Outfit',sans-serif; line-height:1; color:#fff; }
.cp-stub span { font-size:.7rem; font-weight:800; letter-spacing:.14em; color:var(--cor); }
.cp-stub u { text-decoration:none; font-size:1.25rem; margin-top:6px; }
.cp-body { flex:1; min-width:0; padding:14px 16px 14px 14px; display:flex; flex-direction:column; gap:8px; }
.cp-topo { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.cp-nome { font:700 1.05rem 'Outfit',sans-serif; color:#fff; line-height:1.2; overflow-wrap:anywhere; }
.cp-loja { color:#A1A1AA; font-size:.8rem; margin-top:2px; }
.cp-valor { text-align:right; flex:0 0 auto; }
.cp-valor b { display:block; font:800 1.2rem 'Outfit',sans-serif; color:#FFC107; white-space:nowrap; }
.cp-valor small { color:#A1A1AA; font-size:.72rem; white-space:nowrap; }
.cp-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:auto; }
.cp-chip { font-size:.7rem; font-weight:700; padding:4px 10px; border-radius:999px; color:#D4D4D8; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); white-space:nowrap; }
.cp-chip.st { color:var(--cor); background:color-mix(in srgb,var(--cor) 14%,transparent); border-color:color-mix(in srgb,var(--cor) 55%,transparent); text-transform:uppercase; letter-spacing:.04em; }
.cp-chip.st::before { content:""; display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; background:var(--cor); box-shadow:0 0 8px var(--cor); animation:cp-luz 1.6s ease-in-out infinite; }
.cp-card.chegou .cp-chip.st::before { animation:none; }
@keyframes cp-luz { 0%,100%{opacity:1} 50%{opacity:.35} }
.cp-obs { color:#A1A1AA; font-size:.78rem; font-style:italic; }
.cp-vazio { text-align:center; padding:34px 18px; border:1.5px dashed rgba(255,193,7,.45); border-radius:18px; background:radial-gradient(80% 120% at 50% 0%,rgba(255,193,7,.14),transparent); }
.cp-vazio .ic { font-size:2.2rem; filter:drop-shadow(0 0 12px rgba(255,193,7,.7)); }
.cp-vazio b { display:block; margin-top:6px; font:700 1.05rem 'Outfit',sans-serif; color:#fff; } .cp-vazio small { color:#A1A1AA; }

@media (max-width:640px) {
    .cp-kpis { grid-template-columns:1fr 1fr; gap:10px; }
    .cp-kpi-hero { grid-column:1 / -1; }
    .cp-kpi { padding:14px; } .cp-kpi b { font-size:1.3rem; } .cp-kpi-hero b { font-size:1.8rem; }
    [class*="st-key-cp_box"], [data-testid="stForm"] { padding:1rem .9rem .4rem !important; border-radius:18px !important; }
    .cp-total b { font-size:1.45rem; }
    .cp-card { min-height:120px; } .cp-stub { flex-basis:84px; }
}
</style>
"""


def _s(v):
    """Texto seguro (None / NaN viram vazio)."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v).strip()


def _brl(v):
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _data_br(iso):
    iso = _s(iso).split("T")[0]
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return "-"


def _data_obj(iso):
    try:
        return datetime.strptime(_s(iso).split("T")[0], "%Y-%m-%d").date()
    except Exception:
        return None


def _situacao(c, hoje):
    """'chegou' | 'atrasado' | 'aguardando'"""
    if _s(c.get("status_chegada")) == "Chegou":
        return "chegou"
    prev = _data_obj(c.get("data_prevista_chegada"))
    if prev and prev < hoje:
        return "atrasado"
    return "aguardando"


def _kpis_html(compras, hoje):
    mes = [c for c in compras if (_data_obj(c.get("data_compra")) or date.min).replace(day=1) == hoje.replace(day=1)]
    gasto_mes = sum(float(c.get("valor_total") or 0) for c in mes)
    total_geral = sum(float(c.get("valor_total") or 0) for c in compras)
    sit = [_situacao(c, hoje) for c in compras]
    a_caminho = sum(1 for x in sit if x != "chegou")
    atrasadas = sum(1 for x in sit if x == "atrasado")
    sub_cam = f'<span class="alerta">{atrasadas} atrasada(s)</span>' if atrasadas else "<span>tudo no prazo</span>"
    return (
        '<div class="cp-kpis">'
        f'<div class="cp-kpi cp-kpi-hero"><small>Investido em {MESES[hoje.month - 1]}</small><b>{_brl(gasto_mes)}</b><span>{len(mes)} compra(s) no mês</span></div>'
        f'<div class="cp-kpi"><div class="ic">🚚</div><small>A caminho</small><b>{a_caminho}</b>{sub_cam}</div>'
        f'<div class="cp-kpi"><div class="ic">🧾</div><small>Total geral</small><b>{_brl(total_geral)}</b><span>{len(compras)} registro(s)</span></div>'
        '</div>'
    )


def _cartao_html(c, hoje):
    sit = _situacao(c, hoje)
    qtd = int(c.get("quantidade") or 0)
    total = float(c.get("valor_total") or 0)
    unit = total / qtd if qtd > 0 else 0.0
    d = _data_obj(c.get("data_compra"))
    dia, mes, ano = (f"{d.day:02d}", MESES_ABREV[d.month - 1], str(d.year)) if d else ("--", "---", "")
    site = _s(c.get("tipo_aquisicao")) == "Site"
    rotulo = {"chegou": "Chegou", "atrasado": "Atrasado", "aguardando": "A caminho"}[sit]
    chips = [f'<span class="cp-chip st">{rotulo}</span>']
    if sit != "chegou":
        chips.append(f'<span class="cp-chip">📆 Prev. {escape(_data_br(c.get("data_prevista_chegada"))[:5])}</span>')
    if _s(c.get("forma_pagamento")) and _s(c.get("forma_pagamento")) != "Não informado":
        chips.append(f'<span class="cp-chip">💳 {escape(_s(c.get("forma_pagamento")))}</span>')
    if _s(c.get("numero_pedido")):
        chips.append(f'<span class="cp-chip"># {escape(_s(c.get("numero_pedido")))}</span>')
    obs = f'<div class="cp-obs">“{escape(_s(c.get("observacao")))}”</div>' if _s(c.get("observacao")) else ""
    return (
        f'<div class="cp-card {sit}">'
        f'<div class="cp-stub"><b>{dia}</b><span>{mes}</span><small style="color:#A1A1AA;font-size:.68rem">{ano}</small><u>{"🌐" if site else "🏬"}</u></div>'
        f'<div class="cp-body"><div class="cp-topo"><div><div class="cp-nome">{escape(_s(c.get("nome_produto")) or "Produto")}</div>'
        f'<div class="cp-loja">{escape(_s(c.get("fornecedor")) or "—")}</div></div>'
        f'<div class="cp-valor"><b>{_brl(total)}</b><small>{qtd} × {_brl(unit)}</small></div></div>'
        f'{obs}<div class="cp-chips">{"".join(chips)}</div></div></div>'
    )


def render(supabase, emp_id, mostrar_popup):
    st.markdown(_CSS, unsafe_allow_html=True)

    # depois de registrar, limpa os campos para não registrar a mesma compra duas vezes
    if st.session_state.pop("_compra_limpar", False):
        for k in CHAVES_FORM:
            st.session_state.pop(k, None)

    st.title("Controle de Compras")
    st.markdown('<div class="cp-sub">Registre o que entra no seu estoque e acompanhe cada pedido até chegar.</div>', unsafe_allow_html=True)

    hoje = datetime.now().date()
    compras_lista = supabase.table("compras").select("*").eq("empresa_id", emp_id).order("data_compra", desc=True).execute()
    if compras_lista.data:
        st.markdown(_kpis_html(compras_lista.data, hoje), unsafe_allow_html=True)

    # ---------- Etapa 1: produto ----------
    with st.container(key="cp_box1"):
        st.markdown('<div class="cp-step"><i>1</i><b>O que você comprou?</b></div>', unsafe_allow_html=True)
        nome_produto_compra = st.text_input("Nome do Produto", key="compra_nome_produto", placeholder="Ex.: Fita LED 5m")
        tipo_aquisicao = st.radio("Comprado onde?", ["Presencial", "Site"], horizontal=True, key="compra_tipo_aquisicao",
                                  format_func=lambda x: "🏬 Presencial" if x == "Presencial" else "🌐 Site")
        fornecedor = st.text_input("Nome do Site / Loja", key="compra_nome_site", placeholder="Ex.: Mercado Livre, Casa da Luz...")

    # ---------- Etapa 2: valores (total ao vivo) ----------
    with st.container(key="cp_box2"):
        st.markdown('<div class="cp-step"><i>2</i><b>Quanto custou?</b></div>', unsafe_allow_html=True)
        col_cp5a, col_cp5b = st.columns(2)
        with col_cp5a: quantidade_compra = st.number_input("Quantidade Comprada", min_value=1, step=1, value=None, key="compra_qtd")
        with col_cp5b: valor_unit_compra = st.number_input("Valor Unitário (R$)", min_value=0.0, value=None, format="%.2f", key="compra_vunit")
        _q, _v = quantidade_compra or 0, valor_unit_compra or 0.0
        st.markdown(
            f'<div class="cp-total"><div><small>Total da compra</small><span>{_q} × {_brl(_v)}</span></div><b>{_brl(_q * _v)}</b></div>',
            unsafe_allow_html=True)

    # ---------- Etapa 3: entrega e pagamento ----------
    with st.form("form_compras"):
        st.markdown('<div class="cp-step"><i>3</i><b>Entrega e pagamento</b></div>', unsafe_allow_html=True)
        col_cp5, col_cp6 = st.columns(2)
        with col_cp5: data_compra_input = st.date_input("Data da Compra", value=datetime.now().date(), format="DD/MM/YYYY")
        with col_cp6: data_chegada_input = st.date_input("Previsão de Chegada", value=datetime.now().date(), format="DD/MM/YYYY")
        col_cp7, col_cp8 = st.columns(2)
        with col_cp7: forma_pagamento_compra = st.selectbox("Forma de Pagamento", ["Não informado","Pix","Cartão","Dinheiro","Boleto","Outro"])
        with col_cp8: numero_pedido_compra = st.text_input("Nº do Pedido / Nota Fiscal (opcional)")
        observacao_compra = st.text_area("Observação (opcional)", height=90)
        if st.form_submit_button("➕ Registrar Compra", type="primary"):
            if not nome_produto_compra.strip() or not fornecedor.strip(): mostrar_popup("Informe o nome do produto e a loja.", tipo="erro")
            else:
                qtd_calc = quantidade_compra or 0
                vlr_calc = valor_unit_compra or 0.0
                valor_total_calc = qtd_calc * vlr_calc
                supabase.table("compras").insert({"empresa_id": emp_id,"nome_produto": nome_produto_compra,"fornecedor": fornecedor,"tipo_aquisicao": tipo_aquisicao,"local_detalhe": fornecedor,"quantidade": qtd_calc,"valor_total": valor_total_calc,"data_compra": str(data_compra_input),"data_prevista_chegada": str(data_chegada_input),"status_chegada": "Aguardando","forma_pagamento": forma_pagamento_compra,"numero_pedido": numero_pedido_compra,"observacao": observacao_compra}).execute()
                st.session_state["_compra_limpar"] = True
                mostrar_popup("COMPRA CADASTRADA COM SUCESSO!")
                st.rerun()

    # ---------- Histórico ----------
    if compras_lista.data:
        qtd_total = len(compras_lista.data)
        st.markdown(f'<div class="cp-titulo">📋 Histórico de Compras <em>{qtd_total}</em></div>', unsafe_allow_html=True)
        busca = st.text_input("Buscar", key="compras_busca", placeholder="🔎 Buscar por produto ou loja", label_visibility="collapsed")
        filtro = st.radio("Filtro", ["Todas", "A caminho", "Chegaram"], horizontal=True, key="compras_filtro", label_visibility="collapsed")
        lista = compras_lista.data
        if busca.strip():
            b = busca.strip().lower()
            lista = [c for c in lista if b in _s(c.get("nome_produto")).lower() or b in _s(c.get("fornecedor")).lower()]
        if filtro == "A caminho": lista = [c for c in lista if _situacao(c, hoje) != "chegou"]
        elif filtro == "Chegaram": lista = [c for c in lista if _situacao(c, hoje) == "chegou"]

        if lista:
            limite = st.session_state.get("compras_limite", 12)
            st.markdown('<div class="cp-grid">' + "".join(_cartao_html(c, hoje) for c in lista[:limite]) + '</div>', unsafe_allow_html=True)
            if len(lista) > limite:
                if st.button(f"Ver mais ({len(lista) - limite} restantes)", key="compras_ver_mais"):
                    st.session_state["compras_limite"] = limite + 12
                    st.rerun()
        else:
            st.markdown('<div class="cp-vazio"><div class="ic">🔎</div><b>Nada encontrado</b><small>Tente outra busca ou outro filtro.</small></div>', unsafe_allow_html=True)

        df_compras = pd.DataFrame(compras_lista.data)
        df_compras['valor_unitario'] = df_compras['valor_total'] / df_compras['quantidade']
        df_compras['valor_unitario'] = df_compras['valor_unitario'].fillna(0)
        colunas_exibir_compras = [c for c in ["nome_produto","quantidade","valor_unitario","valor_total","fornecedor","tipo_aquisicao","forma_pagamento","numero_pedido","data_compra","data_prevista_chegada","status_chegada","observacao"] if c in df_compras.columns or c == "valor_unitario"]
        with st.expander("📊 Ver tabela completa", expanded=False):
            st.dataframe(df_compras[colunas_exibir_compras], use_container_width=True, hide_index=True)
        with st.expander("🔄 Atualizar Status de Chegada", expanded=False):
            pendentes = df_compras[df_compras['status_chegada'] != 'Chegou'] if 'status_chegada' in df_compras.columns else df_compras
            if len(pendentes) > 0:
                opcoes_pend = {f"{r['nome_produto']} — {r.get('fornecedor','')} (Previsão: {r.get('data_prevista_chegada','-')})": r['id'] for _, r in pendentes.iterrows()}
                escolha_pend = st.selectbox("Selecione o item que chegou", list(opcoes_pend.keys()), key="select_compra_chegou")
                if st.button("✅ Marcar como Chegou", key="btn_marcar_chegou"):
                    supabase.table("compras").update({"status_chegada": "Chegou"}).eq("id", opcoes_pend[escolha_pend]).execute()
                    mostrar_popup("ITEM MARCADO COMO CHEGOU!")
                    st.rerun()
            else: st.caption("Nenhuma compra pendente de chegada.")
        with st.expander("✏️ Editar ou Excluir uma Compra", expanded=False):
            opcoes_edit_compra = {f"{r.get('data_compra','')} — {r.get('nome_produto','Produto')} (R$ {float(r.get('valor_total',0)):.2f})": r['id'] for _, r in df_compras.iterrows()}
            escolha_compra_txt = st.selectbox("Selecione a compra para editar", list(opcoes_edit_compra.keys()), key="select_editar_compra")
            compra_id_sel = opcoes_edit_compra[escolha_compra_txt]
            comp_sel = next(c for c in compras_lista.data if c['id'] == compra_id_sel)
            col_ec1, col_ec2 = st.columns(2)
            with col_ec1: edit_nome_c = st.text_input("Nome do Produto", value=comp_sel.get('nome_produto',''), key="ed_nome_c")
            with col_ec2: edit_loja_c = st.text_input("Loja/Site", value=comp_sel.get('fornecedor',''), key="ed_loja_c")
            col_ec3, col_ec4, col_ec5 = st.columns(3)
            with col_ec3: edit_qtd_c = st.number_input("Quantidade", min_value=1, value=int(comp_sel.get('quantidade') or 1), key="ed_qtd_c")
            with col_ec4:
                q_atual = int(comp_sel.get('quantidade') or 1)
                v_tot_atual = float(comp_sel.get('valor_total') or 0)
                v_unit_atual = v_tot_atual / q_atual if q_atual > 0 else 0.0
                edit_vunit_c = st.number_input("Valor Unitário (R$)", min_value=0.0, value=v_unit_atual, format="%.2f", key="ed_vunit_c")
            with col_ec5:
                tipos_aq = ["Presencial","Site"]
                idx_aq = tipos_aq.index(comp_sel.get('tipo_aquisicao')) if comp_sel.get('tipo_aquisicao') in tipos_aq else 0
                edit_tipo_c = st.selectbox("Comprado onde?", tipos_aq, index=idx_aq, key="ed_tipo_c")
            col_ec6, col_ec7 = st.columns(2)
            with col_ec6:
                try: dt_c = datetime.strptime(str(comp_sel.get('data_compra')).split("T")[0], "%Y-%m-%d").date()
                except Exception: registrar_erro("compras.py:82"); dt_c = datetime.now().date()
                edit_dt_c = st.date_input("Data da Compra", value=dt_c, format="DD/MM/YYYY", key="ed_dt_c")
            with col_ec7:
                try: dt_prev = datetime.strptime(str(comp_sel.get('data_prevista_chegada')).split("T")[0], "%Y-%m-%d").date()
                except Exception: registrar_erro("compras.py:86"); dt_prev = datetime.now().date()
                edit_dt_prev = st.date_input("Previsão de Chegada", value=dt_prev, format="DD/MM/YYYY", key="ed_dt_prev")
            col_ec8, col_ec9 = st.columns(2)
            with col_ec8:
                formas_pg = ["Não informado","Pix","Cartão","Dinheiro","Boleto","Outro"]
                idx_pg = formas_pg.index(comp_sel.get('forma_pagamento')) if comp_sel.get('forma_pagamento') in formas_pg else 0
                edit_forma_pg = st.selectbox("Forma de Pagamento", formas_pg, index=idx_pg, key="ed_forma_pg")
            with col_ec9: edit_num_ped = st.text_input("Nº Pedido", value=comp_sel.get('numero_pedido') or "", key="ed_num_ped")
            edit_obs_c = st.text_area("Observação", value=comp_sel.get('observacao') or "", key="ed_obs_c")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("💾 Salvar Alterações", key="btn_salvar_edit_compra"):
                    if not edit_nome_c.strip() or not edit_loja_c.strip(): mostrar_popup("Informe o nome e loja.", tipo="erro")
                    else:
                        novo_tot_c = edit_qtd_c * edit_vunit_c
                        supabase.table("compras").update({"nome_produto": edit_nome_c,"fornecedor": edit_loja_c,"local_detalhe": edit_loja_c,"quantidade": edit_qtd_c,"valor_total": novo_tot_c,"tipo_aquisicao": edit_tipo_c,"data_compra": str(edit_dt_c),"data_prevista_chegada": str(edit_dt_prev),"forma_pagamento": edit_forma_pg,"numero_pedido": edit_num_ped,"observacao": edit_obs_c}).eq("id", compra_id_sel).execute()
                        mostrar_popup("COMPRA ATUALIZADA COM SUCESSO!")
                        st.rerun()
            with col_b2:
                if st.button("🗑️ Excluir Compra", key="btn_excluir_edit_compra"):
                    supabase.table("compras").delete().eq("id", compra_id_sel).execute()
                    mostrar_popup("COMPRA EXCLUÍDA!")
                    st.rerun()
    else: st.info("Nenhuma compra registrada ainda.")
