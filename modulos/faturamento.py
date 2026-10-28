"""Módulo: 💰 Faturamento (Fluxo de Caixa).

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
from modulos.log import registrar_erro
import io
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_DISPONIVEL = True
except ImportError:
    registrar_erro("faturamento.py:21")
    REPORTLAB_DISPONIVEL = False


def render(supabase, emp_id, formatar_moeda, mostrar_popup):
    st.title("Fluxo de Caixa (Faturamento)")
    st.markdown("#### 🗓️ Selecione o Período do Relatório")
    col_f1, col_f2 = st.columns([1,3])
    ano_atual = datetime.now().year
    with col_f1: ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2100, value=ano_atual, step=1, key="fat_ano")
    nomes_meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    with col_f2: meses_selecionados_nomes = st.multiselect("Mês (ou meses) — deixe vazio para ver o ano inteiro", nomes_meses, default=[nomes_meses[datetime.now().month-1]], key="fat_meses")
    meses_selecionados = [nomes_meses.index(m)+1 for m in meses_selecionados_nomes] if meses_selecionados_nomes else list(range(1,13))
    def _dentro_do_periodo(data_str):
        if not data_str: return False
        try:
            d = datetime.strptime(str(data_str).split("T")[0], "%Y-%m-%d").date()
            return d.year == ano_selecionado and d.month in meses_selecionados
        except Exception: registrar_erro("faturamento.py:39"); return False
    eventos_fat = supabase.table("eventos").select("id, data_inicio, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status","Cancelado").gte("data_inicio", f"{ano_selecionado}-01-01").lt("data_inicio", f"{ano_selecionado+1}-01-01").execute()
    eventos_periodo = [e for e in (eventos_fat.data or []) if _dentro_do_periodo(e.get('data_inicio'))]
    receita_eventos = sum(float(e.get('valor_total') or 0) for e in eventos_periodo)
    qtd_eventos_periodo = len(eventos_periodo)
    try:
        despesas_viagem_resp = supabase.table("despesas_viagem").select("*").eq("empresa_id", emp_id).gte("data_despesa", f"{ano_selecionado}-01-01").lt("data_despesa", f"{ano_selecionado+1}-01-01").execute()
        despesas_viagem_periodo = [d for d in (despesas_viagem_resp.data or []) if _dentro_do_periodo(d.get('data_despesa'))]
    except Exception: registrar_erro("faturamento.py:47"); despesas_viagem_periodo = []
    total_despesas_viagem = sum(float(d.get('valor') or 0) for d in despesas_viagem_periodo)
    try:
        compras_resp = supabase.table("compras").select("*").eq("empresa_id", emp_id).gte("data_compra", f"{ano_selecionado}-01-01").lt("data_compra", f"{ano_selecionado+1}-01-01").execute()
        compras_periodo = [c for c in (compras_resp.data or []) if _dentro_do_periodo(c.get('data_compra'))]
    except Exception: registrar_erro("faturamento.py:52"); compras_periodo = []
    total_investimento_compras = sum(float(c.get('valor_total') or 0) for c in compras_periodo)
    fat_manual_resp = supabase.table("faturamento").select("*").eq("empresa_id", emp_id).gte("data_pagamento", f"{ano_selecionado}-01-01").lt("data_pagamento", f"{ano_selecionado+1}-01-01").execute()
    fat_manual_periodo = [f for f in (fat_manual_resp.data or []) if _dentro_do_periodo(f.get('data_pagamento'))]
    receita_manual = sum(float(f.get('valor') or 0) for f in fat_manual_periodo if f.get('tipo') == 'receita')
    despesa_manual = sum(float(f.get('valor') or 0) for f in fat_manual_periodo if f.get('tipo') == 'despesa')
    lucro_liquido = (receita_eventos + receita_manual) - (total_despesas_viagem + total_investimento_compras + despesa_manual)
    st.markdown("---")
    st.markdown(f"#### 📊 Resumo — {', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("🎉 Receita de Eventos", formatar_moeda(receita_eventos), help=f"{qtd_eventos_periodo} evento(s)")
    col_r2.metric("⛽ Gastos de Viagem", formatar_moeda(total_despesas_viagem))
    col_r3.metric("🛒 Investimento em Compras", formatar_moeda(total_investimento_compras))
    col_r4.metric("💰 Lucro Líquido", formatar_moeda(lucro_liquido))
    st.markdown("---")
    with st.expander("⛽ Registrar Gasto de Viagem", expanded=False):
        with st.form("form_despesa_viagem"):
            categoria_despesa = st.selectbox("Categoria", ["Combustível","Alimentação","Outros"])
            valor_despesa = st.number_input("Valor (R$)", min_value=0.0, step=5.0, value=None, format="%.2f")
            obs_despesa = st.text_input("Observação (opcional)")
            data_despesa_input = st.date_input("Data do Gasto", value=datetime.now().date(), format="DD/MM/YYYY")
            if st.form_submit_button("Registrar Gasto"):
                if (valor_despesa or 0.0) <= 0: mostrar_popup("Informe um valor maior que zero.", tipo="erro")
                else:
                    supabase.table("despesas_viagem").insert({"empresa_id": emp_id,"categoria": categoria_despesa,"valor": (valor_despesa or 0.0),"observacao": obs_despesa,"data_despesa": str(data_despesa_input)}).execute()
                    mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                    st.rerun()
    with st.expander("📄 Extrato de Gastos de Viagem do Período", expanded=False):
        if despesas_viagem_periodo:
            df_despesas_viagem = pd.DataFrame(despesas_viagem_periodo)
            colunas_desp = [c for c in ["data_despesa","categoria","valor","observacao"] if c in df_despesas_viagem.columns]
            df_despesas_viagem_show = df_despesas_viagem[colunas_desp].sort_values("data_despesa", ascending=False).copy()
            df_despesas_viagem_show["data_despesa"] = df_despesas_viagem_show["data_despesa"].apply(lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y"))
            st.dataframe(df_despesas_viagem_show, use_container_width=True, hide_index=True)
        else: st.caption("Nenhum gasto de viagem registrado neste período.")
    def _fmt_data_br_simples(d):
        try: return datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception: registrar_erro("faturamento.py:89"); return str(d)
    if despesas_viagem_periodo:
        with st.expander("✏️ Editar ou Excluir um Gasto de Viagem", expanded=False):
            opcoes_desp = {f"{_fmt_data_br_simples(d.get('data_despesa'))} — {d.get('categoria','-')} — R$ {float(d.get('valor',0)):.2f}" + (f" ({d.get('observacao')})" if d.get('observacao') else ""): d['id'] for d in sorted(despesas_viagem_periodo, key=lambda x: x.get('data_despesa') or '', reverse=True)}
            escolha_desp_txt = st.selectbox("Selecione o lançamento", list(opcoes_desp.keys()), key="select_editar_despesa")
            desp_selecionada = next(d for d in despesas_viagem_periodo if d['id'] == opcoes_desp[escolha_desp_txt])
            col_ed_d1, col_ed_d2 = st.columns(2)
            with col_ed_d1:
                categoria_edit_desp = st.selectbox("Categoria", ["Combustível","Alimentação","Outros"], index=["Combustível","Alimentação","Outros"].index(desp_selecionada.get('categoria')) if desp_selecionada.get('categoria') in ["Combustível","Alimentação","Outros"] else 0, key="edit_categoria_despesa")
            with col_ed_d2: valor_edit_desp = st.number_input("Valor (R$)", min_value=0.0, step=5.0, value=float(desp_selecionada.get('valor') or 0), format="%.2f", key="edit_valor_despesa")
            obs_edit_desp = st.text_input("Observação", value=desp_selecionada.get('observacao') or "", key="edit_obs_despesa")
            data_edit_desp = st.date_input("Data do Gasto", value=datetime.strptime(str(desp_selecionada.get('data_despesa')).split("T")[0], "%Y-%m-%d").date(), format="DD/MM/YYYY", key="edit_data_despesa")
            motivo_edit_desp = st.text_input("Motivo da Edição (obrigatório)", key="motivo_edit_despesa")
            col_btn_d1, col_btn_d2 = st.columns(2)
            with col_btn_d1:
                if st.button("💾 Salvar Alteração", key="btn_salvar_despesa"):
                    if not motivo_edit_desp.strip(): mostrar_popup("Informe o motivo da edição.", tipo="erro")
                    else:
                        data_hora_edit_desp = datetime.now().strftime("%d/%m/%Y às %H:%M")
                        nova_obs_desp = f"{obs_edit_desp} [Editado em {data_hora_edit_desp} — Motivo: {motivo_edit_desp}]".strip()
                        supabase.table("despesas_viagem").update({"categoria": categoria_edit_desp,"valor": valor_edit_desp,"observacao": nova_obs_desp,"data_despesa": str(data_edit_desp)}).eq("id", desp_selecionada['id']).execute()
                        mostrar_popup("ALTERAÇÃO CONCLUÍDA COM SUCESSO!")
                        st.rerun()
            with col_btn_d2:
                if st.button("🗑️ Excluir Lançamento", key="btn_excluir_despesa"):
                    supabase.table("despesas_viagem").delete().eq("id", desp_selecionada['id']).execute()
                    mostrar_popup("LANÇAMENTO EXCLUÍDO!")
                    st.rerun()
    with st.expander("➕ Outro Lançamento no Caixa (Receita ou Despesa Avulsa)", expanded=False):
        with st.form("form_fat"):
            desc_fat = st.text_input("Descrição")
            tipo_fat = st.radio("Tipo de Movimentação", ["receita","despesa"], horizontal=True)
            valor_fat = st.number_input("Valor (R$)", min_value=0.0, value=None, format="%.2f")
            data_fat_input = st.date_input("Data", value=datetime.now().date(), format="DD/MM/YYYY", key="data_fat_manual")
            if st.form_submit_button("Lançar no Caixa"):
                supabase.table("faturamento").insert({"empresa_id": emp_id,"descricao": desc_fat,"tipo": tipo_fat,"valor": (valor_fat or 0.0),"data_pagamento": str(data_fat_input),"pago": True}).execute()
                mostrar_popup("LANÇAMENTO CONCLUÍDO COM SUCESSO!")
                st.rerun()
    st.markdown("### 📜 Extrato Financeiro Completo (Lançamentos Avulsos)")
    fat_lista = supabase.table("faturamento").select("id, data_pagamento, tipo, descricao, valor").eq("empresa_id", emp_id).order("data_pagamento", desc=True).execute()
    if fat_lista.data:
        df_fat_show = pd.DataFrame(fat_lista.data)[["data_pagamento","tipo","descricao","valor"]].copy()
        df_fat_show["data_pagamento"] = df_fat_show["data_pagamento"].apply(lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y"))
        st.dataframe(df_fat_show, use_container_width=True, hide_index=True)
        with st.expander("✏️ Editar ou Excluir um Lançamento Avulso", expanded=False):
            opcoes_fat = {f"{_fmt_data_br_simples(f.get('data_pagamento'))} — {f.get('tipo','-')} — {f.get('descricao','-')} — R$ {float(f.get('valor',0)):.2f}": f['id'] for f in fat_lista.data}
            escolha_fat_txt = st.selectbox("Selecione o lançamento", list(opcoes_fat.keys()), key="select_editar_fat")
            fat_selecionado = next(f for f in fat_lista.data if f['id'] == opcoes_fat[escolha_fat_txt])
            desc_edit_fat = st.text_input("Descrição", value=fat_selecionado.get('descricao') or "", key="edit_desc_fat")
            col_ef1, col_ef2 = st.columns(2)
            with col_ef1: tipo_edit_fat = st.radio("Tipo", ["receita","despesa"], horizontal=True, index=["receita","despesa"].index(fat_selecionado.get('tipo')) if fat_selecionado.get('tipo') in ["receita","despesa"] else 0, key="edit_tipo_fat")
            with col_ef2: valor_edit_fat = st.number_input("Valor (R$)", min_value=0.0, value=float(fat_selecionado.get('valor') or 0), format="%.2f", key="edit_valor_fat")
            data_edit_fat = st.date_input("Data", value=datetime.strptime(str(fat_selecionado.get('data_pagamento')).split("T")[0], "%Y-%m-%d").date(), format="DD/MM/YYYY", key="edit_data_fat")
            motivo_edit_fat = st.text_input("Motivo da Edição (obrigatório)", key="motivo_edit_fat")
            col_btn_f1, col_btn_f2 = st.columns(2)
            with col_btn_f1:
                if st.button("💾 Salvar Alteração", key="btn_salvar_fat"):
                    if not motivo_edit_fat.strip(): mostrar_popup("Informe o motivo da edição.", tipo="erro")
                    else:
                        data_hora_edit_fat = datetime.now().strftime("%d/%m/%Y às %H:%M")
                        nova_desc_fat = f"{desc_edit_fat} [Editado em {data_hora_edit_fat} — Motivo: {motivo_edit_fat}]"
                        supabase.table("faturamento").update({"descricao": nova_desc_fat,"tipo": tipo_edit_fat,"valor": valor_edit_fat,"data_pagamento": str(data_edit_fat)}).eq("id", fat_selecionado['id']).execute()
                        mostrar_popup("ALTERAÇÃO CONCLUÍDA COM SUCESSO!")
                        st.rerun()
            with col_btn_f2:
                if st.button("🗑️ Excluir Lançamento", key="btn_excluir_fat"):
                    supabase.table("faturamento").delete().eq("id", fat_selecionado['id']).execute()
                    mostrar_popup("LANÇAMENTO EXCLUÍDO!")
                    st.rerun()
    st.markdown("---")
    st.markdown("#### 📤 Exportar Relatório do Período Selecionado")
    def montar_dataframe_mensal():
        linhas = []
        for mes_num in meses_selecionados:
            receita_mes = sum(float(e.get('valor_total') or 0) for e in eventos_periodo if datetime.strptime(e['data_inicio'].split("T")[0], "%Y-%m-%d").month == mes_num)
            qtd_mes = sum(1 for e in eventos_periodo if datetime.strptime(e['data_inicio'].split("T")[0], "%Y-%m-%d").month == mes_num)
            viagem_mes = sum(float(d.get('valor') or 0) for d in despesas_viagem_periodo if datetime.strptime(str(d['data_despesa']).split("T")[0], "%Y-%m-%d").month == mes_num)
            compras_mes = sum(float(c.get('valor_total') or 0) for c in compras_periodo if datetime.strptime(str(c['data_compra']).split("T")[0], "%Y-%m-%d").month == mes_num)
            linhas.append({"Mês": nomes_meses[mes_num-1],"Nº Eventos": qtd_mes,"Receita de Eventos (R$)": receita_mes,"Gastos de Viagem (R$)": viagem_mes,"Investimento em Compras (R$)": compras_mes,"Lucro Líquido (R$)": receita_mes - viagem_mes - compras_mes})
        return pd.DataFrame(linhas)
    df_mensal_export = montar_dataframe_mensal()
    st.dataframe(df_mensal_export, use_container_width=True, hide_index=True)
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_mensal_export.to_excel(writer, index=False, sheet_name="Resumo Mensal")
            if despesas_viagem_periodo: pd.DataFrame(despesas_viagem_periodo)[[c for c in ["data_despesa","categoria","valor","observacao"] if c in pd.DataFrame(despesas_viagem_periodo).columns]].to_excel(writer, index=False, sheet_name="Gastos de Viagem")
            if compras_periodo: pd.DataFrame(compras_periodo).to_excel(writer, index=False, sheet_name="Compras")
        buffer_excel.seek(0)
        st.download_button("📊 Baixar Excel do Período", data=buffer_excel, file_name=f"faturamento_{ano_selecionado}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col_exp2:
        if REPORTLAB_DISPONIVEL:
            buffer_pdf_fat = io.BytesIO()
            styles_fat = getSampleStyleSheet()
            story_fat = []
            import os as _os
            caminho_logo_fat = "logo_sem_fundo.png" if _os.path.exists("logo_sem_fundo.png") else ("logo.jpg" if _os.path.exists("logo.jpg") else None)
            COR_DOURADO_F = colors.HexColor("#FFC107")
            COR_PRETO_F = colors.HexColor("#0E0E0E")
            COR_CINZA_CLARO_F = colors.HexColor("#F2F2F2")
            COR_VERDE_F = colors.HexColor("#1B7F3A")
            COR_VERMELHO_F = colors.HexColor("#B3261E")
            COR_AZUL_F = colors.HexColor("#1A5FB4")
            periodo_txt = f"{', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}"
            def _desenhar_moldura(canvas_obj, doc_obj):
                canvas_obj.saveState()
                largura_pagina, altura_pagina = A4
                altura_faixa = 3.2 * cm
                canvas_obj.setFillColor(COR_PRETO_F)
                canvas_obj.rect(0, altura_pagina-altura_faixa, largura_pagina, altura_faixa, fill=1, stroke=0)
                if caminho_logo_fat:
                    try: canvas_obj.drawImage(caminho_logo_fat, 2*cm, altura_pagina-altura_faixa+0.35*cm, width=3.6*cm, height=2.5*cm, preserveAspectRatio=True, mask='auto')
                    except Exception: registrar_erro("faturamento.py:202"); pass
                canvas_obj.setFillColor(COR_DOURADO_F)
                canvas_obj.setFont("Helvetica-Bold", 16)
                canvas_obj.drawString(6.2*cm, altura_pagina-1.5*cm, "EXTRATO FINANCEIRO")
                canvas_obj.setFillColor(colors.white)
                canvas_obj.setFont("Helvetica", 10)
                canvas_obj.drawString(6.2*cm, altura_pagina-2.15*cm, f"Período: {periodo_txt}")
                canvas_obj.setFillColor(colors.grey)
                canvas_obj.setFont("Helvetica", 8)
                canvas_obj.drawString(2*cm, 1.2*cm, f"Luz & Letra — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
                canvas_obj.drawRightString(largura_pagina-2*cm, 1.2*cm, f"Página {doc_obj.page}")
                canvas_obj.restoreState()
            frame_fat = Frame(2*cm, 1.8*cm, A4[0]-4*cm, A4[1]-5.4*cm, id='corpo')
            doc_fat = BaseDocTemplate(buffer_pdf_fat, pagesize=A4)
            doc_fat.addPageTemplates([PageTemplate(id='ComMoldura', frames=[frame_fat], onPage=_desenhar_moldura)])
            story_fat.append(Spacer(1, 10))
            estilo_kpi_label = ParagraphStyle('KpiLabel', fontSize=8.5, textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica-Bold")
            estilo_kpi_valor = ParagraphStyle('KpiValor', fontSize=14, textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica-Bold", spaceBefore=4)
            cartoes = [("🎉 RECEITA DE EVENTOS", formatar_moeda(receita_eventos), COR_DOURADO_F),("⛽ GASTOS DE VIAGEM", formatar_moeda(total_despesas_viagem), COR_VERMELHO_F),("🛒 INVESTIMENTO EM COMPRAS", formatar_moeda(total_investimento_compras), COR_AZUL_F),("💰 LUCRO LÍQUIDO", formatar_moeda(lucro_liquido), COR_VERDE_F if lucro_liquido >= 0 else COR_VERMELHO_F)]
            linha_kpi = [[Table([[Paragraph(label, estilo_kpi_label)],[Paragraph(valor, estilo_kpi_valor)]], colWidths=[4.0*cm], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),cor),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)])) for label, valor, cor in cartoes]]
            tabela_kpi = Table(linha_kpi, colWidths=[4.1*cm]*4, spaceAfter=18)
            tabela_kpi.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
            story_fat.append(tabela_kpi)
            story_fat.append(Spacer(1,20))
            story_fat.append(Paragraph("Detalhamento por Mês", ParagraphStyle('SubTit',fontSize=12,fontName="Helvetica-Bold",textColor=COR_PRETO_F,spaceAfter=8)))
            tabela_fat_dados = [["Mês","Nº Eventos","Receita Eventos","Gastos Viagem","Compras","Lucro Líquido"]]
            for _, row in df_mensal_export.iterrows():
                tabela_fat_dados.append([row["Mês"],str(row["Nº Eventos"]),formatar_moeda(row['Receita de Eventos (R$)']),formatar_moeda(row['Gastos de Viagem (R$)']),formatar_moeda(row['Investimento em Compras (R$)']),formatar_moeda(row['Lucro Líquido (R$)'])])
            tabela_fat_pdf = Table(tabela_fat_dados, colWidths=[2.6*cm,2.2*cm,3.2*cm,3*cm,2.8*cm,3.2*cm])
            estilo_tabela_fat = [('BACKGROUND',(0,0),(-1,0),COR_PRETO_F),('TEXTCOLOR',(0,0),(-1,0),COR_DOURADO_F),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'CENTER'),('FONTSIZE',(0,0),(-1,-1),8.5),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]
            for i in range(1, len(tabela_fat_dados)):
                if i % 2 == 0: estilo_tabela_fat.append(('BACKGROUND',(0,i),(-1,i),COR_CINZA_CLARO_F))
            tabela_fat_pdf.setStyle(TableStyle(estilo_tabela_fat))
            story_fat.append(tabela_fat_pdf)
            story_fat.append(Spacer(1,14))
            story_fat.append(Paragraph(f"<b>Lucro Líquido Total do Período:</b> {formatar_moeda(lucro_liquido)}", ParagraphStyle('Resumo',fontSize=11,textColor=COR_PRETO_F)))
            doc_fat.build(story_fat)
            buffer_pdf_fat.seek(0)
            st.download_button("📄 Baixar PDF do Período", data=buffer_pdf_fat, file_name=f"faturamento_{ano_selecionado}.pdf", mime="application/pdf")
        else: st.caption("⚠️ Para gerar o PDF, instale a biblioteca: `pip install reportlab`")
