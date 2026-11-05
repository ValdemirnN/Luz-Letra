"""Contrato de locação (PDF) — Luz & Letra.

O PDF "Recibo" continua existindo (gerar_recibo_evento_pdf no app.py). Este módulo cria o CONTRATO,
no mesmo modelo do contrato em papel da empresa:
  - Locador: dados da empresa (cadastrados uma vez, em "Dados da empresa para o contrato")
  - Locatário: nome e CPF/CNPJ do cliente
  - Cláusula 1: equipamentos alocados no agendamento
  - Cláusula 2: duração e data de entrega/retirada
  - Cláusula 3: local do evento
  - Cláusula 4: valor total e forma de pagamento (cadastrada no evento)
  - Assinaturas do locador e do locatário no final

Onde ficam os dados:
  eventos.contrato_dados  -> JSON com CPF/CNPJ do cliente, forma de pagamento e entrada (coluna nova, veja SQL_MIGRACAO)
  usuarios.perfil_extra   -> dados da empresa e do DONO (Meu Perfil > Empresa), usados como LOCADOR
"""
import io
import json
import os
from datetime import datetime
from xml.sax.saxutils import escape

import streamlit as st

SQL_MIGRACAO = """ALTER TABLE eventos ADD COLUMN IF NOT EXISTS contrato_dados text;"""

FORMAS_PAGAMENTO = {
    "50_50": "50% na assinatura do contrato + 50% no dia do evento",
    "avista_assinatura": "Tudo de uma vez — na assinatura do contrato",
    "avista_dia": "Tudo de uma vez — no dia do evento",
    "entrada_valor": "Entrada de valor específico na assinatura + restante no dia do evento",
}
_ORDEM_FORMAS = list(FORMAS_PAGAMENTO.keys())

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]
_EXTENSO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito",
            9: "nove", 10: "dez", 11: "onze", 12: "doze", 13: "treze", 14: "quatorze", 15: "quinze",
            16: "dezesseis", 17: "dezessete", 18: "dezoito", 19: "dezenove", 20: "vinte"}


# ------------------------------------------------------------------ utilidades
def _json(txt):
    if isinstance(txt, dict):
        return txt
    if not txt:
        return {}
    try:
        v = json.loads(txt)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def so_digitos(t):
    return "".join(c for c in str(t or "") if c.isdigit())


def fmt_doc(t):
    """Põe pontos, traço e barra no CPF (11 dígitos) ou CNPJ (14 dígitos). Outros valores ficam como estão."""
    d = so_digitos(t)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return str(t or "").strip()


def _data_br(iso):
    try:
        return datetime.strptime(str(iso).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(iso or "-")


def _data_extenso(d):
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}"


def _dias_locacao(ev):
    try:
        ini = datetime.strptime(str(ev.get("data_inicio")).split("T")[0], "%Y-%m-%d").date()
        fim = datetime.strptime(str(ev.get("data_fim_alocacao") or ev.get("data_fim") or ev.get("data_inicio")).split("T")[0], "%Y-%m-%d").date()
        return max(1, (fim - ini).days + 1)
    except Exception:
        return 1


def _extenso(n):
    return _EXTENSO.get(n, str(n))


def dados_do_evento(ev):
    """Lê o JSON de contrato do evento (vazio se a coluna ainda não existir)."""
    return _json((ev or {}).get("contrato_dados"))


def calcular_parcelas(valor_total, dados):
    """Devolve (valor_na_assinatura, valor_no_dia_do_evento)."""
    valor_total = float(valor_total or 0)
    forma = (dados or {}).get("forma_pagamento") or "50_50"
    if forma == "avista_assinatura":
        return valor_total, 0.0
    if forma == "avista_dia":
        return 0.0, valor_total
    if forma == "entrada_valor":
        entrada = min(max(float((dados or {}).get("entrada") or 0), 0.0), valor_total)
        return entrada, valor_total - entrada
    entrada = round(valor_total / 2, 2)  # 50_50
    return entrada, round(valor_total - entrada, 2)


# ------------------------------------------------------------------ banco de dados
def _extra_usuario(supabase, uid):
    try:
        r = supabase.table("usuarios").select("perfil_extra").eq("id", uid).execute()
        bruto = (r.data or [{}])[0].get("perfil_extra")
        return _json(bruto)
    except Exception:
        return {}


