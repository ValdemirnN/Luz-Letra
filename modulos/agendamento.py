"""Módulo: 📅 Agendamento (eventos, kits, devoluções, recibo e Google Agenda).

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
from modulos.log import registrar_erro
import json
from datetime import datetime

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta


def render(supabase, emp_id, formatar_moeda, mostrar_popup, safe_json_load, buscar_devolucoes_pendentes, calcular_disponibilidade_periodo, definir_categoria, formatar_telefone_br, gerar_recibo_evento_pdf, sincronizar_evento_google_agenda_silencioso, REPORTLAB_DISPONIVEL):
    st.title("📅 Gestão de Agendamentos")
    produtos_disp = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).execute()
    dict_produtos = {p['id']: p for p in produtos_disp.data} if produtos_disp.data else {}
    mapa_valor_ref = {p['id']: float(p.get('valor_locacao') or 0) for p in produtos_disp.data} if produtos_disp.data else {}
    eventos_cadastrados = supabase.table("eventos").select("*").eq("empresa_id", emp_id).order("data_inicio", desc=False).execute()
    lista_todos_eventos = eventos_cadastrados.data or []
    try: clientes_resultado = supabase.table("clientes_eventos").select("id, nome, contato").eq("empresa_id", emp_id).execute()
    except Exception: registrar_erro("agendamento.py:22"); clientes_resultado = supabase.table("clientes_eventos").select("id, nome").eq("empresa_id", emp_id).execute()
    mapa_clientes = {c['id']: c for c in clientes_resultado.data} if clientes_resultado.data else {}
    hoje_dt = datetime.now().date()

    eventos_hoje = 0
    eventos_proximos_7_dias = 0
    for ev_kpi in lista_todos_eventos:
        if ev_kpi.get('status') not in ["Cancelado","Concluído"] and ev_kpi.get('data_inicio'):
            try:
                d_ini_kpi = datetime.strptime(ev_kpi['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                if d_ini_kpi == hoje_dt: eventos_hoje += 1
                elif hoje_dt < d_ini_kpi <= (hoje_dt + relativedelta(days=7)): eventos_proximos_7_dias += 1
            except Exception: registrar_erro("agendamento.py:34"); pass

    st.markdown("#### 📊 Visão Operacional")
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("📍 Eventos Hoje", eventos_hoje)
    col_k2.metric("🔜 Próximos 7 Dias", eventos_proximos_7_dias)
    col_k3.metric("📑 Total na Base", len(lista_todos_eventos))
    devolucoes_pend_agenda = buscar_devolucoes_pendentes()
    total_itens_pend_agenda = sum(len(d['itens']) for d in devolucoes_pend_agenda)
    col_k4.metric("🔁 Equip. Não Devolvidos", total_itens_pend_agenda, delta="Atenção" if total_itens_pend_agenda > 0 else None, delta_color="inverse")
    if devolucoes_pend_agenda:
        with st.expander(f"⚠️ {len(devolucoes_pend_agenda)} evento(s) com equipamentos não devolvidos ao estoque", expanded=False):
            for dev_ag in devolucoes_pend_agenda:
                total_qtd_ag = sum(i['quantidade'] for i in dev_ag['itens'])
                st.markdown(f"""
                    <div style="border-left:4px solid #B3261E;background:#1B1B1D;border-radius:8px;padding:10px 14px;margin-bottom:8px;">
                        <div style="font-weight:700;color:#EDEDED;font-size:14px;">{dev_ag['descricao']}</div>
                        <div style="color:#FF6B6B;font-size:12px;font-weight:600;">⚠ encerrado há {dev_ag['dias_atraso']} dia(s) — {total_qtd_ag} peça(s) pendente(s)</div>
                    </div>""", unsafe_allow_html=True)
            st.caption("Abra o evento correspondente na lista abaixo ou no histórico para confirmar a devolução.")
    st.markdown("---")

    st.markdown("#### 🔍 Filtrar Eventos")
    col_f1, col_f2, col_f3 = st.columns([1,1.2,1.5])
    with col_f1: filtro_status = st.multiselect("Status", ["Agendado","Em Andamento","Concluído","Cancelado"], default=["Agendado","Em Andamento"])
    with col_f2: filtro_data = st.date_input("Período (Início e Fim)", value=[hoje_dt, hoje_dt + relativedelta(days=30)], format="DD/MM/YYYY")
    with col_f3: filtro_busca = st.text_input("Buscar Cliente ou Título", placeholder="Digite o nome...")

    eventos_filtrados = []
    for ev in lista_todos_eventos:
        passa_status = (ev.get('status') in filtro_status) if filtro_status else True
        passa_data = True
        if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
            try:
                d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                if not (filtro_data[0] <= d_ini_ev <= filtro_data[1]): passa_data = False
            except Exception: registrar_erro("agendamento.py:70"); passa_data = False
        elif isinstance(filtro_data, tuple) and len(filtro_data) == 1:
            try:
                d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                if d_ini_ev != filtro_data[0]: passa_data = False
            except Exception: registrar_erro("agendamento.py:75"); passa_data = False
        passa_busca = True
        if filtro_busca.strip():
            termo = filtro_busca.lower()
            titulo_b = (ev.get('descricao') or "").lower()
            nome_cli_b = (mapa_clientes.get(ev.get('cliente_id'), {}).get('nome', "")).lower()
            if termo not in titulo_b and termo not in nome_cli_b: passa_busca = False
        if passa_status and passa_data and passa_busca: eventos_filtrados.append(ev)

    st.markdown("---")
    st.subheader(f"📋 Eventos Encontrados ({len(eventos_filtrados)})")

    if eventos_filtrados:
        for ev in eventos_filtrados:
            cliente_info = mapa_clientes.get(ev.get('cliente_id'), {})
            nome_cliente_ev = cliente_info.get('nome', "Cliente não informado")
            contato_cliente_ev = cliente_info.get('contato') or "-"
            titulo_ev = ev.get('descricao') or "Evento sem título"
            data_ini_fmt = ev['data_inicio'].split("T")[0] if ev.get('data_inicio') else "-"
            data_fim_fmt = ev['data_fim_alocacao'].split("T")[0] if ev.get('data_fim_alocacao') else "-"
            def _fmt_br(data_iso):
                if not data_iso or data_iso == "-": return "-"
                try: return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception: registrar_erro("agendamento.py:98"); return data_iso
            data_ini_br = _fmt_br(data_ini_fmt)
            data_fim_br = _fmt_br(data_fim_fmt)
            status_ev = ev.get('status') or "-"
            hora_ini_fmt = ev.get('hora_inicio')[:5] if ev.get('hora_inicio') else "00:00"
            hora_fim_fmt = ev.get('hora_fim')[:5] if ev.get('hora_fim') else "23:59"

            with st.expander(f"🎉 {titulo_ev} — {nome_cliente_ev} | {data_ini_br} ({hora_ini_fmt}) até {data_fim_br} ({hora_fim_fmt}) | Status: {status_ev}"):
                try:
                    itens_ev = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado, devolvido").eq("evento_id", ev['id']).execute()
                except Exception:
                    registrar_erro("agendamento.py:109")
                    itens_ev = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado").eq("evento_id", ev['id']).execute()
                tab_detalhes, tab_add, tab_rem, tab_valores, tab_editar, tab_hist = st.tabs(["📋 Detalhes & Recibo","➕ Adicionar Itens","➖ Remover Itens","💲 Valores","✏️ Editar Evento","🕒 Histórico"])

                with tab_detalhes:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        valor_ev = float(ev.get('valor_total') or 0)
                        st.write(f"**Data e Hora:** {data_ini_br} às {hora_ini_fmt} — {data_fim_br} às {hora_fim_fmt}")
                        st.write(f"**Valor:** R$ {formatar_moeda(valor_ev)}")
                        st.write(f"**Contato do Cliente:** {contato_cliente_ev}")
                        st.write(f"**Observações:** {ev.get('observacao') or '-'}")
                    with col_b:
                        opcoes_status = ["Agendado","Em Andamento","Concluído","Cancelado"]
                        idx_status = opcoes_status.index(status_ev) if status_ev in opcoes_status else 0
                        novo_status = st.selectbox("Alterar Status", opcoes_status, index=idx_status, key=f"status_ev_{ev['id']}")
                        if st.button("Atualizar Status", key=f"btn_status_ev_{ev['id']}"):
                            supabase.table("eventos").update({"status": novo_status}).eq("id", ev['id']).execute()
                            mostrar_popup("STATUS ATUALIZADO COM SUCESSO!")
                            st.rerun()
                    if itens_ev.data:
                        st.markdown("**Itens Alocados:**")
                        for it in itens_ev.data:
                            nome_prod = dict_produtos.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                            detalhe = f" ({it['observacao']})" if it.get('observacao') else ""
                            devolvido_tag = " ✅ devolvido" if it.get('devolvido') else " ⏳ não devolvido"
                            st.write(f"- {it['quantidade']}x {nome_prod}{detalhe}{devolvido_tag}")
                    st.markdown("---")

                    # --- DEVOLUÇÃO DE EQUIPAMENTOS AO ESTOQUE ---
                    try:
                        data_fim_ev_dt = datetime.strptime(data_fim_fmt, "%Y-%m-%d").date() if data_fim_fmt != "-" else None
                    except Exception:
                        registrar_erro("agendamento.py:142")
                        data_fim_ev_dt = None
                    itens_nao_devolvidos = [it for it in (itens_ev.data or []) if not it.get('devolvido')]
                    if itens_nao_devolvidos:
                        evento_encerrado = data_fim_ev_dt is not None and data_fim_ev_dt < datetime.now().date()
                        if evento_encerrado:
                            dias_atraso_ev = (datetime.now().date() - data_fim_ev_dt).days
                            st.error(f"⚠️ Este evento terminou há {dias_atraso_ev} dia(s) e ainda tem equipamentos não devolvidos ao estoque!")
                        else:
                            st.info("🔁 Marque abaixo os itens já devolvidos ao estoque quando o evento terminar.")
                        marcar_devolvidos = {}
                        for it_dev in itens_nao_devolvidos:
                            nome_prod_dev = dict_produtos.get(it_dev['produto_id'], {}).get('nome', f"Produto #{it_dev['produto_id']}")
                            marcar_devolvidos[it_dev['id']] = st.checkbox(f"{it_dev['quantidade']}x {nome_prod_dev} — devolvido ao estoque", key=f"chk_dev_{ev['id']}_{it_dev['id']}")
                        if st.button("✅ Confirmar Devolução dos Itens Marcados", key=f"btn_confirmar_dev_{ev['id']}"):
                            selecionados = [iid for iid, marcado in marcar_devolvidos.items() if marcado]
                            if not selecionados:
                                mostrar_popup("Marque ao menos um item como devolvido.", tipo="erro")
                            else:
                                try:
                                    for iid in selecionados:
                                        supabase.table("itens_evento").update({"devolvido": True, "data_devolucao": str(datetime.now().date())}).eq("id", iid).execute()
                                    mostrar_popup("DEVOLUÇÃO REGISTRADA COM SUCESSO!")
                                    st.rerun()
                                except Exception as e:
                                    registrar_erro("agendamento.py:167")
                                    mostrar_popup(f"Erro ao registrar devolução — verifique se a coluna 'devolvido' existe na tabela itens_evento: {e}", tipo="erro")
                    else:
                        if itens_ev.data:
                            st.success("✅ Todos os itens deste evento já foram devolvidos ao estoque.")
                    st.markdown("---")

                    if REPORTLAB_DISPONIVEL:
                        nome_usuario_pdf = st.session_state.get('nome_usuario') or "Usuário do Sistema"
                        buffer_pdf = gerar_recibo_evento_pdf(ev, itens_ev.data or [], dict_produtos, nome_cliente_ev, contato_cliente_ev, nome_usuario_pdf)
                        st.download_button("📄 Baixar Recibo de Confirmação (PDF)", data=buffer_pdf, file_name=f"recibo_evento_{ev['id']}.pdf", mime="application/pdf", key=f"recibo_pdf_{ev['id']}")

                    st.markdown("---")
                    if ev.get('pagamento_confirmado'):
                        st.success(f"✅ Pagamento confirmado via **{ev.get('metodo_confirmacao_pagamento','-')}** em {ev.get('data_confirmacao_pagamento','-')}")
                        if st.button("🗑️ Desfazer Confirmação", key=f"del_pag_{ev['id']}"):
                            supabase.table("eventos").update({"pagamento_confirmado": False, "metodo_confirmacao_pagamento": None, "data_confirmacao_pagamento": None}).eq("id", ev['id']).execute()
                            mostrar_popup("CONFIRMAÇÃO REMOVIDA!")
                            st.rerun()
                    else:
                        st.warning("⏳ Pagamento ainda não confirmado.")
                        formas_opcoes = ["Dinheiro","Pix","Cartão de Crédito","Cartão de Débito","Boleto","Outro"]
                        num_formas = st.number_input("Quantas formas de pagamento?", min_value=1, max_value=5, value=1, step=1, key=f"num_formas_{ev['id']}")
                        pagamentos_registrar = []
                        for i in range(int(num_formas)):
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                forma_i = st.selectbox(f"Forma {i+1}", formas_opcoes, key=f"forma_{ev['id']}_{i}")
                            with col_p2:
                                valor_i = st.number_input(f"Valor (R$) — Forma {i+1}", min_value=0.0, value=None, placeholder="0,00", format="%.2f", key=f"valor_{ev['id']}_{i}") or 0.0
                            pagamentos_registrar.append({"forma": forma_i, "valor": valor_i})
                        resumo_pag = " + ".join([f"{p['forma']}: R$ {formatar_moeda(p['valor'])}" for p in pagamentos_registrar if p['valor'] > 0])
                        if st.button("✅ Confirmar Pagamento", key=f"btn_conf_pag_{ev['id']}"):
                            supabase.table("eventos").update({
                                "pagamento_confirmado": True,
                                "metodo_confirmacao_pagamento": resumo_pag or "Não informado",
                                "pagamentos_json": json.dumps(pagamentos_registrar),
                                "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")
                            }).eq("id", ev['id']).execute()
                            mostrar_popup("PAGAMENTO CONFIRMADO COM SUCESSO!")
                            st.rerun()

                    if ev.get('google_event_id'): st.caption("📅 Este evento já está sincronizado com a sua Google Agenda.")
                    if st.button("📅 Sincronizar com Google Agenda", key=f"sync_google_{ev['id']}"):
                        novo_id_google = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], ev, ev.get('google_event_id'))
                        if novo_id_google:
                            try: supabase.table("eventos").update({"google_event_id": novo_id_google}).eq("id", ev['id']).execute()
                            except Exception: registrar_erro("agendamento.py:214"); pass
                            mostrar_popup("EVENTO SINCRONIZADO COM A GOOGLE AGENDA!")
                            st.rerun()
                        else: mostrar_popup("Conecte sua Google Agenda em 'Perfil' primeiro.", tipo="erro")


                with tab_add:
                    produtos_disp_edit = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).execute()
                    mapa_valor_ref_add = {p['id']: float(p.get('valor_locacao') or 0) for p in produtos_disp_edit.data} if produtos_disp_edit.data else {}
                    adicoes_selecionadas = {}
                    ev_data_inicio_add = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_inicio') else datetime.now().date()
                    ev_data_fim_add = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_fim_alocacao') else ev_data_inicio_add
                    qtd_alugada_add, detalhe_alugado_add = calcular_disponibilidade_periodo(ev_data_inicio_add, ev_data_fim_add, evento_id_excluir=ev['id'])
                    if produtos_disp_edit.data:
                        for p in produtos_disp_edit.data:
                            js_p = safe_json_load(p.get('observacao'))
                            if js_p:
                                ja_alugado_kit = detalhe_alugado_add.get(p['id'], {})
                                if any((max_v - ja_alugado_kit.get(k,0)) > 0 for k,max_v in js_p.items()):
                                    st.markdown(f"🔠 *{p['nome']}:*")
                                    cols_add = st.columns(6)
                                    idxp = 0
                                    for k, max_v in js_p.items():
                                        disp_k = max(0, max_v - ja_alugado_kit.get(k,0))
                                        if disp_k > 0:
                                            val_add = cols_add[idxp%6].number_input(f"{k} (Disp:{disp_k})", min_value=0, max_value=disp_k, value=None, key=f"add_{ev['id']}_{p['id']}_{k}")
                                            if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_{k}"] = val_add
                                            idxp += 1
                            else:
                                disp_normal = max(0, p['quantidade_estoque'] - qtd_alugada_add.get(p['id'],0))
                                if disp_normal > 0:
                                    val_add = st.number_input(f"{p['nome']} (Disp: {disp_normal})", min_value=0, max_value=disp_normal, value=None, key=f"add_{ev['id']}_{p['id']}_NORMAL")
                                    if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_NORMAL"] = val_add
                    motivo_alteracao = st.text_input("Motivo da Alteração", key=f"motivo_{ev['id']}")
                    if st.button("💾 Registrar Alteração", key=f"btn_add_{ev['id']}"):
                        if not adicoes_selecionadas: mostrar_popup("Selecione ao menos 1 item.", tipo="erro")
                        elif not motivo_alteracao.strip(): mostrar_popup("Informe o motivo da alteração.", tipo="erro")
                        else:
                            try:
                                agrupado = {}
                                for key, qtd in adicoes_selecionadas.items():
                                    p_id_str, sub = key.split("_", 1)
                                    if int(p_id_str) not in agrupado: agrupado[int(p_id_str)] = {'total':0,'detalhes':{}}
                                    agrupado[int(p_id_str)]['total'] += qtd
                                    if sub != "NORMAL": agrupado[int(p_id_str)]['detalhes'][sub] = qtd
                                data_hora_alt = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                resumo_itens = []
                                for p_id, info in agrupado.items():
                                    qtd_total = info['total']
                                    valor_sugerido_add = qtd_total * mapa_valor_ref_add.get(p_id, 0)
                                    obs_json_add = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                    item_existente = supabase.table("itens_evento").select("id, quantidade, observacao, valor_cobrado").eq("evento_id", ev['id']).eq("produto_id", p_id).execute()
                                    if item_existente.data:
                                        item_atual = item_existente.data[0]
                                        nova_qtd_item = item_atual['quantidade'] + qtd_total
                                        novo_valor_item = float(item_atual.get('valor_cobrado') or 0) + valor_sugerido_add
                                        obs_atual_item = safe_json_load(item_atual.get('observacao'))
                                        if obs_atual_item and info['detalhes']:
                                            for k, v in info['detalhes'].items(): obs_atual_item[k] = obs_atual_item.get(k,0) + v
                                            nova_obs_item = json.dumps(obs_atual_item)
                                        elif info['detalhes']: nova_obs_item = obs_json_add
                                        else: nova_obs_item = item_atual.get('observacao','')
                                        supabase.table("itens_evento").update({"quantidade": nova_qtd_item,"observacao": nova_obs_item,"valor_cobrado": novo_valor_item}).eq("id", item_atual['id']).execute()
                                    else:
                                        supabase.table("itens_evento").insert({"empresa_id": emp_id,"evento_id": ev['id'],"produto_id": p_id,"quantidade": qtd_total,"observacao": obs_json_add,"valor_cobrado": valor_sugerido_add}).execute()
                                    resumo_itens.append(f"{qtd_total}x Produto {p_id}")
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"✏️ ALTERAÇÃO: Adicionou {', '.join(resumo_itens)}. Motivo: {motivo_alteracao}","data_registro": data_hora_alt}).execute()
                                mostrar_popup("ADIÇÃO CONCLUÍDA COM SUCESSO!")
                                st.rerun()
                            except Exception as e: registrar_erro("agendamento.py:283"); mostrar_popup(f"Erro: {e}", tipo="erro")

                with tab_rem:
                    if itens_ev.data:
                        remocoes_selecionadas = {}
                        for it in itens_ev.data:
                            prod_info_it = dict_produtos.get(it['produto_id'], {})
                            nome_prod_it = prod_info_it.get('nome', f"Produto #{it['produto_id']}")
                            js_item = safe_json_load(it.get('observacao'))
                            if js_item:
                                st.markdown(f"🔠 *{nome_prod_it} (alocado):*")
                                cols_rem = st.columns(6)
                                idxr = 0
                                for k, qtd_alocada in js_item.items():
                                    if qtd_alocada > 0:
                                        val_rem = cols_rem[idxr%6].number_input(f"{k} (Aloc:{qtd_alocada})", min_value=0, max_value=qtd_alocada, value=None, key=f"rem_{ev['id']}_{it['id']}_{k}")
                                        if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_{k}"] = val_rem
                                        idxr += 1
                            else:
                                val_rem = st.number_input(f"{nome_prod_it} (Aloc: {it['quantidade']})", min_value=0, max_value=it['quantidade'], value=None, key=f"rem_{ev['id']}_{it['id']}_NORMAL")
                                if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_NORMAL"] = val_rem
                        motivo_remocao = st.text_input("Motivo da Remoção", key=f"motivo_rem_{ev['id']}")
                        if st.button("🗑️ Registrar Remoção", key=f"btn_rem_{ev['id']}"):
                            if not remocoes_selecionadas: mostrar_popup("Selecione algum item.", tipo="erro")
                            elif not motivo_remocao.strip(): mostrar_popup("Informe o motivo da remoção.", tipo="erro")
                            else:
                                data_hora_rem = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                dict_itens_ev = {it['id']: it for it in itens_ev.data}
                                resumo_remocao = []
                                agrupado_rem = {}
                                for key, qtd in remocoes_selecionadas.items():
                                    item_id_str, p_id_str, sub = key.split("_", 2)
                                    item_id = int(item_id_str)
                                    if item_id not in agrupado_rem: agrupado_rem[item_id] = {'produto_id': int(p_id_str),'total':0,'detalhes':{}}
                                    agrupado_rem[item_id]['total'] += qtd
                                    if sub != "NORMAL": agrupado_rem[item_id]['detalhes'][sub] = qtd
                                for item_id, info_rem in agrupado_rem.items():
                                    item_atual_rem = dict_itens_ev[item_id]
                                    qtd_remover = info_rem['total']
                                    qtd_antiga_rem = item_atual_rem['quantidade']
                                    valor_antigo_rem = float(item_atual_rem.get('valor_cobrado') or 0)
                                    valor_unit_medio_rem = (valor_antigo_rem / qtd_antiga_rem) if qtd_antiga_rem > 0 else 0
                                    nova_qtd_item_rem = qtd_antiga_rem - qtd_remover
                                    novo_valor_item_rem = max(0, valor_antigo_rem - (valor_unit_medio_rem * qtd_remover))
                                    obs_item_atual = safe_json_load(item_atual_rem.get('observacao'))
                                    if obs_item_atual and info_rem['detalhes']:
                                        for k, v in info_rem['detalhes'].items(): obs_item_atual[k] = max(0, obs_item_atual.get(k,0) - v)
                                        nova_obs_item_rem = json.dumps(obs_item_atual)
                                    else: nova_obs_item_rem = item_atual_rem.get('observacao','')
                                    if nova_qtd_item_rem <= 0: supabase.table("itens_evento").delete().eq("id", item_id).execute()
                                    else: supabase.table("itens_evento").update({"quantidade": nova_qtd_item_rem,"observacao": nova_obs_item_rem,"valor_cobrado": novo_valor_item_rem}).eq("id", item_id).execute()
                                    resumo_remocao.append(f"{qtd_remover}x Removidos")
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"🔻 REMOÇÃO: Retirou {', '.join(resumo_remocao)}. Motivo: {motivo_remocao}","data_registro": data_hora_rem}).execute()
                                mostrar_popup("REMOÇÃO CONCLUÍDA COM SUCESSO!")
                                st.rerun()
                    else: st.caption("Nenhum item alocado.")

                with tab_valores:
                    st.caption("Ajuste o valor final cobrado por item neste evento.")
                    if itens_ev.data:
                        for it in itens_ev.data:
                            nome_prod_v = dict_produtos.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                            valor_ref_item = it['quantidade'] * mapa_valor_ref.get(it['produto_id'], 0)
                            valor_atual_v = float(it.get('valor_cobrado') or 0)
                            col_v1, col_v2 = st.columns([2,1])
                            with col_v1:
                                st.write(f"**{nome_prod_v}** — {it['quantidade']}x")
                                st.caption(f"Valor de referência: R$ {formatar_moeda(valor_ref_item)}")
                            with col_v2:
                                novo_valor_item_v = st.number_input("Valor cobrado (R$)", min_value=0.0, value=valor_atual_v, format="%.2f", key=f"val_item_{it['id']}")
                                if st.button("💾 Salvar", key=f"btn_val_item_{it['id']}"):
                                    supabase.table("itens_evento").update({"valor_cobrado": novo_valor_item_v}).eq("id", it['id']).execute()
                                    mostrar_popup("VALOR ATUALIZADO COM SUCESSO!")
                                    st.rerun()
                            st.markdown("---")
                    else: st.caption("Nenhum item alocado.")

                with tab_editar:
                    def _parse_data_edit(data_iso):
                        if not data_iso: return datetime.now().date()
                        try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").date()
                        except Exception: registrar_erro("agendamento.py:364"); return datetime.now().date()
                    def _parse_time_edit(time_str):
                        if not time_str: return datetime.min.time()
                        try: return datetime.strptime(time_str[:5], "%H:%M").time()
                        except Exception: registrar_erro("agendamento.py:368"); return datetime.min.time()
                    col_ed1, col_ed2, col_ed3, col_ed4 = st.columns(4)
                    with col_ed1: nova_data_inicio_edit = st.date_input("Data de Início", value=_parse_data_edit(ev.get('data_inicio')), format="DD/MM/YYYY", key=f"edit_data_ini_{ev['id']}")
                    with col_ed2: nova_data_fim_edit = st.date_input("Data Fim", value=_parse_data_edit(ev.get('data_fim_alocacao')), format="DD/MM/YYYY", key=f"edit_data_fim_{ev['id']}")
                    with col_ed3: nova_hora_inicio_edit = st.time_input("Hora Início", value=_parse_time_edit(ev.get('hora_inicio')), key=f"edit_hora_ini_{ev['id']}")
                    with col_ed4: nova_hora_fim_edit = st.time_input("Hora Fim", value=_parse_time_edit(ev.get('hora_fim')), key=f"edit_hora_fim_{ev['id']}")
                    novo_valor_edit = st.number_input("Valor Cobrado (R$)", min_value=0.0, step=50.0, value=float(ev.get('valor_total') or 0), format="%.2f", key=f"edit_valor_{ev['id']}")
                    novo_local_edit = st.text_area("Local/Observações", value=ev.get('observacao') or "", key=f"edit_local_{ev['id']}")
                    col_ec1, col_ec2 = st.columns(2)
                    with col_ec1: novo_nome_cliente_edit = st.text_input("Nome do Cliente", value=nome_cliente_ev, key=f"edit_nome_cli_{ev['id']}")
                    with col_ec2: novo_contato_cliente_edit = st.text_input("Contato do Cliente", value=contato_cliente_ev if contato_cliente_ev != "-" else "", key=f"edit_contato_cli_{ev['id']}")
                    justificativa_edit = st.text_input("Justificativa (obrigatório)", key=f"edit_just_{ev['id']}")
                    col_btn_edit1, col_btn_edit2 = st.columns(2)
                    with col_btn_edit1:
                        if st.button("💾 Salvar Alterações", key=f"btn_edit_evento_{ev['id']}"):
                            if not justificativa_edit.strip(): mostrar_popup("Informe a justificativa da alteração.", tipo="erro")
                            else:
                                supabase.table("eventos").update({"data_inicio": str(nova_data_inicio_edit),"data_fim": str(nova_data_fim_edit),"data_fim_alocacao": str(nova_data_fim_edit),"hora_inicio": str(nova_hora_inicio_edit),"hora_fim": str(nova_hora_fim_edit),"valor_total": novo_valor_edit,"observacao": novo_local_edit}).eq("id", ev['id']).execute()
                                if ev.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": novo_nome_cliente_edit,"contato": novo_contato_cliente_edit}).eq("id", ev['cliente_id']).execute()
                                evento_atualizado_google = dict(ev)
                                evento_atualizado_google.update({"data_inicio": str(nova_data_inicio_edit),"data_fim_alocacao": str(nova_data_fim_edit),"observacao": novo_local_edit})
                                novo_id_google_edit = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], evento_atualizado_google, ev.get('google_event_id'))
                                if novo_id_google_edit and not ev.get('google_event_id'):
                                    try: supabase.table("eventos").update({"google_event_id": novo_id_google_edit}).eq("id", ev['id']).execute()
                                    except Exception: registrar_erro("agendamento.py:392"); pass
                                data_hora_edit = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"✏️ EDIÇÃO DE DADOS. Justificativa: {justificativa_edit}","data_registro": data_hora_edit}).execute()
                                mostrar_popup("EDIÇÃO CONCLUÍDA COM SUCESSO!")
                                st.rerun()
                    with col_btn_edit2:
                        if st.button("🗑️ Excluir Evento", key=f"btn_excluir_evento_{ev['id']}"):
                            try:
                                supabase.table("itens_evento").delete().eq("evento_id", ev['id']).execute()
                                supabase.table("historico_eventos").delete().eq("evento_id", ev['id']).execute()
                                supabase.table("eventos").delete().eq("id", ev['id']).execute()
                                mostrar_popup("EVENTO EXCLUÍDO COM SUCESSO!")
                                st.rerun()
                            except Exception as e: registrar_erro("agendamento.py:405"); mostrar_popup(f"Erro ao excluir: {e}", tipo="erro")

                with tab_hist:
                    historico_ev = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev['id']).order("data_registro", desc=True).execute()
                    if historico_ev.data:
                        for h in historico_ev.data: st.write(f"🕒 **{h['data_registro']}** — {h['descricao']}")
                    else: st.caption("Nenhuma alteração registrada.")

    # ==========================================
    # HISTÓRICO DE EVENTOS PASSADOS
    # ==========================================
    st.markdown("---")
    with st.expander("🕒 Histórico de Todos os Eventos", expanded=False):
        st.caption("Todos os eventos cadastrados — inclusive os que ficaram com status em aberto (Agendado/Em Andamento sem conclusão).")
        col_hf1, col_hf2 = st.columns(2)
        with col_hf1: hist_busca = st.text_input("Buscar no histórico", placeholder="Nome do cliente ou evento...", key="hist_busca_ev")
        with col_hf2: hist_status_sel = st.multiselect(
            "Status",
            ["Concluído", "Cancelado", "Agendado", "Em Andamento"],
            default=["Concluído", "Cancelado", "Agendado", "Em Andamento"],
            key="hist_status_ev"
        )
        # Mostra TODOS os eventos que batem com o filtro de status,
        # independente de data — assim eventos esquecidos/abertos aparecem
        todos_status_validos = hist_status_sel or ["Concluído", "Cancelado", "Agendado", "Em Andamento"]
        eventos_historico = [ev for ev in lista_todos_eventos if ev.get('status') in todos_status_validos]
        if hist_busca.strip():
            termo_h = hist_busca.lower()
            eventos_historico = [ev for ev in eventos_historico if termo_h in (ev.get('descricao') or '').lower() or termo_h in (mapa_clientes.get(ev.get('cliente_id'),{}).get('nome','') or '').lower()]
        eventos_historico = sorted(eventos_historico, key=lambda x: x.get('data_inicio') or '', reverse=True)
        st.markdown(f"**{len(eventos_historico)} evento(s) encontrado(s)**")
        if eventos_historico:
            for ev_h in eventos_historico:
                cliente_h = mapa_clientes.get(ev_h.get('cliente_id'), {})
                nome_cli_h = cliente_h.get('nome', 'Cliente não informado')
                titulo_h = ev_h.get('descricao') or 'Evento sem título'
                status_h = ev_h.get('status') or '-'
                def _fmt_h(d):
                    try: return datetime.strptime(d.split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                    except Exception: registrar_erro("agendamento.py:444"); return d or '-'
                data_ini_h = _fmt_h(ev_h.get('data_inicio') or '')
                data_fim_h = _fmt_h(ev_h.get('data_fim_alocacao') or '')
                valor_h = float(ev_h.get('valor_total') or 0)
                icone_h = "✅" if status_h == "Concluído" else ("❌" if status_h == "Cancelado" else "🟡")
                with st.expander(f"{icone_h} {titulo_h} — {nome_cli_h} | {data_ini_h} → {data_fim_h} | R$ {formatar_moeda(valor_h)} | {status_h}"):
                    try:
                        itens_h = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado, devolvido").eq("evento_id", ev_h['id']).execute()
                    except Exception:
                        registrar_erro("agendamento.py:453")
                        itens_h = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado").eq("evento_id", ev_h['id']).execute()
                    contato_h = cliente_h.get('contato') or '-'

                    tab_det_h, tab_status_h, tab_pag_h, tab_edit_h, tab_log_h = st.tabs([
                        "📋 Detalhes", "🔄 Alterar Status", "💳 Pagamento", "✏️ Editar Dados", "🕒 Log"
                    ])

                    # --- ABA DETALHES ---
                    with tab_det_h:
                        col_h1, col_h2 = st.columns(2)
                        with col_h1:
                            st.write(f"**Cliente:** {nome_cli_h}")
                            st.write(f"**Contato:** {contato_h}")
                            st.write(f"**Período:** {data_ini_h} até {data_fim_h}")
                            st.write(f"**Valor:** R$ {formatar_moeda(valor_h)}")
                            st.write(f"**Local/Obs:** {ev_h.get('observacao') or '-'}")
                        with col_h2:
                            st.write(f"**Status:** {status_h}")
                            pag_h = "✅ Confirmado" if ev_h.get('pagamento_confirmado') else "⏳ Pendente"
                            st.write(f"**Pagamento:** {pag_h}")
                            if ev_h.get('metodo_confirmacao_pagamento'): st.write(f"**Método:** {ev_h['metodo_confirmacao_pagamento']}")
                            if ev_h.get('data_confirmacao_pagamento'): st.write(f"**Confirmado em:** {ev_h['data_confirmacao_pagamento']}")
                        if itens_h.data:
                            st.markdown("**Itens alocados:**")
                            for it_h in itens_h.data:
                                nome_p_h = dict_produtos.get(it_h['produto_id'],{}).get('nome',f"Produto #{it_h['produto_id']}")
                                det_h = ""
                                js_h = safe_json_load(it_h.get('observacao'))
                                if js_h: det_h = " — " + ", ".join([f"{k}: {v}x" for k,v in js_h.items()])
                                devolvido_tag_h = " ✅ devolvido" if it_h.get('devolvido') else " ⏳ não devolvido"
                                st.write(f"  • {it_h['quantidade']}x {nome_p_h}{det_h}{devolvido_tag_h}")

                        # --- DEVOLUÇÃO DE EQUIPAMENTOS (HISTÓRICO) ---
                        itens_h_pendentes = [it for it in (itens_h.data or []) if not it.get('devolvido')]
                        if itens_h_pendentes:
                            try:
                                data_fim_h_dt = datetime.strptime(ev_h.get('data_fim_alocacao','').split("T")[0], "%Y-%m-%d").date()
                            except Exception:
                                registrar_erro("agendamento.py:492")
                                data_fim_h_dt = None
                            if data_fim_h_dt and data_fim_h_dt < datetime.now().date():
                                dias_atraso_h = (datetime.now().date() - data_fim_h_dt).days
                                st.error(f"⚠️ Evento encerrado há {dias_atraso_h} dia(s) — ainda há equipamentos não devolvidos ao estoque!")
                            st.markdown("**🔁 Registrar devolução:**")
                            marcar_dev_h = {}
                            for it_dev_h in itens_h_pendentes:
                                nome_prod_dev_h = dict_produtos.get(it_dev_h['produto_id'], {}).get('nome', f"Produto #{it_dev_h['produto_id']}")
                                marcar_dev_h[it_dev_h['id']] = st.checkbox(f"{it_dev_h['quantidade']}x {nome_prod_dev_h} — devolvido ao estoque", key=f"chk_dev_h_{ev_h['id']}_{it_dev_h['id']}")
                            if st.button("✅ Confirmar Devolução", key=f"btn_confirmar_dev_h_{ev_h['id']}"):
                                selecionados_h = [iid for iid, marcado in marcar_dev_h.items() if marcado]
                                if not selecionados_h:
                                    mostrar_popup("Marque ao menos um item como devolvido.", tipo="erro")
                                else:
                                    try:
                                        for iid in selecionados_h:
                                            supabase.table("itens_evento").update({"devolvido": True, "data_devolucao": str(datetime.now().date())}).eq("id", iid).execute()
                                        mostrar_popup("DEVOLUÇÃO REGISTRADA COM SUCESSO!")
                                        st.rerun()
                                    except Exception as e:
                                        registrar_erro("agendamento.py:513")
                                        mostrar_popup(f"Erro ao registrar devolução — verifique se a coluna 'devolvido' existe na tabela itens_evento: {e}", tipo="erro")
                        elif itens_h.data:
                            st.success("✅ Todos os itens deste evento já foram devolvidos ao estoque.")
                        if REPORTLAB_DISPONIVEL:
                            nome_usuario_pdf_h = st.session_state.get('nome_usuario') or 'Usuário'
                            buffer_pdf_h = gerar_recibo_evento_pdf(ev_h, itens_h.data or [], dict_produtos, nome_cli_h, contato_h, nome_usuario_pdf_h)
                            st.download_button("📄 Baixar Recibo (PDF)", data=buffer_pdf_h, file_name=f"recibo_historico_{ev_h['id']}.pdf", mime="application/pdf", key=f"pdf_hist_{ev_h['id']}")

                    # --- ABA ALTERAR STATUS ---
                    with tab_status_h:
                        st.caption("Corrija o status deste evento caso tenha ficado em aberto por engano.")
                        opcoes_status_h = ["Agendado","Em Andamento","Concluído","Cancelado"]
                        idx_status_h = opcoes_status_h.index(status_h) if status_h in opcoes_status_h else 0
                        novo_status_h = st.selectbox("Novo Status", opcoes_status_h, index=idx_status_h, key=f"hist_status_sel_{ev_h['id']}")
                        just_status_h = st.text_input("Justificativa (obrigatório)", key=f"hist_just_status_{ev_h['id']}")
                        if st.button("✅ Salvar Status", key=f"hist_btn_status_{ev_h['id']}"):
                            if not just_status_h.strip():
                                mostrar_popup("Informe a justificativa.", tipo="erro")
                            else:
                                supabase.table("eventos").update({"status": novo_status_h}).eq("id", ev_h['id']).execute()
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev_h['id'], "descricao": f"🔄 STATUS ALTERADO para '{novo_status_h}' via Histórico. Motivo: {just_status_h}", "data_registro": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}).execute()
                                mostrar_popup("STATUS ATUALIZADO COM SUCESSO!")
                                st.rerun()

                    # --- ABA PAGAMENTO ---
                    with tab_pag_h:
                        if ev_h.get('pagamento_confirmado'):
                            st.success(f"✅ Pagamento confirmado via **{ev_h.get('metodo_confirmacao_pagamento','-')}** em {ev_h.get('data_confirmacao_pagamento','-')}")
                            if st.button("🗑️ Desfazer Confirmação", key=f"hist_del_pag_{ev_h['id']}"):
                                supabase.table("eventos").update({"pagamento_confirmado": False, "metodo_confirmacao_pagamento": None, "data_confirmacao_pagamento": None}).eq("id", ev_h['id']).execute()
                                mostrar_popup("CONFIRMAÇÃO REMOVIDA!")
                                st.rerun()
                        else:
                            st.warning("⏳ Pagamento ainda não confirmado.")
                            formas_opcoes_h = ["Dinheiro","Pix","Cartão de Crédito","Cartão de Débito","Boleto","Outro"]
                            num_formas_h = st.number_input("Quantas formas de pagamento?", min_value=1, max_value=5, value=1, step=1, key=f"num_formas_h_{ev_h['id']}")
                            pagamentos_hist = []
                            for i in range(int(num_formas_h)):
                                col_h1, col_h2 = st.columns(2)
                                with col_h1:
                                    forma_h_i = st.selectbox(f"Forma {i+1}", formas_opcoes_h, key=f"forma_h_{ev_h['id']}_{i}")
                                with col_h2:
                                    valor_h_i = st.number_input(f"Valor (R$) — Forma {i+1}", min_value=0.0, value=None, placeholder="0,00", format="%.2f", key=f"valor_h_{ev_h['id']}_{i}") or 0.0
                                pagamentos_hist.append({"forma": forma_h_i, "valor": valor_h_i})
                            resumo_pag_h = " + ".join([f"{p['forma']}: R$ {formatar_moeda(p['valor'])}" for p in pagamentos_hist if p['valor'] > 0])
                            if st.button("✅ Confirmar Pagamento", key=f"hist_btn_pag_{ev_h['id']}"):
                                supabase.table("eventos").update({
                                    "pagamento_confirmado": True,
                                    "metodo_confirmacao_pagamento": resumo_pag_h or "Não informado",
                                    "pagamentos_json": json.dumps(pagamentos_hist),
                                    "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")
                                }).eq("id", ev_h['id']).execute()
                                mostrar_popup("PAGAMENTO CONFIRMADO!")
                                st.rerun()

                    # --- ABA EDITAR DADOS ---
                    with tab_edit_h:
                        st.caption("Corrija datas, valor, local ou dados do cliente.")
                        def _pd(d):
                            if not d: return datetime.now().date()
                            try: return datetime.strptime(d.split("T")[0], "%Y-%m-%d").date()
                            except Exception: registrar_erro("agendamento.py:575"); return datetime.now().date()
                        def _pt(t):
                            if not t: return datetime.min.time()
                            try: return datetime.strptime(t[:5], "%H:%M").time()
                            except Exception: registrar_erro("agendamento.py:579"); return datetime.min.time()
                        col_he1, col_he2, col_he3, col_he4 = st.columns(4)
                        with col_he1: nd_ini_h = st.date_input("Data Início", value=_pd(ev_h.get('data_inicio')), format="DD/MM/YYYY", key=f"hedit_ini_{ev_h['id']}")
                        with col_he2: nd_fim_h = st.date_input("Data Fim", value=_pd(ev_h.get('data_fim_alocacao')), format="DD/MM/YYYY", key=f"hedit_fim_{ev_h['id']}")
                        with col_he3: nh_ini_h = st.time_input("Hora Início", value=_pt(ev_h.get('hora_inicio')), key=f"hedit_hini_{ev_h['id']}")
                        with col_he4: nh_fim_h = st.time_input("Hora Fim", value=_pt(ev_h.get('hora_fim')), key=f"hedit_hfim_{ev_h['id']}")
                        nval_h = st.number_input("Valor (R$)", min_value=0.0, step=50.0, value=float(ev_h.get('valor_total') or 0), format="%.2f", key=f"hedit_val_{ev_h['id']}")
                        nobs_h = st.text_area("Local/Observações", value=ev_h.get('observacao') or "", key=f"hedit_obs_{ev_h['id']}")
                        col_hec1, col_hec2 = st.columns(2)
                        with col_hec1: nnome_cli_h = st.text_input("Nome do Cliente", value=nome_cli_h, key=f"hedit_nome_{ev_h['id']}")
                        with col_hec2: ncont_cli_h = st.text_input("Contato", value=contato_h if contato_h != "-" else "", key=f"hedit_cont_{ev_h['id']}")
                        njust_h = st.text_input("Justificativa (obrigatório)", key=f"hedit_just_{ev_h['id']}")
                        col_hbtn1, col_hbtn2 = st.columns(2)
                        with col_hbtn1:
                            if st.button("💾 Salvar Alterações", key=f"hedit_btn_{ev_h['id']}"):
                                if not njust_h.strip(): mostrar_popup("Informe a justificativa.", tipo="erro")
                                else:
                                    supabase.table("eventos").update({"data_inicio": str(nd_ini_h), "data_fim": str(nd_fim_h), "data_fim_alocacao": str(nd_fim_h), "hora_inicio": str(nh_ini_h), "hora_fim": str(nh_fim_h), "valor_total": nval_h, "observacao": nobs_h}).eq("id", ev_h['id']).execute()
                                    if ev_h.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": nnome_cli_h, "contato": ncont_cli_h}).eq("id", ev_h['cliente_id']).execute()
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev_h['id'], "descricao": f"✏️ EDIÇÃO via Histórico. Justificativa: {njust_h}", "data_registro": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}).execute()
                                    mostrar_popup("ALTERAÇÃO SALVA COM SUCESSO!")
                                    st.rerun()
                        with col_hbtn2:
                            if st.button("🗑️ Excluir Evento", key=f"hedit_del_{ev_h['id']}"):
                                try:
                                    supabase.table("itens_evento").delete().eq("evento_id", ev_h['id']).execute()
                                    supabase.table("historico_eventos").delete().eq("evento_id", ev_h['id']).execute()
                                    supabase.table("eventos").delete().eq("id", ev_h['id']).execute()
                                    mostrar_popup("EVENTO EXCLUÍDO!")
                                    st.rerun()
                                except Exception as e: registrar_erro("agendamento.py:609"); mostrar_popup(f"Erro ao excluir: {e}", tipo="erro")

                    # --- ABA LOG ---
                    with tab_log_h:
                        hist_alt = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev_h['id']).order("data_registro", desc=True).execute()
                        if hist_alt.data:
                            for h_alt in hist_alt.data: st.write(f"🕒 **{h_alt['data_registro']}** — {h_alt['descricao']}")
                        else: st.caption("Nenhuma alteração registrada.")

        else: st.info("Nenhum evento histórico encontrado com esses filtros.")

    st.markdown("---")
    with st.expander("📝 Cadastrar Novo Evento", expanded=False):
        st.markdown("**🗓️ Primeiro, escolha as datas e horários do evento:**")
        col_data1, col_data2, col_hora1, col_hora2 = st.columns(4)
        with col_data1: data_inicio = st.date_input("Data Início", format="DD/MM/YYYY", key="novo_evento_data_inicio")
        with col_data2: data_fim = st.date_input("Data Fim", value=data_inicio, min_value=data_inicio, format="DD/MM/YYYY", key="novo_evento_data_fim")
        with col_hora1: hora_inicio = st.time_input("Hora Início", key="novo_evento_hora_inicio")
        with col_hora2: hora_fim = st.time_input("Hora Fim", key="novo_evento_hora_fim")
        qtd_alugada_form, detalhe_alugado_form = calcular_disponibilidade_periodo(data_inicio, data_fim, hora_inicio, hora_fim)
        with st.form("form_evento"):
            col_1, col_2, col_3, col_3b = st.columns(4)
            with col_1: nome_evento = st.text_input("Título do Evento")
            with col_2: nome_cliente = st.text_input("Nome do Cliente")
            with col_3: contato_cliente = st.text_input("Contato (Telefone/WhatsApp)", placeholder="(84) 99999-9999")
            with col_3b: status_evento = st.selectbox("Status", ["Agendado","Em Andamento","Concluído","Cancelado"])
            st.info(f"📅 Datas selecionadas: **{data_inicio.strftime('%d/%m/%Y')}** até **{data_fim.strftime('%d/%m/%Y')}**")
            valor_evento = st.number_input("Valor Cobrado pelo Evento (R$)", min_value=0.0, step=50.0, value=None, format="%.2f")
            st.markdown("**📍 Localização do Evento**")
            col_7, col_8, col_9, col_10 = st.columns([2,2,1.5,0.5])
            with col_7: local_evento = st.text_input("Local do Evento")
            with col_8: rua_evento = st.text_input("Nome da Rua")
            with col_9: bairro_evento = st.text_input("Bairro")
            with col_10: numero_evento = st.text_input("Número")
            obs_evento_geral = st.text_area("Observações Gerais do Evento")
            st.markdown("---")
            st.subheader("🛒 Itens para o Evento")
            quantidades_selecionadas = {}
            if produtos_disp.data:
                df_p = pd.DataFrame(produtos_disp.data)
                df_p['Categoria'] = df_p['nome'].apply(definir_categoria)
                categorias = sorted(df_p['Categoria'].unique())
                for cat in categorias:
                    st.markdown(f"**{cat}**")
                    prods_cat = df_p[df_p['Categoria'] == cat].to_dict('records')
                    col1, col2, col3 = st.columns(3)
                    colunas = [col1, col2, col3]
                    for index, prod in enumerate(prods_cat):
                        if prod['quantidade_estoque'] > 0:
                            js_estoque = safe_json_load(prod.get('observacao'))
                            if js_estoque:
                                st.markdown(f"🔠 **{prod['nome']}** - *Especifique as peças abaixo:*")
                                cols_k = st.columns(10)
                                idx = 0
                                alugados_prod_kit = detalhe_alugado_form.get(prod['id'], {})
                                for k, max_v in js_estoque.items():
                                    disponivel_k = max_v - alugados_prod_kit.get(k, 0)
                                    if max_v > 0:
                                        qtd_item = cols_k[idx%10].number_input(f"{k} (Livre:{max(0,disponivel_k)})", min_value=0, max_value=max(0,disponivel_k), value=None, key=f"aloc_{prod['id']}_{k}")
                                        quantidades_selecionadas[f"{prod['id']}_{k}"] = qtd_item or 0
                                        idx += 1
                                st.markdown("---")
                            else:
                                with colunas[index%3]:
                                    disponivel_normal = max(0, prod['quantidade_estoque'] - qtd_alugada_form.get(prod['id'],0))
                                    qtd_item_normal = st.number_input(f"{prod['nome']} (Livre: {disponivel_normal})", min_value=0, max_value=disponivel_normal, value=None, key=f"form_prod_{prod['id']}")
                                    quantidades_selecionadas[f"{prod['id']}_NORMAL"] = qtd_item_normal or 0
            if st.form_submit_button("Salvar Evento e Alocar Itens"):
                if not nome_evento or not nome_cliente or not contato_cliente or not local_evento or not rua_evento or not bairro_evento or not numero_evento or valor_evento is None:
                    mostrar_popup("Por favor, preencha todos os campos obrigatórios!", tipo="erro")
                else:
                    estoque_insuficiente = False
                    msg_erro_estoque = ""
                    alocacoes_agrupadas = {}
                    for key, qtd in quantidades_selecionadas.items():
                        if qtd > 0:
                            p_id_str, sub_item = key.split("_", 1)
                            p_id_int = int(p_id_str)
                            prod_info = next((p for p in produtos_disp.data if p['id'] == p_id_int), None)
                            if not prod_info: continue
                            if sub_item == "NORMAL":
                                disp = max(0, prod_info['quantidade_estoque'] - qtd_alugada_form.get(p_id_int,0))
                                if qtd > disp:
                                    estoque_insuficiente = True
                                    msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']}. Pediu {qtd}, temos {disp} livres."
                                    break
                            else:
                                js_est = safe_json_load(prod_info.get('observacao')) or {}
                                disp_sub = max(0, js_est.get(sub_item,0) - detalhe_alugado_form.get(p_id_int,{}).get(sub_item,0))
                                if qtd > disp_sub:
                                    estoque_insuficiente = True
                                    msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']} ({sub_item}). Pediu {qtd}, temos {disp_sub} livres."
                                    break
                            if p_id_int not in alocacoes_agrupadas: alocacoes_agrupadas[p_id_int] = {'total':0,'detalhes':{}}
                            alocacoes_agrupadas[p_id_int]['total'] += qtd
                            if sub_item != "NORMAL": alocacoes_agrupadas[p_id_int]['detalhes'][sub_item] = qtd
                    if estoque_insuficiente:
                        mostrar_popup(msg_erro_estoque, tipo="erro")
                    else:
                        try:
                            contato_cliente_formatado = formatar_telefone_br(contato_cliente)
                            novo_cliente = supabase.table("clientes_eventos").insert({"empresa_id": emp_id,"nome": nome_cliente,"contato": contato_cliente_formatado}).execute()
                            cliente_id_gerado = novo_cliente.data[0]['id']
                            novo_evento = supabase.table("eventos").insert({"empresa_id": emp_id,"cliente_id": cliente_id_gerado,"titulo": nome_evento,"descricao": nome_evento,"data_inicio": str(data_inicio),"data_fim": str(data_fim),"data_fim_alocacao": str(data_fim),"hora_inicio": str(hora_inicio),"hora_fim": str(hora_fim),"status": status_evento,"observacao": f"Local: {local_evento} - {rua_evento}, {numero_evento} - {bairro_evento} - {obs_evento_geral}","valor_total": valor_evento}).execute()
                            evento_id_gerado = novo_evento.data[0]['id']
                            google_event_id_novo = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], novo_evento.data[0])
                            if google_event_id_novo:
                                try: supabase.table("eventos").update({"google_event_id": google_event_id_novo}).eq("id", evento_id_gerado).execute()
                                except Exception: registrar_erro("agendamento.py:717"); pass
                            data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                            for p_id, info in alocacoes_agrupadas.items():
                                obs_json_evento = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                valor_sugerido = info['total'] * mapa_valor_ref.get(p_id, 0)
                                supabase.table("itens_evento").insert({"empresa_id": emp_id,"evento_id": evento_id_gerado,"produto_id": p_id,"quantidade": info['total'],"observacao": obs_json_evento,"valor_cobrado": valor_sugerido}).execute()
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": evento_id_gerado,"descricao": f"🟢 ALOCAÇÃO INICIAL: Adicionou {info['total']}x Produto {p_id}.","data_registro": data_hora}).execute()
                            mostrar_popup("CADASTRO DE EVENTO CONCLUÍDO COM SUCESSO!")
                            st.rerun()
                        except Exception as e: registrar_erro("agendamento.py:726"); mostrar_popup(f"Erro: {e}", tipo="erro")
