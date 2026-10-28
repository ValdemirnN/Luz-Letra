"""Módulo: 👑 Gestão de Assinantes (painel do admin geral).

Recebe as dependências por parâmetro para não depender de variáveis globais do app.py.

Melhorias desta versão:
- Cards de resumo no topo (mesmo estilo do Dashboard).
- Busca, filtros (plano, status, vencimento) e botão "Só pendentes".
- Lista ordenada por urgência (pendentes > vencidos > vencendo > sem assinatura > em dia).
- Linha limpa: empresa + nome em destaque e etiquetas coloridas; detalhes ao abrir.
- Ações separadas em abas (Assinatura / Acesso / Comunicação), com confirmação ao bloquear,
  senha oculta e atalhos de renovação (1, 3, 6, 12 meses).
- Velocidade: UMA consulta para todas as assinaturas (antes era 1 por assinante).
- Extras: exportar Excel, aviso de vencimento em lote e link direto do WhatsApp.
"""
from modulos.log import registrar_erro
import io
import json
import re
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

PRECO_PLANO = {"basico": 79.90, "pro": 89.90}   # mesmos valores que já eram usados no código
OPCOES_MESES = [1, 3, 6, 12]
PASSO_MOSTRAR = 15                               # quantos assinantes aparecem por vez

# Situações de vencimento (também usadas no filtro)
SIT_VENCIDO = "Vencido"
SIT_HOJE = "Vence hoje"
SIT_7D = "Vence em até 7 dias"
SIT_EM_DIA = "Em dia"
SIT_SEM = "Sem assinatura"
SITUACOES = [SIT_VENCIDO, SIT_HOJE, SIT_7D, SIT_EM_DIA, SIT_SEM]

_CSS = """<style>
.ga-grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:6px 0 14px;}
.ga-card{background:#1B1B1D;border-radius:12px;padding:14px 16px;border-top:3px solid #333;min-width:0;}
.ga-card .lbl{font-size:12.5px;color:#9A9A9A;font-weight:600;}
.ga-card .val{font-size:clamp(20px,5vw,28px);font-weight:800;color:#EDEDED;line-height:1.25;margin-top:4px;overflow-wrap:anywhere;}
.ga-head{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;justify-content:space-between;}
.ga-tit{min-width:0;}
.ga-emp{font-size:1.08rem;font-weight:800;color:#F5F5F5;line-height:1.2;overflow-wrap:anywhere;}
.ga-nome{font-size:.88rem;color:#9A9A9A;margin-top:1px;overflow-wrap:anywhere;}
.ga-tags{display:flex;flex-wrap:wrap;gap:6px;}
.ga-tag{font-size:.74rem;font-weight:700;padding:3px 10px;border-radius:999px;background:#26262A;color:#DDD;border:1px solid #3a3a40;white-space:nowrap;}
.ga-tag.ouro{background:rgba(255,193,7,.14);color:#FFC107;border-color:rgba(255,193,7,.4);}
.ga-tag.verde{background:rgba(46,125,50,.20);color:#7CD67F;border-color:rgba(46,125,50,.55);}
.ga-tag.amar{background:rgba(255,193,7,.16);color:#FFD54F;border-color:rgba(255,193,7,.5);}
.ga-tag.laranja{background:rgba(255,138,0,.18);color:#FFB74D;border-color:rgba(255,138,0,.55);}
.ga-tag.verm{background:rgba(179,38,30,.22);color:#FF8A80;border-color:rgba(179,38,30,.6);}
.ga-tag.cinza{background:#26262A;color:#B0B0B8;border-color:#3a3a40;}
</style>"""


# ----------------------------------------------------------------------------------
# Funções auxiliares (sem acesso a banco)
# ----------------------------------------------------------------------------------
def _card(rotulo, valor, cor):
    return (f'<div class="ga-card" style="border-top-color:{cor};">'
            f'<div class="lbl">{rotulo}</div><div class="val">{valor}</div></div>')


def _tag(texto, cor=""):
    return f'<span class="ga-tag {cor}">{texto}</span>'


def _esc(txt):
    """Evita que um nome/empresa com < > & quebre o HTML do cabeçalho."""
    return str(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _extra_dict(bruto):
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto)
        except Exception:
            registrar_erro("gestao_assinantes.py:_extra_dict")
            bruto = {}
    return bruto if isinstance(bruto, dict) else {}