def carregar_locador(supabase, emp_id):
    """Monta os dados do LOCADOR a partir do perfil: aba Empresa + 'Dono da empresa' (Meu Perfil)."""
    extra = _extra_usuario(supabase, st.session_state.get("usuario_id"))
    if not extra.get("dono_nome"):  # usuário logado não é o dono: procura o perfil do dono na mesma empresa
        try:
            r = supabase.table("usuarios").select("perfil_extra").eq("empresa_id", emp_id).execute()
            for linha in (r.data or []):
                ex = _json(linha.get("perfil_extra"))
                if ex.get("dono_nome"):
                    extra = {**ex, **{k: v for k, v in extra.items() if v and k not in ex}}
                    break
        except Exception:
            pass
    razao = extra.get("razao_social") or ""
    if not razao:
        try:
            r = supabase.table("empresas").select("nome_fantasia").eq("id", emp_id).execute()
            razao = (r.data or [{}])[0].get("nome_fantasia") or ""
        except Exception:
            pass
    rua = ", ".join([x for x in [extra.get("endereco"), extra.get("numero")] if x])
    cid_uf = "-".join([x for x in [extra.get("cidade"), extra.get("uf")] if x])
    endereco = ", ".join([x for x in [rua, extra.get("bairro")] if x])
    return {
        "razao_social": razao, "cnpj": extra.get("cnpj") or "", "endereco": endereco,
        "telefone": extra.get("emp_whatsapp") or extra.get("emp_telefone") or "", "cidade": cid_uf,
        "responsavel": extra.get("dono_nome") or "", "nacionalidade": extra.get("dono_nacionalidade") or "",
        "estado_civil": extra.get("dono_estado_civil") or "", "cpf_responsavel": extra.get("dono_cpf") or "",
        "endereco_responsavel": extra.get("dono_endereco") or "",
    }


def faltando_locador(locador):
    nomes = {"razao_social": "nome da empresa", "cnpj": "CNPJ da empresa", "responsavel": "nome do dono",
             "nacionalidade": "nacionalidade do dono", "estado_civil": "estado civil do dono",
             "cpf_responsavel": "CPF do dono", "endereco_responsavel": "endereço do dono"}
    return [v for k, v in nomes.items() if not (locador or {}).get(k)]


