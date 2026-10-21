"""Módulo: 🛒 Compras.

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
from datetime import datetime

import pandas as pd
import streamlit as st


def render(supabase, emp_id, mostrar_popup):
    st.title("Controle de Compras")
    col_cp3, col_cp4 = st.columns(2)
    with col_cp3: nome_produto_compra = st.text_input("Nome do Produto", key="compra_nome_produto")
    with col_cp4: tipo_aquisicao = st.radio("Comprado onde?", ["Presencial","Site"], horizontal=True, key="compra_tipo_aquisicao")
    fornecedor = st.text_input("Nome do Site / Loja", key="compra_nome_site")
    with st.form("form_compras"):
        col_cp5a, col_cp5b, col_cp5c = st.columns(3)
        with col_cp5a: quantidade_compra = st.number_input("Quantidade Comprada", min_value=1, step=1, value=None)
        with col_cp5b: valor_unit_compra = st.number_input("Valor Unitário (R$)", min_value=0.0, value=None, format="%.2f")
        with col_cp5c:
            st.write("")
            st.info("Valor Total é calculado automaticamente ao Registrar.")
        col_cp5, col_cp6 = st.columns(2)
        with col_cp5: data_compra_input = st.date_input("Data da Compra", value=datetime.now().date(), format="DD/MM/YYYY")
        with col_cp6: data_chegada_input = st.date_input("Previsão de Chegada", value=datetime.now().date(), format="DD/MM/YYYY")
        col_cp7, col_cp8 = st.columns(2)
        with col_cp7: forma_pagamento_compra = st.selectbox("Forma de Pagamento", ["Não informado","Pix","Cartão","Dinheiro","Boleto","Outro"])
        with col_cp8: numero_pedido_compra = st.text_input("Nº do Pedido / Nota Fiscal (opcional)")
        observacao_compra = st.text_area("Observação (opcional)")
        if st.form_submit_button("Registrar Compra"):
            if not nome_produto_compra.strip() or not fornecedor.strip(): mostrar_popup("Informe o nome do produto e a loja.", tipo="erro")
            else:
                qtd_calc = quantidade_compra or 0
                vlr_calc = valor_unit_compra or 0.0
                valor_total_calc = qtd_calc * vlr_calc
                supabase.table("compras").insert({"empresa_id": emp_id,"nome_produto": nome_produto_compra,"fornecedor": fornecedor,"tipo_aquisicao": tipo_aquisicao,"local_detalhe": fornecedor,"quantidade": qtd_calc,"valor_total": valor_total_calc,"data_compra": str(data_compra_input),"data_prevista_chegada": str(data_chegada_input),"status_chegada": "Aguardando","forma_pagamento": forma_pagamento_compra,"numero_pedido": numero_pedido_compra,"observacao": observacao_compra}).execute()
                mostrar_popup("COMPRA CADASTRADA COM SUCESSO!")
                st.rerun()
    st.markdown("---")
    st.markdown("### 📋 Histórico de Compras")
    compras_lista = supabase.table("compras").select("*").eq("empresa_id", emp_id).order("data_compra", desc=True).execute()
    if compras_lista.data:
        df_compras = pd.DataFrame(compras_lista.data)
        df_compras['valor_unitario'] = df_compras['valor_total'] / df_compras['quantidade']
        df_compras['valor_unitario'] = df_compras['valor_unitario'].fillna(0)
        colunas_exibir_compras = [c for c in ["nome_produto","quantidade","valor_unitario","valor_total","fornecedor","tipo_aquisicao","forma_pagamento","numero_pedido","data_compra","data_prevista_chegada","status_chegada","observacao"] if c in df_compras.columns or c == "valor_unitario"]
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
                except: dt_c = datetime.now().date()
                edit_dt_c = st.date_input("Data da Compra", value=dt_c, format="DD/MM/YYYY", key="ed_dt_c")
            with col_ec7:
                try: dt_prev = datetime.strptime(str(comp_sel.get('data_prevista_chegada')).split("T")[0], "%Y-%m-%d").date()
                except: dt_prev = datetime.now().date()
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
