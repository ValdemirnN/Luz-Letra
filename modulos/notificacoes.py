"""Notificações por e-mail do Luz & Letra.

Este módulo NÃO depende do Streamlit: ele é usado pelo app (aviso de novo agendamento, na hora)
e pelo script `notificador.py`, que roda todo dia sozinho pelo GitHub Actions (avisos por data).

O que ele envia
  1. Assinatura: avisos 7, 3 e 1 dia antes do vencimento (mesma regra/registro que o app já tinha).
  2. Novo agendamento: resumo do evento, assim que ele é criado.
  3. Compras: chegando (3 e 1 dia antes), chegam hoje, atrasadas (TODO dia até marcar "Chegou").
  4. Manutenção: retorno chegando (3 e 1 dia antes), é hoje, atrasado (TODO dia até concluir).
  5. Pagamento de evento: no dia do evento e TODO dia depois, até o pagamento ser confirmado.
  6. Pendências após o evento: TODO dia depois que o evento passou, enquanto houver equipamento não devolvido
     ou o status continuar "Agendado"/"Em Andamento" (independe de o evento já estar pago).

Para quem vai: SÓ o e-mail de login dos usuários ativos da empresa. Se a empresa tiver "E-mail comercial"
preenchido (aba Empresa do Perfil), ele é usado apenas como "responder para"; o nome do remetente é o nome fantasia.
Obs.: o endereço de envio em si é sempre o Gmail configurado (GMAIL_REMETENTE).
Para não repetir e-mail, cada aviso é registrado na tabela `notificacoes_enviadas`
(usuario_id, tipo, referencia) — a mesma que o app já usa.
"""
import json
import os
import re
import smtplib
import threading
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape

from modulos.log import registrar_erro

try:
    from zoneinfo import ZoneInfo
    _FUSO = ZoneInfo("America/Fortaleza")  # Rio Grande do Norte (UTC-3, sem horário de verão)
except Exception:  # pragma: no cover
    _FUSO = None

MARCOS_VENCIMENTO = (7, 3, 1)
LIMITE_LINHAS = 25  # máximo de itens listados por e-mail (o resto vira "e mais N")

_CFG = {
    "remetente": os.environ.get("GMAIL_REMETENTE", ""),
    "senha": os.environ.get("GMAIL_SENHA_APP", ""),
    "url": os.environ.get("URL_BASE_SISTEMA", ""),
    "pix_chave": os.environ.get("PIX_CHAVE", ""),
    "pix_nome": os.environ.get("PIX_NOME", ""),
}


def configurar(remetente=None, senha=None, url_sistema=None, pix_chave=None, pix_nome=None):
    """O app chama 1x na partida, passando os segredos do Streamlit."""
    for chave, valor in (("remetente", remetente), ("senha", senha), ("url", url_sistema),
                         ("pix_chave", pix_chave), ("pix_nome", pix_nome)):
        if valor:
            _CFG[chave] = valor


def hoje_br():
    return datetime.now(_FUSO).date() if _FUSO else datetime.now().date()


# ----------------------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------------------
def _data(v):
    """'2026-11-10' / '2026-11-10T00:00:00' -> date (ou None)."""
    if not v:
        return None
    try:
        return datetime.strptime(str(v).split("T")[0].split(" ")[0], "%Y-%m-%d").date()
    except Exception:
        return None


def _br(d):
    return d.strftime("%d/%m/%Y") if d else "-"


def _moeda(v):
    try:
        return "R$ " + f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def _dias_txt(n):
    return _plural(abs(n), "dia", "dias")


# ----------------------------------------------------------------------------------
# Envio
# ----------------------------------------------------------------------------------
def configurado():
    return bool(_CFG["remetente"] and _CFG["senha"]) and "SEU_EMAIL_AQUI" not in _CFG["remetente"]


