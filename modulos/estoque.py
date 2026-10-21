"""Módulo: 📦 Estoque.

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
from modulos.log import registrar_erro
import json
from datetime import datetime

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta


def render(supabase, emp_id, formatar_moeda, mostrar_popup, safe_json_load, calcular_detalhamento_periodo_produto, calcular_disponibilidade_periodo, definir_categoria, formatar_telefone_br, prever_icone, status_cor, popup_confirmacao_estoque):
    st.title("Controle de Estoque Inteligente")
    produtos_lista = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).order("nome").execute()

    with st.expander("🔍 Verificar Disponibilidade Rotativa", expanded=True):
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
            st.markdown("#### 📊 Resumo Geral do Período Selecionado")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("📦 Estoque Total", total_geral_estoque)
            col_m2.metric("🔒 Reservado no Período", total_geral_reservado)
            col_m3.metric("✅ Disponível no Período", total_geral_livre)
            st.markdown("---")

            def _cor_barra(disponivel, total):
                if total <= 0: return "#555"
                pct_livre = disponivel / total
                if pct_livre >= 0.5: return "#2E7D32"
                if pct_livre > 0.2: return "#FFC107"
                return "#B3261E"

            categorias = sorted(df_produtos['Categoria'].unique())
            for cat in categorias:
                df_cat = df_produtos[df_produtos['Categoria'] == cat]
                total_fisico = int(df_cat['Estoque Total'].sum())
                total_reservado_cat = int(df_cat['Reservado na Data'].sum())
                total_livre = int(df_cat['Disponível Livre'].sum())
                icone_status = "🟢" if total_livre > 0 else "🔴"
                st.markdown(f"**{cat}**")
                col_c1, col_c2, col_c3 = st.columns(3)
                col_c1.metric("Físico Geral", total_fisico)
                col_c2.metric("Reservado/Locado", total_reservado_cat)
                col_c3.metric(f"{icone_status} Livres no Período", total_livre)

                for _, prod_row in df_cat.iterrows():
                    total_p = int(prod_row['Estoque Total'])
                    reservado_p = int(prod_row['Reservado na Data'])
                    livre_p = int(prod_row['Disponível Livre'])
                    pct_reservado = (reservado_p / total_p * 100) if total_p > 0 else 0
                    cor_barra = _cor_barra(livre_p, total_p)
                    status_label = status_cor(prod_row['quantidade_estoque'])
                    js_kit = safe_json_load(prod_row.get('observacao'))

                    st.markdown(f"""
                        <div style="background:#1B1B1D;border-radius:10px;padding:12px 16px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                <span style="font-size:14.5px;font-weight:700;color:#EDEDED;">{prod_row['Ícone']} {prod_row['nome']}</span>
                                <span style="font-size:12px;color:#9A9A9A;">{status_label}</span>
                            </div>
                            <div style="background:#2E2E30;border-radius:6px;height:10px;width:100%;overflow:hidden;">
                                <div style="background:{cor_barra};height:10px;width:{pct_reservado:.1f}%;"></div>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:12.5px;">
                                <span style="color:#9A9A9A;">📦 Total: <b style="color:#EDEDED;">{total_p}</b></span>
                                <span style="color:#9A9A9A;">🔒 Reservado: <b style="color:#EDEDED;">{reservado_p}</b></span>
                                <span style="color:{cor_barra};">✅ Livre: <b>{livre_p}</b></span>
                            </div>
                        </div>""", unsafe_allow_html=True)

                    if js_kit:
                        alugados_kit = detalhe_alugado.get(prod_row['id'], {})
                        with st.expander(f"Ver detalhamento de {prod_row['nome']} ({len(js_kit)} peças)", expanded=False):
                            itens_kit_ordenados = sorted(js_kit.items())
                            n_col_kit = 6
                            cols_kit_view = st.columns(n_col_kit)
                            for idx_kv, (k, max_v) in enumerate(itens_kit_ordenados):
                                livre_k = max(0, max_v - alugados_kit.get(k, 0))
                                cor_k = "#2E7D32" if livre_k > 0 else "#B3261E"
                                with cols_kit_view[idx_kv % n_col_kit]:
                                    st.markdown(f"""
                                        <div style="text-align:center;background:#2A2A2C;border-radius:6px;padding:6px 2px;margin-bottom:6px;">
                                            <div style="font-size:13px;font-weight:700;color:#EDEDED;">{k}</div>
                                            <div style="font-size:12px;color:{cor_k};font-weight:600;">{livre_k}/{max_v}</div>
                                        </div>""", unsafe_allow_html=True)

                    if reservado_p > 0:
                        linhas_detalhe = calcular_detalhamento_periodo_produto(data_inicio_f, data_fim_f, prod_row['id'], total_p)
                        if linhas_detalhe:
                            with st.expander(f"🕐 Detalhamento por dia e horário — {prod_row['nome']}", expanded=False):
                                st.dataframe(pd.DataFrame(linhas_detalhe), use_container_width=True, hide_index=True)
                st.markdown("---")
        else: st.info("Nenhum produto cadastrado no estoque ainda.")

    with st.expander("➕ Adicionar Novo Item ou Kit", expanded=False):
        tipo_cadastro = st.radio("O que você vai cadastrar?", ["Produto Normal","🔠 Kit Letras (A-Z)","🔢 Kit Números (0 a 9)"])
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
                cols_l = st.columns(6)
                qtd_letras = {}
                for i, l in enumerate(letras): qtd_letras[l] = cols_l[i%6].number_input(l, min_value=0, value=None)
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
                cols_n = st.columns(10)
                qtd_numeros = {}
                for i, num in enumerate(numeros): qtd_numeros[num] = cols_n[i%10].number_input(num, min_value=0, value=None)
                if st.form_submit_button("Salvar Kit Números"):
                    total_numeros = sum((v or 0) for v in qtd_numeros.values())
                    if total_numeros == 0: mostrar_popup("Coloque pelo menos 1 número!", tipo="erro")
                    else:
                        obs_json = json.dumps({k: (v or 0) for k,v in qtd_numeros.items() if (v or 0) > 0})
                        supabase.table("produtos").insert({"empresa_id": emp_id,"nome": nome_prod.upper(),"quantidade_estoque": total_numeros,"valor_locacao": (valor_locacao_numeros or 0),"observacao": obs_json}).execute()
                        mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                        st.rerun()

    with st.expander("💲 Editar Valor de Locação de um Produto", expanded=False):
        if produtos_lista.data:
            opcoes_val = {p['nome']: p for p in produtos_lista.data}
            prod_val_nome = st.selectbox("Produto", list(opcoes_val.keys()), key="sel_editar_valor")
            prod_val = opcoes_val[prod_val_nome]
            valor_atual_salvo = float(prod_val.get('valor_locacao') or 0)
            if valor_atual_salvo > 0: st.caption(f"💾 Valor atual salvo: **R$ {formatar_moeda(valor_atual_salvo)}**")
            else: st.caption("Nenhum valor cadastrado ainda.")
            novo_valor_ref = st.number_input("Novo Valor de Locação por Unidade (R$)", min_value=0.0, value=None, placeholder="Ex: 15,00", format="%.2f", key="input_editar_valor")
            if st.button("💾 Salvar Valor de Referência", key="btn_editar_valor_ref"):
                if novo_valor_ref is None: mostrar_popup("Digite um valor antes de salvar.", tipo="erro")
                else:
                    supabase.table("produtos").update({"valor_locacao": novo_valor_ref}).eq("id", prod_val['id']).execute()
                    mostrar_popup("VALOR ATUALIZADO COM SUCESSO!")
                    st.rerun()
        else: st.info("Nenhum produto cadastrado ainda.")

    with st.expander("🗑️ Excluir ou Reduzir Produto do Estoque", expanded=False):
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
                    cols_pex = st.columns(6)
                    qtds_remover_parcial = {}
                    idxpex = 0
                    for k, max_v in js_prod_excluir.items():
                        if max_v > 0:
                            val_pex = cols_pex[idxpex%6].number_input(f"{k} (Tem: {max_v})", min_value=0, max_value=max_v, value=None, key=f"pex_{produto_id_excluir}_{k}")
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

    with st.expander("⬆️ Adicionar Quantidade a Produto Existente", expanded=False):
        if produtos_lista.data:
            opcoes_add = {f"{p['nome']} (Estoque Atual: {p['quantidade_estoque']})": p for p in produtos_lista.data}
            prod_selecionado_add = st.selectbox("Selecione o produto para aumentar o estoque", list(opcoes_add.keys()), key="select_add_qtd")
            prod_alvo_add = opcoes_add[prod_selecionado_add]
            js_estoque_add = safe_json_load(prod_alvo_add.get('observacao'))
            if js_estoque_add:
                st.markdown(f"**Especifique a quantidade recebida para cada item de {prod_alvo_add['nome']}:**")
                cols_add_kit = st.columns(10)
                idx_add = 0
                qtds_adicionar_kit = {}
                for k, v_atual in js_estoque_add.items():
                    val_add_k = cols_add_kit[idx_add%10].number_input(f"{k} (Tem: {v_atual})", min_value=0, value=None, placeholder="0", key=f"add_kit_{prod_alvo_add['id']}_{k}") or 0
                    if val_add_k > 0: qtds_adicionar_kit[k] = val_add_k
                    idx_add += 1
                if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_kit_estoque"):
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
                if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_normal_estoque"):
                    qtd_final = prod_alvo_add['quantidade_estoque'] + nova_qtd_add
                    supabase.table("produtos").update({"quantidade_estoque": qtd_final}).eq("id", prod_alvo_add['id']).execute()
                    mostrar_popup("Estoque atualizado com sucesso!")
                    st.rerun()

    with st.expander("🔧 Controle de Manutenção", expanded=False):
        tab_enviar_manut, tab_extrato_manut = st.tabs(["Enviar para Manutenção", "📋 Histórico de Manutenção"])

        with tab_enviar_manut:
            if produtos_lista.data:
                opcoes_manut = {p['nome']: p for p in produtos_lista.data}
                prod_manut_nome = st.selectbox("Selecione o Produto", list(opcoes_manut.keys()), key="sel_manut")
                prod_manut = opcoes_manut[prod_manut_nome]

                js_manut = safe_json_load(prod_manut.get('observacao'))

                if js_manut:
                    st.markdown(f"**Especifique quais peças de {prod_manut['nome']} vão para manutenção:**")
                    cols_mkit = st.columns(6)
                    idx_mkit = 0
                    qtds_manut_kit = {}
                    for k, max_v in js_manut.items():
                        if max_v > 0:
                            v_mk = cols_mkit[idx_mkit % 6].number_input(
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

                if st.button("🔧 Registrar Manutenção", key="btn_reg_manut"):
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
                                titulo_exp = (
                                    f"{icone_m} {nome_p} — {m['quantidade']} un. | "
                                        f"Enviado: {data_envio_m} | Retorno: {data_prev_m}{atraso_txt} | "
                                        f"📍 {local_m}"
                                )
    
                                with st.expander(titulo_exp, expanded=False):
                                    st.caption(f"Motivo: {m['motivo']}")
                                    if m.get('local_manutencao'):
                                        st.info(f"📍 **Local:** {m['local_manutencao']}")
                                    if m.get('contato_manutencao'):
                                        st.info(f"📞 **Contato:** {m['contato_manutencao']}")
    
                                    col_mb1, col_mb2 = st.columns(2)
    
                                    with col_mb1:
                                        with st.expander("📅 Atualizar data prevista", expanded=False):
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
    
                                        with st.expander("💀 Mover para Quebrados", expanded=False):
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
    
                                    with col_mb2:
                                        with st.expander("🗑️ Remover do Histórico", expanded=False):
                                            st.caption("Remove apenas o registro. O estoque não é alterado.")
                                            if st.button("🗑️ Confirmar Remoção", key=f"del_manut_ativo_{m['id']}"):
                                                supabase.table("manutencao").delete().eq("id", m['id']).execute()
                                                mostrar_popup("Registro removido do histórico.")
                                                st.rerun()
    
                                    if st.button(
                                        "✅ Confirmar Retorno ao Estoque",
                                        key=f"ret_manut_{m['id']}",
                                        use_container_width=True
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
                                    f"Enviado: {mc.get('data_envio','-')} | "
                                    f"Retornou: {data_retorno_real}{detalhes_kit_c}",
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

    with st.expander("🗑️ Controle de Itens Quebrados", expanded=False):
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
                        cols_qkit = st.columns(6)
                        idx_qkit = 0
                        qtds_quebra_kit = {}
                        for k, max_v in js_quebrado.items():
                            if max_v > 0:
                                v_qk = cols_qkit[idx_qkit % 6].number_input(
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

                if st.button("🗑️ Registrar Quebra / Perda Definitiva", key="btn_reg_quebra"):
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
                    col_qk1, col_qk2 = st.columns(2)
                    col_qk1.metric("📋 Total de Registros", total_quebrados)
                    col_qk2.metric("📦 Total de Peças Perdidas", total_pecas_perdidas)
                    st.markdown("---")

                    for q in quebrados_lista.data:
                        nome_pq = q['produtos']['nome'] if q.get('produtos') else f"Produto #{q['produto_id']}"
                        detalhes_kit_q = ""
                        if q.get('detalhes_kit'):
                            try:
                                dkq = json.loads(q['detalhes_kit'])
                                detalhes_kit_q = " | Peças: " + ", ".join([f"{k}: {v}x" for k, v in dkq.items()])
                            except Exception:
                                registrar_erro("estoque.py:676")
                                pass
                        st.error(
                            f"❌ **{nome_pq}** — {q['quantidade']} un. perdidas em "
                                f"{q['data_registro']}{detalhes_kit_q}"
                        )
                        st.caption(f"Motivo: {q['motivo']}")
                        st.markdown("<hr style='border-color:#333;margin:6px 0'>", unsafe_allow_html=True)
                else:
                    st.info("Nenhum item quebrado registrado.")
            except Exception as e:
                registrar_erro("estoque.py:687")
                st.error(f"Erro ao carregar itens quebrados: {e}")
