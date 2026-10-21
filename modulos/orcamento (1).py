"""Módulo: 🧳 Orçamento de Evento.

Recebe as dependências por parâmetro (injeção) para não depender de variáveis globais do app.py.
"""
import json
from datetime import datetime

import streamlit as st


def render(supabase, emp_id, formatar_moeda, mostrar_popup, safe_json_load,
           calcular_distancia_google_maps, gerar_pdf_orcamento, REPORTLAB_DISPONIVEL):
    ENDERECO_BASE_EMPRESA = st.secrets.get("ENDERECO_BASE_EMPRESA", "")

    produtos_orc = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).order("nome").execute()
    dict_produtos_orc = {p['id']: p for p in produtos_orc.data} if produtos_orc.data else {}

    tab_criar_orc, tab_lista_orc = st.tabs(["📝 Criar Orçamento", "📋 Orçamentos Salvos"])

    # ==========================================
    # CRIAR NOVO ORÇAMENTO
    # ==========================================
    with tab_criar_orc:
        with st.expander("👤 Dados do Cliente e Evento", expanded=True):
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

        with st.expander("🛒 Itens do Orçamento", expanded=True):
            st.caption("Quantidades aproximadas. O detalhamento exato (ex: letras específicas) é feito na hora de confirmar o evento.")
            itens_selecionados_orc = {}
            if produtos_orc.data:
                for p in produtos_orc.data:
                    js_p = safe_json_load(p.get('observacao'))
                    valor_ref = float(p.get('valor_locacao') or 0)
                    col_p1, col_p2 = st.columns([2,1])
                    with col_p1:
                        qtd_p = st.number_input(f"{p['nome']} (Estoque: {p['quantidade_estoque']})", min_value=0, value=None, placeholder="0", key=f"orc_qtd_{p['id']}") or 0
                    with col_p2:
                        valor_unit_p = st.number_input("Valor unit. (R$)", min_value=0.0, value=None, placeholder=f"{valor_ref:.2f}".replace(".",","), format="%.2f", key=f"orc_valor_{p['id']}")
                        valor_unit_p = valor_unit_p if valor_unit_p is not None else valor_ref
                    if qtd_p > 0:
                        itens_selecionados_orc[p['id']] = {"nome": p['nome'], "quantidade": qtd_p, "valor_unit": valor_unit_p, "valor_total": qtd_p * valor_unit_p, "kit": bool(js_p)}

            valor_itens_orc = sum(it['valor_total'] for it in itens_selecionados_orc.values())
            st.info(f"💲 Subtotal dos Itens: **R$ {formatar_moeda(valor_itens_orc)}**")

        with st.expander("🚗 Frete / Deslocamento", expanded=True):
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

        with st.expander("💲 Desconto, Validade e Observações", expanded=True):
            col_d1, col_d2 = st.columns(2)
            with col_d1: desconto_orc = st.number_input("Desconto (R$)", min_value=0.0, value=None, placeholder="0,00", format="%.2f", key="orc_desconto") or 0.0
            with col_d2: validade_orc = st.number_input("Validade da Proposta (dias)", min_value=1, value=None, placeholder="7", key="orc_validade") or 7
            obs_orc = st.text_area("Observações", key="orc_obs")

        valor_total_orc = max(0.0, valor_itens_orc + valor_frete_orc - desconto_orc)
        st.markdown(f"""
            <div style="background:#1B5E20;border-radius:8px;padding:10px 16px;margin:10px 0;display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#B9F6CA;font-size:13px;font-weight:600;">💰 Valor Total do Orçamento</span>
                <span style="color:#FFFFFF;font-size:20px;font-weight:800;">R$ {formatar_moeda(valor_total_orc)}</span>
            </div>""", unsafe_allow_html=True)

        confirmar_evento_ja = st.checkbox("✅ Cliente já confirmou — criar o evento automaticamente ao salvar", key="orc_confirmar_ja")
        st.caption("Desmarcado: fica salvo como orçamento (pré-cadastro) na aba 'Orçamentos Salvos', sem virar evento ainda. Marcado: já cria o evento direto, igual ao cadastro manual em Agendamento.")

        col_sv1, col_sv2 = st.columns(2)
        with col_sv1:
            texto_btn_salvar = "✅ Salvar e Confirmar Evento" if confirmar_evento_ja else "💾 Salvar como Orçamento (Rascunho)"
            if st.button(texto_btn_salvar, key="btn_salvar_orc", use_container_width=True):
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
    with tab_lista_orc:
        try:
            orcamentos_lista = supabase.table("orcamentos").select("*").eq("empresa_id", emp_id).order("data_criacao", desc=True).execute()
        except Exception as e:
            st.error(f"Erro ao carregar orçamentos: {e}")
            orcamentos_lista = type('obj',(object,),{'data':[]})

        if orcamentos_lista.data:
            for orc in orcamentos_lista.data:
                itens_orc = safe_json_load(orc.get('itens_json')) or {}
                itens_orc_lista = list(itens_orc.values()) if isinstance(itens_orc, dict) else []
                status_orc = orc.get('status', 'Rascunho')
                icone_status = {"Rascunho":"📝","Enviado":"📤","Aprovado":"✅","Recusado":"❌","Convertido":"🎉"}.get(status_orc, "📝")

                with st.expander(f"{icone_status} {orc.get('titulo_evento','-')} — {orc.get('nome_cliente','-')} | R$ {formatar_moeda(orc.get('valor_total',0))} | {status_orc}"):
                    col_i1, col_i2 = st.columns(2)
                    with col_i1:
                        st.write(f"**Cliente:** {orc.get('nome_cliente','-')}")
                        st.write(f"**Contato:** {orc.get('contato_cliente','-')}")
                        st.write(f"**Período:** {orc.get('data_inicio','-')} até {orc.get('data_fim','-')}")
                        st.write(f"**Endereço:** {orc.get('endereco_evento','-')}")
                    with col_i2:
                        st.write(f"**Itens:** R$ {formatar_moeda(orc.get('valor_itens',0))}")
                        st.write(f"**Frete:** R$ {formatar_moeda(orc.get('valor_frete',0))} ({orc.get('distancia_km',0)} km)")
                        st.write(f"**Desconto:** R$ {formatar_moeda(orc.get('desconto',0))}")
                        st.write(f"**Total:** R$ {formatar_moeda(orc.get('valor_total',0))}")

                    if itens_orc_lista:
                        st.markdown("**Itens:**")
                        for it in itens_orc_lista:
                            st.write(f"- {it['quantidade']}x {it['nome']} — R$ {formatar_moeda(it['valor_total'])}")

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
                                mostrar_popup(f"Erro ao converter: {e}", tipo="erro")
                    elif status_orc == "Convertido":
                        st.success(f"🎉 Já convertido no Evento #{orc.get('evento_id')} — confira em Agendamento.")
        else:
            st.info("Nenhum orçamento cadastrado ainda. Crie um na aba 'Criar Orçamento'.")
