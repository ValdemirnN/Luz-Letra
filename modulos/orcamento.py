"""Módulo: 🧳 Orçamento de Evento.

Recebe as dependências por parâmetro (injeção) para não depender de variáveis globais do app.py.
Visual: mesmo padrão do Estoque (seções em pílulas, cartões com brilho dourado, botões dourados).
Toda a lógica (cálculo, salvar, PDF, converter em evento) continua a mesma; só a apresentação mudou.
"""
from html import escape
from modulos.log import registrar_erro
import json
from datetime import datetime

import streamlit as st

_CSS = """
<style>
.oc-sub { color:#A1A1AA; font-size:.95rem; margin:-.2rem 0 1rem; }
.oc-chip-titulo { display:flex; align-items:center; gap:8px; margin:0 0 .6rem; font:700 1.05rem 'Outfit',sans-serif; color:#fff; }
.oc-chip-titulo em { font-style:normal; font:600 .76rem 'Inter',sans-serif; color:#A1A1AA; }

/* navegação por seções (pílulas) — mesmo visual do Estoque */
.st-key-orc_secao, .st-key-orc_secao [data-testid="stRadio"] { width:100% !important; }
.st-key-orc_secao [role="radiogroup"], .st-key-orc_filtro_status [role="radiogroup"] { gap:8px; flex-wrap:wrap; padding:2px 2px 8px; }
.st-key-orc_secao [role="radiogroup"] > div, .st-key-orc_filtro_status [role="radiogroup"] > div { flex:0 0 auto; }
.st-key-orc_secao [data-testid="stRadioOption"], .st-key-orc_secao [role="radiogroup"] > label,
.st-key-orc_filtro_status [data-testid="stRadioOption"], .st-key-orc_filtro_status [role="radiogroup"] > label {
    padding:9px 16px; border-radius:999px; cursor:pointer; white-space:nowrap; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); transition:all .15s ease; }
.st-key-orc_secao [data-testid="stRadioOption"] p, .st-key-orc_filtro_status [data-testid="stRadioOption"] p { white-space:nowrap; margin:0; }
.st-key-orc_secao [data-testid="stRadioOption"] > div > div:first-child, .st-key-orc_filtro_status [data-testid="stRadioOption"] > div > div:first-child,
.st-key-orc_secao [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child,
.st-key-orc_filtro_status [role="radiogroup"] > label:not([data-testid="stRadioOption"]) > div:first-child { display:none !important; }
.st-key-orc_secao [data-testid="stRadioOption"]:hover, .st-key-orc_filtro_status [data-testid="stRadioOption"]:hover { border-color:rgba(255,193,7,.5); }
.st-key-orc_secao [data-testid="stRadioOption"]:has(input:checked), .st-key-orc_secao [role="radiogroup"] > label:has(input:checked) {
    background:linear-gradient(135deg,#FFC107,#FF9F1C); border-color:transparent; box-shadow:0 8px 22px rgba(255,160,0,.35); }
.st-key-orc_secao [data-testid="stRadioOption"]:has(input:checked) p { color:#1a1200 !important; font-weight:800; }
.st-key-orc_filtro_status [data-testid="stRadioOption"] { padding:6px 13px; }
.st-key-orc_filtro_status [data-testid="stRadioOption"] p { font-size:.84rem; }
.st-key-orc_filtro_status [data-testid="stRadioOption"]:has(input:checked), .st-key-orc_filtro_status [role="radiogroup"] > label:has(input:checked) {
    background:linear-gradient(135deg,rgba(255,193,7,.28),rgba(255,159,28,.10)); border-color:#FFC107; box-shadow:0 0 16px rgba(255,193,7,.22); }
.st-key-orc_filtro_status [data-testid="stRadioOption"]:has(input:checked) p { color:#FFC107 !important; font-weight:800; }

/* cartões das seções */
[class*="st-key-oc_box"] {
    position:relative; border:1px solid rgba(255,255,255,.10) !important; border-radius:20px !important; padding:1.1rem 1.15rem .7rem !important;
    background:linear-gradient(160deg,rgba(255,255,255,.065),rgba(255,255,255,.02)) !important; box-shadow:0 12px 32px rgba(0,0,0,.35); margin-bottom:.9rem; }
[class*="st-key-oc_box"]::before { content:""; position:absolute; left:22px; right:22px; top:-1px; height:2px; border-radius:2px;
    background:linear-gradient(90deg,transparent,#FFC107,transparent); box-shadow:0 0 12px rgba(255,193,7,.7); }

/* linhas de item (produto) */
[class*="st-key-oc_item_"] { padding:.55rem .8rem .35rem !important; margin-bottom:.5rem; border-radius:16px !important;
    background:rgba(255,255,255,.04) !important; border:1px solid rgba(255,255,255,.09) !important; transition:border-color .15s ease, box-shadow .15s ease; }
[class*="st-key-oc_item_"]:has(.oc-sel) { border-color:rgba(255,193,7,.65) !important; background:linear-gradient(145deg,rgba(255,193,7,.10),rgba(255,255,255,.03)) !important; box-shadow:0 0 18px rgba(255,193,7,.15); }
.oc-prod-nome { font:700 .98rem 'Outfit',sans-serif; color:#fff; overflow-wrap:anywhere; line-height:1.25; }
.oc-prod-meta { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.oc-prod-meta span { font-size:.7rem; font-weight:700; padding:3px 9px; border-radius:999px; color:#D4D4D8; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); }
.oc-prod-meta .tot { color:#1a1200; background:#FFC107; border-color:transparent; }
.oc-prod-meta .kit { color:#38BDF8; border-color:rgba(56,189,248,.45); background:rgba(56,189,248,.10); }

/* subtotal e resumo final */
.oc-subtotal { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:12px 16px; border-radius:14px; margin:.4rem 0 .5rem;
    background:rgba(255,193,7,.10); border:1px solid rgba(255,193,7,.35); }
.oc-subtotal span { color:#D4D4D8; font-weight:600; font-size:.9rem; } .oc-subtotal b { color:#FFC107; font:800 1.2rem 'Outfit',sans-serif; }
.oc-resumo { display:grid; grid-template-columns:repeat(3,1fr) 1.5fr; gap:12px; margin:.3rem 0 1rem; }
.oc-resumo > div { padding:12px 14px; border-radius:16px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); }
.oc-resumo small { display:block; color:#A1A1AA; font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.oc-resumo b { display:block; margin-top:4px; font:800 1.3rem 'Outfit',sans-serif; color:#fff; line-height:1.1; }
.oc-resumo .desc b { color:#F87171; }
.oc-resumo .total { background:linear-gradient(135deg,#1B5E20,#2E7D32); border-color:rgba(52,211,153,.5); box-shadow:0 0 26px rgba(52,211,153,.22); }
.oc-resumo .total small { color:#B9F6CA; } .oc-resumo .total b { font-size:1.75rem; }

/* botões principais dourados */
[data-testid="stMain"] [class*="st-key-oc_acoes"] button[kind="primary"] { min-height:52px; font-weight:800; }
[data-testid="stMain"] [class*="st-key-oc_acoes"] button { min-height:52px; }

/* lista de orçamentos salvos */
.oc-card { --cor:#9CA3AF; display:flex; gap:14px; padding:14px 16px; margin:.6rem 0 .2rem; border-radius:18px; position:relative; overflow:hidden;
    background:linear-gradient(145deg,rgba(255,255,255,.075),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.10); }
.oc-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--cor); box-shadow:0 0 12px var(--cor); }
.oc-card.Rascunho { --cor:#9CA3AF; } .oc-card.Enviado { --cor:#38BDF8; } .oc-card.Aprovado { --cor:#34D399; } .oc-card.Recusado { --cor:#F87171; } .oc-card.Convertido { --cor:#FFC107; }
.oc-ic { flex:0 0 40px; height:40px; display:grid; place-items:center; font-size:1.25rem; border-radius:12px; background:color-mix(in srgb,var(--cor) 15%,transparent); border:1px solid color-mix(in srgb,var(--cor) 45%,transparent); }
.oc-info { flex:1; min-width:0; }
.oc-top { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.oc-top b { font:700 1.02rem 'Outfit',sans-serif; color:#fff; overflow-wrap:anywhere; }
.oc-valor { flex:0 0 auto; font:800 1.05rem 'Outfit',sans-serif; color:var(--cor); white-space:nowrap; }
.oc-sub2 { color:#A1A1AA; font-size:.8rem; margin-top:3px; overflow-wrap:anywhere; }
.oc-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:9px; }
.oc-chips span { font-size:.7rem; font-weight:700; padding:4px 10px; border-radius:999px; color:#D4D4D8; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); }
.oc-chips .st { color:var(--cor); background:color-mix(in srgb,var(--cor) 14%,transparent); border-color:color-mix(in srgb,var(--cor) 55%,transparent); }
.oc-det { display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; margin:.2rem 0 .6rem; font-size:.9rem; color:#D4D4D8; }
.oc-det b { color:#fff; }
.oc-itens { margin:.2rem 0 .8rem; padding:0; list-style:none; }
.oc-itens li { display:flex; justify-content:space-between; gap:10px; padding:7px 12px; margin-bottom:5px; border-radius:12px; background:rgba(255,255,255,.05); font-size:.88rem; color:#E4E4E7; }
.oc-itens li b { color:#FFC107; white-space:nowrap; }

@media (max-width:900px) {
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4)) { flex-wrap:wrap !important; gap:.5rem !important; }
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4)) > [data-testid="stColumn"] { flex:1 1 calc(50% - .5rem) !important; min-width:calc(50% - .5rem) !important; width:auto !important; }
    .oc-resumo { grid-template-columns:1fr 1fr; } .oc-resumo .total { grid-column:span 2; }
}
@media (max-width:640px) {
    .st-key-orc_secao [role="radiogroup"] { gap:6px; }
    .st-key-orc_secao [data-testid="stRadioOption"] { padding:7px 12px; } .st-key-orc_secao [data-testid="stRadioOption"] p { font-size:.84rem; }
    [class*="st-key-oc_box"] { padding:1rem .9rem .5rem !important; border-radius:18px !important; }
    [class*="st-key-oc_item_"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.5rem !important; }
    [class*="st-key-oc_item_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex:1 1 calc(50% - .5rem) !important; min-width:calc(50% - .5rem) !important; width:auto !important; }
    [class*="st-key-oc_item_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex:1 1 100% !important; min-width:100% !important; }
    .oc-det { grid-template-columns:1fr; }
    .oc-card { padding:12px 13px; gap:11px; }
    [data-testid="stMain"] [class*="st-key-oc_acoes"] button[kind="primary"] { width:100%; }
}
</style>
"""