def enviar_email(destinatario, assunto, texto, html=None, responder_para=None, nome_remetente=None):
    """Envia pelo Gmail (senha de app). destinatario: e-mail ou lista de e-mails. Devolve True/False."""
    if not configurado():
        registrar_erro("notificacoes.py:enviar", "GMAIL_REMETENTE/GMAIL_SENHA_APP não configurados")
        return False
    destinos = [destinatario] if isinstance(destinatario, str) else list(destinatario)
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = formataddr((nome_remetente or "Luz & Letra", _CFG["remetente"]), charset="utf-8")
        msg["To"] = ", ".join(destinos)
        if responder_para:
            msg["Reply-To"] = responder_para
        msg.attach(MIMEText(texto, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
            servidor.login(_CFG["remetente"], _CFG["senha"])
            servidor.sendmail(_CFG["remetente"], destinos, msg.as_string())
        return True
    except Exception:
        registrar_erro("notificacoes.py:enviar", ", ".join(destinos))
        return False


def _enviar_para_usuario(u, assunto, texto, html):
    return enviar_email(u["emails"], assunto, texto, html, responder_para=u.get("responder_para"), nome_remetente=u.get("remetente_nome"))


_CORES = {"verm": "#C62828", "amar": "#B26A00", "azul": "#1565C0", "verde": "#2E7D32"}


def _montar(titulo, intro, blocos, rodape=""):
    """blocos: [(titulo, cor, [linhas])]  ->  (texto, html)"""
    texto = [titulo, "", intro, ""]
    html = [
        '<div style="font-family:Arial,Helvetica,sans-serif;background:#f4f4f5;padding:24px">',
        '<div style="max-width:620px;margin:auto;background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e4e4e7">',
        '<div style="background:#1B1B1D;padding:18px 24px"><span style="color:#FFC107;font-size:20px;font-weight:700">Luz &amp; Letra</span></div>',
        f'<div style="padding:24px"><h2 style="margin:0 0 8px 0;color:#18181b;font-size:19px">{escape(titulo)}</h2>',
        f'<p style="margin:0 0 18px 0;color:#52525b;font-size:15px;line-height:1.5">{escape(intro)}</p>',
    ]
    for tit, cor, linhas in blocos:
        if not linhas:
            continue
        texto.append(tit.upper())
        cor_hex = _CORES.get(cor, "#52525b")
        html.append(f'<div style="margin:14px 0 6px 0;font-weight:700;color:{cor_hex};font-size:14px">{escape(tit)}</div>')
        html.append('<ul style="margin:0;padding:0 0 0 18px;color:#27272a;font-size:14px;line-height:1.6">')
        mostradas = linhas[:LIMITE_LINHAS]
        for ln in mostradas:
            texto.append(f"  • {ln}")
            html.append(f"<li>{escape(ln)}</li>")
        if len(linhas) > LIMITE_LINHAS:
            extra = f"e mais {len(linhas) - LIMITE_LINHAS} item(ns) — veja no sistema"
            texto.append(f"  • {extra}")
            html.append(f"<li>{escape(extra)}</li>")
        html.append("</ul>")
        texto.append("")
    if _CFG["url"]:
        texto += [f"Abrir o sistema: {_CFG['url']}", ""]
        html.append(f'<p style="margin:22px 0 0 0"><a href="{escape(_CFG["url"])}" style="background:#FFC107;color:#1a1200;'
                    f'padding:11px 20px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px">Abrir o sistema</a></p>')
    if rodape:
        texto.append(rodape)
        html.append(f'<p style="margin:18px 0 0 0;color:#71717a;font-size:12px">{escape(rodape)}</p>')
    html.append("</div></div></div>")
    texto.append("— Equipe Luz & Letra")
    return "\n".join(texto), "".join(html)


# ----------------------------------------------------------------------------------
# Destinatários e registro de envios
# ----------------------------------------------------------------------------------
_EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _extra(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return {}
    return v if isinstance(v, dict) else {}


def _usuarios_ativos(sb):
    """{empresa_id: [usuários]} — cada usuário traz 'emails' (só o login),
    'responder_para' (e-mail comercial) e 'remetente_nome' (nome fantasia · Luz & Letra)."""
    try:
        r = sb.table("usuarios").select("id, email, nome, empresa_id, perfil, ativo, perfil_extra").eq("ativo", True).neq("perfil", "admin_geral").execute()
    except Exception:  # coluna perfil_extra ainda não criada
        registrar_erro("notificacoes.py:perfil_extra")
        r = sb.table("usuarios").select("id, email, nome, empresa_id, perfil, ativo").eq("ativo", True).neq("perfil", "admin_geral").execute()
    linhas = [u for u in (r.data or []) if u.get("empresa_id") and (u.get("email") or "").strip()]

    # e-mail comercial por empresa (primeiro preenchido entre os usuários dela)
    comercial = {}
    for u in linhas:
        em = (_extra(u.get("perfil_extra")).get("emp_email") or "").strip()
        if em and _EMAIL_OK.match(em) and u["empresa_id"] not in comercial:
            comercial[u["empresa_id"]] = em
    nomes = {}
    try:
        ids = list({u["empresa_id"] for u in linhas})
        if ids:
            for e in (sb.table("empresas").select("id, nome_fantasia").in_("id", ids).execute().data or []):
                nomes[e["id"]] = (e.get("nome_fantasia") or "").strip()
    except Exception:
        registrar_erro("notificacoes.py:empresas")

    por_empresa = {}
    vistos = set()
    for u in linhas:
        login = u["email"].strip()
        if login.lower() in vistos:
            continue
        vistos.add(login.lower())
        com = comercial.get(u["empresa_id"])
        nome_emp = nomes.get(u["empresa_id"])
        u["emails"] = [login]  # o aviso vai SÓ para o e-mail de login cadastrado; o comercial fica como "responder para"
        u["responder_para"] = com
        u["remetente_nome"] = f"{nome_emp} · Luz & Letra" if nome_emp else "Luz & Letra"
        por_empresa.setdefault(u["empresa_id"], []).append(u)
    return por_empresa


def _ja_enviou(sb, uid, tipo, ref, cache):
    k = (uid, tipo, ref)
    if k in cache:
        return cache[k]
    try:
        r = sb.table("notificacoes_enviadas").select("id").eq("usuario_id", uid).eq("tipo", tipo).eq("referencia", ref).limit(1).execute()
        cache[k] = bool(r.data)
    except Exception:
        registrar_erro("notificacoes.py:ja_enviou")
        cache[k] = False
    return cache[k]


def _marcar(sb, uid, tipo, ref, cache):
    try:
        sb.table("notificacoes_enviadas").insert({"usuario_id": uid, "tipo": tipo, "referencia": ref,
                                                  "enviado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}).execute()
        cache[(uid, tipo, ref)] = True
    except Exception:
        registrar_erro("notificacoes.py:marcar")


def _enviar_digest(sb, usuarios, itens, assunto_fn, titulo, intro, ordem_blocos, cache, dry_run, rodape=""):
    """Um e-mail por usuário com TODOS os itens ainda não avisados a ele.
    itens: [{'tipo','ref','bloco','cor','linha'}]. Devolve quantos e-mails foram enviados."""
    enviados = 0
    for u in usuarios:
        novos = [it for it in itens if not _ja_enviou(sb, u["id"], it["tipo"], it["ref"], cache)]
        if not novos:
            continue
        blocos = []
        for nome_bloco, cor in ordem_blocos:
            linhas = [it["linha"] for it in novos if it["bloco"] == nome_bloco]
            if linhas:
                blocos.append((nome_bloco, cor, linhas))
        assunto = assunto_fn(novos)
        texto, html = _montar(titulo, intro, blocos, rodape)
        if dry_run:
            print(f"[SIMULAÇÃO] para {', '.join(u['emails'])}: {assunto} ({len(novos)} item(ns))")
            enviados += 1
            continue
        if _enviar_para_usuario(u, assunto, texto, html):
            enviados += 1
            for it in novos:
                _marcar(sb, u["id"], it["tipo"], it["ref"], cache)
    return enviados


def _fase(dias):
    """dias = data prevista - hoje."""
    if dias < 0:
        return "atrasada"
    if dias == 0:
        return "hoje"
    if dias == 1:
        return "1d"
    if dias in (2, 3):
        return "3d"
    return None


def _fim_evento(e):
    """Mesma data final que o app usa (data_fim_alocacao é a que o usuário edita)."""
    return _data(e.get("data_fim_alocacao")) or _data(e.get("data_fim")) or _data(e.get("data_inicio"))


def _em_lotes(lista, n=80):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


# ----------------------------------------------------------------------------------
# 1) Assinatura
# ----------------------------------------------------------------------------------
def _rotina_assinatura(sb, hoje, por_empresa, cache, dry_run):
    enviados = 0
    for empresa_id, usuarios in por_empresa.items():
        try:
            r = sb.table("assinaturas").select("data_vencimento").eq("empresa_id", empresa_id).order("data_vencimento", desc=True).limit(1).execute()
        except Exception:
            registrar_erro("notificacoes.py:assinatura")
            continue
        if not r.data:
            continue
        venc = _data(r.data[0].get("data_vencimento"))
        if not venc:
            continue
        dias = (venc - hoje).days
        if dias not in MARCOS_VENCIMENTO:
            continue
        venc_str = venc.strftime("%Y-%m-%d")
        tipo = f"expiracao_{dias}d"
        for u in usuarios:
            if _ja_enviou(sb, u["id"], tipo, venc_str, cache):
                continue
            nome = u.get("nome") or u["email"]
            if dias == 1:
                assunto = "⚠️ Último dia! Sua assinatura Luz & Letra expira AMANHÃ"
            else:
                assunto = f"⚠️ Sua assinatura Luz & Letra vence em {dias} dias"
            linhas = [f"Vencimento: {_br(venc)}", "Para renovar: Perfil → Assinatura → Renovar meu plano atual"]
            if _CFG["pix_chave"]:
                linhas.append(f"Pix: {_CFG['pix_chave']}" + (f" ({_CFG['pix_nome']})" if _CFG["pix_nome"] else ""))
            texto, html = _montar(
                f"Sua assinatura vence em {_dias_txt(dias)}",
                f"Olá, {nome}! Renove para manter seu acesso sem interrupção. "
                "Depois do vencimento, o acesso é bloqueado automaticamente 1 dia depois.",
                [("Como renovar", "amar", linhas)])
            if dry_run:
                print(f"[SIMULAÇÃO] para {', '.join(u['emails'])}: {assunto}")
                enviados += 1
            elif _enviar_para_usuario(u, assunto, texto, html):
                enviados += 1
                _marcar(sb, u["id"], tipo, venc_str, cache)
    return enviados


# ----------------------------------------------------------------------------------
# 3) Compras
# ----------------------------------------------------------------------------------
_BLOCOS_PRAZO = [("Atrasadas", "verm"), ("Para hoje", "amar"), ("Chegando", "azul")]


def _rotina_compras(sb, hoje, por_empresa, cache, dry_run, desde):
    r = sb.table("compras").select("*").neq("status_chegada", "Chegou").execute()
    por_emp = {}
    for c in (r.data or []):
        prev = _data(c.get("data_prevista_chegada"))
        if not prev or (desde and prev < desde):
            continue
        fase = _fase((prev - hoje).days)
        if not fase:
            continue
        dias = (prev - hoje).days
        ref = f"{c['id']}:{hoje}" if fase == "atrasada" else f"{c['id']}:{prev}"
        base = f"{c.get('nome_produto') or 'Compra'} ({c.get('quantidade') or 0}x)"
        forn = f" — {c['fornecedor']}" if c.get("fornecedor") else ""
        if fase == "atrasada":
            bloco, linha = "Atrasadas", f"{base}{forn} — previsto para {_br(prev)}, atrasada há {_dias_txt(dias)}"
        elif fase == "hoje":
            bloco, linha = "Para hoje", f"{base}{forn} — chegada prevista para hoje"
        else:
            bloco, linha = "Chegando", f"{base}{forn} — chega em {_dias_txt(dias)} ({_br(prev)})"
        por_emp.setdefault(c["empresa_id"], []).append({"tipo": f"compra_{fase}", "ref": ref, "bloco": bloco, "linha": linha})

    def assunto(novos):
        atr = sum(1 for i in novos if i["bloco"] == "Atrasadas")
        hj = sum(1 for i in novos if i["bloco"] == "Para hoje")
        partes = []
        if atr: partes.append(_plural(atr, "atrasada", "atrasadas"))
        if hj: partes.append(f"{hj} para hoje")
        if len(novos) - atr - hj: partes.append(f"{len(novos) - atr - hj} chegando")
        return ("🚨 " if atr else "🛒 ") + "Luz & Letra — Compras: " + ", ".join(partes)

    total = 0
    for empresa_id, itens in por_emp.items():
        total += _enviar_digest(sb, por_empresa.get(empresa_id, []), itens, assunto, "Compras que precisam da sua atenção",
                                "Confira as compras abaixo. Quando o item chegar, marque \"Chegou\" em Compras para parar os avisos.",
                                _BLOCOS_PRAZO, cache, dry_run)
    return total


# ----------------------------------------------------------------------------------
# 4) Manutenção
# ----------------------------------------------------------------------------------
def _rotina_manutencao(sb, hoje, por_empresa, cache, dry_run, desde):
    r = sb.table("manutencao").select("*").neq("status", "Concluído").execute()
    linhas_m = r.data or []
    ids_prod = list({m["produto_id"] for m in linhas_m if m.get("produto_id")})
    nomes = {}
    if ids_prod:
        try:
            for p in (sb.table("produtos").select("id, nome").in_("id", ids_prod).execute().data or []):
                nomes[p["id"]] = p.get("nome")
        except Exception:
            registrar_erro("notificacoes.py:produtos")
    por_emp = {}
    for m in linhas_m:
        prev = _data(m.get("data_prevista_retorno"))
        if not prev or (desde and prev < desde):
            continue
        dias = (prev - hoje).days
        fase = _fase(dias)
        if not fase:
            continue
        ref = f"{m['id']}:{hoje}" if fase == "atrasada" else f"{m['id']}:{prev}"
        base = f"{nomes.get(m.get('produto_id')) or 'Item'} ({m.get('quantidade') or 0}x)"
        local = f" — {m['local_manutencao']}" if m.get("local_manutencao") else ""
        if fase == "atrasada":
            bloco, linha = "Atrasados", f"{base}{local} — retorno previsto em {_br(prev)}, atrasado há {_dias_txt(dias)}"
        elif fase == "hoje":
            bloco, linha = "Para hoje", f"{base}{local} — retirada prevista para hoje"
        else:
            bloco, linha = "Chegando", f"{base}{local} — retirada em {_dias_txt(dias)} ({_br(prev)})"
        por_emp.setdefault(m["empresa_id"], []).append({"tipo": f"manut_{fase}", "ref": ref, "bloco": bloco, "linha": linha})

    def assunto(novos):
        atr = sum(1 for i in novos if i["bloco"] == "Atrasados")
        hj = sum(1 for i in novos if i["bloco"] == "Para hoje")
        partes = []
        if atr: partes.append(_plural(atr, "atrasado", "atrasados"))
        if hj: partes.append(f"{hj} para hoje")
        if len(novos) - atr - hj: partes.append(f"{len(novos) - atr - hj} chegando")
        return ("🚨 " if atr else "🔧 ") + "Luz & Letra — Manutenção: " + ", ".join(partes)

    total = 0
    for empresa_id, itens in por_emp.items():
        total += _enviar_digest(sb, por_empresa.get(empresa_id, []), itens, assunto, "Itens em manutenção para retirar",
                                "Estes itens estão perto (ou além) da data prevista de retorno. "
                                "Depois de retirar, conclua em Estoque → Manutenção para parar os avisos.",
                                [("Atrasados", "verm"), ("Para hoje", "amar"), ("Chegando", "azul")], cache, dry_run)
    return total


# ----------------------------------------------------------------------------------
# 5) Pagamento de evento pendente
# ----------------------------------------------------------------------------------
def _rotina_pagamento_eventos(sb, hoje, por_empresa, cache, dry_run, desde):
    r = sb.table("eventos").select("*").neq("status", "Cancelado").lte("data_inicio", str(hoje)).execute()
    eventos = [e for e in (r.data or []) if not e.get("pagamento_confirmado")]
    ids_cli = list({e["cliente_id"] for e in eventos if e.get("cliente_id")})
    clientes = {}
    if ids_cli:
        try:
            for c in (sb.table("clientes_eventos").select("id, nome").in_("id", ids_cli).execute().data or []):
                clientes[c["id"]] = c.get("nome")
        except Exception:
            registrar_erro("notificacoes.py:clientes")
    por_emp = {}
    for e in eventos:
        fim = _fim_evento(e)
        if not fim or fim > hoje or (desde and fim < desde):
            continue
        dias = (hoje - fim).days
        quando = "é hoje" if dias == 0 else f"foi há {_dias_txt(dias)}"
        linha = (f"{e.get('titulo') or 'Evento'} — cliente {clientes.get(e.get('cliente_id')) or '-'} — "
                 f"evento em {_br(fim)} ({quando}) — valor {_moeda(e.get('valor_total'))}")
        bloco = "Evento de hoje" if dias == 0 else "Evento já realizado"
        por_emp.setdefault(e["empresa_id"], []).append({"tipo": "evento_pagamento", "ref": f"{e['id']}:{hoje}", "bloco": bloco, "linha": linha})

    def assunto(novos):
        return f"💰 Luz & Letra — {_plural(len(novos), 'pagamento de evento pendente', 'pagamentos de eventos pendentes')}"

    total = 0
    for empresa_id, itens in por_emp.items():
        total += _enviar_digest(sb, por_empresa.get(empresa_id, []), itens, assunto, "Pagamento de evento pendente",
                                "O evento já aconteceu (ou acontece hoje) e o pagamento ainda não foi confirmado. "
                                "Quando receber, confirme em Agendamento → Pagamento. Você será avisado uma vez por dia até lá.",
                                [("Evento de hoje", "amar"), ("Evento já realizado", "verm")], cache, dry_run)
    return total


# ----------------------------------------------------------------------------------
# 6) Pendências depois do evento: equipamentos não devolvidos / status não atualizado
#    (todo dia, até resolver — não depende do pagamento)
# ----------------------------------------------------------------------------------
def _rotina_pendencias_evento(sb, hoje, por_empresa, cache, dry_run, desde):
    r = sb.table("eventos").select("*").neq("status", "Cancelado").lte("data_inicio", str(hoje)).execute()
    encerrados = []
    for e in (r.data or []):
        fim = _fim_evento(e)
        if fim and fim < hoje and not (desde and fim < desde):  # mesma regra do app: encerrado = data final já passou
            encerrados.append((e, fim))
    if not encerrados:
        return 0

    # itens ainda não devolvidos
    pendentes = {}
    ids_ev = [e["id"] for e, _ in encerrados]
    try:
        for lote in _em_lotes(ids_ev):
            for it in (sb.table("itens_evento").select("id, evento_id, produto_id, quantidade, devolvido").in_("evento_id", lote).execute().data or []):
                if not it.get("devolvido"):
                    pendentes.setdefault(it["evento_id"], []).append(it)
    except Exception:  # coluna 'devolvido' ainda não existe
        registrar_erro("notificacoes.py:itens_devolvido")
    ids_prod = list({i["produto_id"] for lst in pendentes.values() for i in lst if i.get("produto_id")})
    nomes_p = {}
    try:
        for lote in _em_lotes(ids_prod):
            for p_ in (sb.table("produtos").select("id, nome").in_("id", lote).execute().data or []):
                nomes_p[p_["id"]] = p_.get("nome")
    except Exception:
        registrar_erro("notificacoes.py:produtos_pend")
    ids_cli = list({e["cliente_id"] for e, _ in encerrados if e.get("cliente_id")})
    clientes = {}
    try:
        for lote in _em_lotes(ids_cli):
            for c in (sb.table("clientes_eventos").select("id, nome").in_("id", lote).execute().data or []):
                clientes[c["id"]] = c.get("nome")
    except Exception:
        registrar_erro("notificacoes.py:clientes_pend")

    por_emp = {}
    for e, fim in encerrados:
        itens = pendentes.get(e["id"], [])
        status_aberto = (e.get("status") or "") in ("Agendado", "Em Andamento")
        if not itens and not status_aberto:
            continue
        dias = (hoje - fim).days
        motivos = []
        if itens:
            lista = [f"{i.get('quantidade') or 0}x {nomes_p.get(i.get('produto_id')) or 'Item'}" for i in itens[:4]]
            mais = f" e mais {len(itens) - 4}" if len(itens) > 4 else ""
            motivos.append(f"equipamentos não devolvidos ({', '.join(lista)}{mais})")
        if status_aberto:
            motivos.append(f"status ainda \"{e.get('status')}\"")
        linha = (f"{e.get('titulo') or e.get('descricao') or 'Evento'} — cliente {clientes.get(e.get('cliente_id')) or '-'} — "
                 f"terminou em {_br(fim)} (há {_dias_txt(dias)}) — pendente: " + "; ".join(motivos))
        bloco = "Equipamentos não devolvidos" if itens else "Status do evento não atualizado"
        por_emp.setdefault(e["empresa_id"], []).append({"tipo": "evento_pendencia", "ref": f"{e['id']}:{hoje}", "bloco": bloco, "linha": linha})

    def assunto(novos):
        return f"📦 Luz & Letra — {_plural(len(novos), 'evento com pendência', 'eventos com pendências')} (devolução/status)"

    total = 0
    for empresa_id, itens in por_emp.items():
        total += _enviar_digest(sb, por_empresa.get(empresa_id, []), itens, assunto, "Eventos encerrados com pendências",
                                "A data destes eventos já passou. Registre a devolução dos equipamentos e atualize o status "
                                "(Concluído) em Agendamento. Você será avisado todo dia até resolver, mesmo que o evento já esteja pago.",
                                [("Equipamentos não devolvidos", "verm"), ("Status do evento não atualizado", "amar")], cache, dry_run)
    return total


# ----------------------------------------------------------------------------------
# Rotina diária (chamada pelo notificador.py)
# ----------------------------------------------------------------------------------
def rodar_rotina_diaria(sb, hoje=None, dry_run=False, desde=None):
    """desde: ignora compras/manutenções/eventos com data anterior a esta (evita avisar sobre o passado
    quando o recurso é ligado pela primeira vez). Aceita date ou 'AAAA-MM-DD'."""
    hoje = hoje or hoje_br()
    if isinstance(desde, str):
        desde = _data(desde)
    por_empresa = _usuarios_ativos(sb)
    cache = {}
    resumo = {}
    for nome, fn in (("assinatura", lambda: _rotina_assinatura(sb, hoje, por_empresa, cache, dry_run)),
                     ("compras", lambda: _rotina_compras(sb, hoje, por_empresa, cache, dry_run, desde)),
                     ("manutencao", lambda: _rotina_manutencao(sb, hoje, por_empresa, cache, dry_run, desde)),
                     ("pagamento_eventos", lambda: _rotina_pagamento_eventos(sb, hoje, por_empresa, cache, dry_run, desde)),
                     ("pendencias_evento", lambda: _rotina_pendencias_evento(sb, hoje, por_empresa, cache, dry_run, desde))):
        try:
            resumo[nome] = fn()
        except Exception:
            registrar_erro(f"notificacoes.py:{nome}")
            resumo[nome] = "erro"
    return resumo


# ----------------------------------------------------------------------------------
# 2) Novo agendamento (chamado pelo app logo depois de criar o evento)
# ----------------------------------------------------------------------------------
def avisar_novo_agendamento(sb, empresa_id, evento_id, em_segundo_plano=True):
    """Monta o resumo do evento e envia aos usuários da empresa. Nunca levanta erro."""
    try:
        ev = (sb.table("eventos").select("*").eq("id", evento_id).execute().data or [None])[0]
        if not ev:
            return
        cli = {}
        if ev.get("cliente_id"):
            cli = (sb.table("clientes_eventos").select("*").eq("id", ev["cliente_id"]).execute().data or [{}])[0]
        itens = sb.table("itens_evento").select("produto_id, quantidade").eq("evento_id", evento_id).execute().data or []
        nomes = {}
        ids = list({i["produto_id"] for i in itens if i.get("produto_id")})
        if ids:
            for p in (sb.table("produtos").select("id, nome").in_("id", ids).execute().data or []):
                nomes[p["id"]] = p.get("nome")
        ini, fim = _data(ev.get("data_inicio")), _data(ev.get("data_fim"))
        periodo = _br(ini) if not fim or fim == ini else f"{_br(ini)} a {_br(fim)}"
        horario = f"{str(ev.get('hora_inicio') or '')[:5]} às {str(ev.get('hora_fim') or '')[:5]}".strip()
        resumo = [
            f"Evento: {ev.get('titulo') or '-'}",
            f"Cliente: {cli.get('nome') or '-'}" + (f" — {cli['contato']}" if cli.get("contato") else ""),
            f"Data: {periodo}" + (f" · {horario}" if horario and horario != "às" else ""),
            f"Local/observações: {ev.get('observacao') or '-'}",
            f"Valor: {_moeda(ev.get('valor_total'))}",
            f"Status: {ev.get('status') or 'Agendado'}",
        ]
        lista = [f"{nomes.get(i.get('produto_id')) or 'Item'} — {i.get('quantidade') or 0}x" for i in itens]
        blocos = [("Resumo do agendamento", "verde", resumo)]
        if lista:
            blocos.append(("Itens reservados", "azul", lista))
        texto, html = _montar("Novo agendamento cadastrado", "Um novo evento foi agendado no sistema.", blocos)
        assunto = f"📅 Novo agendamento: {ev.get('titulo') or 'evento'} — {periodo}"
        usuarios = _usuarios_ativos(sb).get(empresa_id, [])
        cache = {}
    except Exception:
        registrar_erro("notificacoes.py:novo_agendamento")
        return

    def _enviar():
        for u in usuarios:
            try:
                if _ja_enviou(sb, u["id"], "agendamento", str(evento_id), cache):
                    continue
                if _enviar_para_usuario(u, assunto, texto, html):
                    _marcar(sb, u["id"], "agendamento", str(evento_id), cache)
            except Exception:
                registrar_erro("notificacoes.py:novo_agendamento_envio")

    if em_segundo_plano:
        threading.Thread(target=_enviar, daemon=True).start()
    else:
        _enviar()