def _telefone(extra):
    for chave in ("telefone", "emp_whatsapp", "emp_telefone"):
        v = extra.get(chave)
        if v and re.sub(r"\D", "", str(v)):
            return str(v)
    return ""


def _link_whatsapp(telefone, mensagem):
    d = re.sub(r"\D", "", telefone or "")
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) not in (10, 11):
        return None
    return f"https://wa.me/55{d}?text={quote(mensagem)}"


def _situacao(venc_str, hoje):
    """Devolve (situacao, dias, texto_da_etiqueta, cor_da_etiqueta)."""
    if not venc_str:
        return SIT_SEM, None, "Sem assinatura", "cinza"
    try:
        dias = (datetime.strptime(venc_str, "%Y-%m-%d").date() - hoje).days
    except Exception:
        registrar_erro("gestao_assinantes.py:_situacao")
        return SIT_SEM, None, "Sem data", "cinza"
    if dias < 0:
        return SIT_VENCIDO, dias, f"Vencido há {abs(dias)} dia(s)", "verm"
    if dias == 0:
        return SIT_HOJE, dias, "Vence HOJE", "laranja"
    if dias <= 7:
        return SIT_7D, dias, f"Vence em {dias} dia(s)", "amar"
    return SIT_EM_DIA, dias, f"Vence em {dias} dias", "verde"


def _prioridade(a):
    """Quanto menor, mais no topo."""
    if a["aguardando"]:
        return 0
    return {SIT_VENCIDO: 1, SIT_HOJE: 2, SIT_7D: 2, SIT_SEM: 3, SIT_EM_DIA: 4}[a["situacao"]]


def _montar_assinantes(users, vencimentos, hoje):
    lista = []
    for u in users:
        emp = u.get("empresas") or {}
        venc = vencimentos.get(u.get("empresa_id"))
        situacao, dias, txt_venc, cor_venc = _situacao(venc, hoje)
        metodo = u.get("metodo_pagamento")
        ativo = bool(u.get("ativo"))
        extra = _extra_dict(u.get("perfil_extra"))
        lista.append({
            "u": u, "id": u["id"], "empresa_id": u.get("empresa_id"),
            "empresa": emp.get("nome_fantasia") or "Sem Empresa",
            "nome": u.get("nome") or u["email"],
            "email": u.get("email") or "",
            "plano": (u.get("plano") or "basico").lower(),
            "ativo": ativo,
            "email_ok": bool(u.get("email_confirmado", False)),
            "comprovante": u.get("comprovante_pagamento"),
            "aguardando": (metodo in ["manual", "pix_manual"]) and (not ativo or bool(u.get("comprovante_pagamento"))),
            "venc": venc, "situacao": situacao, "dias": dias, "txt_venc": txt_venc, "cor_venc": cor_venc,
            "telefone": _telefone(extra),
        })
    lista.sort(key=lambda a: (_prioridade(a), a["dias"] if a["dias"] is not None else 10**6, a["empresa"].lower()))
    return lista


def _filtrar(lista, busca, planos, status, situacao, so_pendentes):
    termo = (busca or "").strip().lower()
    saida = []
    for a in lista:
        if termo and not any(termo in (a[k] or "").lower() for k in ("empresa", "nome", "email")):
            continue
        if planos and a["plano"] not in planos:
            continue
        if status == "Ativos" and not a["ativo"]:
            continue
        if status == "Bloqueados" and a["ativo"]:
            continue
        if situacao and a["situacao"] not in situacao:
            continue
        if so_pendentes and not a["aguardando"]:
            continue
        saida.append(a)
    return saida


def _excel_assinantes(lista):
    df = pd.DataFrame([{
        "Empresa": a["empresa"], "Nome": a["nome"], "E-mail": a["email"], "Telefone": a["telefone"] or "-",
        "Plano": a["plano"].upper(), "Status": "Ativo" if a["ativo"] else "Bloqueado",
        "Vencimento": a["venc"] or "Sem assinatura",
        "Dias para vencer": a["dias"] if a["dias"] is not None else "-",
        "Situação": a["situacao"], "E-mail confirmado": "Sim" if a["email_ok"] else "Não",
        "Aguardando confirmação": "Sim" if a["aguardando"] else "Não",
    } for a in lista])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Assinantes")
    buf.seek(0)
    return buf


