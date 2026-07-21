import streamlit as st
import json
import hashlib
import base64
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import smtplib
from email.mime.text import MIMEText
import requests
import secrets
import time

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==========================================
st.set_page_config(page_title="Luz & Letras - Sistema", page_icon="logo.jpg", layout="wide")

# ==========================================
# CUSTOMIZAÇÃO DE INTERFACE (CSS)
# ==========================================
st.markdown("""
<style>
/* Oculta a mensagem 'Press Enter to submit form' */
div[data-testid="InputInstructions"] { 
    display: none !important; 
}

/* Oculta os botões de + e - dos campos de número */
input[type="number"]::-webkit-inner-spin-button, 
input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
input[type="number"] {
    -moz-appearance: textfield;
}
</style>
""", unsafe_allow_html=True)

# Função auxiliar para formatar moeda com ponto no milhar e vírgula nos centavos
def formatar_moeda(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ==========================================
# LOGO DE FUNDO ANIMADA (MARCA D'ÁGUA COM BRILHO)
# ==========================================
def aplicar_fundo_com_logo(caminho_logo="logo.jpg"):
    try:
        with open(caminho_logo, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode()

        st.markdown(f"""
        <style>
        .stApp {{
            position: relative;
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: url("data:image/jpg;base64,{logo_base64}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: min(45vw, 480px);
            opacity: 0.07;
            z-index: 0;
            pointer-events: none;
            animation: brilhoPulsante 4s ease-in-out infinite;
        }}
        @keyframes brilhoPulsante {{
            0%   {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
            50%  {{ opacity: 0.11; filter: drop-shadow(0 0 35px #FFD700); }}
            100% {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
        }}
        .stApp > * {{
            position: relative;
            z-index: 1;
        }}
        [data-testid="stSidebar"] img {{
            animation: brilhoSidebar 3s ease-in-out infinite;
            border-radius: 12px;
        }}
        @keyframes brilhoSidebar {{
            0%   {{ filter: drop-shadow(0 0 6px rgba(255, 215, 0, 0.35)); }}
            50%  {{ filter: drop-shadow(0 0 18px rgba(255, 215, 0, 0.75)); }}
            100% {{ filter: drop-shadow(0 0 6px rgba(255, 215, 0, 0.35)); }}
        }}
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        pass

aplicar_fundo_com_logo()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://eootqeatgqcnenngnexp.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_secret_oxjLrfF5a0AcTNcs7Bimpg_a5TWQTJB")

# ==========================================
# CONFIGURAÇÕES DE E-MAIL E PAGAMENTO
# ==========================================
GMAIL_REMETENTE = st.secrets.get("GMAIL_REMETENTE", "SEU_EMAIL_AQUI@gmail.com")
GMAIL_SENHA_APP = st.secrets.get("GMAIL_SENHA_APP", "SUA_SENHA_DE_APP_DE_16_DIGITOS")
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "COLOQUE_SEU_ACCESS_TOKEN_DO_MERCADO_PAGO_AQUI")
URL_BASE_SISTEMA = st.secrets.get("URL_BASE_SISTEMA", "http://localhost:8501")
VALOR_ASSINATURA_MENSAL = 49.90

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro ao conectar com o banco. Verifique suas chaves.")
    st.stop()


# ==========================================
# 2. CONTROLE DE SESSÃO E SEGURANÇA
# ==========================================
SECRET_TOKEN_KEY = "luzletras_sistema_2026_chave_secreta"

def gerar_token_sessao(usuario_id, senha_hash):
    base = f"{usuario_id}:{senha_hash}:{SECRET_TOKEN_KEY}"
    return hashlib.sha256(base.encode()).hexdigest()[:24]

def restaurar_sessao_por_token():
    try:
        params = st.query_params
        uid_param = params.get("uid")
        tk_param = params.get("tk")
        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)
            try:
                resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, nome").eq("id", usuario_id_restaurar).execute()
            except Exception:
                resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo").eq("id", usuario_id_restaurar).execute()

            if resultado.data:
                usuario = resultado.data[0]
                token_esperado = gerar_token_sessao(usuario['id'], usuario['senha_hash'])
                if usuario['ativo'] and tk_param == token_esperado:
                    plano_valido = True
                    if usuario.get('empresa_id'):
                        assinatura_check = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", usuario['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                        if assinatura_check.data:
                            venc_check = assinatura_check.data[0]['data_vencimento'].split("T")[0]
                            if datetime.strptime(venc_check, "%Y-%m-%d").date() < datetime.now().date():
                                plano_valido = False
                    if plano_valido:
                        nome_usuario_restaurar = usuario.get('nome') or usuario.get('email', 'Usuário')
                        st.session_state.update({
                            'logado': True, 'perfil': usuario['perfil'],
                            'empresa_id': usuario['empresa_id'], 'usuario_id': usuario['id'],
                            'nome_usuario': nome_usuario_restaurar
                        })
                    else:
                        st.query_params.clear()
    except Exception:
        pass

def enviar_email_confirmacao(destinatario, nome_destinatario, token):
    link_confirmacao = f"{URL_BASE_SISTEMA}/?confirmar_email={token}"
    corpo = f"""Olá {nome_destinatario},\n\nObrigado por criar sua conta no Luz & Letras Sistema!\n\nPara confirmar seu e-mail, clique no link abaixo:\n{link_confirmacao}\n\nSe você não solicitou este cadastro, apenas ignore este e-mail.\n"""
    msg = MIMEText(corpo)
    msg['Subject'] = "Confirme seu e-mail - Luz & Letras Sistema"
    msg['From'] = GMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as servidor:
            servidor.login(GMAIL_REMETENTE, GMAIL_SENHA_APP)
            servidor.sendmail(GMAIL_REMETENTE, destinatario, msg.as_string())
        return True
    except Exception as e:
        st.warning(f"Conta criada, mas erro ao enviar e-mail ({e}).")
        return False

def confirmar_email_por_link():
    try:
        token_param = st.query_params.get("confirmar_email")
        if token_param:
            resultado = supabase.table("usuarios").select("id, email, nome").eq("token_confirmacao", token_param).execute()
            if resultado.data:
                usuario_confirmado = resultado.data[0]
                supabase.table("usuarios").update({"email_confirmado": True, "token_confirmacao": None}).eq("id", usuario_confirmado['id']).execute()
                st.session_state.update({
                    'conta_criada_id': usuario_confirmado['id'],
                    'conta_criada_email': usuario_confirmado['email'],
                    'conta_criada_nome': usuario_confirmado.get('nome') or usuario_confirmado['email']
                })
                st.success("✅ E-mail confirmado com sucesso! Agora escolha e conclua a forma de pagamento abaixo.")
            else:
                st.warning("Link de confirmação inválido ou já utilizado.")
            st.query_params.clear()
    except Exception:
        pass

confirmar_email_por_link()

def criar_preferencia_pagamento_mp(usuario_id, email_cliente, descricao):
    url = "https://api.mercadopago.com/checkout/preferences"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "items": [{"title": descricao, "quantity": 1, "unit_price": float(VALOR_ASSINATURA_MENSAL), "currency_id": "BRL"}],
        "payer": {"email": email_cliente},
        "external_reference": str(usuario_id),
        "back_urls": {"success": URL_BASE_SISTEMA, "failure": URL_BASE_SISTEMA, "pending": URL_BASE_SISTEMA}
    }
    resposta = requests.post(url, json=payload, headers=headers, timeout=15)
    resposta.raise_for_status()
    return resposta.json()

def verificar_pagamento_mp(usuario_id):
    url = "https://api.mercadopago.com/v1/payments/search"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
    params = {"external_reference": str(usuario_id)}
    resposta = requests.get(url, headers=headers, params=params, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()
    for pagamento in dados.get("results", []):
        if pagamento.get("status") == "approved":
            return True
    return False

def ativar_conta_apos_pagamento(usuario_id, metodo):
    hoje = datetime.now()
    novo_venc = hoje + relativedelta(months=1)
    resultado_user = supabase.table("usuarios").select("empresa_id").eq("id", usuario_id).execute()
    if resultado_user.data:
        empresa_id_pagamento = resultado_user.data[0]['empresa_id']
        supabase.table("assinaturas").update({"data_vencimento": novo_venc.strftime("%Y-%m-%d")}).eq("empresa_id", empresa_id_pagamento).execute()
    supabase.table("usuarios").update({"ativo": True, "metodo_pagamento": metodo}).eq("id", usuario_id).execute()

if 'logado' not in st.session_state:
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': ''})
    restaurar_sessao_por_token()

def fazer_logout():
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': ''})
    st.query_params.clear()

if not st.session_state['logado']:
    st.sidebar.image("logo.jpg", use_container_width=True)
    st.title("🔒 Login - Luz & Letras Sistema")

    with st.form("form_login"):
        email_login = st.text_input("E-mail")
        senha_login = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        try:
            try:
                resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, nome").eq("email", email_login).execute()
            except Exception:
                resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo").eq("email", email_login).execute()

            if resultado.data:
                usuario = resultado.data[0]
                if not usuario['ativo']:
                    st.error("Usuário bloqueado. Fale com o administrador.")
                elif usuario['senha_hash'] == senha_login:
                    nome_usuario_login = usuario.get('nome') or usuario.get('email', 'Usuário')
                    st.session_state.update({'logado': True, 'perfil': usuario['perfil'], 'empresa_id': usuario['empresa_id'], 'usuario_id': usuario['id'], 'nome_usuario': nome_usuario_login})
                    token_gerado = gerar_token_sessao(usuario['id'], usuario['senha_hash'])
                    st.query_params.update({"uid": str(usuario['id']), "tk": token_gerado})
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("E-mail não encontrado.")
        except Exception as e:
            st.error(f"Erro ao tentar logar: {e}")

    st.markdown("---")
    with st.expander("🆕 Ainda não tem conta? Criar conta"):
        st.caption("Sua conta será criada como **pendente**. Você vai precisar confirmar o e-mail e concluir o pagamento pra liberar o acesso.")
        with st.form("form_criar_conta"):
            nome_empresa_cadastro = st.text_input("Nome da sua Empresa/Negócio")
            nome_usuario_cadastro = st.text_input("Seu Nome")
            email_cadastro = st.text_input("E-mail")
            senha_cadastro = st.text_input("Senha", type="password", help="Mínimo 7 caracteres, com pelo menos 1 letra maiúscula e 1 número")
            senha_cadastro_confirma = st.text_input("Confirme a Senha", type="password")
            criar_conta_btn = st.form_submit_button("Criar Conta")

        if criar_conta_btn:
            erros_cadastro = []
            if not nome_empresa_cadastro.strip() or not nome_usuario_cadastro.strip() or not email_cadastro.strip():
                erros_cadastro.append("Preencha todos os campos.")
            if senha_cadastro != senha_cadastro_confirma:
                erros_cadastro.append("As senhas não coincidem.")
            if len(senha_cadastro) < 7:
                erros_cadastro.append("A senha precisa ter no mínimo 7 caracteres.")
            if not any(c.isupper() for c in senha_cadastro):
                erros_cadastro.append("A senha precisa ter pelo menos 1 letra maiúscula.")
            if not any(c.isdigit() for c in senha_cadastro):
                erros_cadastro.append("A senha precisa ter pelo menos 1 número.")

            if erros_cadastro:
                for erro_msg in erros_cadastro:
                    st.error(erro_msg)
            else:
                try:
                    email_existente = supabase.table("usuarios").select("id").eq("email", email_cadastro).execute()
                    if email_existente.data:
                        st.error("Já existe uma conta com esse e-mail.")
                    else:
                        plano_padrao = supabase.table("planos").select("id").order("id").limit(1).execute()
                        if not plano_padrao.data:
                            st.error("Nenhum plano cadastrado no sistema ainda. Cadastre pelo menos 1 plano na tabela 'planos' do Supabase.")
                        else:
                            plano_id_padrao = plano_padrao.data[0]['id']
                            nova_empresa = supabase.table("empresas").insert({"nome_fantasia": nome_empresa_cadastro}).execute()
                            empresa_id_criada = nova_empresa.data[0]['id']
                            hoje_cadastro = datetime.now().strftime("%Y-%m-%d")
                            supabase.table("assinaturas").insert({"empresa_id": empresa_id_criada, "plano_id": plano_id_padrao, "data_inicio": hoje_cadastro, "data_vencimento": hoje_cadastro}).execute()

                            token_confirmacao_novo = secrets.token_urlsafe(24)
                            dados_novo_usuario = {
                                "email": email_cadastro, "senha_hash": senha_cadastro, "perfil": "dono",
                                "empresa_id": empresa_id_criada, "ativo": False,
                                "nome": nome_usuario_cadastro, "email_confirmado": False,
                                "token_confirmacao": token_confirmacao_novo
                            }
                            try:
                                novo_usuario_criado = supabase.table("usuarios").insert(dados_novo_usuario).execute()
                            except Exception:
                                novo_usuario_criado = supabase.table("usuarios").insert({
                                    "email": email_cadastro, "senha_hash": senha_cadastro, "perfil": "dono",
                                    "empresa_id": empresa_id_criada, "ativo": False
                                }).execute()
                            enviar_email_confirmacao(email_cadastro, nome_usuario_cadastro, token_confirmacao_novo)
                            st.success("📧 Conta criada! Enviamos um e-mail de confirmação para você.")
                except Exception as e:
                    st.error(f"Erro ao criar conta: {e}")

    if st.session_state.get('conta_criada_id'):
        st.markdown("---")
        st.subheader("💳 Finalizar Pagamento da Assinatura")
        st.caption(f"Conta: **{st.session_state['conta_criada_email']}** — Valor: **R$ {VALOR_ASSINATURA_MENSAL:.2f}/mês**")

        metodo_escolhido = st.radio("Como você quer pagar?", ["📱 Pix (Mercado Pago)", "💳 Cartão de Crédito (Mercado Pago)", "🤝 Vou pagar em mãos"], key="metodo_pagamento_radio")

        if metodo_escolhido.startswith("🤝"):
            comprovante_pagamento = st.text_area("Descreva o comprovante do pagamento")
            if st.button("📤 Enviar Comprovante e Aguardar Confirmação"):
                if not comprovante_pagamento.strip():
                    st.warning("Descreva o comprovante antes de enviar.")
                else:
                    try:
                        try:
                            supabase.table("usuarios").update({"metodo_pagamento": "manual", "comprovante_pagamento": comprovante_pagamento}).eq("id", st.session_state['conta_criada_id']).execute()
                        except Exception:
                            supabase.table("usuarios").update({"metodo_pagamento": "manual"}).eq("id", st.session_state['conta_criada_id']).execute()
                        st.success("✅ Comprovante enviado! Assim que o administrador confirmar, sua conta será liberada.")
                        del st.session_state['conta_criada_id']
                        del st.session_state['conta_criada_email']
                        del st.session_state['conta_criada_nome']
                    except Exception as e:
                        st.error(f"Erro ao registrar: {e}")
        else:
            metodo_codigo = "pix" if metodo_escolhido.startswith("📱") else "cartao"
            if st.button("Gerar Link de Pagamento"):
                try:
                    preferencia = criar_preferencia_pagamento_mp(st.session_state['conta_criada_id'], st.session_state['conta_criada_email'], "Assinatura Mensal - Luz & Letras Sistema")
                    st.session_state['link_pagamento_mp'] = preferencia.get('init_point')
                    supabase.table("usuarios").update({"metodo_pagamento": metodo_codigo}).eq("id", st.session_state['conta_criada_id']).execute()
                except Exception as e:
                    st.error(f"Erro ao gerar o link: {e}")

            if st.session_state.get('link_pagamento_mp'):
                st.link_button("🔗 Ir para o Pagamento", st.session_state['link_pagamento_mp'])
                if st.button("🔄 Já paguei, verificar agora"):
                    if verificar_pagamento_mp(st.session_state['conta_criada_id']):
                        ativar_conta_apos_pagamento(st.session_state['conta_criada_id'], metodo_codigo)
                        st.success("✅ Pagamento confirmado! Sua conta já está ativa.")
                        del st.session_state['conta_criada_id']
                        del st.session_state['conta_criada_email']
                        del st.session_state['conta_criada_nome']
                        if 'link_pagamento_mp' in st.session_state:
                            del st.session_state['link_pagamento_mp']
                    else:
                        st.warning("Ainda não identificamos o pagamento. Aguarde alguns segundos e tente novamente.")

# ==========================================
# 4. ÁREA LOGADA (SISTEMA COMPLETO)
# ==========================================
else:
    check_user = supabase.table("usuarios").select("ativo").eq("id", st.session_state['usuario_id']).execute()
    if check_user.data and not check_user.data[0]['ativo']:
        st.error("Sua sessão foi desconectada pelo Administrador.")
        fazer_logout()
        st.rerun()

    st.sidebar.image("logo.jpg", use_container_width=True)
    st.sidebar.button("Sair / Desconectar", on_click=fazer_logout) 
    st.sidebar.markdown("---")

    if st.session_state['perfil'] == 'admin_geral':
        opcoes_menu = ["👑 Gestão de Assinantes", "📊 Dashboard", "📅 Agendamento", "📦 Estoque", "🛒 Compras", "💰 Faturamento"]
    else:
        opcoes_menu = ["📊 Dashboard", "📅 Agendamento", "📦 Estoque", "🛒 Compras", "💰 Faturamento"]

    menu = st.sidebar.radio("Módulos do Sistema", opcoes_menu)
    emp_id = st.session_state.get('empresa_id')

    if not emp_id:
        st.stop()

    def safe_json_load(val):
        if val and isinstance(val, str) and val.startswith('{'):
            try: return json.loads(val)
            except: return None
        return None

    def formatar_telefone_br(numero):
        if not numero: return numero
        apenas_digitos = "".join(c for c in numero if c.isdigit())
        if len(apenas_digitos) < 10: return numero
        ddd = apenas_digitos[:2]
        resto = apenas_digitos[2:]
        if len(resto) >= 9: return f"({ddd}) {resto[:5]}-{resto[5:]}"
        else: return f"({ddd}) {resto[:4]}-{resto[4:]}"

    def gerar_recibo_evento_pdf(evento_dict, itens_lista, dict_produtos_ref, nome_cliente_pdf, contato_cliente_pdf, nome_usuario_confirmou):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=2 * cm, rightMargin=2 * cm)
        styles = getSampleStyleSheet()
        story = []
        try:
            import os as _os
            caminho_logo_pdf = "logo_sem_fundo.png" if _os.path.exists("logo_sem_fundo.png") else "logo.jpg"
            logo_img = RLImage(caminho_logo_pdf, width=6 * cm, height=3 * cm, preserveAspectRatio=True)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 12))
        except: pass

        titulo_style = ParagraphStyle('TituloRecibo', parent=styles['Title'], fontSize=18, alignment=TA_CENTER, spaceAfter=6)
        story.append(Paragraph("RECIBO DE CONFIRMAÇÃO DO EVENTO", titulo_style))
        story.append(Spacer(1, 16))

        def _fmt_data_pdf(data_iso):
            if not data_iso or data_iso == "-": return "-"
            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            except: return data_iso

        data_ini_pdf = _fmt_data_pdf(evento_dict.get('data_inicio'))
        data_fim_pdf = _fmt_data_pdf(evento_dict.get('data_fim_alocacao'))
        valor_pdf = float(evento_dict.get('valor_total') or 0)

        dados_texto = f"""<b>Evento:</b> {evento_dict.get('descricao', '-')}<br/><b>Cliente:</b> {nome_cliente_pdf}<br/><b>Contato:</b> {contato_cliente_pdf}<br/><b>Data do Evento:</b> {data_ini_pdf} a {data_fim_pdf}<br/><b>Local/Observações:</b> {evento_dict.get('observacao', '-')}<br/><b>Valor Cobrado:</b> {formatar_moeda(valor_pdf)}<br/><b>Status:</b> {evento_dict.get('status', '-')}<br/>"""
        story.append(Paragraph(dados_texto, styles['Normal']))
        story.append(Spacer(1, 18))
        story.append(Paragraph("<b>Produtos Alocados para este Evento:</b>", styles['Heading3']))
        story.append(Spacer(1, 6))

        tabela_dados = [["Produto", "Quantidade", "Detalhes"]]
        if itens_lista:
            for it in itens_lista:
                nome_prod_pdf = dict_produtos_ref.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                detalhe_pdf = it.get('observacao') or "-"
                tabela_dados.append([nome_prod_pdf, str(it['quantidade']), detalhe_pdf])
        else: tabela_dados.append(["Nenhum item alocado", "-", "-"])

        tabela_pdf = Table(tabela_dados, colWidths=[6 * cm, 3 * cm, 7 * cm])
        tabela_pdf.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#FFC107")),('TEXTCOLOR', (0, 0), (-1, 0), colors.black),('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),('GRID', (0, 0), (-1, -1), 0.5, colors.grey),('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),('FONTSIZE', (0, 0), (-1, -1), 9)]))
        story.append(tabela_pdf)
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"Evento confirmado por: <b>{nome_usuario_confirmou}</b>", styles['Normal']))
        story.append(Paragraph(f"Data de emissão: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        return buffer

    def prever_icone(nome):
        n = nome.lower()
        if any(x in n for x in ['cadeira', 'poltrona', 'sofa', 'sofá', 'puff', 'banco']): return '🪑'
        if any(x in n for x in ['mesa', 'prato', 'copo', 'taça', 'talher']): return '🍽️'
        if any(x in n for x in ['som', 'caixa', 'audio', 'dj', 'microfone']): return '🔊'
        if any(x in n for x in ['luz', 'ilumina', 'led', 'refletor', 'canhão']): return '💡'
        if any(x in n for x in ['painel', 'fundo', 'cenario']): return '🖼️'
        if any(x in n for x in ['flor', 'arranjo', 'vaso']): return '💐'
        return '📦'

    def status_cor(qtd):
        if qtd > 50: return '🟢 Seguro'
        elif qtd >= 10: return '🟡 Atenção'
        else: return '🔴 Crítico'

    def definir_categoria(nome):
        n = nome.upper()
        if "LETRA" in n: return "🔠 LETRAS ILUMINADAS"
        if "NÚMERO" in n or "NUMERO" in n: return "🔢 NÚMEROS ILUMINADOS"
        if any(x in n for x in ['MESA', 'CADEIRA', 'POLTRONA', 'SOFÁ', 'PUFF', 'BANCO']): return "🪑 MOBÍLIA E MÓVEIS"
        if any(x in n for x in ['SOM', 'CAIXA', 'MICROFONE', 'DJ']): return "🔊 EQUIPAMENTOS DE SOM"
        if any(x in n for x in ['LUZ', 'REFLETOR', 'LED']): return "💡 ILUMINAÇÃO"
        return "📦 OUTROS ITENS GERAIS"

    def calcular_disponibilidade_periodo(data_ini_periodo, data_fim_periodo, evento_id_excluir=None):
        qtd_alugada = {}
        detalhe_alugado = {}
        eventos_check = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        eventos_no_periodo = []
        if eventos_check.data:
            for ev_c in eventos_check.data:
                if evento_id_excluir and ev_c['id'] == evento_id_excluir: continue
                if not ev_c.get('data_inicio') or not ev_c.get('data_fim_alocacao'): continue
                ev_inicio_c = datetime.strptime(ev_c['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                ev_fim_c = datetime.strptime(ev_c['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                if (ev_inicio_c <= data_fim_periodo) and (ev_fim_c >= data_ini_periodo):
                    eventos_no_periodo.append(ev_c['id'])
        if eventos_no_periodo:
            itens_check = supabase.table("itens_evento").select("produto_id, quantidade, observacao").in_("evento_id", eventos_no_periodo).execute()
            if itens_check.data:
                for item_c in itens_check.data:
                    pid_c = item_c['produto_id']
                    qtd_alugada[pid_c] = qtd_alugada.get(pid_c, 0) + item_c['quantidade']
                    js_item_c = safe_json_load(item_c['observacao'])
                    if js_item_c:
                        if pid_c not in detalhe_alugado: detalhe_alugado[pid_c] = {}
                        for k_c, v_c in js_item_c.items():
                            detalhe_alugado[pid_c][k_c] = detalhe_alugado[pid_c].get(k_c, 0) + v_c
        return qtd_alugada, detalhe_alugado


    if menu == "👑 Gestão de Assinantes":
        st.title("Painel Master")
        try:
            users = supabase.table("usuarios").select("id, email, ativo, senha_hash, nome, email_confirmado, metodo_pagamento, comprovante_pagamento, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()
        except:
            users = supabase.table("usuarios").select("id, email, ativo, senha_hash, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()

        if users.data:
            for u in users.data:
                assinatura = supabase.table("assinaturas").select("data_inicio, data_vencimento").eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                venc = assinatura.data[0]['data_vencimento'].split("T")[0] if assinatura.data else "Sem Assinatura"
                nome_fantasia = u['empresas']['nome_fantasia'] if u['empresas'] else "Sem Empresa"
                email_confirmado_u = u.get('email_confirmado', False)
                metodo_pag_u = u.get('metodo_pagamento')
                comprovante_u = u.get('comprovante_pagamento')
                nome_u = u.get('nome') or u['email']
                icone_email = "✅" if email_confirmado_u else "❌"
                aguardando_manual = (metodo_pag_u == "manual") and (not u['ativo'])

                titulo_expander = f"🏢 {nome_fantasia} - {nome_u} ({u['email']}) | Validade: {venc} | E-mail: {icone_email}"
                if aguardando_manual: titulo_expander = "🔔 " + titulo_expander + " | ⏳ Aguardando confirmação manual"

                with st.expander(titulo_expander):
                    if aguardando_manual:
                        st.warning("⏳ Esta pessoa escolheu pagar em mãos e aguarda confirmação.")
                        if comprovante_u: st.info(f"📎 Comprovante: {comprovante_u}")
                        if st.button("✅ Confirmar Pagamento Recebido", key=f"conf_manual_{u['id']}"):
                            ativar_conta_apos_pagamento(u['id'], "manual")
                            st.success("Conta ativada com sucesso!")
                            time.sleep(1.5)
                            st.rerun()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"Status Atual: **{'Ativo' if u['ativo'] else 'Bloqueado'}**")
                        if st.button("Bloq/Desbloq", key=f"blk_{u['id']}"):
                            supabase.table("usuarios").update({"ativo": not u['ativo']}).eq("id", u['id']).execute()
                            st.rerun()
                    with col2:
                        nova_senha = st.text_input("Nova Senha", key=f"pwd_{u['id']}")
                        if st.button("Mudar Senha", key=f"btn_pwd_{u['id']}") and nova_senha:
                            supabase.table("usuarios").update({"senha_hash": nova_senha}).eq("id", u['id']).execute()
                            st.success("Senha alterada!")
                    with col3:
                        meses_add = st.number_input("Estender plano (meses)", min_value=1, key=f"mes_{u['id']}", value=1)
                        if st.button("Renovar", key=f"ren_{u['id']}"):
                            novo_venc = datetime.strptime(venc, "%Y-%m-%d") + relativedelta(months=meses_add)
                            supabase.table("assinaturas").update({"data_vencimento": novo_venc.strftime("%Y-%m-%d")}).eq("empresa_id", u['empresa_id']).execute()
                            st.rerun()
        else: st.info("Nenhuma empresa comprou o sistema ainda.")

    elif menu == "📊 Dashboard":
        st.title("Dashboard e Gráficos")
        nome_exibicao = st.session_state.get('nome_usuario') or "Usuário"
        st.markdown(f"### 👋 Bem-vindo, {nome_exibicao}!")
        col_grafico1, col_grafico2 = st.columns(2)
        with col_grafico1:
            st.subheader("Receitas vs Despesas")
            faturamento = supabase.table("faturamento").select("tipo, valor").eq("empresa_id", emp_id).execute()
            if faturamento.data: st.bar_chart(pd.DataFrame(faturamento.data).groupby("tipo")["valor"].sum(), color="#FFC107")
            else: st.write("Sem dados.")
        with col_grafico2:
            st.subheader("Status dos Eventos")
            eventos = supabase.table("eventos").select("status").eq("empresa_id", emp_id).execute()
            if eventos.data:
                status_counts = pd.DataFrame(eventos.data)["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                mapa_cores_status = {"Concluído": "#1B5E20", "Agendado": "#FFC107", "Cancelado": "#D32F2F", "Em Andamento": "#66BB6A"}
                fig_status = px.bar(status_counts, x="Status", y="Quantidade", color="Status", color_discrete_map=mapa_cores_status, text="Quantidade")
                fig_status.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_status, use_container_width=True)
            else: st.write("Sem dados.")

    elif menu == "📅 Agendamento":
        st.title("Agendamento e Locação de Itens")
        produtos_disp = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao").eq("empresa_id", emp_id).execute()
        dict_produtos = {p['id']: p for p in produtos_disp.data} if produtos_disp.data else {}

        st.markdown("---")
        st.subheader("📋 Eventos Já Cadastrados")
        eventos_cadastrados = supabase.table("eventos").select("*").eq("empresa_id", emp_id).order("data_inicio", desc=True).execute()

        if eventos_cadastrados.data:
            try: clientes_resultado = supabase.table("clientes_eventos").select("id, nome, contato").eq("empresa_id", emp_id).execute()
            except: clientes_resultado = supabase.table("clientes_eventos").select("id, nome").eq("empresa_id", emp_id).execute()
            mapa_clientes = {c['id']: c for c in clientes_resultado.data} if clientes_resultado.data else {}

            for ev in eventos_cadastrados.data:
                cliente_info = mapa_clientes.get(ev.get('cliente_id'), {})
                nome_cliente_ev = cliente_info.get('nome', "Cliente não informado")
                contato_cliente_ev = cliente_info.get('contato') or "-"
                titulo_ev = ev.get('descricao') or "Evento sem título"
                data_ini_fmt = ev['data_inicio'].split("T")[0] if ev.get('data_inicio') else "-"
                data_fim_fmt = ev['data_fim_alocacao'].split("T")[0] if ev.get('data_fim_alocacao') else "-"

                def _fmt_br(data_iso):
                    if not data_iso or data_iso == "-": return "-"
                    try: return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except: return data_iso

                data_ini_br = _fmt_br(data_ini_fmt)
                data_fim_br = _fmt_br(data_fim_fmt)
                status_ev = ev.get('status') or "-"

                with st.expander(f"🎉 {titulo_ev} — {nome_cliente_ev} | {data_ini_br} até {data_fim_br} | Status: {status_ev}"):
                    itens_ev = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao").eq("evento_id", ev['id']).execute()
                    tab_detalhes, tab_add, tab_rem, tab_editar, tab_hist = st.tabs(["📋 Detalhes & Recibo", "➕ Adicionar Itens", "➖ Remover Itens", "✏️ Editar Evento", "🕒 Histórico"])

                    with tab_detalhes:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            valor_ev = float(ev.get('valor_total') or 0)
                            st.write(f"**Data do Evento:** {data_ini_br} até {data_fim_br}")
                            st.write(f"**Valor:** {formatar_moeda(valor_ev)}")
                            st.write(f"**Contato do Cliente:** {contato_cliente_ev}")
                            st.write(f"**Observações:** {ev.get('observacao') or '-'}")
                        with col_b:
                            opcoes_status = ["Agendado", "Em Andamento", "Concluído", "Cancelado"]
                            idx_status = opcoes_status.index(status_ev) if status_ev in opcoes_status else 0
                            novo_status = st.selectbox("Alterar Status", opcoes_status, index=idx_status, key=f"status_ev_{ev['id']}")
                            if st.button("Atualizar Status", key=f"btn_status_ev_{ev['id']}"):
                                supabase.table("eventos").update({"status": novo_status}).eq("id", ev['id']).execute()
                                st.success("🎉 STATUS ATUALIZADO COM SUCESSO!")
                                time.sleep(1.5)
                                st.rerun()
                        if itens_ev.data:
                            st.markdown("**Itens Alocados:**")
                            for it in itens_ev.data:
                                nome_prod = dict_produtos.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                                detalhe = f" ({it['observacao']})" if it.get('observacao') else ""
                                st.write(f"- {it['quantidade']}x {nome_prod}{detalhe}")
                        st.markdown("---")
                        if REPORTLAB_DISPONIVEL:
                            nome_usuario_pdf = st.session_state.get('nome_usuario') or "Usuário do Sistema"
                            buffer_pdf = gerar_recibo_evento_pdf(ev, itens_ev.data or [], dict_produtos, nome_cliente_ev, contato_cliente_ev, nome_usuario_pdf)
                            st.download_button("📄 Baixar Recibo de Confirmação (PDF)", data=buffer_pdf, file_name=f"recibo_evento_{ev['id']}.pdf", mime="application/pdf", key=f"recibo_pdf_{ev['id']}")
                    
                    with tab_add:
                        produtos_disp_edit = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao").eq("empresa_id", emp_id).execute()
                        adicoes_selecionadas = {}
                        ev_data_inicio_add = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_inicio') else datetime.now().date()
                        ev_data_fim_add = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_fim_alocacao') else ev_data_inicio_add
                        qtd_alugada_add, detalhe_alugado_add = calcular_disponibilidade_periodo(ev_data_inicio_add, ev_data_fim_add, evento_id_excluir=ev['id'])
                        
                        if produtos_disp_edit.data:
                            for p in produtos_disp_edit.data:
                                js_p = safe_json_load(p.get('observacao'))
                                if js_p:
                                    ja_alugado_kit = detalhe_alugado_add.get(p['id'], {})
                                    if any((max_v - ja_alugado_kit.get(k, 0)) > 0 for k, max_v in js_p.items()):
                                        st.markdown(f"🔠 *{p['nome']}:*")
                                        cols_add = st.columns(6)
                                        idxp = 0
                                        for k, max_v in js_p.items():
                                            disp_k = max(0, max_v - ja_alugado_kit.get(k, 0))
                                            if disp_k > 0:
                                                val_add = cols_add[idxp % 6].number_input(f"{k} (Disp:{disp_k})", min_value=0, max_value=disp_k, value=None, key=f"add_{ev['id']}_{p['id']}_{k}")
                                                if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_{k}"] = val_add
                                                idxp += 1
                                else:
                                    disp_normal = max(0, p['quantidade_estoque'] - qtd_alugada_add.get(p['id'], 0))
                                    if disp_normal > 0:
                                        val_add = st.number_input(f"{p['nome']} (Disp: {disp_normal})", min_value=0, max_value=disp_normal, value=None, key=f"add_{ev['id']}_{p['id']}_NORMAL")
                                        if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_NORMAL"] = val_add

                        motivo_alteracao = st.text_input("Motivo da Alteração", key=f"motivo_{ev['id']}")
                        if st.button("💾 Registrar Alteração", key=f"btn_add_{ev['id']}"):
                            if not adicoes_selecionadas: st.warning("Selecione ao menos 1 item.")
                            elif not motivo_alteracao.strip(): st.warning("Informe o motivo.")
                            else:
                                try:
                                    agrupado = {}
                                    for key, qtd in adicoes_selecionadas.items():
                                        p_id_str, sub = key.split("_", 1)
                                        if int(p_id_str) not in agrupado: agrupado[int(p_id_str)] = {'total': 0, 'detalhes': {}}
                                        agrupado[int(p_id_str)]['total'] += qtd
                                        if sub != "NORMAL": agrupado[int(p_id_str)]['detalhes'][sub] = qtd
                                    
                                    data_hora_alt = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    resumo_itens = []
                                    for p_id, info in agrupado.items():
                                        qtd_total = info['total']
                                        obs_json_add = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                        item_existente = supabase.table("itens_evento").select("id, quantidade, observacao").eq("evento_id", ev['id']).eq("produto_id", p_id).execute()

                                        if item_existente.data:
                                            item_atual = item_existente.data[0]
                                            nova_qtd_item = item_atual['quantidade'] + qtd_total
                                            obs_atual_item = safe_json_load(item_atual.get('observacao'))
                                            if obs_atual_item and info['detalhes']:
                                                for k, v in info['detalhes'].items():
                                                    obs_atual_item[k] = obs_atual_item.get(k, 0) + v
                                                nova_obs_item = json.dumps(obs_atual_item)
                                            elif info['detalhes']:
                                                nova_obs_item = obs_json_add
                                            else:
                                                nova_obs_item = item_atual.get('observacao', '')
                                            supabase.table("itens_evento").update({"quantidade": nova_qtd_item, "observacao": nova_obs_item}).eq("id", item_atual['id']).execute()
                                        else:
                                            supabase.table("itens_evento").insert({"empresa_id": emp_id, "evento_id": ev['id'], "produto_id": p_id, "quantidade": qtd_total, "observacao": obs_json_add}).execute()
                                        resumo_itens.append(f"{qtd_total}x Produto {p_id}")

                                    texto_hist_alt = f"✏️ ALTERAÇÃO: Adicionou {', '.join(resumo_itens)}. Motivo: {motivo_alteracao}"
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev['id'], "descricao": texto_hist_alt, "data_registro": data_hora_alt}).execute()

                                    st.success("🎉 ADIÇÃO CONCLUÍDA COM SUCESSO!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e: st.error(f"Erro: {e}")

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
                                            val_rem = cols_rem[idxr % 6].number_input(f"{k} (Aloc:{qtd_alocada})", min_value=0, max_value=qtd_alocada, value=None, key=f"rem_{ev['id']}_{it['id']}_{k}")
                                            if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_{k}"] = val_rem
                                            idxr += 1
                                else:
                                    val_rem = st.number_input(f"{nome_prod_it} (Aloc: {it['quantidade']})", min_value=0, max_value=it['quantidade'], value=None, key=f"rem_{ev['id']}_{it['id']}_NORMAL")
                                    if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_NORMAL"] = val_rem

                            motivo_remocao = st.text_input("Motivo da Remoção", key=f"motivo_rem_{ev['id']}")
                            if st.button("🗑️ Registrar Remoção", key=f"btn_rem_{ev['id']}"):
                                if not remocoes_selecionadas: st.warning("Selecione algo.")
                                elif not motivo_remocao.strip(): st.warning("Informe o motivo.")
                                else:
                                    data_hora_rem = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    dict_itens_ev = {it['id']: it for it in itens_ev.data}
                                    resumo_remocao = []
                                    agrupado_rem = {}
                                    for key, qtd in remocoes_selecionadas.items():
                                        item_id_str, p_id_str, sub = key.split("_", 2)
                                        item_id = int(item_id_str)
                                        if item_id not in agrupado_rem: agrupado_rem[item_id] = {'produto_id': int(p_id_str), 'total': 0, 'detalhes': {}}
                                        agrupado_rem[item_id]['total'] += qtd
                                        if sub != "NORMAL": agrupado_rem[item_id]['detalhes'][sub] = qtd

                                    for item_id, info_rem in agrupado_rem.items():
                                        item_atual_rem = dict_itens_ev[item_id]
                                        qtd_remover = info_rem['total']
                                        nova_qtd_item_rem = item_atual_rem['quantidade'] - qtd_remover
                                        obs_item_atual = safe_json_load(item_atual_rem.get('observacao'))
                                        if obs_item_atual and info_rem['detalhes']:
                                            for k, v in info_rem['detalhes'].items(): obs_item_atual[k] = max(0, obs_item_atual.get(k, 0) - v)
                                            nova_obs_item_rem = json.dumps(obs_item_atual)
                                        else: nova_obs_item_rem = item_atual_rem.get('observacao', '')

                                        if nova_qtd_item_rem <= 0: supabase.table("itens_evento").delete().eq("id", item_id).execute()
                                        else: supabase.table("itens_evento").update({"quantidade": nova_qtd_item_rem, "observacao": nova_obs_item_rem}).eq("id", item_id).execute()
                                        resumo_remocao.append(f"{qtd_remover}x Removidos")

                                    texto_hist_rem = f"🔻 REMOÇÃO: Retirou {', '.join(resumo_remocao)}. Motivo: {motivo_remocao}"
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev['id'], "descricao": texto_hist_rem, "data_registro": data_hora_rem}).execute()
                                    st.success("🎉 REMOÇÃO CONCLUÍDA COM SUCESSO!")
                                    time.sleep(1.5)
                                    st.rerun()
                        else: st.caption("Nenhum item alocado.")

                    with tab_editar:
                        def _parse_data_edit(data_iso):
                            if not data_iso: return datetime.now().date()
                            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").date()
                            except: return datetime.now().date()
                        col_ed1, col_ed2 = st.columns(2)
                        with col_ed1: nova_data_inicio_edit = st.date_input("Data de Início", value=_parse_data_edit(ev.get('data_inicio')), format="DD/MM/YYYY", key=f"edit_data_ini_{ev['id']}")
                        with col_ed2: nova_data_fim_edit = st.date_input("Data Fim", value=_parse_data_edit(ev.get('data_fim_alocacao')), format="DD/MM/YYYY", key=f"edit_data_fim_{ev['id']}")
                        
                        novo_valor_edit = st.number_input("Valor Cobrado (R$)", min_value=0.0, step=50.0, value=float(ev.get('valor_total') or 0), format="%.2f", key=f"edit_valor_{ev['id']}")
                        novo_local_edit = st.text_area("Local/Observações", value=ev.get('observacao') or "", key=f"edit_local_{ev['id']}")
                        col_ec1, col_ec2 = st.columns(2)
                        with col_ec1: novo_nome_cliente_edit = st.text_input("Nome do Cliente", value=nome_cliente_ev, key=f"edit_nome_cli_{ev['id']}")
                        with col_ec2: novo_contato_cliente_edit = st.text_input("Contato do Cliente", value=contato_cliente_ev if contato_cliente_ev != "-" else "", key=f"edit_contato_cli_{ev['id']}")
                        justificativa_edit = st.text_input("Justificativa (obrigatório)", key=f"edit_just_{ev['id']}")

                        if st.button("💾 Salvar Alterações", key=f"btn_edit_evento_{ev['id']}"):
                            if not justificativa_edit.strip(): st.warning("Informe a justificativa.")
                            else:
                                supabase.table("eventos").update({"data_inicio": str(nova_data_inicio_edit), "data_fim_alocacao": str(nova_data_fim_edit), "valor_total": novo_valor_edit, "observacao": novo_local_edit}).eq("id", ev['id']).execute()
                                if ev.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": novo_nome_cliente_edit, "contato": novo_contato_cliente_edit}).eq("id", ev['cliente_id']).execute()
                                data_hora_edit = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev['id'], "descricao": f"✏️ EDIÇÃO DE DADOS. Justificativa: {justificativa_edit}", "data_registro": data_hora_edit}).execute()
                                st.success("🎉 EDIÇÃO CONCLUÍDA COM SUCESSO!")
                                time.sleep(1.5)
                                st.rerun()

                    with tab_hist:
                        historico_ev = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev['id']).order("data_registro", desc=True).execute()
                        if historico_ev.data:
                            for h in historico_ev.data: st.write(f"🕒 **{h['data_registro']}** — {h['descricao']}")

        st.markdown("---")
        with st.expander("📝 Cadastrar Novo Evento", expanded=False):
            st.markdown("**🗓️ Primeiro, escolha as datas do evento:**")
            col_data1, col_data2 = st.columns(2)
            with col_data1: data_inicio = st.date_input("Data de Início do Evento", format="DD/MM/YYYY", key="novo_evento_data_inicio")
            with col_data2: data_fim = st.date_input("Até quando os produtos ficam alocados? (Data Fim)", format="DD/MM/YYYY", value=data_inicio, key="novo_evento_data_fim")

            qtd_alugada_form, detalhe_alugado_form = calcular_disponibilidade_periodo(data_inicio, data_fim)

            with st.form("form_evento"):
                col_1, col_2, col_3, col_3b = st.columns(4)
                with col_1: nome_evento = st.text_input("Título do Evento (Ex: Casamento)")
                with col_2: nome_cliente = st.text_input("Nome do Cliente (Contratante)") 
                with col_3: contato_cliente = st.text_input("Contato (Telefone/WhatsApp)", placeholder="(84) 99999-9999")
                with col_3b: status_evento = st.selectbox("Status", ["Agendado", "Em Andamento", "Concluído", "Cancelado"])

                st.info(f"📅 Datas selecionadas: **{data_inicio.strftime('%d/%m/%Y')}** até **{data_fim.strftime('%d/%m/%Y')}**")
                valor_evento = st.number_input("Valor Cobrado pelo Evento (R$)", min_value=0.0, step=50.0, value=None, format="%.2f")

                st.markdown("**📍 Localização do Evento**")
                col_7, col_8, col_9, col_10 = st.columns([2, 2, 1.5, 0.5])
                with col_7: local_evento = st.text_input("Local do Evento (Ex: Salão Splendor)")
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
                                            qtd_item = cols_k[idx%10].number_input(f"{k} (Livre:{max(0, disponivel_k)})", min_value=0, max_value=max(0, disponivel_k), value=None, key=f"aloc_{prod['id']}_{k}")
                                            quantidades_selecionadas[f"{prod['id']}_{k}"] = qtd_item or 0
                                            idx += 1
                                    st.markdown("---")
                                else:
                                    with colunas[index % 3]:
                                        disponivel_normal = max(0, prod['quantidade_estoque'] - qtd_alugada_form.get(prod['id'], 0))
                                        qtd_item_normal = st.number_input(f"{prod['nome']} (Livre: {disponivel_normal})", min_value=0, max_value=disponivel_normal, value=None, key=f"form_prod_{prod['id']}")
                                        quantidades_selecionadas[f"{prod['id']}_NORMAL"] = qtd_item_normal or 0

                if st.form_submit_button("Salvar Evento e Alocar Itens"):
                    if not nome_evento or not nome_cliente or not contato_cliente or not local_evento or not rua_evento or not bairro_evento or not numero_evento or valor_evento is None:
                        st.error("⚠️ Por favor, preencha todos os campos obrigatórios. Apenas 'Observações Gerais' é opcional.")
                    else:
                        alocacoes_agrupadas = {}
                        for key, qtd in quantidades_selecionadas.items():
                            if qtd > 0:
                                p_id_str, sub_item = key.split("_", 1)
                                if int(p_id_str) not in alocacoes_agrupadas: alocacoes_agrupadas[int(p_id_str)] = {'total': 0, 'detalhes': {}}
                                alocacoes_agrupadas[int(p_id_str)]['total'] += qtd
                                if sub_item != "NORMAL": alocacoes_agrupadas[int(p_id_str)]['detalhes'][sub_item] = qtd

                        try:
                            contato_cliente_formatado = formatar_telefone_br(contato_cliente)
                            novo_cliente = supabase.table("clientes_eventos").insert({"empresa_id": emp_id, "nome": nome_cliente, "contato": contato_cliente_formatado}).execute()
                            cliente_id_gerado = novo_cliente.data[0]['id']
                            
                            novo_evento = supabase.table("eventos").insert({
                                "empresa_id": emp_id, "cliente_id": cliente_id_gerado, "titulo": nome_evento,
                                "descricao": nome_evento, "data_inicio": str(data_inicio), "data_fim_alocacao": str(data_fim), 
                                "status": status_evento, "observacao": f"Local: {local_evento} - {rua_evento}, {numero_evento} - {bairro_evento} - {obs_evento_geral}",
                                "valor_total": valor_evento
                            }).execute()
                            evento_id_gerado = novo_evento.data[0]['id']

                            data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                            for p_id, info in alocacoes_agrupadas.items():
                                obs_json_evento = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                supabase.table("itens_evento").insert({"empresa_id": emp_id, "evento_id": evento_id_gerado, "produto_id": p_id, "quantidade": info['total'], "observacao": obs_json_evento}).execute()
                                supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": evento_id_gerado, "descricao": f"🟢 ALOCAÇÃO INICIAL: Adicionou {info['total']}x Produto {p_id}.", "data_registro": data_hora}).execute()

                            st.success("🎉 CADASTRO CONCLUÍDO COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e: st.error(f"Erro: {e}")

    elif menu == "📦 Estoque":
        st.title("Controle de Estoque Inteligente")
        produtos_lista = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao").eq("empresa_id", emp_id).order("nome").execute()
        
        with st.expander("🔍 Verificar Disponibilidade Rotativa", expanded=True):
            col_d1, col_d2 = st.columns(2)
            with col_d1: data_inicio_f = st.date_input("De (Data Inicial)", format="DD/MM/YYYY")
            with col_d2: data_fim_f = st.date_input("Até (Data Final)", value=data_inicio_f, format="DD/MM/YYYY")

            if produtos_lista.data:
                df_produtos = pd.DataFrame(produtos_lista.data)
                df_produtos['Categoria'] = df_produtos['nome'].apply(definir_categoria)
                df_produtos['Ícone'] = df_produtos['nome'].apply(prever_icone)
                df_produtos['Item'] = df_produtos['Ícone'] + " " + df_produtos['nome']
                df_produtos['Estoque Total'] = df_produtos['quantidade_estoque']

                def format_obs(val):
                    js = safe_json_load(val)
                    if js: return ", ".join([f"{k}: {v}x" for k, v in js.items()])
                    return val if val else ""
                df_produtos['Detalhes/Inventário'] = df_produtos['observacao'].apply(format_obs)
                df_produtos['Status'] = df_produtos['quantidade_estoque'].apply(status_cor)

                eventos = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
                eventos_no_periodo = []
                if eventos.data:
                    for ev in eventos.data:
                        if not ev.get('data_inicio') or not ev.get('data_fim_alocacao'): continue
                        ev_inicio = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                        ev_fim = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                        if (ev_inicio <= data_fim_f) and (ev_fim >= data_inicio_f):
                            eventos_no_periodo.append(ev['id'])
                
                qtd_alugada = {}
                detalhe_alugado = {}
                if eventos_no_periodo:
                    itens = supabase.table("itens_evento").select("produto_id, quantidade, observacao").in_("evento_id", eventos_no_periodo).execute()
                    if itens.data:
                        for item in itens.data:
                            pid = item['produto_id']
                            qtd_alugada[pid] = qtd_alugada.get(pid, 0) + item['quantidade']
                            js_item = safe_json_load(item['observacao'])
                            if js_item:
                                if pid not in detalhe_alugado: detalhe_alugado[pid] = {}
                                for k, v in js_item.items(): detalhe_alugado[pid][k] = detalhe_alugado[pid].get(k, 0) + v

                def calcular_disponivel(row): return row['quantidade_estoque'] - qtd_alugada.get(row['id'], 0)
                def calc_livres_detalhe(row):
                    js_estoque = safe_json_load(row['observacao'])
                    if js_estoque:
                        alugados = detalhe_alugado.get(row['id'], {})
                        livres = []
                        for k, v in js_estoque.items():
                            restante = v - alugados.get(k, 0)
                            if restante > 0: livres.append(f"{k}: {restante}x")
                        return ", ".join(livres) if livres else "Tudo alugado"
                    return ""

                df_produtos['Reservado na Data'] = df_produtos['id'].map(lambda x: qtd_alugada.get(x, 0))
                df_produtos['Disponível Livre'] = df_produtos.apply(calcular_disponivel, axis=1)
                df_produtos['Sub-Itens Livres na Data'] = df_produtos.apply(calc_livres_detalhe, axis=1)
                colunas_mostrar = ['Item', 'Status', 'Detalhes/Inventário', 'Estoque Total', 'Reservado na Data', 'Disponível Livre', 'Sub-Itens Livres na Data']

                total_geral_estoque = int(df_produtos['Estoque Total'].sum())
                total_geral_reservado = int(df_produtos['Reservado na Data'].sum())
                total_geral_livre = int(df_produtos['Disponível Livre'].sum())

                st.markdown("#### 📊 Resumo Geral do Período Selecionado")
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("📦 Estoque Total", total_geral_estoque)
                col_m2.metric("🔒 Reservado/Locado no Período", total_geral_reservado)
                col_m3.metric("✅ Disponível no Período", total_geral_livre)
                st.markdown("---")

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
                    st.dataframe(df_cat[colunas_mostrar], use_container_width=True, hide_index=True)
                    st.markdown("---")
            else: st.info("Nenhum produto cadastrado no estoque ainda.")

        with st.expander("➕ Adicionar Novo Item ou Kit", expanded=False):
            tipo_cadastro = st.radio("O que você vai cadastrar?", ["Produto Normal", "🔠 Kit Letras (A-Z)", "🔢 Kit Números (1 a 100)"])
            with st.form("form_estoque_add"):
                if tipo_cadastro == "Produto Normal":
                    nome_prod = st.text_input("Nome do Item (Ex: CADEIRA DE FERRO)")
                    qtd_prod = st.number_input("Quantidade Total Físico", min_value=0, value=None)
                    obs_prod = st.text_input("Observação Simples (Opcional)")
                    if st.form_submit_button("Salvar Produto Normal"):
                        if nome_prod.strip():
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": (qtd_prod or 0), "observacao": obs_prod}).execute()
                            st.success("🎉 CADASTRO CONCLUÍDO COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()    
                elif tipo_cadastro == "🔠 Kit Letras (A-Z)":
                    nome_prod = st.text_input("Nome do Kit", value="LETRAS ILUMINADAS")
                    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    cols_l = st.columns(6)
                    qtd_letras = {}
                    for i, l in enumerate(letras):
                        qtd_letras[l] = cols_l[i%6].number_input(f"Letra {l}", min_value=0, value=None)
                    if st.form_submit_button("Salvar Kit Letras"):
                        total_letras = sum((v or 0) for v in qtd_letras.values())
                        if total_letras == 0: st.error("Coloque pelo menos 1 letra!")
                        else:
                            obs_json = json.dumps({k: (v or 0) for k, v in qtd_letras.items() if (v or 0) > 0})
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": total_letras, "observacao": obs_json}).execute()
                            st.success("🎉 CADASTRO CONCLUÍDO COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()
                elif tipo_cadastro == "🔢 Kit Números (1 a 100)":
                    nome_prod = st.text_input("Nome do Kit", value="NÚMEROS ILUMINADOS")
                    numeros = [str(n) for n in range(1, 101)]
                    cols_n = st.columns(10)
                    qtd_numeros = {}
                    for i, num in enumerate(numeros):
                        qtd_numeros[num] = cols_n[i%10].number_input(num, min_value=0, value=None)
                    if st.form_submit_button("Salvar Kit Números"):
                        total_numeros = sum((v or 0) for v in qtd_numeros.values())
                        if total_numeros == 0: st.error("Coloque pelo menos 1 número!")
                        else:
                            obs_json = json.dumps({k: (v or 0) for k, v in qtd_numeros.items() if (v or 0) > 0})
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": total_numeros, "observacao": obs_json}).execute()
                            st.success("🎉 CADASTRO CONCLUÍDO COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()

        with st.expander("🗑️ Excluir ou Reduzir Produto do Estoque", expanded=False):
            if produtos_lista.data:
                opcoes_produtos_excluir = {f"{p['nome']} (ID {p['id']}, Estoque: {p['quantidade_estoque']})": p['id'] for p in produtos_lista.data}
                dict_produtos_lista = {p['id']: p for p in produtos_lista.data}
                produto_escolhido_label = st.selectbox("Selecione o produto", list(opcoes_produtos_excluir.keys()), key="select_excluir_produto")
                produto_id_excluir = opcoes_produtos_excluir[produto_escolhido_label]
                produto_selecionado_info = dict_produtos_lista[produto_id_excluir]

                tipo_remocao = st.radio("O que você quer fazer?", ["Remover quantidade parcial (ex: quebrou 5 cadeiras)", "Excluir o produto inteiro do estoque"], key="radio_tipo_remocao")

                if tipo_remocao.startswith("Remover quantidade parcial"):
                    js_prod_excluir = safe_json_load(produto_selecionado_info.get('observacao'))
                    if js_prod_excluir:
                        cols_pex = st.columns(6)
                        qtds_remover_parcial = {}
                        idxpex = 0
                        for k, max_v in js_prod_excluir.items():
                            if max_v > 0:
                                val_pex = cols_pex[idxpex % 6].number_input(f"{k} (Tem: {max_v})", min_value=0, max_value=max_v, value=None, key=f"pex_{produto_id_excluir}_{k}")
                                if (val_pex or 0) > 0: qtds_remover_parcial[k] = val_pex
                                idxpex += 1
                        motivo_pex = st.text_input("Motivo da remoção", key=f"motivo_pex_{produto_id_excluir}")
                        
                        total_remover_pex = sum(qtds_remover_parcial.values())
                        if total_remover_pex > 0 and motivo_pex.strip():
                            st.warning(f"⚠️ Tem certeza que deseja remover **{total_remover_pex} peças** de **{produto_selecionado_info['nome']}** parcialmente?")
                            if st.button("✅ Sim, Confirmar Remoção", key=f"btn_pex_{produto_id_excluir}"):
                                novo_json_pex = dict(js_prod_excluir)
                                for k, v in qtds_remover_parcial.items(): novo_json_pex[k] = max(0, novo_json_pex.get(k, 0) - v)
                                supabase.table("produtos").update({"quantidade_estoque": max(0, produto_selecionado_info['quantidade_estoque'] - total_remover_pex), "observacao": json.dumps(novo_json_pex)}).eq("id", produto_id_excluir).execute()
                                st.success("🎉 REMOÇÃO PARCIAL CONCLUÍDA COM SUCESSO!")
                                time.sleep(1.5)
                                st.rerun()
                    else:
                        qtd_disponivel_pex = produto_selecionado_info['quantidade_estoque']
                        qtd_remover_normal = st.number_input(f"Quanto deseja remover de {produto_selecionado_info['nome']}? (Tem: {qtd_disponivel_pex})", min_value=0, max_value=qtd_disponivel_pex, value=None, key=f"pex_normal_{produto_id_excluir}")
                        motivo_pex_normal = st.text_input("Motivo da remoção", key=f"motivo_pex_normal_{produto_id_excluir}")
                        
                        if (qtd_remover_normal or 0) > 0 and motivo_pex_normal.strip():
                            st.warning(f"⚠️ Tem certeza que deseja remover **{qtd_remover_normal} peças** de **{produto_selecionado_info['nome']}** parcialmente?")
                            if st.button("✅ Sim, Confirmar Remoção", key=f"btn_pex_normal_{produto_id_excluir}"):
                                supabase.table("produtos").update({"quantidade_estoque": max(0, qtd_disponivel_pex - qtd_remover_normal)}).eq("id", produto_id_excluir).execute()
                                st.success("🎉 REMOÇÃO PARCIAL CONCLUÍDA COM SUCESSO!")
                                time.sleep(1.5)
                                st.rerun()

                else:
                    st.warning(f"⚠️ Tem certeza que deseja excluir **{produto_selecionado_info['nome']} COMPLETAMENTE** do estoque?")
                    if st.button("🗑️ Sim, Excluir Produto Inteiro", key="btn_excluir_produto"):
                        try:
                            itens_usando = supabase.table("itens_evento").select("id").eq("produto_id", produto_id_excluir).execute()
                            if itens_usando.data: st.error("Não é possível excluir: este produto está alocado em um evento. Remova a alocação primeiro.")
                            else:
                                supabase.table("produtos").delete().eq("id", produto_id_excluir).execute()
                                st.success("🎉 EXCLUSÃO CONCLUÍDA COM SUCESSO!")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e: st.error(f"Erro ao excluir: {e}")
            else: st.info("Nenhum produto cadastrado para excluir.")

    elif menu == "🛒 Compras":
        st.title("Controle de Compras")
        col_cp3, col_cp4 = st.columns(2)
        with col_cp3: nome_produto_compra = st.text_input("Nome do Produto", key="compra_nome_produto")
        with col_cp4: tipo_aquisicao = st.radio("Comprado onde?", ["Presencial", "Site"], horizontal=True, key="compra_tipo_aquisicao")

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
            with col_cp7: forma_pagamento_compra = st.selectbox("Forma de Pagamento", ["Não informado", "Pix", "Cartão", "Dinheiro", "Boleto", "Outro"])
            with col_cp8: numero_pedido_compra = st.text_input("Nº do Pedido / Nota Fiscal (opcional)")
            observacao_compra = st.text_area("Observação (opcional)")

            if st.form_submit_button("Registrar Compra"):
                if not nome_produto_compra.strip() or not fornecedor.strip(): st.warning("Informe o nome e a loja.")
                else:
                    qtd_calc = quantidade_compra or 0
                    vlr_calc = valor_unit_compra or 0.0
                    valor_total_calc = qtd_calc * vlr_calc

                    supabase.table("compras").insert({
                        "empresa_id": emp_id, "nome_produto": nome_produto_compra, "fornecedor": fornecedor, "tipo_aquisicao": tipo_aquisicao, "local_detalhe": fornecedor,
                        "quantidade": qtd_calc, "valor_total": valor_total_calc, "data_compra": str(data_compra_input), "data_prevista_chegada": str(data_chegada_input),
                        "status_chegada": "Aguardando", "forma_pagamento": forma_pagamento_compra, "numero_pedido": numero_pedido_compra, "observacao": observacao_compra
                    }).execute()
                    st.success("🎉 COMPRA CADASTRADA COM SUCESSO!")
                    time.sleep(1.5)
                    st.rerun()

        st.markdown("---")
        st.markdown("### 📋 Histórico de Compras")
        compras_lista = supabase.table("compras").select("*").eq("empresa_id", emp_id).order("data_compra", desc=True).execute()

        if compras_lista.data:
            df_compras = pd.DataFrame(compras_lista.data)
            df_compras['valor_unitario'] = df_compras['valor_total'] / df_compras['quantidade']
            df_compras['valor_unitario'] = df_compras['valor_unitario'].fillna(0)

            colunas_exibir_compras = [c for c in [
                "nome_produto", "quantidade", "valor_unitario", "valor_total", "fornecedor", "tipo_aquisicao",
                "forma_pagamento", "numero_pedido", "data_compra", "data_prevista_chegada", "status_chegada", "observacao"
            ] if c in df_compras.columns or c == "valor_unitario"]
            st.dataframe(df_compras[colunas_exibir_compras], use_container_width=True, hide_index=True)

            with st.expander("🔄 Atualizar Status de Chegada", expanded=False):
                pendentes = df_compras[df_compras['status_chegada'] != 'Chegou'] if 'status_chegada' in df_compras.columns else df_compras
                if len(pendentes) > 0:
                    opcoes_pend = {
                        f"{r['nome_produto']} — {r.get('fornecedor','')} (Previsão: {r.get('data_prevista_chegada','-')})": r['id']
                        for _, r in pendentes.iterrows()
                    }
                    escolha_pend = st.selectbox("Selecione o item que chegou", list(opcoes_pend.keys()), key="select_compra_chegou")
                    if st.button("✅ Marcar como Chegou", key="btn_marcar_chegou"):
                        supabase.table("compras").update({"status_chegada": "Chegou"}).eq("id", opcoes_pend[escolha_pend]).execute()
                        st.success("📦 ITEM MARCADO COMO CHEGOU!")
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.caption("Nenhuma compra pendente de chegada.")

            # ========================================================
            # NOVA ÁREA: EDITAR OU EXCLUIR COMPRAS
            # ========================================================
            with st.expander("✏️ Editar ou Excluir uma Compra", expanded=False):
                opcoes_edit_compra = {
                    f"{r.get('data_compra', '')} — {r.get('nome_produto', 'Produto')} (R$ {float(r.get('valor_total', 0)):.2f})": r['id']
                    for _, r in df_compras.iterrows()
                }
                escolha_compra_txt = st.selectbox("Selecione a compra para editar", list(opcoes_edit_compra.keys()), key="select_editar_compra")
                compra_id_sel = opcoes_edit_compra[escolha_compra_txt]
                comp_sel = next(c for c in compras_lista.data if c['id'] == compra_id_sel)

                col_ec1, col_ec2 = st.columns(2)
                with col_ec1: edit_nome_c = st.text_input("Nome do Produto", value=comp_sel.get('nome_produto', ''), key="ed_nome_c")
                with col_ec2: edit_loja_c = st.text_input("Loja/Site", value=comp_sel.get('fornecedor', ''), key="ed_loja_c")

                col_ec3, col_ec4, col_ec5 = st.columns(3)
                with col_ec3: edit_qtd_c = st.number_input("Quantidade", min_value=1, value=int(comp_sel.get('quantidade') or 1), key="ed_qtd_c")
                with col_ec4:
                    q_atual = int(comp_sel.get('quantidade') or 1)
                    v_tot_atual = float(comp_sel.get('valor_total') or 0)
                    v_unit_atual = v_tot_atual / q_atual if q_atual > 0 else 0.0
                    edit_vunit_c = st.number_input("Valor Unitário (R$)", min_value=0.0, value=v_unit_atual, format="%.2f", key="ed_vunit_c")
                with col_ec5: 
                    tipos_aq = ["Presencial", "Site"]
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
                    formas_pg = ["Não informado", "Pix", "Cartão", "Dinheiro", "Boleto", "Outro"]
                    idx_pg = formas_pg.index(comp_sel.get('forma_pagamento')) if comp_sel.get('forma_pagamento') in formas_pg else 0
                    edit_forma_pg = st.selectbox("Forma de Pagamento", formas_pg, index=idx_pg, key="ed_forma_pg")
                with col_ec9: edit_num_ped = st.text_input("Nº Pedido", value=comp_sel.get('numero_pedido') or "", key="ed_num_ped")

                edit_obs_c = st.text_area("Observação", value=comp_sel.get('observacao') or "", key="ed_obs_c")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("💾 Salvar Alterações", key="btn_salvar_edit_compra"):
                        if not edit_nome_c.strip() or not edit_loja_c.strip(): st.warning("Informe o nome e loja.")
                        else:
                            novo_tot_c = edit_qtd_c * edit_vunit_c
                            supabase.table("compras").update({
                                "nome_produto": edit_nome_c, "fornecedor": edit_loja_c, "local_detalhe": edit_loja_c,
                                "quantidade": edit_qtd_c, "valor_total": novo_tot_c, "tipo_aquisicao": edit_tipo_c,
                                "data_compra": str(edit_dt_c), "data_prevista_chegada": str(edit_dt_prev),
                                "forma_pagamento": edit_forma_pg, "numero_pedido": edit_num_ped,
                                "observacao": edit_obs_c
                            }).eq("id", compra_id_sel).execute()
                            st.success("🎉 COMPRA ATUALIZADA COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()
                with col_b2:
                    if st.button("🗑️ Excluir Compra", key="btn_excluir_edit_compra"):
                        supabase.table("compras").delete().eq("id", compra_id_sel).execute()
                        st.success("🗑️ COMPRA EXCLUÍDA!")
                        time.sleep(1.5)
                        st.rerun()
        else:
            st.info("Nenhuma compra registrada ainda.")

    elif menu == "💰 Faturamento":
        st.title("Fluxo de Caixa (Faturamento)")

        st.markdown("#### 🗓️ Selecione o Período do Relatório")
        col_f1, col_f2 = st.columns([1, 3])

        ano_atual = datetime.now().year
        with col_f1:
            ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2100, value=ano_atual, step=1, key="fat_ano")

        nomes_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        with col_f2:
            meses_selecionados_nomes = st.multiselect(
                "Mês (ou meses) — deixe vazio para ver o ano inteiro",
                nomes_meses, default=[nomes_meses[datetime.now().month - 1]], key="fat_meses"
            )
        meses_selecionados = [nomes_meses.index(m) + 1 for m in meses_selecionados_nomes] if meses_selecionados_nomes else list(range(1, 13))

        def _dentro_do_periodo(data_str):
            if not data_str: return False
            try:
                d = datetime.strptime(str(data_str).split("T")[0], "%Y-%m-%d").date()
                return d.year == ano_selecionado and d.month in meses_selecionados
            except Exception: return False

        eventos_fat = supabase.table("eventos").select("id, data_inicio, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        eventos_periodo = [e for e in (eventos_fat.data or []) if _dentro_do_periodo(e.get('data_inicio'))]
        receita_eventos = sum(float(e.get('valor_total') or 0) for e in eventos_periodo)
        qtd_eventos_periodo = len(eventos_periodo)

        try:
            despesas_viagem_resp = supabase.table("despesas_viagem").select("*").eq("empresa_id", emp_id).execute()
            despesas_viagem_periodo = [d for d in (despesas_viagem_resp.data or []) if _dentro_do_periodo(d.get('data_despesa'))]
        except Exception: despesas_viagem_periodo = []
        total_despesas_viagem = sum(float(d.get('valor') or 0) for d in despesas_viagem_periodo)

        try:
            compras_resp = supabase.table("compras").select("*").eq("empresa_id", emp_id).execute()
            compras_periodo = [c for c in (compras_resp.data or []) if _dentro_do_periodo(c.get('data_compra'))]
        except Exception: compras_periodo = []
        total_investimento_compras = sum(float(c.get('valor_total') or 0) for c in compras_periodo)

        fat_manual_resp = supabase.table("faturamento").select("*").eq("empresa_id", emp_id).execute()
        fat_manual_periodo = [f for f in (fat_manual_resp.data or []) if _dentro_do_periodo(f.get('data_pagamento'))]
        receita_manual = sum(float(f.get('valor') or 0) for f in fat_manual_periodo if f.get('tipo') == 'receita')
        despesa_manual = sum(float(f.get('valor') or 0) for f in fat_manual_periodo if f.get('tipo') == 'despesa')

        lucro_liquido = (receita_eventos + receita_manual) - (total_despesas_viagem + total_investimento_compras + despesa_manual)

        st.markdown("---")
        st.markdown(f"#### 📊 Resumo — {', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}")

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("🎉 Receita de Eventos", formatar_moeda(receita_eventos), help=f"{qtd_eventos_periodo} evento(s) no período")
        col_r2.metric("⛽ Gastos de Viagem", formatar_moeda(total_despesas_viagem))
        col_r3.metric("🛒 Investimento em Compras", formatar_moeda(total_investimento_compras))
        col_r4.metric("💰 Lucro Líquido", formatar_moeda(lucro_liquido))

        st.markdown("---")
        with st.expander("⛽ Registrar Gasto de Viagem", expanded=False):
            with st.form("form_despesa_viagem"):
                categoria_despesa = st.selectbox("Categoria", ["Combustível", "Alimentação", "Outros"])
                valor_despesa = st.number_input("Valor (R$)", min_value=0.0, step=5.0, value=None, format="%.2f")
                obs_despesa = st.text_input("Observação (opcional)")
                data_despesa_input = st.date_input("Data do Gasto", value=datetime.now().date(), format="DD/MM/YYYY")

                if st.form_submit_button("Registrar Gasto"):
                    if (valor_despesa or 0.0) <= 0: st.warning("Informe um valor maior que zero.")
                    else:
                        supabase.table("despesas_viagem").insert({
                            "empresa_id": emp_id, "categoria": categoria_despesa, "valor": (valor_despesa or 0.0),
                            "observacao": obs_despesa, "data_despesa": str(data_despesa_input)
                        }).execute()
                        st.success("🎉 CADASTRO CONCLUÍDO COM SUCESSO!")
                        time.sleep(1.5)
                        st.rerun()

        with st.expander("📄 Extrato de Gastos de Viagem do Período", expanded=False):
            if despesas_viagem_periodo:
                df_despesas_viagem = pd.DataFrame(despesas_viagem_periodo)
                colunas_desp = [c for c in ["data_despesa", "categoria", "valor", "observacao"] if c in df_despesas_viagem.columns]
                df_despesas_viagem_show = df_despesas_viagem[colunas_desp].sort_values("data_despesa", ascending=False).copy()
                df_despesas_viagem_show["data_despesa"] = df_despesas_viagem_show["data_despesa"].apply(
                    lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                )
                st.dataframe(df_despesas_viagem_show, use_container_width=True, hide_index=True)
            else: st.caption("Nenhum gasto de viagem registrado neste período.")

        def _fmt_data_br_simples(d):
            try: return datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception: return str(d)

        if despesas_viagem_periodo:
            with st.expander("✏️ Editar ou Excluir um Gasto de Viagem", expanded=False):
                opcoes_desp = {
                    f"{_fmt_data_br_simples(d.get('data_despesa'))} — {d.get('categoria','-')} — R$ {float(d.get('valor',0)):.2f}" + (f" ({d.get('observacao')})" if d.get('observacao') else ""): d['id']
                    for d in sorted(despesas_viagem_periodo, key=lambda x: x.get('data_despesa') or '', reverse=True)
                }
                escolha_desp_txt = st.selectbox("Selecione o lançamento", list(opcoes_desp.keys()), key="select_editar_despesa")
                desp_selecionada = next(d for d in despesas_viagem_periodo if d['id'] == opcoes_desp[escolha_desp_txt])

                col_ed_d1, col_ed_d2 = st.columns(2)
                with col_ed_d1:
                    categoria_edit_desp = st.selectbox(
                        "Categoria", ["Combustível", "Alimentação", "Outros"],
                        index=["Combustível", "Alimentação", "Outros"].index(desp_selecionada.get('categoria')) if desp_selecionada.get('categoria') in ["Combustível", "Alimentação", "Outros"] else 0,
                        key="edit_categoria_despesa"
                    )
                with col_ed_d2: valor_edit_desp = st.number_input("Valor (R$)", min_value=0.0, step=5.0, value=float(desp_selecionada.get('valor') or 0), format="%.2f", key="edit_valor_despesa")
                obs_edit_desp = st.text_input("Observação", value=desp_selecionada.get('observacao') or "", key="edit_obs_despesa")
                data_edit_desp = st.date_input(
                    "Data do Gasto",
                    value=datetime.strptime(str(desp_selecionada.get('data_despesa')).split("T")[0], "%Y-%m-%d").date(),
                    format="DD/MM/YYYY", key="edit_data_despesa"
                )
                motivo_edit_desp = st.text_input("Motivo da Edição (obrigatório)", key="motivo_edit_despesa")

                col_btn_d1, col_btn_d2 = st.columns(2)
                with col_btn_d1:
                    if st.button("💾 Salvar Alteração", key="btn_salvar_despesa"):
                        if not motivo_edit_desp.strip(): st.warning("Informe o motivo da edição.")
                        else:
                            data_hora_edit_desp = datetime.now().strftime("%d/%m/%Y às %H:%M")
                            nova_obs_desp = f"{obs_edit_desp} [Editado em {data_hora_edit_desp} — Motivo: {motivo_edit_desp}]".strip()
                            supabase.table("despesas_viagem").update({
                                "categoria": categoria_edit_desp, "valor": valor_edit_desp,
                                "observacao": nova_obs_desp, "data_despesa": str(data_edit_desp)
                            }).eq("id", desp_selecionada['id']).execute()
                            st.success("🎉 ALTERAÇÃO CONCLUÍDA COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()
                with col_btn_d2:
                    if st.button("🗑️ Excluir Lançamento", key="btn_excluir_despesa"):
                        supabase.table("despesas_viagem").delete().eq("id", desp_selecionada['id']).execute()
                        st.success("🗑️ LANÇAMENTO EXCLUÍDO!")
                        time.sleep(1.5)
                        st.rerun()

        with st.expander("➕ Outro Lançamento no Caixa (Receita ou Despesa Avulsa)", expanded=False):
            with st.form("form_fat"):
                desc_fat = st.text_input("Descrição (Ex: Pagamento de Luz, Recebimento Extra)")
                tipo_fat = st.radio("Tipo de Movimentação", ["receita", "despesa"], horizontal=True)
                valor_fat = st.number_input("Valor (R$)", min_value=0.0, value=None, format="%.2f")
                data_fat_input = st.date_input("Data", value=datetime.now().date(), format="DD/MM/YYYY", key="data_fat_manual")

                if st.form_submit_button("Lançar no Caixa"):
                    supabase.table("faturamento").insert({
                        "empresa_id": emp_id, "descricao": desc_fat, "tipo": tipo_fat,
                        "valor": (valor_fat or 0.0), "data_pagamento": str(data_fat_input), "pago": True
                    }).execute()
                    st.success("🎉 LANÇAMENTO CONCLUÍDO COM SUCESSO!")
                    time.sleep(1.5)
                    st.rerun()

        st.markdown("### 📜 Extrato Financeiro Completo (Lançamentos Avulsos)")
        fat_lista = supabase.table("faturamento").select("id, data_pagamento, tipo, descricao, valor").eq("empresa_id", emp_id).order("data_pagamento", desc=True).execute()
        if fat_lista.data:
            df_fat_show = pd.DataFrame(fat_lista.data)[["data_pagamento", "tipo", "descricao", "valor"]].copy()
            df_fat_show["data_pagamento"] = df_fat_show["data_pagamento"].apply(
                lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            )
            st.dataframe(df_fat_show, use_container_width=True, hide_index=True)

            with st.expander("✏️ Editar ou Excluir um Lançamento Avulso", expanded=False):
                opcoes_fat = {
                    f"{_fmt_data_br_simples(f.get('data_pagamento'))} — {f.get('tipo','-')} — {f.get('descricao','-')} — R$ {float(f.get('valor',0)):.2f}": f['id']
                    for f in fat_lista.data
                }
                escolha_fat_txt = st.selectbox("Selecione o lançamento", list(opcoes_fat.keys()), key="select_editar_fat")
                fat_selecionado = next(f for f in fat_lista.data if f['id'] == opcoes_fat[escolha_fat_txt])

                desc_edit_fat = st.text_input("Descrição", value=fat_selecionado.get('descricao') or "", key="edit_desc_fat")
                col_ef1, col_ef2 = st.columns(2)
                with col_ef1:
                    tipo_edit_fat = st.radio(
                        "Tipo", ["receita", "despesa"], horizontal=True,
                        index=["receita", "despesa"].index(fat_selecionado.get('tipo')) if fat_selecionado.get('tipo') in ["receita", "despesa"] else 0,
                        key="edit_tipo_fat"
                    )
                with col_ef2: valor_edit_fat = st.number_input("Valor (R$)", min_value=0.0, value=float(fat_selecionado.get('valor') or 0), format="%.2f", key="edit_valor_fat")
                data_edit_fat = st.date_input(
                    "Data",
                    value=datetime.strptime(str(fat_selecionado.get('data_pagamento')).split("T")[0], "%Y-%m-%d").date(),
                    format="DD/MM/YYYY", key="edit_data_fat"
                )
                motivo_edit_fat = st.text_input("Motivo da Edição (obrigatório)", key="motivo_edit_fat")

                col_btn_f1, col_btn_f2 = st.columns(2)
                with col_btn_f1:
                    if st.button("💾 Salvar Alteração", key="btn_salvar_fat"):
                        if not motivo_edit_fat.strip(): st.warning("Informe o motivo da edição.")
                        else:
                            data_hora_edit_fat = datetime.now().strftime("%d/%m/%Y às %H:%M")
                            nova_desc_fat = f"{desc_edit_fat} [Editado em {data_hora_edit_fat} — Motivo: {motivo_edit_fat}]"
                            supabase.table("faturamento").update({
                                "descricao": nova_desc_fat, "tipo": tipo_edit_fat,
                                "valor": valor_edit_fat, "data_pagamento": str(data_edit_fat)
                            }).eq("id", fat_selecionado['id']).execute()
                            st.success("🎉 ALTERAÇÃO CONCLUÍDA COM SUCESSO!")
                            time.sleep(1.5)
                            st.rerun()
                with col_btn_f2:
                    if st.button("🗑️ Excluir Lançamento", key="btn_excluir_fat"):
                        supabase.table("faturamento").delete().eq("id", fat_selecionado['id']).execute()
                        st.success("🗑️ LANÇAMENTO EXCLUÍDO!")
                        time.sleep(1.5)
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
                linhas.append({
                    "Mês": nomes_meses[mes_num - 1],
                    "Nº Eventos": qtd_mes,
                    "Receita de Eventos (R$)": receita_mes,
                    "Gastos de Viagem (R$)": viagem_mes,
                    "Investimento em Compras (R$)": compras_mes,
                    "Lucro Líquido (R$)": receita_mes - viagem_mes - compras_mes
                })
            return pd.DataFrame(linhas)

        df_mensal_export = montar_dataframe_mensal()
        st.dataframe(df_mensal_export, use_container_width=True, hide_index=True)

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
                df_mensal_export.to_excel(writer, index=False, sheet_name="Resumo Mensal")
                if despesas_viagem_periodo: pd.DataFrame(despesas_viagem_periodo)[[c for c in ["data_despesa", "categoria", "valor", "observacao"] if c in pd.DataFrame(despesas_viagem_periodo).columns]].to_excel(writer, index=False, sheet_name="Gastos de Viagem")
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
                COR_DOURADO = colors.HexColor("#FFC107")
                COR_PRETO = colors.HexColor("#0E0E0E")
                COR_CINZA_CLARO = colors.HexColor("#F2F2F2")
                COR_VERDE = colors.HexColor("#1B7F3A")
                COR_VERMELHO = colors.HexColor("#B3261E")
                COR_AZUL = colors.HexColor("#1A5FB4")
                periodo_txt = f"{', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}"

                def _desenhar_moldura(canvas_obj, doc_obj):
                    canvas_obj.saveState()
                    largura_pagina, altura_pagina = A4
                    altura_faixa = 3.2 * cm
                    canvas_obj.setFillColor(COR_PRETO)
                    canvas_obj.rect(0, altura_pagina - altura_faixa, largura_pagina, altura_faixa, fill=1, stroke=0)
                    if caminho_logo_fat:
                        try: canvas_obj.drawImage(caminho_logo_fat, 2 * cm, altura_pagina - altura_faixa + 0.35 * cm, width=3.6 * cm, height=2.5 * cm, preserveAspectRatio=True, mask='auto')
                        except Exception: pass
                    canvas_obj.setFillColor(COR_DOURADO)
                    canvas_obj.setFont("Helvetica-Bold", 16)
                    canvas_obj.drawString(6.2 * cm, altura_pagina - 1.5 * cm, "EXTRATO FINANCEIRO")
                    canvas_obj.setFillColor(colors.white)
                    canvas_obj.setFont("Helvetica", 10)
                    canvas_obj.drawString(6.2 * cm, altura_pagina - 2.15 * cm, f"Período: {periodo_txt}")
                    canvas_obj.setFillColor(colors.grey)
                    canvas_obj.setFont("Helvetica", 8)
                    canvas_obj.drawString(2 * cm, 1.2 * cm, f"Luz & Letra — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
                    canvas_obj.drawRightString(largura_pagina - 2 * cm, 1.2 * cm, f"Página {doc_obj.page}")
                    canvas_obj.restoreState()

                frame_fat = Frame(2 * cm, 1.8 * cm, A4[0] - 4 * cm, A4[1] - 5.4 * cm, id='corpo')
                doc_fat = BaseDocTemplate(buffer_pdf_fat, pagesize=A4)
                doc_fat.addPageTemplates([PageTemplate(id='ComMoldura', frames=[frame_fat], onPage=_desenhar_moldura)])
                story_fat.append(Spacer(1, 10))

                estilo_kpi_label = ParagraphStyle('KpiLabel', fontSize=8.5, textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica-Bold")
                estilo_kpi_valor = ParagraphStyle('KpiValor', fontSize=14, textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica-Bold", spaceBefore=4)
                cartoes = [
                    ("🎉 RECEITA DE EVENTOS", formatar_moeda(receita_eventos), COR_DOURADO),
                    ("⛽ GASTOS DE VIAGEM", formatar_moeda(total_despesas_viagem), COR_VERMELHO),
                    ("🛒 INVESTIMENTO EM COMPRAS", formatar_moeda(total_investimento_compras), COR_AZUL),
                    ("💰 LUCRO LÍQUIDO", formatar_moeda(lucro_liquido), COR_VERDE if lucro_liquido >= 0 else COR_VERMELHO),
                ]
                linha_kpi = [[
                    Table([[Paragraph(label, estilo_kpi_label)], [Paragraph(valor, estilo_kpi_valor)]],
                          colWidths=[4.0 * cm],
                          style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), cor), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
                    for label, valor, cor in cartoes
                ]]
                tabela_kpi = Table(linha_kpi, colWidths=[4.1 * cm] * 4, spaceAfter=18)
                tabela_kpi.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]))
                story_fat.append(tabela_kpi)
                story_fat.append(Spacer(1, 20))
                story_fat.append(Paragraph("Detalhamento por Mês", ParagraphStyle('SubTit', fontSize=12, fontName="Helvetica-Bold", textColor=COR_PRETO, spaceAfter=8)))

                tabela_fat_dados = [["Mês", "Nº Eventos", "Receita Eventos", "Gastos Viagem", "Compras", "Lucro Líquido"]]
                for _, row in df_mensal_export.iterrows():
                    tabela_fat_dados.append([
                        row["Mês"], str(row["Nº Eventos"]),
                        formatar_moeda(row['Receita de Eventos (R$)']), 
                        formatar_moeda(row['Gastos de Viagem (R$)']), 
                        formatar_moeda(row['Investimento em Compras (R$)']), 
                        formatar_moeda(row['Lucro Líquido (R$)'])
                    ])
                tabela_fat_pdf = Table(tabela_fat_dados, colWidths=[2.6*cm, 2.2*cm, 3.2*cm, 3*cm, 2.8*cm, 3.2*cm])
                estilo_tabela_fat = [
                    ('BACKGROUND', (0, 0), (-1, 0), COR_PRETO), ('TEXTCOLOR', (0, 0), (-1, 0), COR_DOURADO), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 0), (-1, -1), 8.5), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]
                for i in range(1, len(tabela_fat_dados)):
                    if i % 2 == 0: estilo_tabela_fat.append(('BACKGROUND', (0, i), (-1, i), COR_CINZA_CLARO))
                tabela_fat_pdf.setStyle(TableStyle(estilo_tabela_fat))
                story_fat.append(tabela_fat_pdf)
                story_fat.append(Spacer(1, 14))
                story_fat.append(Paragraph(f"<b>Lucro Líquido Total do Período:</b> {formatar_moeda(lucro_liquido)}", ParagraphStyle('Resumo', fontSize=11, textColor=COR_PRETO)))

                doc_fat.build(story_fat)
                buffer_pdf_fat.seek(0)
                st.download_button("📄 Baixar PDF do Período", data=buffer_pdf_fat, file_name=f"faturamento_{ano_selecionado}.pdf", mime="application/pdf")
            else: st.caption("⚠️ Para gerar o PDF, instale a biblioteca: `pip install reportlab`")
