"""Módulo: 📊 Dashboard.

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
from modulos.log import registrar_erro
import html
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st


def render(supabase, emp_id, formatar_moeda, buscar_devolucoes_pendentes):
    import plotly.graph_objects as go
    st.markdown("""<style>.stApp::before { display: none !important; }</style>""", unsafe_allow_html=True)
    st.markdown("""<style>
.dash-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:8px 0 4px;}
.dash-card{background:#1B1B1D;border-radius:12px;padding:14px 16px;border-top:3px solid #333;min-width:0;}
.dash-card .lbl{font-size:12.5px;color:#9A9A9A;font-weight:600;}
.dash-card .val{font-size:clamp(20px,5vw,28px);font-weight:800;color:#EDEDED;line-height:1.25;margin-top:4px;overflow-wrap:anywhere;}
.dash-card .tag{display:inline-block;margin-top:6px;font-size:11.5px;font-weight:700;border-radius:20px;padding:2px 10px;}
.dash-ev-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));}
@media (max-width:640px){
.dash-card.destaque{grid-column:span 2;}
h1{font-size:1.65rem !important;line-height:1.25 !important;}
.block-container{padding-left:1rem !important;padding-right:1rem !important;}
}
</style>""", unsafe_allow_html=True)
    st.title("📊 Dashboard e Inteligência de Negócio")
    nome_exibicao = st.session_state.get('nome_usuario') or "Usuário"
    st.markdown(f"#### 👋 Bem-vindo, {nome_exibicao}!")

    def _kpi(rotulo, valor, cor_borda="#333", tag=None, destaque=False):
        tag_html = ""
        if tag:
            txt, cor_tag, bg_tag = tag
            tag_html = f'<div class="tag" style="color:{cor_tag};background:{bg_tag};">{txt}</div>'
        classe = "dash-card destaque" if destaque else "dash-card"
        return (f'<div class="{classe}" style="border-top-color:{cor_borda};">'
                f'<div class="lbl">{rotulo}</div><div class="val">{valor}</div>{tag_html}</div>')

    def _fig_ranking(df, col_x, cor_barra):
        fig = px.bar(df, x=col_x, y="Produto", orientation='h', template="plotly_dark", text="Label", color_discrete_sequence=[cor_barra])
        fig.update_traces(textposition='outside', cliponaxis=False, textfont=dict(size=12, color="white"))
        fig.update_layout(dragmode=False, showlegend=False, height=max(200, 52 * len(df) + 20),
            plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
            xaxis=dict(showgrid=False, showticklabels=False, title="", zeroline=False, fixedrange=True, range=[0, float(df[col_x].max()) * 1.75]),
            yaxis=dict(title="", showgrid=False, tickfont=dict(size=12, color='white'), fixedrange=True, automargin=True),
            margin=dict(t=10, b=0, l=0, r=10))
        return fig

    hoje_date = datetime.now().date()
    try: eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao, clientes_eventos(nome)").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
    except Exception: registrar_erro("dashboard.py:22"); eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
    receita_ev = sum(float(e.get('valor_total') or 0) for e in (eventos_dash.data or []))
    total_eventos_ativos = len(eventos_dash.data) if eventos_dash.data else 0
    ticket_medio = receita_ev / total_eventos_ativos if total_eventos_ativos > 0 else 0.0
    try: compras_dash = supabase.table("compras").select("valor_total, data_compra").eq("empresa_id", emp_id).execute()
    except Exception: registrar_erro("dashboard.py:27"); compras_dash = type('obj',(object,),{'data':[]})
    despesa_comp = sum(float(c.get('valor_total') or 0) for c in (compras_dash.data or []))
    try: viagens_dash = supabase.table("despesas_viagem").select("valor, data_despesa").eq("empresa_id", emp_id).execute()
    except Exception: registrar_erro("dashboard.py:30"); viagens_dash = type('obj',(object,),{'data':[]})
    despesa_viagem = sum(float(v.get('valor') or 0) for v in (viagens_dash.data or []))
    try: fat_dash = supabase.table("faturamento").select("tipo, valor, data_pagamento").eq("empresa_id", emp_id).execute()
    except Exception: registrar_erro("dashboard.py:33"); fat_dash = type('obj',(object,),{'data':[]})
    receita_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'receita')
    despesa_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'despesa')
    total_receitas = receita_ev + receita_manual
    total_despesas = despesa_comp + despesa_viagem + despesa_manual
    lucro_liquido = total_receitas - total_despesas
    lucro_pos = lucro_liquido >= 0
    kpis_html = "".join([
        _kpi("💰 Receita Total", f"R$ {formatar_moeda(total_receitas)}", "#2E7D32"),
        _kpi("📉 Despesas Totais", f"R$ {formatar_moeda(total_despesas)}", "#C62828"),
        _kpi("✨ Lucro Líquido", f"R$ {formatar_moeda(lucro_liquido)}", "#FFC107" if lucro_pos else "#C62828",
             tag=("↑ Positivo", "#4CAF50", "rgba(76,175,80,0.15)") if lucro_pos else ("↓ Atenção", "#FF6B6B", "rgba(255,107,107,0.15)"),
             destaque=True),
        _kpi("💳 Ticket Médio", f"R$ {formatar_moeda(ticket_medio)}"),
        _kpi("🎉 Eventos Ativos", total_eventos_ativos),
    ])
    st.markdown(f'<div class="dash-grid">{kpis_html}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # ==========================================
    # PRÓXIMOS EVENTOS — em destaque no topo
    # ==========================================
    st.subheader("🗓️ Próximos Eventos")
    st.caption("Seus compromissos iminentes.")
    eventos_futuros_topo = []
    if eventos_dash.data:
        for ev in eventos_dash.data:
            try:
                d_ini = datetime.strptime(ev['data_inicio'].split('T')[0], "%Y-%m-%d").date()
                if d_ini >= hoje_date and ev['status'] != "Concluído":
                    eventos_futuros_topo.append({'Data': d_ini, 'DataStr': d_ini.strftime("%d/%m"),
                        'Cliente': ev.get('clientes_eventos',{}).get('nome','Cliente') if ev.get('clientes_eventos') else 'Cliente',
                        'Evento': ev.get('descricao','Evento')})
            except Exception: registrar_erro("dashboard.py:61"); pass
    eventos_futuros_topo = sorted(eventos_futuros_topo, key=lambda x: x['Data'])[:6]
    if eventos_futuros_topo:
        cards_ev = []
        for evf in eventos_futuros_topo:
            dias_ate = (evf['Data'] - hoje_date).days
            if dias_ate == 0: badge_pe = ("HOJE", "#FFC107")
            elif dias_ate == 1: badge_pe = ("AMANHÃ", "#FF9800")
            else: badge_pe = (f"em {dias_ate} dias", "#2E7D32")
            ev_txt = str(evf['Evento'])
            ev_curto = html.escape(ev_txt[:22] + ('...' if len(ev_txt) > 22 else ''))
            cards_ev.append(
                f'<div style="background:#1B1B1D;border-radius:10px;padding:12px 14px;border-top:3px solid {badge_pe[1]};min-width:0;">'
                f'<div style="font-size:20px;font-weight:800;color:#EDEDED;">{evf["DataStr"]}</div>'
                f'<div style="font-size:11px;font-weight:700;color:{badge_pe[1]};margin-bottom:6px;">{badge_pe[0]}</div>'
                f'<div style="font-size:13px;font-weight:600;color:#EDEDED;">{html.escape(str(evf["Cliente"]))}</div>'
                f'<div style="font-size:12px;color:#9A9A9A;">{ev_curto}</div></div>')
        st.markdown(f'<div class="dash-ev-grid">{"".join(cards_ev)}</div>', unsafe_allow_html=True)
    else:
        st.info("Agenda livre! Nenhum evento futuro programado.")
    # Eventos já encerrados que seguem sem o status "Concluído" distorcem os números do painel
    sem_baixa = 0
    for ev in (eventos_dash.data or []):
        try:
            d_ref = ev.get('data_fim_alocacao') or ev.get('data_inicio')
            d_fim_ev = datetime.strptime(str(d_ref).split('T')[0], "%Y-%m-%d").date()
            if d_fim_ev < hoje_date and ev.get('status') not in ("Concluído", "Cancelado"): sem_baixa += 1
        except Exception: registrar_erro("dashboard.py:sem_baixa"); pass
    if sem_baixa:
        st.caption(f"⚠️ {sem_baixa} evento(s) já encerrado(s) ainda não estão marcados como Concluído. Atualize na aba 📅 Agendamento para o painel ficar fiel.")
    st.markdown("---")

    def _cabecalho_alerta(icone, titulo, qtd, cor_bg, cor_txt):
        return (f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
                f'<span style="font-size:20px;">{icone}</span>'
                f'<span style="font-size:15px;font-weight:700;color:#EDEDED;">{titulo}</span>'
                f'<span style="background:{cor_bg};color:{cor_txt};font-size:12px;font-weight:700;border-radius:20px;padding:2px 10px;margin-left:auto;">{qtd}</span></div>')

    def _card_alerta(titulo, subtitulo, cor_borda, direita=""):
        return (f'<div style="border-left:4px solid {cor_borda};background:#1B1B1D;border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
                f'<span style="font-weight:700;color:#EDEDED;font-size:14px;">{titulo}</span>{direita}</div>'
                f'<div style="font-size:12.5px;margin-top:2px;">{subtitulo}</div></div>')

    def _lista_com_expander(cards, max_visivel=3):
        st.markdown("".join(cards[:max_visivel]), unsafe_allow_html=True)
        if len(cards) > max_visivel:
            with st.expander(f"Ver todos ({len(cards)})"):
                st.markdown("".join(cards[max_visivel:]), unsafe_allow_html=True)

    col_alerta1, col_alerta2 = st.columns(2)
    with col_alerta1:
        try:
            manutencao_check = supabase.table("manutencao").select("quantidade, produtos(nome), data_envio, data_prevista_retorno, local_manutencao").eq("empresa_id", emp_id).eq("status", "Em Manutenção").execute()
            if manutencao_check.data:
                hoje_manut_dash = datetime.now().date()
                st.markdown(_cabecalho_alerta("🔧", "Itens em Manutenção", len(manutencao_check.data), "#FFC107", "#0E0E0E"), unsafe_allow_html=True)
                cards_manut = []
                for m in manutencao_check.data:
                    nome_p = m['produtos']['nome'] if m.get('produtos') else "Item"
                    local_m_dash = m.get('local_manutencao') or "Local não informado"
                    dias_fora = None
                    try:
                        dt_envio_dash = datetime.strptime(str(m.get('data_envio')).split("T")[0], "%Y-%m-%d").date()
                        dias_fora = (hoje_manut_dash - dt_envio_dash).days
                    except Exception: registrar_erro("dashboard.py:100"); pass
                    atrasado_dash = False
                    try:
                        dt_prev_dash = datetime.strptime(str(m.get('data_prevista_retorno')).split("T")[0], "%Y-%m-%d").date()
                        atrasado_dash = hoje_manut_dash > dt_prev_dash
                    except Exception: registrar_erro("dashboard.py:105"); pass
                    cor_borda = "#B3261E" if atrasado_dash else "#FFC107"
                    tag_atraso = '<span style="color:#FF6B6B;font-size:11px;font-weight:700;white-space:nowrap;">⚠ ATRASADO</span>' if atrasado_dash else ""
                    dias_txt = f"há {dias_fora} dia(s)" if dias_fora is not None else ""
                    sub = f'<span style="color:#9A9A9A;">📍 {html.escape(str(local_m_dash))}{(" · " + dias_txt) if dias_txt else ""}</span>'
                    cards_manut.append(_card_alerta(f"{m['quantidade']}x {html.escape(str(nome_p))}", sub, cor_borda, tag_atraso))
                _lista_com_expander(cards_manut)
            else:
                st.success("✅ Nenhum item em manutenção no momento.")
        except Exception: registrar_erro("dashboard.py:119"); pass
    with col_alerta2:
        devolucoes_pend_dash = buscar_devolucoes_pendentes()
        if devolucoes_pend_dash:
            total_itens_pend_dash = sum(len(d['itens']) for d in devolucoes_pend_dash)
            st.markdown(_cabecalho_alerta("🔁", "Equipamentos Não Devolvidos", total_itens_pend_dash, "#B3261E", "#EDEDED"), unsafe_allow_html=True)
            cards_dev = []
            for dev in devolucoes_pend_dash:
                total_qtd_dev = sum(i['quantidade'] for i in dev['itens'])
                sub = f'<span style="color:#FF6B6B;font-weight:600;">⚠ encerrado há {dev["dias_atraso"]} dia(s) — {total_qtd_dev} peça(s) pendente(s)</span>'
                cards_dev.append(_card_alerta(html.escape(str(dev['descricao'])), sub, "#B3261E"))
            _lista_com_expander(cards_dev)
            st.caption("Confirme a devolução na aba 📅 Agendamento, dentro do evento.")
        else:
            st.success("✅ Nenhum equipamento pendente de devolução.")
    try:
        estoque_check = supabase.table("produtos").select("nome, quantidade_estoque").eq("empresa_id", emp_id).execute()
        if estoque_check.data:
            zerados = [p['nome'] for p in estoque_check.data if (p.get('quantidade_estoque') or 0) <= 0]
            if zerados: st.error(f"⚠️ **Estoque zerado:** {', '.join(zerados)}")
    except Exception: registrar_erro("dashboard.py:145"); pass
    st.markdown("<br>", unsafe_allow_html=True)
    COR_FUNDO_GRAFICO = "#161618"
    col_g1, col_g2 = st.columns([2,1])
    with col_g1:
        st.subheader("📈 Evolução Financeira")
        timeline_data = []
        for e in (eventos_dash.data or []):
            if e.get('data_inicio'): timeline_data.append({'Data': e['data_inicio'].split("T")[0], 'Receita': float(e.get('valor_total') or 0), 'Despesa': 0.0})
        for f in (fat_dash.data or []):
            if f.get('data_pagamento') and f.get('tipo') == 'receita': timeline_data.append({'Data': f['data_pagamento'].split("T")[0], 'Receita': float(f.get('valor') or 0), 'Despesa': 0.0})
        for c in (compras_dash.data or []):
            if c.get('data_compra'): timeline_data.append({'Data': c['data_compra'].split("T")[0], 'Receita': 0.0, 'Despesa': float(c.get('valor_total') or 0)})
        for v in (viagens_dash.data or []):
            if v.get('data_despesa'): timeline_data.append({'Data': v['data_despesa'].split("T")[0], 'Receita': 0.0, 'Despesa': float(v.get('valor') or 0)})
        for f in (fat_dash.data or []):
            if f.get('data_pagamento') and f.get('tipo') == 'despesa': timeline_data.append({'Data': f['data_pagamento'].split("T")[0], 'Receita': 0.0, 'Despesa': float(f.get('valor') or 0)})
        if timeline_data:
            import plotly.graph_objects as go
            df_tl = pd.DataFrame(timeline_data)
            df_tl['Data'] = pd.to_datetime(df_tl['Data'])
            df_tl['Mes'] = df_tl['Data'].dt.to_period('M')
            df_m = df_tl.groupby('Mes')[['Receita','Despesa']].sum()
            # preenche meses sem lançamento com zero, para a linha do tempo ficar contínua
            df_m = df_m.reindex(pd.period_range(df_m.index.min(), df_m.index.max(), freq='M'), fill_value=0.0)
            df_m = df_m.tail(12).reset_index()
            df_m.columns = ['Mes','Receita','Despesa']
            df_m['Lucro'] = df_m['Receita'] - df_m['Despesa']
            df_m['Rotulo'] = df_m['Mes'].dt.strftime('%m/%Y')
            fig_evolucao = go.Figure()
            fig_evolucao.add_bar(x=df_m['Rotulo'], y=df_m['Receita'], name="Receita", marker_color="#2E7D32",
                hovertemplate="Receita: R$ %{y:,.2f}<extra></extra>")
            fig_evolucao.add_bar(x=df_m['Rotulo'], y=df_m['Despesa'], name="Despesa", marker_color="#C62828",
                hovertemplate="Despesa: R$ %{y:,.2f}<extra></extra>")
            fig_evolucao.add_scatter(x=df_m['Rotulo'], y=df_m['Lucro'], name="Lucro", mode="lines+markers",
                line=dict(color="#FFC107", width=3), marker=dict(size=8),
                hovertemplate="Lucro: R$ %{y:,.2f}<extra></extra>")
            fig_evolucao.update_layout(template="plotly_dark", plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                barmode="group", bargap=0.35, separators=",.", dragmode=False, hovermode="x unified", height=320,
                yaxis=dict(title="", showgrid=True, gridcolor="#333", fixedrange=True, tickformat=",.0f", zeroline=True, zerolinecolor="#555", automargin=True),
                xaxis=dict(title="", showgrid=False, fixedrange=True, type="category"),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig_evolucao, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False})
        else: st.info("Aguardando lançamentos financeiros para gerar a linha do tempo.")
    with col_g2:
        st.subheader("📊 Status dos Eventos")
        if eventos_dash.data:
            df_status = pd.DataFrame(eventos_dash.data)
            status_counts = df_status["status"].value_counts().reset_index()
            status_counts.columns = ["Status","Quantidade"]
            mapa_cores_status = {"Concluído":"#2E7D32","Agendado":"#FFC107","Cancelado":"#C62828","Em Andamento":"#0277BD"}
            fig_status = px.pie(status_counts, names="Status", values="Quantidade", hole=0.6, color="Status", color_discrete_map=mapa_cores_status, template="plotly_dark")
            fig_status.update_traces(textposition='inside', textinfo='percent', marker=dict(line=dict(color=COR_FUNDO_GRAFICO, width=3)))
            fig_status.add_annotation(text=f"<b>{total_eventos_ativos}</b><br>Eventos", x=0.5, y=0.5, font_size=18, showarrow=False, align="center")
            fig_status.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5, title=""), height=320, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=10,b=10,l=0,r=0))
            st.plotly_chart(fig_status, use_container_width=True, config={'displayModeBar': False})
        else: st.info("Sem eventos para analisar.")
    st.markdown("---")
    col_g3, col_g4 = st.columns([1,1.4])
    ids_ativos_hoje = []
    if eventos_dash.data:
        for ev in eventos_dash.data:
            try:
                d_ini = datetime.strptime(ev['data_inicio'].split('T')[0], "%Y-%m-%d").date()
                d_fim = datetime.strptime(ev['data_fim_alocacao'].split('T')[0], "%Y-%m-%d").date()
                if d_ini <= hoje_date <= d_fim: ids_ativos_hoje.append(ev['id'])
            except Exception: registrar_erro("dashboard.py:212"); pass
    itens_alocados_hoje = 0
    if ids_ativos_hoje:
        try:
            it_hoje = supabase.table("itens_evento").select("quantidade").in_("evento_id", ids_ativos_hoje).execute()
            itens_alocados_hoje = sum(i['quantidade'] for i in (it_hoje.data or []))
        except Exception: registrar_erro("dashboard.py:218"); pass
    total_estoque_fisico = 1
    prods_ref_data = []
    try:
        prod_all = supabase.table("produtos").select("id, nome, quantidade_estoque, valor_locacao").eq("empresa_id", emp_id).execute()
        if prod_all.data:
            total_estoque_fisico = max(1, sum(p['quantidade_estoque'] for p in prod_all.data))
            prods_ref_data = prod_all.data
    except Exception: registrar_erro("dashboard.py:226"); pass
    taxa_ocupacao = (itens_alocados_hoje / total_estoque_fisico) * 100
    with col_g3:
        st.subheader("🎯 Taxa de Ocupação Hoje")
        st.caption("Volume do estoque total alugado no momento.")
        fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=taxa_ocupacao,
            number={'suffix':"%",'font':{'size':34,'color':'#FFC107'}},
            title={'text':f"{itens_alocados_hoje} de {total_estoque_fisico} itens na rua",'font':{'size':13}},
            gauge={'axis':{'range':[None,100]},'bar':{'color':"#FFC107"},'bgcolor':"#333",'borderwidth':0,
                'steps':[{'range':[0,40],'color':"rgba(46,125,50,0.3)"},{'range':[40,80],'color':"rgba(255,193,7,0.3)"},{'range':[80,100],'color':"rgba(198,40,40,0.3)"}]}))
        fig_gauge.update_layout(template="plotly_dark", plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=50,b=20,l=35,r=35), height=250)
        st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})
    with col_g4:
        st.subheader("🏆 Ranking de Produtos")
        st.caption("O que mais sai e o que dá mais lucro.")
        tab_qtd, tab_lucro = st.tabs(["Por Quantidade","Por Rentabilidade (R$)"])
        try:
            itens_dash = supabase.table("itens_evento").select(
                "evento_id, produto_id, quantidade, valor_cobrado"
            ).eq("empresa_id", emp_id).execute()
        except Exception:
            registrar_erro("dashboard.py:247")
            itens_dash = type('obj', (object,), {'data': []})

        # Monta o mapa de eventos com valor_total E soma de itens calculada
        eventos_dash_map = {}
        try:
            ev_ids = list({i['evento_id'] for i in (itens_dash.data or [])})
            if ev_ids:
                ev_resp = supabase.table("eventos").select(
                    "id, valor_total"
                ).in_("id", ev_ids).execute()
                # Calcula quantidade_total somando os itens que já temos
                qtd_por_evento = {}
                for i in (itens_dash.data or []):
                    qtd_por_evento[i['evento_id']] = qtd_por_evento.get(i['evento_id'], 0) + i['quantidade']
                for e in (ev_resp.data or []):
                    eventos_dash_map[e['id']] = {
                        'valor_total': e.get('valor_total') or 0,
                        'quantidade_total': qtd_por_evento.get(e['id'], 0)
                    }
        except Exception:
            registrar_erro("dashboard.py:268")
            pass

        if itens_dash.data and prods_ref_data:
            mapa_nomes = {p['id']: p['nome'] for p in prods_ref_data}
            mapa_valor_locacao = {p['id']: float(p.get('valor_locacao') or 0) for p in prods_ref_data}

            with tab_qtd:
                uso_produtos = {}
                for item in itens_dash.data:
                    pid = item['produto_id']
                    uso_produtos[pid] = uso_produtos.get(pid, 0) + item['quantidade']
                total_alugueis_historico = sum(uso_produtos.values())
                if uso_produtos:
                    df_top = pd.DataFrame([{"Produto": mapa_nomes.get(pid, f"Prod {pid}"), "Locações": qtd} for pid, qtd in uso_produtos.items()])
                    df_top = df_top.sort_values(by="Locações", ascending=True).tail(5)
                    df_top['Porcentagem'] = (df_top['Locações'] / total_alugueis_historico) * 100
                    df_top['Label'] = df_top['Locações'].astype(str) + " (" + df_top['Porcentagem'].round(1).astype(str) + "%)"
                    fig_top = _fig_ranking(df_top, "Locações", "#FFC107")
                    st.plotly_chart(fig_top, use_container_width=True, config={'displayModeBar': False})

            with tab_lucro:
                itens_por_evento = {}
                for item in itens_dash.data:
                    ev_id = item['evento_id']
                    itens_por_evento.setdefault(ev_id, []).append(item)

                receita_por_produto = {}
                for item in itens_dash.data:
                    pid = item['produto_id']
                    valor_item = float(item.get('valor_cobrado') or 0)

                    if valor_item == 0:
                        valor_item = mapa_valor_locacao.get(pid, 0) * item['quantidade']

                    if valor_item == 0:
                        try:
                            ev_id = item['evento_id']
                            evento_ref = eventos_dash_map.get(ev_id, {})
                            valor_geral = float(evento_ref.get('valor_total') or 0)
                            quantidade_geral = int(evento_ref.get('quantidade_total') or 0)
                            preco_unitario = float(valor_geral) / quantidade_geral if quantidade_geral > 0 else 0.0
                            valor_item = preco_unitario * item['quantidade']
                        except Exception:
                            registrar_erro("dashboard.py:316")
                            pass

                    receita_por_produto[pid] = receita_por_produto.get(pid, 0) + valor_item

                dados_lucro = [{"Produto": mapa_nomes.get(pid, f"Prod {pid}"), "Receita": v}
                               for pid, v in receita_por_produto.items() if v > 0]
                if dados_lucro:
                    df_lucro = pd.DataFrame(dados_lucro)
                    df_lucro = df_lucro.sort_values(by="Receita", ascending=True).tail(5)
                    df_lucro['Label'] = df_lucro['Receita'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                    )
                    fig_lucro = _fig_ranking(df_lucro, "Receita", "#2E7D32")
                    st.plotly_chart(fig_lucro, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("Nenhuma receita encontrada. Cadastre o valor de locação dos produtos no Estoque.")
        else:
            st.info("Dados insuficientes para ranking.")