# ----------------------------------------------------------------------------------
# Acesso ao banco
# ----------------------------------------------------------------------------------
def _buscar_usuarios(supabase):
    base = "id, email, ativo, nome, email_confirmado, metodo_pagamento, comprovante_pagamento, plano, empresas(nome_fantasia), empresa_id"
    tentativas = [base + ", perfil_extra", base, "id, email, ativo, empresas(nome_fantasia), empresa_id"]
    for i, cols in enumerate(tentativas):
        try:
            return supabase.table("usuarios").select(cols).neq("perfil", "admin_geral").execute().data or []
        except Exception:
            registrar_erro(f"gestao_assinantes.py:_buscar_usuarios[{i}]")
    return []


def _buscar_vencimentos(supabase, empresa_ids):
    """UMA consulta para todas as empresas (antes: uma por assinante, dentro do loop)."""
    ids = sorted({e for e in empresa_ids if e is not None})
    if not ids:
        return {}
    resp = supabase.table("assinaturas").select("empresa_id, data_vencimento").in_("empresa_id", ids).execute()
    venc = {}
    for r in resp.data or []:
        v = (r.get("data_vencimento") or "").split("T")[0]
        if v and v > venc.get(r["empresa_id"], ""):
            venc[r["empresa_id"]] = v          # fica o vencimento mais recente de cada empresa
    return venc


def _receita_do_mes(supabase, hoje):
    try:
        ini = hoje.replace(day=1).strftime("%Y-%m-%d")
        r = supabase.table("historico_pagamentos").select("valor").gte("data_pagamento", ini).execute()
        return sum(float(p.get("valor") or 0) for p in (r.data or []))
    except Exception:
        registrar_erro("gestao_assinantes.py:_receita_do_mes")
        return None