def salvar_dados_evento(supabase, evento_id, dados):
    dados = dict(dados or {})
    dados["doc_cliente"] = fmt_doc(dados.get("doc_cliente"))
    try:
        supabase.table("eventos").update({"contrato_dados": json.dumps(dados, ensure_ascii=False)}).eq("id", evento_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def avisar_migracao(erro):
    st.warning("⚠️ Não consegui salvar os dados do contrato. Rode este SQL uma vez no Supabase (SQL Editor) e tente de novo:")
    st.code(SQL_MIGRACAO, language="sql")
    st.caption(f"Detalhe técnico: {erro}")


# ------------------------------------------------------------------ interface
def ui_campos_contrato(chave, dados_ini=None, valor_total=None):
    """Campos do contrato (CPF/CNPJ do cliente + forma de pagamento). Funciona dentro ou fora de st.form."""
    dados_ini = dados_ini or {}
    forma_ini = dados_ini.get("forma_pagamento") if dados_ini.get("forma_pagamento") in FORMAS_PAGAMENTO else "50_50"
    st.markdown("**📄 Dados para o contrato**")
    c1, c2, c3 = st.columns([1.2, 2.2, 1.2])
    with c1:
        doc = st.text_input("CPF ou CNPJ do cliente", value=dados_ini.get("doc_cliente", ""), key=f"{chave}_doc")
    with c2:
        forma = st.selectbox("Forma de pagamento", _ORDEM_FORMAS, index=_ORDEM_FORMAS.index(forma_ini),
                             format_func=lambda k: FORMAS_PAGAMENTO[k], key=f"{chave}_forma")
    with c3:
        entrada = st.number_input("Valor da entrada (R$)", min_value=0.0, step=50.0,
                                  value=float(dados_ini.get("entrada") or 0.0), format="%.2f", key=f"{chave}_entrada",
                                  help="Só é usado na opção 'Entrada de valor específico'.")
    return {"doc_cliente": (doc or "").strip(), "forma_pagamento": forma, "entrada": float(entrada or 0)}


def ui_completar_evento(supabase, ev, chave, mostrar_popup):
    """Expander para preencher/atualizar CPF/CNPJ e forma de pagamento de um evento (inclusive os antigos)."""
    dados = dados_do_evento(ev)
    pendente = not dados.get("doc_cliente") or not dados.get("forma_pagamento")
    titulo = "⚠️ Completar dados do contrato" if pendente else "📝 Dados do contrato (CPF/CNPJ e pagamento)"
    with st.expander(titulo, expanded=False):
        novos = ui_campos_contrato(chave, dados)
        if st.button("💾 Salvar dados do contrato", key=f"{chave}_salvar"):
            ok, err = salvar_dados_evento(supabase, ev["id"], novos)
            if ok:
                mostrar_popup("DADOS DO CONTRATO SALVOS COM SUCESSO!")
                st.rerun()
            else:
                avisar_migracao(err)


# ------------------------------------------------------------------ PDF
def gerar_contrato_pdf(evento, itens_lista, dict_produtos, nome_cliente, locador, safe_json_load, formatar_moeda):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

    locador = locador or {}
    dados = dados_do_evento(evento)
    e = lambda v: escape(str(v)) if v not in (None, "") else ""
    campo = lambda v, vazio="______________________": f"<b>{e(v)}</b>" if v else vazio

    COR_DOURADO = colors.HexColor("#FFC107")
    COR_PRETO = colors.HexColor("#0E0E0E")
    logo = next((p for p in ("logo_sem_fundo.png", "logo.jpg") if os.path.exists(p)), None)
    empresa_nome = (locador.get("razao_social") or "Luz & Letra").upper()

    def _pagina(c, doc):
        c.saveState()
        w, h = A4
        faixa = 2.8 * cm
        c.setFillColor(COR_PRETO)
        c.rect(0, h - faixa, w, faixa, fill=1, stroke=0)
        if logo:
            try:
                c.drawImage(logo, 2 * cm, h - faixa + 0.3 * cm, width=3.6 * cm, height=2.2 * cm, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        c.setFillColor(COR_DOURADO)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(6.2 * cm, h - 1.35 * cm, "CONTRATO DE LOCAÇÃO")
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 9.5)
        c.drawString(6.2 * cm, h - 2.0 * cm, empresa_nome)
        c.setFillColor(colors.grey)
        c.setFont("Helvetica", 8)
        c.drawString(2 * cm, 1.1 * cm, f"{locador.get('razao_social') or 'Luz & Letra'} — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        c.drawRightString(w - 2 * cm, 1.1 * cm, f"Página {doc.page}")
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title="Contrato de Locação")
    doc.addPageTemplates([PageTemplate(id="ctr", frames=[Frame(2 * cm, 1.8 * cm, A4[0] - 4 * cm, A4[1] - 5.2 * cm)], onPage=_pagina)])
    base = getSampleStyleSheet()["Normal"]
    corpo = ParagraphStyle("corpo", parent=base, fontName="Times-Roman", fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=9)
    cab = ParagraphStyle("cab", parent=base, fontName="Times-Roman", fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#333333"))
    titulo = ParagraphStyle("titulo", parent=base, fontName="Times-Bold", fontSize=13, leading=17, alignment=TA_CENTER, spaceBefore=10, spaceAfter=12)
    centro = ParagraphStyle("centro", parent=corpo, alignment=TA_CENTER)

    story = []
    linhas_cab = [e(locador.get("endereco")) and f"{e(locador.get('endereco'))}",
                  f"CNPJ: {e(fmt_doc(locador.get('cnpj')))}" if locador.get("cnpj") else "",
                  f"TEL: {e(locador.get('telefone'))}" if locador.get("telefone") else ""]
    story.append(Paragraph("<br/>".join([l for l in linhas_cab if l]) or "&nbsp;", cab))
    story.append(Paragraph("<u>CONTRATO DE PRESTAÇÃO DE SERVIÇO</u>", titulo))

    # Partes — LOCADOR (empresa + dono) e LOCATARIO (cliente)
    BR = "______________________"
    def sub(v, vazio=BR):  # negrito + sublinhado (como no contrato em papel)
        return f"<b><u>{e(v)}</u></b>" if v else vazio
    cnpj_loc = fmt_doc(locador.get("cnpj"))
    cpf_resp = fmt_doc(locador.get("cpf_responsavel"))
    quali = ", ".join([x for x in [locador.get("nacionalidade"), locador.get("estado_civil")] if x])
    quali = f", {e(quali)}" if quali else ""
    story.append(Paragraph(
        f"Pelo presente instrumento particular, de um lado {sub(empresa_nome)} inscrito no CNPJ: {e(cnpj_loc) if cnpj_loc else BR} "
        f"tendo como responsável {sub(locador.get('responsavel'))}{quali}, inscrito no CPF: {e(cpf_resp) if cpf_resp else BR}, "
        f"residente e domiciliado a {e(locador.get('endereco_responsavel')) if locador.get('endereco_responsavel') else BR}, "
        f"doravante denominado <b><u>LOCADOR</u></b> e de outro lado {campo(nome_cliente)}, inscrito no CNPJ ou CPF: "
        f"{campo(fmt_doc(dados.get('doc_cliente')))}, doravante denominado <b><u>LOCATARIO</u></b>, tem entre si, justo e acertado "
        f"o presente contrato de locação de equipamentos que se regerá pelas cláusulas e condições descritas a seguir.", corpo))

    # Cláusula 1 — equipamentos
    partes = []
    for it in (itens_lista or []):
        nome = (dict_produtos.get(it.get("produto_id"), {}) or {}).get("nome", f"Produto #{it.get('produto_id')}")
        det = ""
        js = safe_json_load(it.get("observacao"))
        if js:
            det = " (" + ", ".join(f"{k}: {v}x" for k, v in js.items()) + ")"
        partes.append(f"{it.get('quantidade')}x {nome}{det}")
    lista_itens = "; ".join(partes) if partes else "nenhum equipamento alocado"
    story.append(Paragraph(
        f"<b><u>CLÁUSULA 1ª:</u></b> O presente contrato tem como objeto o serviço de ({campo(lista_itens)}) em bom estado de "
        f"conservação e correto funcionamento, de propriedade do <b><u>LOCADOR</u></b>, que serão locados ao <b><u>LOCATARIO</u></b>.", corpo))

    # Cláusula 2 — duração
    n = _dias_locacao(evento)
    dia = _data_br(evento.get("data_inicio"))
    hi = (evento.get("hora_inicio") or "")[:5]
    hf = (evento.get("hora_fim") or "")[:5]
    horario = f", no horário de {hi} às {hf}" if hi and hf else ""
    story.append(Paragraph(
        f"<b><u>CLÁUSULA 2ª:</u></b> A locação terá duração de {n:02d} ({_extenso(n)}) {'dia' if n == 1 else 'dias'}, sendo que os "
        f"equipamentos descritos na cláusula primeira serão entregues e instalados pelo <b><u>LOCADOR</u></b> no dia <b>({e(dia)})</b>"
        f"{e(horario)} e retirados no término do evento.", corpo))

    # Cláusula 3 — local
    local = (evento.get("observacao") or "").strip()
    if local.lower().startswith("local:"): local = local[6:].strip()
    local = local.rstrip(" -,;").strip()
    story.append(Paragraph(
        f"<b><u>CLÁUSULA 3ª:</u></b> O endereço onde os bens serão entregues e instalados no dia <b>{e(dia)}</b> é: {campo(local, '______________________________________')}.", corpo))

    # Cláusula 4 — valores
    total = float(evento.get("valor_total") or 0)
    ass, dia_ev = calcular_parcelas(total, dados)
    forma = dados.get("forma_pagamento") or "50_50"
    R = lambda v: f"<b>R$ {formatar_moeda(v)}</b>"
    if forma == "avista_assinatura":
        pg = f"O pagamento será feito integralmente, no valor de {R(total)}, no ato da assinatura do contrato."
    elif forma == "avista_dia":
        pg = f"O pagamento será feito integralmente, no valor de {R(total)}, no dia do evento."
    else:
        pg = f"Sendo que será pago {R(ass)} no ato da assinatura do contrato e o restante {R(dia_ev)} no dia do evento."
    story.append(Paragraph(f"<b><u>CLÁUSULA 4ª:</u></b> Valor total do contrato {R(total)}. {pg}", corpo))

    # Cláusula 5 — devolução
    story.append(Paragraph(
        "<b><u>CLÁUSULA 5ª:</u></b> Ao final da locação os bens deverão ser devolvidos pelo <b><u>LOCATARIO</u></b> nas mesmas condições "
        "de conservação e funcionamento que foram recebidos, sob pena de responder por perdas e danos.", corpo))
    story.append(Paragraph("Por estarem assim justos e contratados, firmam o presente instrumento em duas vias de igual teor.", corpo))

    # Assinaturas
    cidade = locador.get("cidade") or ""
    hoje = _data_extenso(datetime.now().date())
    linha = "_" * 46
    assin = Table([
        [linha], [Paragraph(f"<b>{e(locador.get('responsavel') or empresa_nome)}</b> (LOCADOR)", centro)],
        [Spacer(1, 30)],
        [linha], [Paragraph(f"<b>{e(nome_cliente)}</b> (LOCATARIO)", centro)],
    ], colWidths=[12 * cm])
    assin.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    bloco = KeepTogether([Spacer(1, 26), Paragraph(f"{e(cidade) + ', ' if cidade else ''}{hoje}", centro), Spacer(1, 30), assin])
    story.append(bloco)

    doc.build(story)
    buf.seek(0)
    return buf