SECOES = ["📝 Criar Orçamento", "📋 Orçamentos Salvos"]
STATUS_ICONE = {"Rascunho": "📝", "Enviado": "📤", "Aprovado": "✅", "Recusado": "❌", "Convertido": "🎉"}
FILTROS_STATUS = ["Todos"] + list(STATUS_ICONE.keys())


def _data_br(d):
    try:
        return datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(d) if d else "-"


def render(supabase, emp_id, formatar_moeda, mostrar_popup, safe_json_load,
           calcular_distancia_google_maps, gerar_pdf_orcamento, REPORTLAB_DISPONIVEL):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="oc-sub">Monte a proposta, calcule o frete, gere o PDF e transforme em evento quando o cliente confirmar.</div>', unsafe_allow_html=True)

    ENDERECO_BASE_EMPRESA = st.secrets.get("ENDERECO_BASE_EMPRESA", "")

    produtos_orc = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).order("nome").execute()
    dict_produtos_orc = {p['id']: p for p in produtos_orc.data} if produtos_orc.data else {}

    secao_orc = st.radio("Seção", SECOES, horizontal=True, key="orc_secao", label_visibility="collapsed")

    # Só uma seção é desenhada por vez (pílulas). Ao olhar os orçamentos salvos, reafirma os campos do
    # formulário para o que foi digitado não se perder quando voltar para "Criar Orçamento".
    if secao_orc != SECOES[0]:
        for _k in [k for k in list(st.session_state.keys()) if isinstance(k, str) and k.startswith("orc_") and k not in ("orc_secao", "orc_filtro_status")]:
            st.session_state[_k] = st.session_state[_k]

    # ==========================================
    # CRIAR NOVO ORÇAMENTO
    # ==========================================
    if secao_orc == SECOES[0]:
        with st.container(key="oc_box_dados"):
            st.markdown('<div class="oc-chip-titulo">👤 Dados do Cliente e Evento</div>', unsafe_allow_html=True)
            col_o1, col_o2 = st.columns(2)
            with col_o1: nome_cliente_orc = st.text_input("Nome do Cliente", key="orc_nome_cliente")
            with col_o2: contato_cliente_orc = st.text_input("Contato", key="orc_contato_cliente")
            titulo_orc = st.text_input("Título / Descrição do Evento", key="orc_titulo")
            endereco_evento_orc = st.text_input("Endereço do Evento", key="orc_endereco_evento", placeholder="Rua, número, bairro, cidade")

            col_od1, col_od2, col_oh1, col_oh2 = st.columns(4)
            with col_od1: data_ini_orc = st.date_input("Data Início", format="DD/MM/YYYY", key="orc_data_ini")
            with col_od2: data_fim_orc = st.date_input("Data Fim", value=data_ini_orc, min_value=data_ini_orc, format="DD/MM/YYYY", key="orc_data_fim")
            with col_oh1: hora_ini_orc = st.time_input("Hora Início", key="orc_hora_ini")
            with col_oh2: hora_fim_orc = st.time_input("Hora Fim", key="orc_hora_fim")

        with st.container(key="oc_box_itens"):
            st.markdown('<div class="oc-chip-titulo">🛒 Itens do Orçamento <em>quantidades aproximadas — o detalhamento exato (ex: letras específicas) é feito ao confirmar o evento</em></div>', unsafe_allow_html=True)
            itens_selecionados_orc = {}
            if produtos_orc.data:
                for p in produtos_orc.data:
                    js_p = safe_json_load(p.get('observacao'))
                    valor_ref = float(p.get('valor_locacao') or 0)
                    with st.container(key=f"oc_item_{p['id']}"):
                        col_p0, col_p1, col_p2 = st.columns([2.2, 1, 1.2])
                        with col_p1:
                            qtd_p = st.number_input("Quantidade", min_value=0, value=None, placeholder="0", key=f"orc_qtd_{p['id']}") or 0
                        with col_p2:
                            valor_unit_p = st.number_input("Valor unit. (R$)", min_value=0.0, value=None, placeholder=f"{valor_ref:.2f}".replace(".", ","), format="%.2f", key=f"orc_valor_{p['id']}")
                            valor_unit_p = valor_unit_p if valor_unit_p is not None else valor_ref
                        with col_p0:
                            chips = f"<span>📦 Estoque: {p['quantidade_estoque']}</span>"
                            if js_p: chips += '<span class="kit">🔤 Kit</span>'
                            if qtd_p > 0:
                                chips += f'<span class="tot">{qtd_p}x = R$ {formatar_moeda(qtd_p * valor_unit_p)}</span>'
                            marca = '<i class="oc-sel"></i>' if qtd_p > 0 else ''
                            st.markdown(f'{marca}<div class="oc-prod-nome">{escape(str(p["nome"]))}</div><div class="oc-prod-meta">{chips}</div>', unsafe_allow_html=True)
                        if qtd_p > 0:
                            itens_selecionados_orc[p['id']] = {"nome": p['nome'], "quantidade": qtd_p, "valor_unit": valor_unit_p, "valor_total": qtd_p * valor_unit_p, "kit": bool(js_p)}
            else:
                st.info("Nenhum produto cadastrado no Estoque ainda.")

            valor_itens_orc = sum(it['valor_total'] for it in itens_selecionados_orc.values())
            st.markdown(f'<div class="oc-subtotal"><span>💲 Subtotal dos Itens ({len(itens_selecionados_orc)} selecionado(s))</span><b>R$ {formatar_moeda(valor_itens_orc)}</b></div>', unsafe_allow_html=True)

        with st.container(key="oc_box_frete"):
            st.markdown('<div class="oc-chip-titulo">🚗 Frete / Deslocamento</div>', unsafe_allow_html=True)
            col_fr1, col_fr2 = st.columns(2)
            with col_fr1: origem_orc = st.text_input("Endereço de Origem (sua base)", value="", placeholder=ENDERECO_BASE_EMPRESA, key="orc_origem")
            with col_fr2:
                if st.button("📍 Calcular Distância", key="btn_calc_dist_orc"):
                    if not origem_orc.strip() or not endereco_evento_orc.strip():
                        mostrar_popup("Preencha o endereço de origem e o do evento.", tipo="erro")
                    else:
                        try:
                            km_calc, dur_calc = calcular_distancia_google_maps(origem_orc, endereco_evento_orc)
                            st.session_state['orc_km_calc'] = km_calc
                            st.session_state['orc_dur_calc'] = dur_calc
                            mostrar_popup(f"Distância calculada: {km_calc:.1f} km")
                        except Exception as e:
                            registrar_erro("orcamento.py:71")
                            mostrar_popup(f"Erro ao calcular distância: {e}", tipo="erro")

            km_atual = st.session_state.get('orc_km_calc', 0.0)
            dur_atual = st.session_state.get('orc_dur_calc', 0.0)
            if km_atual:
                st.caption(f"📏 {km_atual:.1f} km (ida) — aprox. {dur_atual:.0f} min de trajeto")

            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1: distancia_manual = st.number_input("Distância (km, ida)", min_value=0.0, value=None, placeholder=f"{km_atual:.1f}".replace(".",","), format="%.1f", key="orc_dist_manual")
            distancia_manual = distancia_manual if distancia_manual is not None else float(km_atual)
            with col_c2: consumo_veic = st.number_input("Consumo do veículo (km/l)", min_value=0.1, value=None, placeholder="10,0", format="%.1f", key="orc_consumo")
            consumo_veic = consumo_veic if consumo_veic is not None else 10.0
            with col_c3: preco_comb = st.number_input("Preço do combustível (R$/l)", min_value=0.0, value=None, placeholder="6,20", format="%.2f", key="orc_preco_comb")
            preco_comb = preco_comb if preco_comb is not None else 6.20

            valor_frete_sugerido = (distancia_manual * 2 / consumo_veic) * preco_comb if consumo_veic > 0 else 0.0
            st.caption(f"⛽ Sugestão automática (ida e volta): R$ {formatar_moeda(valor_frete_sugerido)}")
            valor_frete_orc = st.number_input("Valor final do Frete (R$)", min_value=0.0, value=None, placeholder=f"{valor_frete_sugerido:.2f}".replace(".",","), format="%.2f", key="orc_frete_final")
            valor_frete_orc = valor_frete_orc if valor_frete_orc is not None else valor_frete_sugerido

        with st.container(key="oc_box_desc"):
            st.markdown('<div class="oc-chip-titulo">💲 Desconto, Validade e Observações</div>', unsafe_allow_html=True)
            col_d1, col_d2 = st.columns(2)
            with col_d1: desconto_orc = st.number_input("Desconto (R$)", min_value=0.0, value=None, placeholder="0,00", format="%.2f", key="orc_desconto") or 0.0
            with col_d2: validade_orc = st.number_input("Validade da Proposta (dias)", min_value=1, value=None, placeholder="7", key="orc_validade") or 7
            obs_orc = st.text_area("Observações", key="orc_obs")

        valor_total_orc = max(0.0, valor_itens_orc + valor_frete_orc - desconto_orc)
        st.markdown(f"""
            <div class="oc-resumo">
                <div><small>🛒 Itens</small><b>R$ {formatar_moeda(valor_itens_orc)}</b></div>
                <div><small>🚗 Frete</small><b>R$ {formatar_moeda(valor_frete_orc)}</b></div>
                <div class="desc"><small>🏷️ Desconto</small><b>- R$ {formatar_moeda(desconto_orc)}</b></div>
                <div class="total"><small>💰 Valor Total do Orçamento</small><b>R$ {formatar_moeda(valor_total_orc)}</b></div>
            </div>""", unsafe_allow_html=True)

        with st.container(key="oc_box_confirma"):
            confirmar_evento_ja = st.checkbox("✅ Cliente já confirmou — criar o evento automaticamente ao salvar", key="orc_confirmar_ja")
            st.caption("Desmarcado: fica salvo como orçamento (pré-cadastro) na aba 'Orçamentos Salvos', sem virar evento ainda. Marcado: já cria o evento direto, igual ao cadastro manual em Agendamento.")

        with st.container(key="oc_acoes"):
            col_sv1, col_sv2 = st.columns(2)
        with col_sv1:
            texto_btn_salvar = "✅ Salvar e Confirmar Evento" if confirmar_evento_ja else "💾 Salvar como Orçamento (Rascunho)"
            if st.button(texto_btn_salvar, key="btn_salvar_orc", use_container_width=True, type="primary"):
                if not nome_cliente_orc.strip() or not titulo_orc.strip():
                    mostrar_popup("Preencha ao menos o nome do cliente e o título do evento.", tipo="erro")
                elif not itens_selecionados_orc:
                    mostrar_popup("Selecione ao menos um item.", tipo="erro")
                else:
                    try:
                        status_inicial_orc = "Convertido" if confirmar_evento_ja else "Rascunho"
                        novo_orc = supabase.table("orcamentos").insert({
                            "empresa_id": emp_id, "nome_cliente": nome_cliente_orc, "contato_cliente": contato_cliente_orc,
                            "titulo_evento": titulo_orc, "endereco_evento": endereco_evento_orc,
                            "data_inicio": str(data_ini_orc), "data_fim": str(data_fim_orc),
                            "hora_inicio": str(hora_ini_orc), "hora_fim": str(hora_fim_orc),
                            "itens_json": json.dumps(itens_selecionados_orc), "valor_itens": valor_itens_orc,
                            "origem_endereco": origem_orc, "distancia_km": distancia_manual, "duracao_min": dur_atual,
                            "consumo_veiculo": consumo_veic, "preco_combustivel": preco_comb, "valor_frete": valor_frete_orc,
                            "desconto": desconto_orc, "valor_total": valor_total_orc, "validade_dias": int(validade_orc),
                            "status": status_inicial_orc, "observacoes": obs_orc
                        }).execute()

                        if confirmar_evento_ja:
                            orc_id_novo = novo_orc.data[0]['id']
                            novo_cliente_direto = supabase.table("clientes_eventos").insert({
                                "empresa_id": emp_id, "nome": nome_cliente_orc, "contato": contato_cliente_orc
                            }).execute()
                            cliente_id_direto = novo_cliente_direto.data[0]['id']
                            novo_evento_direto = supabase.table("eventos").insert({
                                "empresa_id": emp_id, "cliente_id": cliente_id_direto,
                                "titulo": titulo_orc, "descricao": titulo_orc,
                                "data_inicio": str(data_ini_orc), "data_fim": str(data_fim_orc),
                                "data_fim_alocacao": str(data_fim_orc), "hora_inicio": str(hora_ini_orc),
                                "hora_fim": str(hora_fim_orc), "status": "Agendado",
                                "observacao": f"Local: {endereco_evento_orc or '-'} | {obs_orc or ''}",
                                "valor_total": valor_total_orc
                            }).execute()
                            evento_id_direto = novo_evento_direto.data[0]['id']
                            data_hora_direto = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                            for pid, item in itens_selecionados_orc.items():
                                supabase.table("itens_evento").insert({
                                    "empresa_id": emp_id, "evento_id": evento_id_direto, "produto_id": int(pid),
                                    "quantidade": item['quantidade'], "observacao": "", "valor_cobrado": item['valor_total']
                                }).execute()
                            supabase.table("historico_eventos").insert({
                                "empresa_id": emp_id, "evento_id": evento_id_direto,
                                "descricao": f"🟢 Evento criado direto do Orçamento #{orc_id_novo} (confirmado na hora). Revise o detalhamento de kits (letras/números) se houver.",
                                "data_registro": data_hora_direto
                            }).execute()
                            supabase.table("orcamentos").update({"evento_id": evento_id_direto}).eq("id", orc_id_novo).execute()
                            mostrar_popup("ORÇAMENTO SALVO E EVENTO CRIADO COM SUCESSO!")
                        else:
                            mostrar_popup("ORÇAMENTO SALVO COMO RASCUNHO!")
                        st.rerun()
                    except Exception as e:
                        registrar_erro("orcamento.py:164")
                        mostrar_popup(f"Erro ao salvar: {e}", tipo="erro")
        with col_sv2:
            if REPORTLAB_DISPONIVEL and st.button("📄 Gerar PDF (sem salvar)", key="btn_pdf_orc_direto", use_container_width=True):
                orc_temp = {"titulo_evento": titulo_orc, "data_inicio": str(data_ini_orc), "data_fim": str(data_fim_orc),
                    "endereco_evento": endereco_evento_orc, "validade_dias": validade_orc, "valor_itens": valor_itens_orc,
                    "valor_frete": valor_frete_orc, "desconto": desconto_orc, "valor_total": valor_total_orc, "observacoes": obs_orc}
                buffer_orc = gerar_pdf_orcamento(orc_temp, list(itens_selecionados_orc.values()), nome_cliente_orc, contato_cliente_orc)
                st.download_button("⬇️ Baixar PDF Gerado", data=buffer_orc, file_name=f"orcamento_{nome_cliente_orc}.pdf", mime="application/pdf", key="download_pdf_orc_direto")

    # ==========================================
    # ORÇAMENTOS SALVOS
    # ==========================================
    else:
        try:
            orcamentos_lista = supabase.table("orcamentos").select("*").eq("empresa_id", emp_id).order("data_criacao", desc=True).execute()
        except Exception as e:
            registrar_erro("orcamento.py:181")
            st.error(f"Erro ao carregar orçamentos: {e}")
            orcamentos_lista = type('obj',(object,),{'data':[]})

        if orcamentos_lista.data:
            contagem = {k: 0 for k in STATUS_ICONE}
            for o in orcamentos_lista.data:
                contagem[o.get('status', 'Rascunho')] = contagem.get(o.get('status', 'Rascunho'), 0) + 1
            rotulos_filtro = {f: (f"Todos ({len(orcamentos_lista.data)})" if f == "Todos" else f"{STATUS_ICONE[f]} {f} ({contagem.get(f, 0)})") for f in FILTROS_STATUS}
            filtro_status = st.radio("Status", FILTROS_STATUS, horizontal=True, key="orc_filtro_status",
                                     format_func=lambda k: rotulos_filtro[k], label_visibility="collapsed")
            lista_filtrada = [o for o in orcamentos_lista.data if filtro_status == "Todos" or o.get('status', 'Rascunho') == filtro_status]
            if not lista_filtrada:
                st.info("Nenhum orçamento com esse status.")

            for orc in lista_filtrada:
                itens_orc = safe_json_load(orc.get('itens_json')) or {}
                itens_orc_lista = list(itens_orc.values()) if isinstance(itens_orc, dict) else []
                status_orc = orc.get('status', 'Rascunho')
                icone_status = STATUS_ICONE.get(status_orc, "📝")

                st.markdown(f"""
                    <div class="oc-card {escape(str(status_orc))}">
                        <div class="oc-ic">{icone_status}</div>
                        <div class="oc-info">
                            <div class="oc-top"><b>{escape(str(orc.get('titulo_evento') or '-'))}</b><span class="oc-valor">R$ {formatar_moeda(orc.get('valor_total', 0))}</span></div>
                            <div class="oc-sub2">👤 {escape(str(orc.get('nome_cliente') or '-'))}</div>
                            <div class="oc-chips">
                                <span class="st">{icone_status} {escape(str(status_orc))}</span>
                                <span>📅 {_data_br(orc.get('data_inicio'))} → {_data_br(orc.get('data_fim'))}</span>
                                <span>🛒 {len(itens_orc_lista)} item(ns)</span>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                with st.expander("Ver detalhes e ações"):
                    st.markdown(f"""
                        <div class="oc-det">
                            <div>👤 <b>Cliente:</b> {escape(str(orc.get('nome_cliente') or '-'))}</div>
                            <div>📞 <b>Contato:</b> {escape(str(orc.get('contato_cliente') or '-'))}</div>
                            <div>📅 <b>Período:</b> {_data_br(orc.get('data_inicio'))} até {_data_br(orc.get('data_fim'))}</div>
                            <div>📍 <b>Endereço:</b> {escape(str(orc.get('endereco_evento') or '-'))}</div>
                            <div>🛒 <b>Itens:</b> R$ {formatar_moeda(orc.get('valor_itens', 0))}</div>
                            <div>🚗 <b>Frete:</b> R$ {formatar_moeda(orc.get('valor_frete', 0))} ({orc.get('distancia_km', 0)} km)</div>
                            <div>🏷️ <b>Desconto:</b> R$ {formatar_moeda(orc.get('desconto', 0))}</div>
                            <div>💰 <b>Total:</b> R$ {formatar_moeda(orc.get('valor_total', 0))}</div>
                        </div>""", unsafe_allow_html=True)

                    if itens_orc_lista:
                        linhas = "".join(f"<li><span>{it['quantidade']}x {escape(str(it['nome']))}</span><b>R$ {formatar_moeda(it['valor_total'])}</b></li>" for it in itens_orc_lista)
                        st.markdown(f'<ul class="oc-itens">{linhas}</ul>', unsafe_allow_html=True)

                    if REPORTLAB_DISPONIVEL:
                        buffer_orc_salvo = gerar_pdf_orcamento(orc, itens_orc_lista, orc.get('nome_cliente','-'), orc.get('contato_cliente','-'))
                        st.download_button("📄 Baixar PDF", data=buffer_orc_salvo, file_name=f"orcamento_{orc['id']}.pdf", mime="application/pdf", key=f"pdf_orc_salvo_{orc['id']}")

                    st.markdown("---")
                    col_st1, col_st2, col_st3, col_st4 = st.columns(4)
                    with col_st1:
                        if status_orc not in ["Convertido"] and st.button("📤 Marcar Enviado", key=f"btn_enviado_{orc['id']}"):
                            supabase.table("orcamentos").update({"status": "Enviado"}).eq("id", orc['id']).execute()
                            st.rerun()
                    with col_st2:
                        if status_orc not in ["Convertido"] and st.button("✅ Marcar Aprovado", key=f"btn_aprovado_{orc['id']}"):
                            supabase.table("orcamentos").update({"status": "Aprovado"}).eq("id", orc['id']).execute()
                            st.rerun()
                    with col_st3:
                        if status_orc not in ["Convertido"] and st.button("❌ Marcar Recusado", key=f"btn_recusado_{orc['id']}"):
                            supabase.table("orcamentos").update({"status": "Recusado"}).eq("id", orc['id']).execute()
                            st.rerun()
                    with col_st4:
                        if st.button("🗑️ Excluir", key=f"btn_del_orc_{orc['id']}"):
                            supabase.table("orcamentos").delete().eq("id", orc['id']).execute()
                            mostrar_popup("ORÇAMENTO EXCLUÍDO!")
                            st.rerun()

                    if status_orc == "Aprovado":
                        st.markdown("---")
                        if st.button("🔄 Converter em Evento", key=f"btn_converter_{orc['id']}", type="primary"):
                            try:
                                novo_cliente_orc = supabase.table("clientes_eventos").insert({
                                    "empresa_id": emp_id, "nome": orc.get('nome_cliente'), "contato": orc.get('contato_cliente')
                                }).execute()
                                cliente_id_novo = novo_cliente_orc.data[0]['id']
                                novo_evento_orc = supabase.table("eventos").insert({
                                    "empresa_id": emp_id, "cliente_id": cliente_id_novo,
                                    "titulo": orc.get('titulo_evento'), "descricao": orc.get('titulo_evento'),
                                    "data_inicio": orc.get('data_inicio'), "data_fim": orc.get('data_fim'),
                                    "data_fim_alocacao": orc.get('data_fim'), "hora_inicio": orc.get('hora_inicio'),
                                    "hora_fim": orc.get('hora_fim'), "status": "Agendado",
                                    "observacao": f"Local: {orc.get('endereco_evento','-')} | {orc.get('observacoes','')}",
                                    "valor_total": orc.get('valor_total')
                                }).execute()
                                evento_id_novo = novo_evento_orc.data[0]['id']
                                data_hora_conv = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                for pid_str, item in itens_orc.items():
                                    supabase.table("itens_evento").insert({
                                        "empresa_id": emp_id, "evento_id": evento_id_novo, "produto_id": int(pid_str),
                                        "quantidade": item['quantidade'], "observacao": "", "valor_cobrado": item['valor_total']
                                    }).execute()
                                supabase.table("historico_eventos").insert({
                                    "empresa_id": emp_id, "evento_id": evento_id_novo,
                                    "descricao": f"🔄 Evento criado a partir do Orçamento #{orc['id']}. Revise o detalhamento de kits (letras/números) se houver.",
                                    "data_registro": data_hora_conv
                                }).execute()
                                supabase.table("orcamentos").update({"status": "Convertido", "evento_id": evento_id_novo}).eq("id", orc['id']).execute()
                                mostrar_popup("EVENTO CRIADO COM SUCESSO A PARTIR DO ORÇAMENTO!")
                                st.rerun()
                            except Exception as e:
                                registrar_erro("orcamento.py:267")
                                mostrar_popup(f"Erro ao converter: {e}", tipo="erro")
                    elif status_orc == "Convertido":
                        st.success(f"🎉 Já convertido no Evento #{orc.get('evento_id')} — confira em Agendamento.")
        else:
            st.info("Nenhum orçamento cadastrado ainda. Crie um na aba 'Criar Orçamento'.")