def _fmt_data(venc):
    try:
        return datetime.strptime(venc, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return "—"


# ----------------------------------------------------------------------------------
# Um assinante (cabeçalho com etiquetas + detalhes/ações dentro do expander)
# ----------------------------------------------------------------------------------
def _desenhar_assinante(a, hoje, supabase, formatar_moeda, mostrar_popup, hash_senha,
                        enviar_email_expiracao, ativar_conta_apos_pagamento, registrar_pagamento_historico):
    uid = a["id"]
    pro = a["plano"] == "pro"
    admin_nome = st.session_state.get("nome_usuario", "Admin")
    venc_fmt = _fmt_data(a["venc"])

    with st.container(border=True):
        tags = []
        if a["aguardando"]:
            tags.append(_tag("⏳ Aguardando confirmação", "laranja"))
        tags.append(_tag("PRO" if pro else "BÁSICO", "ouro" if pro else ""))
        tags.append(_tag("Ativo", "verde") if a["ativo"] else _tag("Bloqueado", "verm"))
        tags.append(_tag(a["txt_venc"], a["cor_venc"]))
        tags.append(_tag("✉️ E-mail confirmado", "verde") if a["email_ok"] else _tag("✉️ E-mail não confirmado", "cinza"))
        st.markdown(
            f'<div class="ga-head"><div class="ga-tit"><div class="ga-emp">🏢 {_esc(a["empresa"])}</div>'
            f'<div class="ga-nome">{_esc(a["nome"])}</div></div><div class="ga-tags">{"".join(tags)}</div></div>',
            unsafe_allow_html=True)

        with st.expander("Detalhes e ações"):
            # ---------- pagamento em mãos aguardando aprovação ----------
            if a["aguardando"]:
                st.warning("⏳ Esta pessoa escolheu pagar em mãos e está aguardando aprovação.")
                if a["comprovante"]:
                    st.info(f"📎 Comprovante: {a['comprovante']}")
                if st.button("✅ Confirmar Pagamento Recebido", key=f"conf_manual_{uid}"):
                    venc_ant = a["venc"] or "Sem Assinatura"
                    ativar_conta_apos_pagamento(uid, "manual")
                    ass_novo = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", a["empresa_id"]).order("data_vencimento", desc=True).limit(1).execute()
                    venc_novo = ass_novo.data[0]["data_vencimento"].split("T")[0] if ass_novo.data else venc_ant
                    registrar_pagamento_historico(a["empresa_id"], uid, a["plano"], PRECO_PLANO.get(a["plano"], 89.90), "manual",
                                                  venc_ant, venc_novo, aprovado_por=admin_nome)
                    supabase.table("usuarios").update({"comprovante_pagamento": None}).eq("id", uid).execute()
                    mostrar_popup("Conta ativada com sucesso!")
                    st.rerun()

            # ---------- dados ----------
            d1, d2 = st.columns(2)
            d1.markdown(f"**E-mail:** {a['email'] or '—'}")
            d1.markdown(f"**Telefone:** {a['telefone'] or '—'}")
            d2.markdown(f"**Validade:** {venc_fmt}")
            d2.markdown(f"**Plano:** {a['plano'].upper()}")

            t_ass, t_acc, t_com = st.tabs(["📅 Assinatura", "🔐 Acesso", "✉️ Comunicação"])

            # ---------- ASSINATURA ----------
            with t_ass:
                if not a["venc"]:
                    st.warning("Esta empresa não tem assinatura cadastrada, então não há o que renovar.")
                meses = st.radio("Renovar por", OPCOES_MESES, horizontal=True, key=f"ga_mes_{uid}",
                                 format_func=lambda m: f"{m} mês" if m == 1 else f"{m} meses")
                preco = PRECO_PLANO.get(a["plano"], 89.90)
                valor = st.number_input("Valor recebido (R$)", min_value=0.0, value=round(preco * meses, 2),
                                        format="%.2f", key=f"ga_valor_{uid}_{meses}")
                if a["venc"]:
                    base = max(datetime.strptime(a["venc"], "%Y-%m-%d").date(), hoje)
                    novo_prev = base + relativedelta(months=int(meses))
                    st.caption(f"Novo vencimento: **{novo_prev.strftime('%d/%m/%Y')}**")
                if st.button("🔄 Renovar", key=f"ren_{uid}", disabled=not a["venc"]):
                    base = max(datetime.strptime(a["venc"], "%Y-%m-%d").date(), hoje)
                    novo_venc = (datetime.combine(base, datetime.min.time()) + relativedelta(months=int(meses))).strftime("%Y-%m-%d")
                    supabase.table("assinaturas").update({"data_vencimento": novo_venc}).eq("empresa_id", a["empresa_id"]).execute()
                    st.cache_data.clear()
                    if not a["ativo"]:
                        supabase.table("usuarios").update({"ativo": True}).eq("id", uid).execute()
                    registrar_pagamento_historico(a["empresa_id"], uid, a["plano"], valor, "manual_admin",
                                                  a["venc"], novo_venc, aprovado_por=admin_nome)
                    mostrar_popup("Plano renovado com sucesso!")
                    st.rerun()

            # ---------- ACESSO ----------
            with t_acc:
                st.markdown(f"**Status:** {'✅ Ativo' if a['ativo'] else '🔴 Bloqueado'}")
                flag = f"ga_cb_{uid}"
                if a["ativo"]:
                    if st.session_state.get(flag):
                        st.warning(f"Bloquear o acesso de **{a['empresa']}**? Ninguém dessa conta conseguirá entrar até você desbloquear.")
                        c1, c2 = st.columns(2)
                        if c1.button("🔒 Sim, bloquear", key=f"ga_blk_sim_{uid}", type="primary"):
                            supabase.table("usuarios").update({"ativo": False}).eq("id", uid).execute()
                            st.session_state.pop(flag, None)
                            st.rerun()
                        if c2.button("Cancelar", key=f"ga_blk_nao_{uid}"):
                            st.session_state.pop(flag, None)
                            st.rerun()
                    elif st.button("🔒 Bloquear acesso", key=f"blk_{uid}"):
                        st.session_state[flag] = True
                        st.rerun()
                elif st.button("🔓 Desbloquear acesso", key=f"blk_{uid}"):
                    supabase.table("usuarios").update({"ativo": True}).eq("id", uid).execute()
                    st.rerun()

                st.divider()
                n_pwd = st.session_state.get(f"ga_pwdn_{uid}", 0)   # muda após salvar → campo volta vazio
                nova_senha = st.text_input("Nova senha", type="password", key=f"pwd_{uid}_{n_pwd}",
                                           placeholder="Mínimo de 7 caracteres")
                if st.button("🔑 Mudar senha", key=f"btn_pwd_{uid}"):
                    if len(nova_senha or "") < 7:
                        mostrar_popup("A nova senha precisa ter no mínimo 7 caracteres.", tipo="erro")
                    else:
                        supabase.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("id", uid).execute()
                        st.session_state[f"ga_pwdn_{uid}"] = n_pwd + 1
                        mostrar_popup("Senha alterada!")
                        st.rerun()

            # ---------- COMUNICAÇÃO ----------
            with t_com:
                if a["email"] and a["ativo"] and a["venc"]:
                    if st.button("📧 Enviar aviso de vencimento por e-mail", key=f"aviso_manual_{uid}"):
                        try:
                            dias_r = (datetime.strptime(a["venc"], "%Y-%m-%d").date() - hoje).days
                            if enviar_email_expiracao(a["email"], a["nome"], max(1, dias_r), venc_fmt):
                                mostrar_popup("E-mail enviado com sucesso!")
                            else:
                                mostrar_popup("Erro ao enviar e-mail.", tipo="erro")
                        except Exception as e:
                            registrar_erro("gestao_assinantes.py:aviso_manual")
                            mostrar_popup(f"Erro: {e}", tipo="erro")
                else:
                    st.caption("O aviso por e-mail só está disponível para assinantes ativos, com e-mail e assinatura cadastrados.")

                primeiro = (a["nome"] or "").split(" ")[0]
                if a["dias"] is None:
                    msg = f"Olá, {primeiro}! Aqui é da Luz & Letra. Posso te ajudar com a sua assinatura?"
                elif a["dias"] < 0:
                    msg = f"Olá, {primeiro}! Aqui é da Luz & Letra. Sua assinatura venceu em {venc_fmt}. Posso te ajudar com a renovação?"
                else:
                    msg = f"Olá, {primeiro}! Aqui é da Luz & Letra. Sua assinatura vence em {venc_fmt}. Posso te ajudar com a renovação?"
                link = _link_whatsapp(a["telefone"], msg)
                if link:
                    st.link_button("💬 Chamar no WhatsApp", link)
                else:
                    st.caption("💬 WhatsApp indisponível: o assinante não tem telefone válido no perfil.")


# ----------------------------------------------------------------------------------
# Aba "Assinantes"
# ----------------------------------------------------------------------------------
def _aba_assinantes(supabase, formatar_moeda, mostrar_popup, hash_senha, enviar_email_expiracao,
                    ativar_conta_apos_pagamento, registrar_pagamento_historico):
    hoje = datetime.now().date()
    users = _buscar_usuarios(supabase)
    if not users:
        st.info("Nenhuma empresa cadastrada ainda.")
        return
    try:
        vencimentos = _buscar_vencimentos(supabase, [u.get("empresa_id") for u in users])
    except Exception:
        registrar_erro("gestao_assinantes.py:vencimentos")
        st.error("Não foi possível carregar as datas de vencimento das assinaturas.")
        vencimentos = {}
    assinantes = _montar_assinantes(users, vencimentos, hoje)

    # ---------- 1. cards de resumo ----------
    n_total = len(assinantes)
    n_ativos = sum(1 for a in assinantes if a["ativo"])
    n_vencendo = sum(1 for a in assinantes if a["situacao"] in (SIT_HOJE, SIT_7D))
    n_vencidos = sum(1 for a in assinantes if a["situacao"] == SIT_VENCIDO)
    n_pend = sum(1 for a in assinantes if a["aguardando"])
    receita = _receita_do_mes(supabase, hoje)
    st.markdown(
        '<div class="ga-grid">'
        + _card("👥 Total de assinantes", n_total, "#FFC107")
        + _card("✅ Ativos", n_ativos, "#2E7D32")
        + _card("🟡 Vencendo em até 7 dias", n_vencendo, "#F9A825")
        + _card("🔴 Vencidos", n_vencidos, "#C62828")
        + _card("⏳ Aguardando confirmação", n_pend, "#FB8C00")
        + _card("💰 Receita do mês", f"R$ {formatar_moeda(receita)}" if receita is not None else "—", "#2E7D32")
        + "</div>", unsafe_allow_html=True)

    # ---------- 2. busca e filtros ----------
    cb1, cb2 = st.columns([3, 1], vertical_alignment="bottom")
    busca = cb1.text_input("🔎 Buscar", key="ga_busca", placeholder="Empresa, nome ou e-mail...")
    so_pend = cb2.toggle(f"🔔 Só pendentes ({n_pend})", key="ga_so_pend")
    cf1, cf2, cf3 = st.columns(3)
    planos = cf1.multiselect("Plano", ["basico", "pro"], key="ga_f_plano", format_func=lambda p: "Básico" if p == "basico" else "PRO")
    status = cf2.selectbox("Status", ["Todos", "Ativos", "Bloqueados"], key="ga_f_status")
    situacao = cf3.multiselect("Vencimento", SITUACOES, key="ga_f_sit")
    filtrados = _filtrar(assinantes, busca, planos, status, situacao, so_pend)

    # ---------- 7. extras: exportar e aviso em lote ----------
    candidatos = [a for a in assinantes if a["ativo"] and a["email"] and a["situacao"] in (SIT_HOJE, SIT_7D)]
    cx1, cx2, cx3 = st.columns([2, 1, 1], vertical_alignment="center")
    cx1.caption(f"Mostrando {len(filtrados)} de {n_total} assinantes · ordenados por urgência")
    cx2.download_button("📊 Exportar Excel", data=_excel_assinantes(filtrados),
                        file_name=f"assinantes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Exporta a lista como está filtrada na tela.")
    if cx3.button(f"📧 Avisar vencimentos ({len(candidatos)})", key="ga_lote", disabled=not candidatos,
                  help="Envia o aviso de vencimento a todos os ativos que vencem hoje ou em até 7 dias."):
        st.session_state["ga_conf_lote"] = True
    if st.session_state.get("ga_conf_lote") and candidatos:
        st.warning(f"Enviar o aviso de vencimento por e-mail para **{len(candidatos)}** assinante(s) que vencem em até 7 dias?")
        l1, l2, _ = st.columns([1, 1, 2])
        if l1.button("✅ Sim, enviar", key="ga_lote_sim", type="primary"):
            ok, falhas = 0, []
            with st.spinner("Enviando e-mails..."):
                for a in candidatos:
                    try:
                        enviado = enviar_email_expiracao(a["email"], a["nome"], max(1, a["dias"]), _fmt_data(a["venc"]))
                    except Exception:
                        registrar_erro("gestao_assinantes.py:aviso_lote")
                        enviado = False
                    if enviado:
                        ok += 1
                    else:
                        falhas.append(a["empresa"])
            st.session_state.pop("ga_conf_lote", None)
            if falhas:
                st.error(f"{ok} enviado(s). Falhou para: {', '.join(falhas)}")
            else:
                st.success(f"✅ {ok} e-mail(s) enviado(s) com sucesso!")
        if l2.button("Cancelar", key="ga_lote_nao"):
            st.session_state.pop("ga_conf_lote", None)
            st.rerun()

    # ---------- 4/5/6. lista ----------
    if not filtrados:
        st.info("Nenhum assinante encontrado com esses filtros.")
        return
    limite = st.session_state.get("ga_limite", PASSO_MOSTRAR)
    for a in filtrados[:limite]:
        _desenhar_assinante(a, hoje, supabase, formatar_moeda, mostrar_popup, hash_senha,
                            enviar_email_expiracao, ativar_conta_apos_pagamento, registrar_pagamento_historico)
    if len(filtrados) > limite:
        if st.button(f"⬇️ Mostrar mais ({len(filtrados) - limite} restantes)", key="ga_mais"):
            st.session_state["ga_limite"] = limite + PASSO_MOSTRAR
            st.rerun()


def render(supabase, formatar_moeda, mostrar_popup, hash_senha, enviar_email_expiracao, ativar_conta_apos_pagamento, registrar_pagamento_historico):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("👑 Painel Master — Gestão de Assinantes")
    tab_assinantes, tab_pagamentos = st.tabs(["👥 Assinantes", "💳 Histórico de Pagamentos"])

    with tab_assinantes:
        _aba_assinantes(supabase, formatar_moeda, mostrar_popup, hash_senha, enviar_email_expiracao,
                        ativar_conta_apos_pagamento, registrar_pagamento_historico)

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
                        except Exception: registrar_erro("gestao_assinantes.py:132"); return str(d) if d else '-'
                    data_pag_fmt = pag.get('data_pagamento','-')
                    if data_pag_fmt and data_pag_fmt != '-':
                        try: data_pag_fmt = datetime.strptime(data_pag_fmt[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y às %H:%M")
                        except Exception: registrar_erro("gestao_assinantes.py:136"); pass
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
            registrar_erro("gestao_assinantes.py:188")
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
