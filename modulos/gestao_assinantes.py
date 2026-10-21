"""Módulo: 👑 Gestão de Assinantes (painel do admin geral).

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.
"""
import io
from datetime import datetime

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta


def render(supabase, formatar_moeda, mostrar_popup, hash_senha, enviar_email_expiracao, ativar_conta_apos_pagamento, registrar_pagamento_historico):
    st.title("👑 Painel Master — Gestão de Assinantes")
    tab_assinantes, tab_pagamentos = st.tabs(["👥 Assinantes", "💳 Histórico de Pagamentos"])

    with tab_assinantes:
        try:
            users = supabase.table("usuarios").select(
                "id, email, ativo, nome, email_confirmado, metodo_pagamento, comprovante_pagamento, plano, empresas(nome_fantasia), empresa_id"
            ).neq("perfil", "admin_geral").execute()
        except Exception:
            users = supabase.table("usuarios").select("id, email, ativo, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()

        if users.data:
            for u in users.data:
                assinatura = supabase.table("assinaturas").select("data_inicio, data_vencimento").eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                venc = assinatura.data[0]['data_vencimento'].split("T")[0] if assinatura.data else "Sem Assinatura"
                try:
                    venc_date_adm = datetime.strptime(venc, "%Y-%m-%d").date()
                    hoje_admin = datetime.now().date()
                    dias_venc = (venc_date_adm - hoje_admin).days
                    if dias_venc < 0: badge_venc = f"🔴 Vencido há {abs(dias_venc)} dia(s)"
                    elif dias_venc == 0: badge_venc = "🟠 Vence HOJE"
                    elif dias_venc <= 7: badge_venc = f"🟡 Vence em {dias_venc} dia(s)"
                    else: badge_venc = f"🟢 Vence em {dias_venc} dias"
                except Exception: badge_venc = "❓ Sem data"

                nome_fantasia = u['empresas']['nome_fantasia'] if u.get('empresas') else "Sem Empresa"
                email_confirmado_u = u.get('email_confirmado', False)
                metodo_pag_u = u.get('metodo_pagamento')
                comprovante_u = u.get('comprovante_pagamento')
                nome_u = u.get('nome') or u['email']
                plano_u = u.get('plano') or 'basico'
                icone_email = "✅" if email_confirmado_u else "❌"
                aguardando_manual = (metodo_pag_u in ["manual", "pix_manual"]) and (not u['ativo'] or u.get('comprovante_pagamento'))

                prefixo = "🔔 " if aguardando_manual else ""
                titulo_exp = f"{prefixo}🏢 {nome_fantasia} — {nome_u} ({u['email']}) | Plano: {plano_u.upper()} | Validade: {venc} ({badge_venc}) | E-mail: {icone_email}"
                if aguardando_manual: titulo_exp += " | ⏳ Aguardando confirmação"

                with st.expander(titulo_exp):
                    if aguardando_manual:
                        st.warning("⏳ Esta pessoa escolheu pagar em mãos e está aguardando aprovação.")
                        if comprovante_u: st.info(f"📎 Comprovante: {comprovante_u}")
                        if st.button("✅ Confirmar Pagamento Recebido", key=f"conf_manual_{u['id']}"):
                            venc_ant = venc
                            ativar_conta_apos_pagamento(u['id'], "manual")
                            ass_novo = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                            venc_novo = ass_novo.data[0]['data_vencimento'].split("T")[0] if ass_novo.data else venc
                            valor_plano_conf = 79.90 if plano_u == 'basico' else 89.90
                            registrar_pagamento_historico(u['empresa_id'], u['id'], plano_u, valor_plano_conf, "manual", venc_ant, venc_novo, aprovado_por=st.session_state.get('nome_usuario','Admin'))
                            supabase.table("usuarios").update({"comprovante_pagamento": None}).eq("id", u['id']).execute()
                            mostrar_popup("Conta ativada com sucesso!")
                            st.rerun()

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Status:** {'✅ Ativo' if u['ativo'] else '🔴 Bloqueado'}")
                        if st.button("🔄 Bloq/Desbloq", key=f"blk_{u['id']}"):
                            supabase.table("usuarios").update({"ativo": not u['ativo']}).eq("id", u['id']).execute()
                            st.rerun()
                        if u.get('email') and u['ativo']:
                            if st.button("📧 Enviar Aviso de Vencimento", key=f"aviso_manual_{u['id']}"):
                                try:
                                    venc_fmt_adm = datetime.strptime(venc, "%Y-%m-%d").strftime("%d/%m/%Y")
                                    dias_r = (datetime.strptime(venc, "%Y-%m-%d").date() - datetime.now().date()).days
                                    sucesso_email = enviar_email_expiracao(u['email'], u.get('nome') or u['email'], max(1, dias_r), venc_fmt_adm)
                                    if sucesso_email: mostrar_popup("E-mail enviado com sucesso!")
                                    else: mostrar_popup("Erro ao enviar e-mail.", tipo="erro")
                                except Exception as e: mostrar_popup(f"Erro: {e}", tipo="erro")
                    with col2:
                        nova_senha = st.text_input("Nova Senha", key=f"pwd_{u['id']}")
                        if st.button("🔑 Mudar Senha", key=f"btn_pwd_{u['id']}") and nova_senha:
                            supabase.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("id", u['id']).execute()
                            mostrar_popup("Senha alterada!")
                    with col3:
                        meses_add = st.number_input("Estender (meses)", min_value=1, key=f"mes_{u['id']}", value=1)
                        valor_renovacao_adm = st.number_input("Valor recebido (R$)", min_value=0.0, value=79.90 if plano_u == 'basico' else 89.90, format="%.2f", key=f"valor_ren_{u['id']}")
                        if st.button("🔄 Renovar", key=f"ren_{u['id']}"):
                            try: data_base_ren = max(datetime.strptime(venc, "%Y-%m-%d").date(), datetime.now().date())
                            except Exception: data_base_ren = datetime.now().date()
                            novo_venc_adm = (datetime.combine(data_base_ren, datetime.min.time()) + relativedelta(months=int(meses_add))).strftime("%Y-%m-%d")
                            supabase.table("assinaturas").update({"data_vencimento": novo_venc_adm}).eq("empresa_id", u['empresa_id']).execute()
                            st.cache_data.clear()
                            if not u['ativo']: supabase.table("usuarios").update({"ativo": True}).eq("id", u['id']).execute()
                            registrar_pagamento_historico(u['empresa_id'], u['id'], plano_u, valor_renovacao_adm, "manual_admin", venc, novo_venc_adm, aprovado_por=st.session_state.get('nome_usuario','Admin'))
                            mostrar_popup("Plano renovado com sucesso!")
                            st.rerun()
        else: st.info("Nenhuma empresa cadastrada ainda.")

    with tab_pagamentos:
        st.subheader("💳 Histórico Completo de Pagamentos")
        st.caption("Todos os pagamentos confirmados manualmente pelo admin ou via sistema.")
        col_hpf1, col_hpf2, col_hpf3 = st.columns(3)
        with col_hpf1: filtro_hp_empresa = st.text_input("Buscar empresa ou e-mail", key="filtro_hp_empresa", placeholder="Digite para filtrar...")
        with col_hpf2: filtro_hp_metodo = st.multiselect("Método de Pagamento", ["manual","pix_manual","cartao","manual_admin"], key="filtro_hp_metodo")
        with col_hpf3: filtro_hp_plano = st.multiselect("Plano", ["basico","pro"], key="filtro_hp_plano")
        try:
            hist_pag_resp = supabase.table("historico_pagamentos").select("*, empresas(nome_fantasia), usuarios(email, nome)").order("data_pagamento", desc=True).execute()
            pagamentos = hist_pag_resp.data or []
            if filtro_hp_empresa.strip():
                termo_hp = filtro_hp_empresa.lower()
                pagamentos = [p for p in pagamentos if termo_hp in (p.get('empresas',{}).get('nome_fantasia','') or '').lower() or termo_hp in (p.get('usuarios',{}).get('email','') or '').lower() or termo_hp in (p.get('usuarios',{}).get('nome','') or '').lower()]
            if filtro_hp_metodo: pagamentos = [p for p in pagamentos if p.get('metodo_pagamento') in filtro_hp_metodo]
            if filtro_hp_plano: pagamentos = [p for p in pagamentos if p.get('plano') in filtro_hp_plano]
            total_recebido = sum(float(p.get('valor') or 0) for p in pagamentos)
            col_mp1, col_mp2, col_mp3 = st.columns(3)
            col_mp1.metric("📋 Total de Registros", len(pagamentos))
            col_mp2.metric("💰 Valor Total Registrado", f"R$ {formatar_moeda(total_recebido)}")
            col_mp3.metric("📅 Último Pagamento", pagamentos[0]['data_pagamento'][:10] if pagamentos else "-")
            st.markdown("---")
            if pagamentos:
                for pag in pagamentos:
                    nome_emp_pag = pag.get('empresas',{}).get('nome_fantasia','Sem empresa') if pag.get('empresas') else 'Sem empresa'
                    email_u_pag = pag.get('usuarios',{}).get('email','-') if pag.get('usuarios') else '-'
                    nome_u_pag = pag.get('usuarios',{}).get('nome','-') if pag.get('usuarios') else '-'
                    def _fmt_pag(d):
                        try: return datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                        except Exception: return str(d) if d else '-'
                    data_pag_fmt = pag.get('data_pagamento','-')
                    if data_pag_fmt and data_pag_fmt != '-':
                        try: data_pag_fmt = datetime.strptime(data_pag_fmt[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y às %H:%M")
                        except Exception: pass
                    valor_pag = float(pag.get('valor') or 0)
                    metodo_pag = pag.get('metodo_pagamento') or '-'
                    plano_pag = (pag.get('plano') or 'basico').upper()
                    aprovado_pag = pag.get('aprovado_por') or 'Sistema'
                    venc_ant_fmt = _fmt_pag(pag.get('vencimento_anterior'))
                    venc_nov_fmt = _fmt_pag(pag.get('vencimento_novo'))
                    with st.expander(f"🏢 {nome_emp_pag} — {nome_u_pag} | R$ {formatar_moeda(valor_pag)} | {plano_pag} | Pago em: {data_pag_fmt}"):
                        col_pd1, col_pd2, col_pd3 = st.columns(3)
                        with col_pd1:
                            st.write(f"**Empresa:** {nome_emp_pag}")
                            st.write(f"**Usuário:** {nome_u_pag}")
                            st.write(f"**E-mail:** {email_u_pag}")
                        with col_pd2:
                            st.write(f"**Plano:** {plano_pag}")
                            st.write(f"**Valor:** R$ {formatar_moeda(valor_pag)}")
                            st.write(f"**Método:** {metodo_pag}")
                        with col_pd3:
                            st.write(f"**Data do Pagamento:** {data_pag_fmt}")
                            st.write(f"**Venc. Anterior:** {venc_ant_fmt}")
                            st.write(f"**Novo Vencimento:** {venc_nov_fmt}")
                            st.write(f"**Aprovado por:** {aprovado_pag}")
                        st.markdown("---")
                        col_del1, col_del2 = st.columns([3,1])
                        with col_del2:
                            motivo_del_pag = st.text_input("Motivo para excluir", key=f"motivo_del_pag_{pag['id']}")
                            if st.button("🗑️ Excluir Registro", key=f"del_pag_{pag['id']}"):
                                if not motivo_del_pag.strip(): st.error("Informe o motivo da exclusão.")
                                else:
                                    supabase.table("historico_pagamentos").delete().eq("id", pag['id']).execute()
                                    mostrar_popup(f"Registro excluído. Motivo: {motivo_del_pag}")
                                    st.rerun()
                st.markdown("---")
                df_hist_pag = pd.DataFrame([{
                    "Empresa": p.get('empresas',{}).get('nome_fantasia','-') if p.get('empresas') else '-',
                    "Usuário": p.get('usuarios',{}).get('nome','-') if p.get('usuarios') else '-',
                    "E-mail": p.get('usuarios',{}).get('email','-') if p.get('usuarios') else '-',
                    "Plano": (p.get('plano') or '').upper(),
                    "Valor (R$)": float(p.get('valor') or 0),
                    "Método": p.get('metodo_pagamento') or '-',
                    "Data Pagamento": p.get('data_pagamento') or '-',
                    "Venc. Anterior": p.get('vencimento_anterior') or '-',
                    "Novo Vencimento": p.get('vencimento_novo') or '-',
                    "Aprovado por": p.get('aprovado_por') or '-',
                } for p in pagamentos])
                buf_xls_pag = io.BytesIO()
                with pd.ExcelWriter(buf_xls_pag, engine="openpyxl") as writer:
                    df_hist_pag.to_excel(writer, index=False, sheet_name="Pagamentos")
                buf_xls_pag.seek(0)
                st.download_button("📊 Exportar Histórico em Excel", data=buf_xls_pag, file_name=f"pagamentos_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.info("Nenhum pagamento registrado ainda.")
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")
            st.info("Execute o SQL abaixo no Supabase para criar as tabelas necessárias:")
            st.code("""
CREATE TABLE IF NOT EXISTS historico_pagamentos (
    id SERIAL PRIMARY KEY, empresa_id INTEGER, usuario_id INTEGER,
    plano TEXT, valor NUMERIC(10,2), metodo_pagamento TEXT,
    data_pagamento TIMESTAMP DEFAULT NOW(),
    vencimento_anterior TEXT, vencimento_novo TEXT, aprovado_por TEXT
);
CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
    id SERIAL PRIMARY KEY, usuario_id INTEGER,
    tipo TEXT, referencia TEXT, enviado_em TIMESTAMP DEFAULT NOW()
);
""", language="sql")
