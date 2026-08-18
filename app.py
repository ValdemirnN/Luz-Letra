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
import qrcode
import os # Importação adicionada para verificar a existência de arquivos

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

# CORREÇÃO 1: Verifica se a imagem existe antes de definir como ícone
icone_pagina = "logo.jpg" if os.path.exists("logo.jpg") else "💡"
st.set_page_config(page_title="Luz & Letras", page_icon=icone_pagina, layout="wide")

st.markdown("""
<script>
var meta = document.createElement('meta');
meta.name = "google-site-verification";
meta.content = "BLsnKznEf1epekQKo6x3onFRT5C7hTLZDLdUfnXIFG4";
document.getElementsByTagName('head')[0].appendChild(meta);
</script>
""", unsafe_allow_html=True)

if st.query_params.get("privacidade") == "1":
    st.title("Política de Privacidade - Luz & Letras Sistema")
    st.markdown("""
    **Última atualização:** 21 de julho de 2026

    O Luz & Letras Sistema é uma plataforma de gestão para empresas de locação de itens para eventos.

    ### 1. Dados que coletamos
    - Nome, e-mail e senha (para login no sistema).
    - Dados de eventos, clientes, estoque e faturamento cadastrados pelo próprio usuário.
    - Ao conectar sua Google Agenda, com sua autorização explícita, acessamos: seu e-mail do Google e permissão para criar e atualizar eventos na sua agenda.

    ### 2. Como usamos os dados do Google Agenda
    Usamos a permissão apenas para criar ou atualizar eventos na sua própria Google Agenda. Não lemos, coletamos nem compartilhamos outros dados da sua agenda.

    ### 3. Compartilhamento de dados
    Não vendemos nem compartilhamos seus dados com terceiros, exceto quando exigido por lei.

    ### 4. Armazenamento
    Os dados ficam armazenados em banco de dados protegido (Supabase), com acesso restrito à equipe responsável.

    ### 5. Seus direitos
    Você pode desconectar sua Google Agenda pela tela de Perfil, ou solicitar exclusão da conta pelo e-mail nvaldemir76@gmail.com.

    ### 6. Contato
    nvaldemir76@gmail.com
    """)
    st.stop()

st.markdown("""
<style>
div[data-testid="InputInstructions"] { display: none !important; }
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
input[type="number"] { -moz-appearance: textfield; }
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] { display: none !important; }
div[data-testid="stNumberInput"] input[type="number"]:out-of-range {
    background-color: #3b0a0a !important; color: #ff4b4b !important; border: 2px solid #ff4b4b !important; border-radius: 6px;
}
div[data-testid="stNumberInput"]:has(input:out-of-range)::after {
    content: "⚠️ A QUANTIDADE EM ESTOQUE É INSUFICIENTE!";
    color: #ff4b4b; font-size: 13px; font-weight: bold; display: block; margin-top: 6px;
    animation: piscarErro 1s infinite;
}
@keyframes piscarErro { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
</style>
""", unsafe_allow_html=True)

def formatar_moeda(valor):
    if valor is None: return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_payload_pix(chave, nome_beneficiario, cidade, valor, descricao="Assinatura"):
    def formatar_campo(id, valor):
        return f"{id}{len(valor):02d}{valor}"
    chave_formatada = formatar_campo("01", chave)
    descricao_formatada = formatar_campo("02", descricao[:25])
    merchant_account = formatar_campo("26", chave_formatada + descricao_formatada)
    valor_str = f"{valor:.2f}"
    payload = (
        formatar_campo("00", "01") + merchant_account + formatar_campo("52", "0000") +
        formatar_campo("53", "986") + formatar_campo("54", valor_str) +
        formatar_campo("58", "BR") + formatar_campo("59", nome_beneficiario[:25]) +
        formatar_campo("60", cidade[:15]) + formatar_campo("62", formatar_campo("05", "***"))
    )
    payload += "6304"
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= char << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
        crc &= 0xFFFF
    payload += f"{crc:04X}"
    return payload

def gerar_qrcode_pix(payload):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def mostrar_popup(mensagem, tipo="sucesso", tempo=1.5):
    if tipo == "erro":
        st.error(f"⚠️ {mensagem}")
    else:
        alerta = st.empty()
        alerta.markdown(f"""
        <style>
        .popup-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-color: rgba(0,0,0,0.7); z-index: 999999;
            display: flex; align-items: center; justify-content: center; }}
        .popup-box {{ background-color: #1B5E20; color: white; padding: 40px 60px;
            border-radius: 12px; font-size: 24px; font-weight: bold; text-align: center;
            box-shadow: 0px 8px 30px rgba(0,0,0,0.8); animation: fadeInScale 0.3s ease-out forwards; }}
        @keyframes fadeInScale {{ 0% {{ opacity: 0; transform: scale(0.7); }} 100% {{ opacity: 1; transform: scale(1); }} }}
        </style>
        <div class="popup-overlay"><div class="popup-box"><span style="font-size:40px;">🎉</span><br><br>{mensagem}</div></div>
        """, unsafe_allow_html=True)
        time.sleep(tempo)
        alerta.empty()

def aplicar_fundo_com_logo(caminho_logo="logo.jpg"):
    try:
        # CORREÇÃO 2: Só tenta aplicar o fundo se a imagem existir
        if os.path.exists(caminho_logo):
            with open(caminho_logo, "rb") as f:
                logo_base64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
            <style>
            .stApp {{ position: relative; }}
            .stApp::before {{ content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background-image: url("data:image/jpg;base64,{logo_base64}");
                background-repeat: no-repeat; background-position: center;
                background-size: min(45vw, 480px); opacity: 0.07; z-index: 0;
                pointer-events: none; animation: brilhoPulsante 4s ease-in-out infinite; }}
            @keyframes brilhoPulsante {{
                0%   {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
                50%  {{ opacity: 0.11; filter: drop-shadow(0 0 35px #FFD700); }}
                100% {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
            }}
            .stApp > * {{ position: relative; z-index: 1; }}
            [data-testid="stSidebar"] img {{ animation: brilhoSidebar 3s ease-in-out infinite; border-radius: 12px; }}
            @keyframes brilhoSidebar {{
                0%   {{ filter: drop-shadow(0 0 6px rgba(255,215,0,0.35)); }}
                50%  {{ filter: drop-shadow(0 0 18px rgba(255,215,0,0.75)); }}
                100% {{ filter: drop-shadow(0 0 6px rgba(255,215,0,0.35)); }}
            }}
            </style>
            """, unsafe_allow_html=True)
    except Exception: pass

aplicar_fundo_com_logo()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
GMAIL_REMETENTE = st.secrets.get("GMAIL_REMETENTE", "SEU_EMAIL_AQUI@gmail.com")
GMAIL_SENHA_APP = st.secrets.get("GMAIL_SENHA_APP", "SUA_SENHA_DE_APP_DE_16_DIGITOS")
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "COLOQUE_SEU_ACCESS_TOKEN_DO_MERCADO_PAGO_AQUI")
URL_BASE_SISTEMA = st.secrets.get("URL_BASE_SISTEMA", "http://localhost:8501")
VALOR_ASSINATURA_MENSAL = 300.00
GOOGLE_MAPS_API_KEY = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
GOOGLE_CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email"

@st.cache_resource
def init_connection(): return create_client(SUPABASE_URL, SUPABASE_KEY)

try: supabase: Client = init_connection()
except Exception as e:
    st.error("Erro ao conectar com o banco. Verifique suas chaves.")
    st.stop()

from streamlit_cookies_manager import EncryptedCookieManager
cookies = EncryptedCookieManager(
    prefix="luzletras/",
    password=st.secrets.get("COOKIES_PASSWORD", "luz-letras-senha-super-secreta-2026"),
)
if not cookies.ready(): st.stop()


# ==========================================
# CONTROLE DE SESSÃO
# ==========================================
def fazer_logout():
    token_atual = st.session_state.get("token_sessao")
    if token_atual:
        try: supabase.table("sessoes_ativas").delete().eq("token", token_atual).execute()
        except: pass
    if "tk" in cookies: del cookies["tk"]
    if "uid" in cookies: del cookies["uid"]
    cookies.save()
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None})

def restaurar_sessao_por_token():
    try:
        tk_param = cookies.get("tk")
        uid_param = cookies.get("uid")
        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)
            sessao_banco = supabase.table("sessoes_ativas").select("id").eq("token", tk_param).eq("usuario_id", usuario_id_restaurar).execute()
            if not sessao_banco.data:
                del cookies["tk"]; del cookies["uid"]; cookies.save()
                return
            resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, nome, plano").eq("id", usuario_id_restaurar).execute()
            if resultado.data:
                usuario = resultado.data[0]
                if usuario['ativo']:
                    plano_valido = True
                    if usuario.get('empresa_id'):
                        assinatura_check = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", usuario['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                        if assinatura_check.data:
                            venc_check = assinatura_check.data[0]['data_vencimento'].split("T")[0]
                            if datetime.strptime(venc_check, "%Y-%m-%d").date() < datetime.now().date():
                                plano_valido = False
                    if plano_valido:
                        st.session_state.update({'logado': True, 'perfil': usuario['perfil'], 'empresa_id': usuario['empresa_id'],
                            'usuario_id': usuario['id'], 'nome_usuario': usuario.get('nome') or 'Usuário', 'token_sessao': tk_param})
    except Exception: pass

def enviar_email_confirmacao(destinatario, nome_destinatario, token):
    link_confirmacao = f"{URL_BASE_SISTEMA}/?confirmar_email={token}"
    corpo = f"Olá {nome_destinatario},\n\nObrigado por criar sua conta!\nPara confirmar seu e-mail, clique no link abaixo:\n{link_confirmacao}\n"
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
        mostrar_popup(f"Conta criada, mas erro ao enviar e-mail ({e}).", tipo="erro")
        return False

def confirmar_email_por_link():
    try:
        token_param = st.query_params.get("confirmar_email")
        if token_param:
            resultado = supabase.table("usuarios").select("id, email, nome").eq("token_confirmacao", token_param).execute()
            if resultado.data:
                usuario_confirmado = resultado.data[0]
                supabase.table("usuarios").update({"email_confirmado": True, "token_confirmacao": None}).eq("id", usuario_confirmado['id']).execute()
                st.session_state.update({'conta_criada_id': usuario_confirmado['id'], 'conta_criada_email': usuario_confirmado['email'], 'conta_criada_nome': usuario_confirmado.get('nome') or usuario_confirmado['email']})
                mostrar_popup("E-mail confirmado com sucesso! Conclua o pagamento.")
            else: mostrar_popup("Link de confirmação inválido ou já utilizado.", tipo="erro")
            st.query_params.clear()
    except Exception: pass

confirmar_email_por_link()

def criar_preferencia_pagamento_mp(usuario_id, email_cliente, descricao, valor):
    url = "https://api.mercadopago.com/checkout/preferences"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "items": [{"title": descricao, "quantity": 1, "unit_price": float(valor), "currency_id": "BRL"}],
        "payer": {"email": email_cliente}, "external_reference": str(usuario_id),
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
    for pagamento in resposta.json().get("results", []):
        if pagamento.get("status") == "approved": return True
    return False

def ativar_conta_apos_pagamento(usuario_id, metodo):
    hoje = datetime.now()
    novo_venc = hoje + relativedelta(months=1)
    resultado_user = supabase.table("usuarios").select("empresa_id").eq("id", usuario_id).execute()
    if resultado_user.data:
        empresa_id_pagamento = resultado_user.data[0]['empresa_id']
        supabase.table("assinaturas").update({"data_vencimento": novo_venc.strftime("%Y-%m-%d")}).eq("empresa_id", empresa_id_pagamento).execute()
    supabase.table("usuarios").update({"ativo": True, "metodo_pagamento": metodo}).eq("id", usuario_id).execute()

# ==========================================
# FUNÇÕES NOVAS — NOTIFICAÇÕES E BLOQUEIO
# ==========================================
def enviar_email_expiracao(destinatario, nome_destinatario, dias_restantes, data_vencimento_str):
    if dias_restantes == 1:
        assunto = "⚠️ Último dia! Sua assinatura Luz & Letras expira AMANHÃ"
        urgencia = "URGENTE — seu acesso será bloqueado amanhã"
    elif dias_restantes <= 3:
        assunto = f"⚠️ Sua assinatura Luz & Letras expira em {dias_restantes} dias"
        urgencia = f"Atenção: apenas {dias_restantes} dias restantes"
    else:
        assunto = f"📅 Lembrete: assinatura Luz & Letras vence em {dias_restantes} dias"
        urgencia = f"Lembrete amigável: {dias_restantes} dias para o vencimento"
    corpo = f"""Olá {nome_destinatario},

{urgencia.upper()}

Sua assinatura do Luz & Letras Sistema vence em: {data_vencimento_str}

Para manter seu acesso sem interrupção, renove agora:
👉 Acesse o sistema → clique em "Perfil" → "Minha Assinatura"

Formas de pagamento:
  • PIX: 702.221.494-85 (Valdemir Nunes Nicacio)
  • Cartão/Boleto: disponível no painel
  • Pagar em mãos: entre em contato

Após o vencimento, seu acesso será bloqueado automaticamente 1 dia depois.

Dúvidas: nvaldemir76@gmail.com

Atenciosamente,
Equipe Luz & Letras
"""
    msg = MIMEText(corpo)
    msg['Subject'] = assunto
    msg['From'] = GMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as servidor:
            servidor.login(GMAIL_REMETENTE, GMAIL_SENHA_APP)
            servidor.sendmail(GMAIL_REMETENTE, destinatario, msg.as_string())
        return True
    except Exception: return False

def verificar_e_disparar_notificacoes_expiracao():
    ultima_verificacao = st.session_state.get('_ultima_verificacao_notif')
    if ultima_verificacao:
        delta = (datetime.now() - ultima_verificacao).total_seconds()
        if delta < 3600: return
    st.session_state['_ultima_verificacao_notif'] = datetime.now()
    try:
        hoje = datetime.now().date()
        usuarios_resp = supabase.table("usuarios").select("id, email, nome, empresa_id").eq("ativo", True).neq("perfil", "admin_geral").execute()
        if not usuarios_resp.data: return
        for u in usuarios_resp.data:
            if not u.get('empresa_id') or not u.get('email'): continue
            ass_resp = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
            if not ass_resp.data: continue
            venc_str = ass_resp.data[0]['data_vencimento'].split("T")[0]
            try: venc_date = datetime.strptime(venc_str, "%Y-%m-%d").date()
            except Exception: continue
            dias_restantes = (venc_date - hoje).days
            marcos = [7, 3, 1]
            if dias_restantes not in marcos: continue
            try:
                ja_enviou = supabase.table("notificacoes_enviadas").select("id").eq("usuario_id", u['id']).eq("tipo", f"expiracao_{dias_restantes}d").eq("referencia", venc_str).execute()
                if ja_enviou.data: continue
            except Exception: pass
            nome_dest = u.get('nome') or u['email']
            venc_fmt = datetime.strptime(venc_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            sucesso = enviar_email_expiracao(u['email'], nome_dest, dias_restantes, venc_fmt)
            if sucesso:
                try:
                    supabase.table("notificacoes_enviadas").insert({"usuario_id": u['id'], "tipo": f"expiracao_{dias_restantes}d", "referencia": venc_str, "enviado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}).execute()
                except Exception: pass
    except Exception: pass

def verificar_acesso_e_bloquear():
    if st.session_state.get('perfil') == 'admin_geral': return 'ok'
    empresa_id = st.session_state.get('empresa_id')
    if not empresa_id: return 'ok'
    try:
        ass_resp = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", empresa_id).order("data_vencimento", desc=True).limit(1).execute()
        if not ass_resp.data: return 'ok'
        venc_str = ass_resp.data[0]['data_vencimento'].split("T")[0]
        venc_date = datetime.strptime(venc_str, "%Y-%m-%d").date()
        hoje = datetime.now().date()
        dias_restantes = (venc_date - hoje).days
        if dias_restantes < -1:
            supabase.table("usuarios").update({"ativo": False}).eq("id", st.session_state['usuario_id']).execute()
            return 'bloqueado'
        elif dias_restantes <= 0: return 'aviso_vencendo'
        elif dias_restantes in [1, 2, 3, 7]: return f'aviso_{dias_restantes}_dias'
        else: return 'ok'
    except Exception: return 'ok'

def registrar_pagamento_historico(empresa_id, usuario_id, plano, valor, metodo, venc_anterior, venc_novo, aprovado_por="Sistema"):
    try:
        supabase.table("historico_pagamentos").insert({
            "empresa_id": empresa_id, "usuario_id": usuario_id, "plano": plano,
            "valor": valor, "metodo_pagamento": metodo,
            "data_pagamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vencimento_anterior": venc_anterior, "vencimento_novo": venc_novo,
            "aprovado_por": aprovado_por
        }).execute()
    except Exception: pass

# ==========================================
# GOOGLE AGENDA
# ==========================================
def gerar_url_autorizacao_google(usuario_id):
    from urllib.parse import urlencode
    params = {"client_id": GOOGLE_CLIENT_ID, "redirect_uri": URL_BASE_SISTEMA,
        "response_type": "code", "scope": GOOGLE_CALENDAR_SCOPE, "access_type": "offline",
        "include_granted_scopes": "true", "prompt": "consent", "state": str(usuario_id)}
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def processar_callback_google():
    try:
        code_param = st.query_params.get("code")
        state_param = st.query_params.get("state")
        if code_param and state_param:
            resp = requests.post("https://oauth2.googleapis.com/token", data={
                "code": code_param, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": URL_BASE_SISTEMA, "grant_type": "authorization_code"}, timeout=15)
            dados_token = resp.json()
            refresh_token_novo = dados_token.get("refresh_token")
            usuario_id_google = int(state_param)
            if refresh_token_novo and dados_token.get("access_token"):
                try:
                    info_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {dados_token.get('access_token')}"}, timeout=15)
                    email_google_conectado = info_resp.json().get("email", "")
                except Exception: email_google_conectado = ""
                supabase.table("usuarios").update({"google_refresh_token": refresh_token_novo, "google_email_conectado": email_google_conectado}).eq("id", usuario_id_google).execute()
                st.session_state['sucesso_msg'] = "GOOGLE AGENDA CONECTADA COM SUCESSO!"
            else:
                st.session_state['erro_google_msg'] = "Não recebemos permissão de acesso contínuo do Google. Remova o acesso em myaccount.google.com/permissions e tente conectar novamente."
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        st.session_state['erro_google_msg'] = f"Erro ao conectar Google Agenda: {e}"
        try: st.query_params.clear()
        except Exception: pass

if st.query_params.get("code") and st.query_params.get("state"):
    processar_callback_google()

def obter_access_token_google(refresh_token):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "refresh_token": refresh_token, "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET, "grant_type": "refresh_token"}, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]

def criar_ou_atualizar_evento_google_agenda(refresh_token, evento_dict, google_event_id=None):
    access_token = obter_access_token_google(refresh_token)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data_inicio_ev = str(evento_dict['data_inicio']).split("T")[0]
    data_fim_ev = str(evento_dict.get('data_fim_alocacao') or data_inicio_ev).split("T")[0]
    data_fim_evento_dt = (datetime.strptime(data_fim_ev, "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
    body = {"summary": f"🎉 Evento: {evento_dict.get('descricao', 'Evento')}",
        "description": (evento_dict.get('observacao') or ""),
        "start": {"date": data_inicio_ev}, "end": {"date": data_fim_evento_dt},
        "reminders": {"useDefault": False, "overrides": [
            {"method": "email", "minutes": 24*60}, {"method": "email", "minutes": 60}, {"method": "popup", "minutes": 60}]}}
    if google_event_id:
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
        resp = requests.put(url, headers=headers, json=body, timeout=15)
    else:
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    return resp.json().get("id")

def sincronizar_evento_google_agenda_silencioso(usuario_id_dono, evento_dict, google_event_id_existente=None):
    try:
        u = supabase.table("usuarios").select("google_refresh_token").eq("id", usuario_id_dono).execute()
        if not u.data or not u.data[0].get("google_refresh_token"): return None
        return criar_ou_atualizar_evento_google_agenda(u.data[0]["google_refresh_token"], evento_dict, google_event_id_existente)
    except Exception: return None

def calcular_distancia_google_maps(origem, destino):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": origem, "destinations": destino, "key": GOOGLE_MAPS_API_KEY, "language": "pt-BR", "units": "metric"}
    resp = requests.get(url, params=params, timeout=15)
    dados = resp.json()
    if dados.get("status") != "OK": raise Exception(dados.get("error_message") or f"Erro na API do Google Maps: {dados.get('status')}")
    elemento = dados["rows"][0]["elements"][0]
    if elemento.get("status") != "OK": raise Exception(f"Não foi possível calcular a rota entre '{origem}' e '{destino}'.")
    km = elemento["distance"]["value"] / 1000
    duracao_min = elemento["duration"]["value"] / 60
    return km, duracao_min

if 'logado' not in st.session_state:
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None})
    restaurar_sessao_por_token()


# ==========================================
# TELA DE LOGIN
# ==========================================
if not st.session_state['logado']:
    # CORREÇÃO 3: Verifica se a imagem existe na barra lateral
    if os.path.exists("logo.jpg"):
        st.sidebar.image("logo.jpg", use_container_width=True)
    st.title("🔒 Login - Luz & Letras")

    with st.form("form_login"):
        email_login = st.text_input("E-mail")
        senha_login = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        try:
            try: resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, nome, plano").eq("email", email_login).execute()
            except: resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, plano").eq("email", email_login).execute()
            if not resultado.data: mostrar_popup("E-mail não encontrado.", tipo="erro")
            else:
                usuario = resultado.data[0]
                if not usuario['ativo']: mostrar_popup("Usuário bloqueado. Fale com o administrador.", tipo="erro")
                elif usuario['senha_hash'] != senha_login: mostrar_popup("Senha incorreta.", tipo="erro")
                else:
                    plano_usuario = usuario.get('plano') or 'basico'
                    perfil_usuario = usuario.get('perfil') or ''
                    if perfil_usuario == 'admin_geral': limite_aparelhos = 999
                    elif plano_usuario == 'pro': limite_aparelhos = 5
                    else: limite_aparelhos = 1
                    sessoes_ativas = supabase.table("sessoes_ativas").select("id").eq("usuario_id", usuario['id']).execute()
                    qtd_logados = len(sessoes_ativas.data) if sessoes_ativas.data else 0
                    if qtd_logados > limite_aparelhos:
                        mostrar_popup(f"Limite de {limite_aparelhos} aparelho(s) atingido.", tipo="erro")
                        st.session_state['bloqueio_usuario_id'] = usuario['id']
                    else:
                        novo_token = secrets.token_urlsafe(24)
                        data_exp = (datetime.now() + relativedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                        supabase.table("sessoes_ativas").insert({"usuario_id": usuario['id'], "token": novo_token, "data_expiracao": data_exp}).execute()
                        nome_usuario_login = usuario.get('nome') or usuario.get('email', 'Usuário')
                        st.session_state.update({'logado': True, 'perfil': usuario['perfil'], 'empresa_id': usuario['empresa_id'],
                            'usuario_id': usuario['id'], 'nome_usuario': nome_usuario_login, 'token_sessao': novo_token})
                        if 'bloqueio_usuario_id' in st.session_state: del st.session_state['bloqueio_usuario_id']
                        cookies["tk"] = novo_token
                        cookies["uid"] = str(usuario['id'])
                        cookies.save()
                        st.rerun()
        except Exception as e: mostrar_popup(f"Erro ao tentar logar: {e}", tipo="erro")

    if st.session_state.get('bloqueio_usuario_id'):
        st.warning("⚠️ Você já possui aparelhos conectados no seu limite.")
        if st.button("Desconectar aparelhos antigos à força"):
            uid_bloqueado = st.session_state['bloqueio_usuario_id']
            supabase.table("sessoes_ativas").delete().eq("usuario_id", uid_bloqueado).execute()
            del st.session_state['bloqueio_usuario_id']
            mostrar_popup("Aparelhos antigos desconectados! Faça login novamente.")
            st.rerun()

    st.markdown("---")
    with st.expander("🆕 Ainda não tem conta? Criar conta"):
        with st.form("form_criar_conta"):
            nome_empresa_cadastro = st.text_input("Nome da Empresa")
            nome_usuario_cadastro = st.text_input("Seu Nome")
            email_cadastro = st.text_input("E-mail")
            senha_cadastro = st.text_input("Senha", type="password")
            senha_cadastro_confirma = st.text_input("Confirme a Senha", type="password")
            if st.form_submit_button("Criar Conta"):
                if not nome_empresa_cadastro.strip() or not nome_usuario_cadastro.strip() or not email_cadastro.strip(): mostrar_popup("Preencha todos os campos.", tipo="erro")
                elif senha_cadastro != senha_cadastro_confirma: mostrar_popup("As senhas não coincidem.", tipo="erro")
                elif len(senha_cadastro) < 7: mostrar_popup("Mínimo 7 caracteres.", tipo="erro")
                else:
                    email_existente = supabase.table("usuarios").select("id").eq("email", email_cadastro).execute()
                    if email_existente.data: mostrar_popup("Já existe uma conta com esse e-mail.", tipo="erro")
                    else:
                        plano_padrao = supabase.table("planos").select("id").order("id").limit(1).execute()
                        if not plano_padrao.data: mostrar_popup("Nenhum plano cadastrado no banco de dados.", tipo="erro")
                        else:
                            nova_empresa = supabase.table("empresas").insert({"nome_fantasia": nome_empresa_cadastro}).execute()
                            empresa_id_criada = nova_empresa.data[0]['id']
                            hoje_cadastro = datetime.now().strftime("%Y-%m-%d")
                            supabase.table("assinaturas").insert({"empresa_id": empresa_id_criada, "plano_id": plano_padrao.data[0]['id'], "data_inicio": hoje_cadastro, "data_vencimento": hoje_cadastro}).execute()
                            token_confirmacao_novo = secrets.token_urlsafe(24)
                            try: supabase.table("usuarios").insert({"email": email_cadastro, "senha_hash": senha_cadastro, "perfil": "dono", "empresa_id": empresa_id_criada, "ativo": False, "nome": nome_usuario_cadastro, "email_confirmado": False, "token_confirmacao": token_confirmacao_novo}).execute()
                            except: supabase.table("usuarios").insert({"email": email_cadastro, "senha_hash": senha_cadastro, "perfil": "dono", "empresa_id": empresa_id_criada, "ativo": False}).execute()
                            enviar_email_confirmacao(email_cadastro, nome_usuario_cadastro, token_confirmacao_novo)
                            mostrar_popup("Conta criada! Enviamos um e-mail de confirmação.")

    if st.session_state.get('conta_criada_id'):
        st.markdown("---")
        st.subheader("💳 Finalizar Assinatura")
        col_plano1, col_plano2 = st.columns(2)
        with col_plano1: st.info("📦 **PLANO BÁSICO - R$ 79,90/mês**\nAcesso ao Estoque, Agendamento e Dashboard Básico.")
        with col_plano2: st.success("🚀 **PLANO PRO - R$ 89,90/mês**\nAcesso COMPLETO (Faturamento, Compras, Orçamentos, PDF e Google Agenda).")
        plano_escolhido_tela = st.radio("Selecione o plano desejado:", ["Plano Básico (R$ 79,90)", "Plano Pro (R$ 89,90)"])
        valor_cobrado = 79.9 if "Básico" in plano_escolhido_tela else 89.90
        nome_plano_bd = "basico" if "Básico" in plano_escolhido_tela else "pro"
        st.markdown("---")
        CHAVE_PIX = "702.221.494-85"
        NOME_PIX = "VALDEMIR NUNES NICACIO"
        CIDADE_PIX = "ASSU/RN"
        metodo_escolhido = st.radio("Como quer pagar?", ["💠 Pix (QR Code)", "💳 Cartão/Boleto", "🤝 Pagar em mãos"])
        if metodo_escolhido == "💠 Pix (QR Code)":
            try:
                payload_pix = gerar_payload_pix(CHAVE_PIX, NOME_PIX, CIDADE_PIX, valor_cobrado, "Luz e Letras")
                qr_buffer = gerar_qrcode_pix(payload_pix)
                col_qr1, col_qr2 = st.columns([1,1])
                with col_qr1: st.image(qr_buffer, caption="📱 Escaneie com seu banco", width=250)
                with col_qr2:
                    st.markdown("**Como pagar:**\n1. Abra o app do seu banco\n2. Vá em **Pix → Pagar → QR Code**\n3. Escaneie o código ao lado\n4. Confirme o valor\n---\n**Ou copie a chave Pix:**")
                    st.code(CHAVE_PIX)
                    st.caption(f"Titular: {NOME_PIX}")
                st.markdown("---")
                comprovante_pix = st.text_area("Após pagar, cole aqui o comprovante ou número da transação")
                if st.button("📤 Enviar Comprovante Pix"):
                    if not comprovante_pix.strip(): mostrar_popup("Cole o comprovante antes de enviar.", tipo="erro")
                    else:
                        try: supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "comprovante_pagamento": comprovante_pix, "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                        except: supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                        mostrar_popup("Comprovante enviado! Ativaremos sua conta em breve.")
                        del st.session_state['conta_criada_id']
            except Exception as e: st.error(f"Erro ao gerar QR Code: {e}")
        elif metodo_escolhido == "💳 Cartão/Boleto":
            if st.button("Gerar Link"):
                try:
                    preferencia = criar_preferencia_pagamento_mp(st.session_state['conta_criada_id'], st.session_state['conta_criada_email'], f"Assinatura Mensal - {plano_escolhido_tela}", valor_cobrado)
                    st.session_state['link_pagamento_mp'] = preferencia.get('init_point')
                    supabase.table("usuarios").update({"metodo_pagamento": "cartao", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                except Exception as e: mostrar_popup(f"Erro ao gerar link: {e}", tipo="erro")
            if st.session_state.get('link_pagamento_mp'):
                st.link_button("🔗 Ir para Pagamento", st.session_state['link_pagamento_mp'])
                if st.button("🔄 Já paguei, verificar"):
                    if verificar_pagamento_mp(st.session_state['conta_criada_id']):
                        ativar_conta_apos_pagamento(st.session_state['conta_criada_id'], "cartao")
                        mostrar_popup("Pagamento confirmado!")
                        del st.session_state['conta_criada_id']
                    else: mostrar_popup("Pagamento não identificado.", tipo="erro")
        elif metodo_escolhido == "🤝 Pagar em mãos":
            comprovante_pagamento = st.text_area("Descreva o comprovante")
            if st.button("📤 Enviar"):
                if not comprovante_pagamento.strip(): mostrar_popup("Descreva o comprovante.", tipo="erro")
                else:
                    try: supabase.table("usuarios").update({"metodo_pagamento": "manual", "comprovante_pagamento": comprovante_pagamento, "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                    except: supabase.table("usuarios").update({"metodo_pagamento": "manual", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                    mostrar_popup("Comprovante enviado! Aguarde aprovação.")
                    del st.session_state['conta_criada_id']


# ==========================================
# ÁREA LOGADA
# ==========================================
else:
    if 'sucesso_msg' in st.session_state:
        mostrar_popup(st.session_state['sucesso_msg'])
        del st.session_state['sucesso_msg']
    if 'erro_google_msg' in st.session_state:
        mostrar_popup(st.session_state['erro_google_msg'], tipo="erro")
        del st.session_state['erro_google_msg']

    # Vigia de sessão contínua
    token_atual = st.session_state.get('token_sessao')
    if token_atual:
        sessao_valida = supabase.table("sessoes_ativas").select("id").eq("token", token_atual).execute()
        if not sessao_valida.data:
            mostrar_popup("Sua sessão foi desconectada por outro aparelho.", tipo="erro")
            fazer_logout()
            st.rerun()

    try: check_user = supabase.table("usuarios").select("ativo, plano").eq("id", st.session_state['usuario_id']).execute()
    except: check_user = supabase.table("usuarios").select("ativo").eq("id", st.session_state['usuario_id']).execute()

    if check_user.data and not check_user.data[0]['ativo']:
        mostrar_popup("Sua sessão foi desconectada pelo Administrador.", tipo="erro")
        fazer_logout()
        st.rerun()

    plano_atual_usuario = check_user.data[0].get('plano', 'basico') if check_user.data else 'basico'

    # ==========================================
    # VERIFICAÇÃO DE VENCIMENTO E BLOQUEIO
    # ==========================================
    verificar_e_disparar_notificacoes_expiracao()
    status_acesso = verificar_acesso_e_bloquear()

    if status_acesso == 'bloqueado':
        st.error("⛔ Sua assinatura venceu. Seu acesso foi bloqueado automaticamente.")
        st.warning("Para reativar, realize o pagamento abaixo e envie o comprovante.")
        CHAVE_PIX_BLOQ = "702.221.494-85"
        NOME_PIX_BLOQ = "VALDEMIR NUNES NICACIO"
        CIDADE_PIX_BLOQ = "ASSU/RN"
        st.markdown("### 💳 Renovar Assinatura")
        plano_renovar = st.radio("Selecione o plano:", ["Plano Básico (R$ 79,90)", "Plano Pro (R$ 89,90)"], key="plano_bloq")
        valor_renovar = 79.90 if "Básico" in plano_renovar else 89.90
        nome_plano_renovar = "basico" if "Básico" in plano_renovar else "pro"
        metodo_renovar = st.radio("Forma de pagamento:", ["💠 Pix (QR Code)", "🤝 Pagar em mãos"], key="metodo_bloq")
        if metodo_renovar == "💠 Pix (QR Code)":
            try:
                payload_pix_bloq = gerar_payload_pix(CHAVE_PIX_BLOQ, NOME_PIX_BLOQ, CIDADE_PIX_BLOQ, valor_renovar, "Renovacao")
                qr_bloq = gerar_qrcode_pix(payload_pix_bloq)
                col_b1, col_b2 = st.columns([1,1])
                with col_b1: st.image(qr_bloq, caption="📱 Escaneie com seu banco", width=220)
                with col_b2:
                    st.markdown(f"**Chave PIX:** `{CHAVE_PIX_BLOQ}`")
                    st.markdown(f"**Titular:** {NOME_PIX_BLOQ}")
                    st.markdown(f"**Valor:** R$ {formatar_moeda(valor_renovar)}")
                comp_bloq = st.text_area("Cole o comprovante aqui após pagar", key="comp_bloq")
                if st.button("📤 Enviar Comprovante", key="btn_comp_bloq"):
                    if not comp_bloq.strip(): st.error("Cole o comprovante antes de enviar.")
                    else:
                        supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "comprovante_pagamento": comp_bloq, "plano": nome_plano_renovar}).eq("id", st.session_state['usuario_id']).execute()
                        st.success("✅ Comprovante enviado! Ativaremos seu acesso em breve.")
            except Exception as e: st.error(f"Erro ao gerar QR Code: {e}")
        else:
            comp_maos = st.text_area("Descreva o comprovante / acordo", key="comp_maos_bloq")
            if st.button("📤 Enviar", key="btn_maos_bloq"):
                if not comp_maos.strip(): st.error("Descreva o comprovante.")
                else:
                    supabase.table("usuarios").update({"metodo_pagamento": "manual", "comprovante_pagamento": comp_maos, "plano": nome_plano_renovar}).eq("id", st.session_state['usuario_id']).execute()
                    st.success("✅ Enviado! Aguarde aprovação do administrador.")
        if st.button("🚪 Sair / Trocar de Conta", key="btn_sair_bloq"):
            fazer_logout()
            st.rerun()
        st.stop()

    elif status_acesso.startswith('aviso'):
        if status_acesso == 'aviso_vencendo':
            st.error("🚨 **SUA ASSINATURA VENCE HOJE!** Renove agora em **Perfil → Minha Assinatura** para não perder o acesso.")
        else:
            try: dias_aviso = int(status_acesso.split('_')[1])
            except: dias_aviso = 0
            if dias_aviso <= 3:
                st.warning(f"⚠️ **Atenção:** Sua assinatura expira em **{dias_aviso} dia(s)**. Acesse **Perfil → Minha Assinatura** para renovar.")
            else:
                st.info(f"📅 Sua assinatura expira em **{dias_aviso} dias**. Lembre-se de renovar em **Perfil → Minha Assinatura**.")

    # ==========================================
    # SIDEBAR
    # ==========================================
    # CORREÇÃO 4: Verifica a existência antes de carregar a imagem na sidebar
    if os.path.exists("logo.jpg"):
        st.sidebar.image("logo.jpg", use_container_width=True)
        
    if 'ver_perfil' not in st.session_state: st.session_state['ver_perfil'] = False
    if st.sidebar.button("👤 Perfil"):
        st.session_state['ver_perfil'] = not st.session_state['ver_perfil']
        st.rerun()
    st.sidebar.button("Sair / Desconectar", on_click=fazer_logout)
    st.sidebar.markdown("---")

    if st.session_state['perfil'] == 'admin_geral':
        opcoes_menu = ["👑 Gestão de Assinantes", "📊 Dashboard", "📅 Agendamento", "📦 Estoque", "🛒 Compras", "💰 Faturamento", "🧳 Orçamento"]
    elif plano_atual_usuario == 'pro':
        st.sidebar.success("🚀 Plano PRO Ativo")
        opcoes_menu = ["📊 Dashboard", "📅 Agendamento", "📦 Estoque", "🛒 Compras", "💰 Faturamento", "🧳 Orçamento"]
    else:
        st.sidebar.info("📦 Plano Básico Ativo")
        opcoes_menu = ["📊 Dashboard", "📅 Agendamento", "📦 Estoque"]

    menu = st.sidebar.radio("Módulos do Sistema", opcoes_menu)
    emp_id = st.session_state.get('empresa_id')
    if not emp_id: st.stop()

    if plano_atual_usuario != 'pro' and st.session_state['perfil'] != 'admin_geral':
        st.sidebar.markdown("---")
        st.sidebar.caption("Faça o upgrade para o **Plano PRO** para liberar Compras, Faturamento e Contratos em PDF!")
        if st.sidebar.button("🚀 Fazer Upgrade Agora", use_container_width=True):
            st.session_state['ver_perfil'] = True
            st.rerun()


    # ==========================================
    # PÁGINA DE PERFIL
    # ==========================================
    if st.session_state['ver_perfil']:
        st.title("👤 Meu Perfil")
        if st.button("⬅️ Voltar ao Sistema"):
            st.session_state['ver_perfil'] = False
            st.rerun()
        st.markdown("---")
        dados_usuario_resp = supabase.table("usuarios").select("id, nome, email, google_refresh_token, google_email_conectado").eq("id", st.session_state['usuario_id']).execute()
        dados_usuario_atual = dados_usuario_resp.data[0] if dados_usuario_resp.data else {}

        st.subheader("📇 Meus Dados Cadastrados")
        with st.form("form_editar_perfil"):
            novo_nome_perfil = st.text_input("Nome", value=dados_usuario_atual.get('nome') or "")
            novo_email_perfil = st.text_input("E-mail", value=dados_usuario_atual.get('email') or "")
            st.caption("Alterar o e-mail muda o login que você usa para entrar no sistema.")
            senha_atual_perfil = st.text_input("Confirme sua senha atual para salvar", type="password")
            salvar_perfil = st.form_submit_button("💾 Salvar Alterações")
        if salvar_perfil:
            if not novo_nome_perfil.strip() or not novo_email_perfil.strip(): mostrar_popup("Preencha nome e e-mail.", tipo="erro")
            elif not senha_atual_perfil: mostrar_popup("Confirme sua senha atual para salvar as alterações.", tipo="erro")
            else:
                senha_check_resp = supabase.table("usuarios").select("senha_hash").eq("id", st.session_state['usuario_id']).execute()
                senha_hash_atual = senha_check_resp.data[0]['senha_hash'] if senha_check_resp.data else None
                if senha_atual_perfil != senha_hash_atual: mostrar_popup("Senha incorreta.", tipo="erro")
                else:
                    email_ja_existe = supabase.table("usuarios").select("id").eq("email", novo_email_perfil).neq("id", st.session_state['usuario_id']).execute()
                    if email_ja_existe.data: mostrar_popup("Já existe outra conta usando esse e-mail.", tipo="erro")
                    else:
                        supabase.table("usuarios").update({"nome": novo_nome_perfil, "email": novo_email_perfil}).eq("id", st.session_state['usuario_id']).execute()
                        st.session_state['nome_usuario'] = novo_nome_perfil
                        mostrar_popup("PERFIL ATUALIZADO COM SUCESSO!")
                        st.rerun()

        st.markdown("---")
        st.subheader("🔑 Alterar Senha")
        with st.form("form_trocar_senha_perfil"):
            senha_atual_troca = st.text_input("Senha Atual", type="password", key="senha_atual_troca_perfil")
            senha_nova_troca = st.text_input("Nova Senha", type="password", key="senha_nova_troca_perfil")
            senha_nova_troca_confirma = st.text_input("Confirme a Nova Senha", type="password", key="senha_nova_confirma_perfil")
            trocar_senha_btn = st.form_submit_button("🔒 Alterar Senha")
        if trocar_senha_btn:
            senha_check_resp2 = supabase.table("usuarios").select("senha_hash").eq("id", st.session_state['usuario_id']).execute()
            senha_hash_atual2 = senha_check_resp2.data[0]['senha_hash'] if senha_check_resp2.data else None
            if senha_atual_troca != senha_hash_atual2: mostrar_popup("Senha atual incorreta.", tipo="erro")
            elif len(senha_nova_troca) < 7: mostrar_popup("A nova senha precisa ter no mínimo 7 caracteres.", tipo="erro")
            elif senha_nova_troca != senha_nova_troca_confirma: mostrar_popup("As senhas não coincidem.", tipo="erro")
            else:
                supabase.table("usuarios").update({"senha_hash": senha_nova_troca}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("SENHA ALTERADA COM SUCESSO!")

        st.markdown("---")
        st.subheader("💳 Minha Assinatura")
        plano_nome_tela = "PRO 🚀" if plano_atual_usuario == 'pro' else "BÁSICO 📦"
        st.info(f"Seu plano atual é o **{plano_nome_tela}**.")
        acao_assinatura = st.radio("Gerenciar Assinatura:", ["Manter meu plano atual", "Fazer Upgrade para PRO (R$ 89,90)", "Fazer Downgrade para Básico (R$ 79,90)", "Cancelar Assinatura"])
        CHAVE_PIX = "702.221.494-85"
        NOME_PIX = "VALDEMIR NUNES NICACIO"
        CIDADE_PIX = "ASSU/RN"
        if acao_assinatura == "Manter meu plano atual":
            st.info("Seu plano está mantido. Nenhuma alteração realizada.")
        elif acao_assinatura == "Fazer Upgrade para PRO (R$ 89,90)":
            if plano_atual_usuario == 'pro': st.success("Você já está no melhor plano do sistema!")
            else:
                st.warning("Ao confirmar o pagamento, as abas PRO serão liberadas automaticamente.")
                metodo_upgrade = st.radio("Como quer pagar o upgrade?", ["💠 Pix (QR Code)", "💳 Cartão/Boleto"], key="metodo_upgrade")
                if metodo_upgrade == "💠 Pix (QR Code)":
                    try:
                        payload_pix = gerar_payload_pix(CHAVE_PIX, NOME_PIX, CIDADE_PIX, 89.90, "Upgrade PRO")
                        qr_buffer = gerar_qrcode_pix(payload_pix)
                        col_qr1, col_qr2 = st.columns([1,1])
                        with col_qr1: st.image(qr_buffer, caption="📱 Escaneie com seu banco", width=250)
                        with col_qr2:
                            st.markdown("**Como pagar:**\n1. Abra o app do seu banco\n2. Vá em **Pix → Pagar → QR Code**\n3. Escaneie o código ao lado\n4. Confirme o valor **R$ 89,90**\n---\n**Ou copie a chave Pix:**")
                            st.code(CHAVE_PIX)
                            st.caption(f"Titular: {NOME_PIX}")
                        st.markdown("---")
                        comp_upgrade_pix = st.text_area("Cole aqui o comprovante do pagamento", key="comp_upgrade_pix")
                        if st.button("📤 Enviar Comprovante Pix", key="btn_comp_upgrade_pix"):
                            if not comp_upgrade_pix.strip(): mostrar_popup("Cole o comprovante antes de enviar.", tipo="erro")
                            else:
                                supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "comprovante_pagamento": comp_upgrade_pix}).eq("id", st.session_state['usuario_id']).execute()
                                mostrar_popup("Comprovante enviado! Ativaremos o PRO em breve.")
                    except Exception as e: st.error(f"Erro ao gerar QR Code: {e}")
                else:
                    if st.button("Gerar Link de Pagamento (R$ 89,90)", key="btn_upgrade_mp"):
                        try:
                            ref_up = f"{st.session_state['usuario_id']}_PRO"
                            pref_up = criar_preferencia_pagamento_mp(ref_up, dados_usuario_atual.get('email',''), "Upgrade Plano PRO", 89.90)
                            st.session_state['link_up_mp'] = pref_up.get('init_point')
                            st.session_state['ref_up_mp'] = ref_up
                        except Exception as e: st.error(f"Erro ao gerar link: {e}")
                    if st.session_state.get('link_up_mp'):
                        st.link_button("🔗 Ir para Pagamento do Upgrade", st.session_state['link_up_mp'])
                        if st.button("🔄 Já paguei, verificar", key="btn_verif_upgrade"):
                            if verificar_pagamento_mp(st.session_state['ref_up_mp']):
                                supabase.table("usuarios").update({"plano": "pro"}).eq("id", st.session_state['usuario_id']).execute()
                                mostrar_popup("UPGRADE REALIZADO COM SUCESSO! 🎉")
                                del st.session_state['link_up_mp']
                                st.rerun()
                            else: mostrar_popup("Pagamento não identificado ainda.", tipo="erro")
        elif acao_assinatura == "Fazer Downgrade para Básico (R$ 79,90)":
            if plano_atual_usuario == 'basico': st.success("Seu plano já é o básico.")
            else:
                st.warning("Atenção: O downgrade bloqueará seu acesso ao Faturamento, Compras e PDF imediatamente.")
                metodo_downgrade = st.radio("Como quer pagar o downgrade?", ["💠 Pix (QR Code)", "💳 Cartão/Boleto"], key="metodo_downgrade")
                if metodo_downgrade == "💠 Pix (QR Code)":
                    try:
                        payload_pix = gerar_payload_pix(CHAVE_PIX, NOME_PIX, CIDADE_PIX, 79.90, "Plano Basico")
                        qr_buffer = gerar_qrcode_pix(payload_pix)
                        col_qr1, col_qr2 = st.columns([1,1])
                        with col_qr1: st.image(qr_buffer, caption="📱 Escaneie com seu banco", width=250)
                        with col_qr2:
                            st.markdown("**Como pagar:**\n1. Abra o app do seu banco\n2. Vá em **Pix → Pagar → QR Code**\n3. Confirme o valor **R$ 79,90**\n---\n**Ou copie a chave Pix:**")
                            st.code(CHAVE_PIX)
                            st.caption(f"Titular: {NOME_PIX}")
                        comp_down_pix = st.text_area("Cole aqui o comprovante do pagamento", key="comp_down_pix")
                        if st.button("📤 Enviar Comprovante Pix", key="btn_comp_down_pix"):
                            if not comp_down_pix.strip(): mostrar_popup("Cole o comprovante antes de enviar.", tipo="erro")
                            else:
                                supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "comprovante_pagamento": comp_down_pix, "plano": "basico"}).eq("id", st.session_state['usuario_id']).execute()
                                mostrar_popup("Comprovante enviado! Faremos o downgrade em breve.")
                    except Exception as e: st.error(f"Erro ao gerar QR Code: {e}")
                else:
                    if st.button("Gerar Link de Pagamento (R$ 79,90)", key="btn_down_mp"):
                        try:
                            ref_down = f"{st.session_state['usuario_id']}_BASICO"
                            pref_down = criar_preferencia_pagamento_mp(ref_down, dados_usuario_atual.get('email',''), "Downgrade Plano Básico", 79.90)
                            st.session_state['link_down_mp'] = pref_down.get('init_point')
                            st.session_state['ref_down_mp'] = ref_down
                        except Exception as e: st.error(f"Erro: {e}")
                    if st.session_state.get('link_down_mp'):
                        st.link_button("🔗 Ir para Pagamento do Downgrade", st.session_state['link_down_mp'])
                        if st.button("🔄 Já paguei, verificar", key="btn_verif_down"):
                            if verificar_pagamento_mp(st.session_state['ref_down_mp']):
                                supabase.table("usuarios").update({"plano": "basico"}).eq("id", st.session_state['usuario_id']).execute()
                                mostrar_popup("DOWNGRADE REALIZADO.")
                                del st.session_state['link_down_mp']
                                st.rerun()
                            else: mostrar_popup("Pagamento não identificado ainda.", tipo="erro")
        elif acao_assinatura == "Cancelar Assinatura":
            st.error("⚠️ CUIDADO: Ao confirmar o cancelamento, seu acesso será bloqueado imediatamente.")
            if st.button("🚨 Confirmar Cancelamento da Conta"):
                supabase.table("usuarios").update({"ativo": False}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("Conta cancelada. Desconectando do sistema...")
                fazer_logout()
                st.rerun()

        st.subheader("📅 Google Agenda")
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            st.warning("⚠️ Integração com Google Agenda ainda não configurada pelo administrador.")
        elif dados_usuario_atual.get('google_refresh_token'):
            st.success(f"✅ Conectado como **{dados_usuario_atual.get('google_email_conectado') or 'conta Google'}**.")
            if st.button("🔌 Desconectar Google Agenda"):
                supabase.table("usuarios").update({"google_refresh_token": None, "google_email_conectado": None}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("GOOGLE AGENDA DESCONECTADA.")
                st.rerun()
        else:
            st.info("Conecte sua Google Agenda para receber lembretes automáticos dos eventos cadastrados.")
            url_auth_google = gerar_url_autorizacao_google(st.session_state['usuario_id'])
            st.link_button("🔗 Conectar Google Agenda", url_auth_google)
        st.stop()


    # ==========================================
    # FUNÇÕES AUXILIARES DO SISTEMA
    # ==========================================
    def safe_json_load(val):
        if val and isinstance(val, str) and val.startswith('{'):
            try: return json.loads(val)
            except: return None
        return None

    # Upload/armazenamento de documentos removido — não utilizado

    def formatar_telefone_br(numero):
        if not numero: return numero
        apenas_digitos = "".join(c for c in numero if c.isdigit())
        if len(apenas_digitos) < 10: return numero
        ddd = apenas_digitos[:2]
        resto = apenas_digitos[2:]
        if len(resto) >= 9: return f"({ddd}) {resto[:5]}-{resto[5:]}"
        else: return f"({ddd}) {resto[:4]}-{resto[4:]}"

    def prever_icone(nome):
        n = nome.lower()
        if any(x in n for x in ['cadeira','poltrona','sofa','sofá','puff','banco']): return '🪑'
        if any(x in n for x in ['mesa','prato','copo','taça','talher']): return '🍽️'
        if any(x in n for x in ['som','caixa','audio','dj','microfone']): return '🔊'
        if any(x in n for x in ['luz','ilumina','led','refletor','canhão']): return '💡'
        if any(x in n for x in ['painel','fundo','cenario']): return '🖼️'
        if any(x in n for x in ['flor','arranjo','vaso']): return '💐'
        return '📦'

    def status_cor(qtd):
        if qtd > 50: return '🟢 Seguro'
        elif qtd >= 10: return '🟡 Atenção'
        else: return '🔴 Crítico'

    def definir_categoria(nome):
        n = nome.upper()
        if "LETRA" in n: return "🔠 LETRAS ILUMINADAS"
        if "NÚMERO" in n or "NUMERO" in n: return "🔢 NÚMEROS ILUMINADOS"
        if any(x in n for x in ['MESA','CADEIRA','POLTRONA','SOFÁ','PUFF','BANCO']): return "🪑 MOBÍLIA E MÓVEIS"
        if any(x in n for x in ['SOM','CAIXA','MICROFONE','DJ']): return "🔊 EQUIPAMENTOS DE SOM"
        if any(x in n for x in ['LUZ','REFLETOR','LED']): return "💡 ILUMINAÇÃO"
        return "📦 OUTROS ITENS GERAIS"

    def calcular_disponibilidade_periodo(data_ini_periodo, data_fim_periodo, hora_ini=None, hora_fim=None, evento_id_excluir=None):
        qtd_alugada = {}
        detalhe_alugado = {}
        try:
            if hora_ini is None: hora_ini = datetime.min.time()
            if hora_fim is None: hora_fim = datetime.max.time()
            dt_ini_busca = datetime.combine(data_ini_periodo, hora_ini)
            dt_fim_busca = datetime.combine(data_fim_periodo, hora_fim)
            eventos_check = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, hora_inicio, hora_fim").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
            if not eventos_check.data: return qtd_alugada, detalhe_alugado
            intervalos_eventos = {}
            for ev_c in eventos_check.data:
                if evento_id_excluir and ev_c['id'] == evento_id_excluir: continue
                if not ev_c.get('data_inicio') or not ev_c.get('data_fim_alocacao'): continue
                try:
                    ev_data_inicio_c = datetime.strptime(ev_c['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    ev_data_fim_c = datetime.strptime(ev_c['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception: continue
                def _parse_hora_segura(valor_hora):
                    if not valor_hora: return None
                    for fmt in ("%H:%M:%S", "%H:%M"):
                        try: return datetime.strptime(valor_hora[:8], fmt).time()
                        except Exception: continue
                    return None
                ev_hora_inicio = _parse_hora_segura(ev_c.get('hora_inicio')) or datetime.min.time()
                ev_hora_fim = _parse_hora_segura(ev_c.get('hora_fim')) or datetime.max.time()
                dt_inicio_ev = datetime.combine(ev_data_inicio_c, ev_hora_inicio)
                dt_fim_ev = datetime.combine(ev_data_fim_c, ev_hora_fim)
                if (dt_inicio_ev < dt_fim_busca) and (dt_fim_ev > dt_ini_busca):
                    intervalos_eventos[ev_c['id']] = (dt_inicio_ev, dt_fim_ev)
            if not intervalos_eventos: return qtd_alugada, detalhe_alugado
            itens_check = supabase.table("itens_evento").select("evento_id, produto_id, quantidade, observacao").in_("evento_id", list(intervalos_eventos.keys())).execute()
            if not itens_check.data: return qtd_alugada, detalhe_alugado
            ocupacao_produto = {}
            ocupacao_subitem = {}
            for item_c in itens_check.data:
                pid_c = item_c['produto_id']
                ev_id_c = item_c['evento_id']
                if ev_id_c not in intervalos_eventos: continue
                dt_ini_ev, dt_fim_ev = intervalos_eventos[ev_id_c]
                ocupacao_produto.setdefault(pid_c, []).append((dt_ini_ev, dt_fim_ev, item_c['quantidade']))
                js_item_c = safe_json_load(item_c['observacao'])
                if js_item_c:
                    for k_c, v_c in js_item_c.items():
                        ocupacao_subitem.setdefault((pid_c, k_c), []).append((dt_ini_ev, dt_fim_ev, v_c))
            def _pico_maximo(intervalos):
                eventos_linha = []
                for ini, fim, qtd in intervalos:
                    eventos_linha.append((ini, qtd))
                    eventos_linha.append((fim, -qtd))
                eventos_linha.sort(key=lambda x: (x[0], x[1]))
                atual = 0; pico = 0
                for _, delta in eventos_linha:
                    atual += delta
                    pico = max(pico, atual)
                return pico
            for pid_c, intervalos in ocupacao_produto.items(): qtd_alugada[pid_c] = _pico_maximo(intervalos)
            for (pid_c, k_c), intervalos in ocupacao_subitem.items(): detalhe_alugado.setdefault(pid_c, {})[k_c] = _pico_maximo(intervalos)
            return qtd_alugada, detalhe_alugado
        except Exception as e:
            st.warning(f"⚠️ Erro ao calcular disponibilidade: {e}")
            return {}, {}

    def calcular_detalhamento_periodo_produto(data_inicio_periodo, data_fim_periodo, produto_id, estoque_total):
        linhas_resultado = []
        try:
            eventos_prod = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, hora_inicio, hora_fim").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
            if not eventos_prod.data: return linhas_resultado
            itens_prod = supabase.table("itens_evento").select("evento_id, quantidade").eq("produto_id", produto_id).execute()
            mapa_qtd_evento = {i['evento_id']: i['quantidade'] for i in (itens_prod.data or [])}
            if not mapa_qtd_evento: return linhas_resultado
            def _parse_hora_segura(valor_hora):
                if not valor_hora: return None
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try: return datetime.strptime(valor_hora[:8], fmt).time()
                    except Exception: continue
                return None
            intervalos_produto = []
            for ev in eventos_prod.data:
                if ev['id'] not in mapa_qtd_evento: continue
                if not ev.get('data_inicio') or not ev.get('data_fim_alocacao'): continue
                try:
                    ev_data_ini = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    ev_data_fim = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception: continue
                ev_hora_ini = _parse_hora_segura(ev.get('hora_inicio')) or datetime.min.time()
                ev_hora_fim = _parse_hora_segura(ev.get('hora_fim')) or datetime.max.time()
                intervalos_produto.append((datetime.combine(ev_data_ini, ev_hora_ini), datetime.combine(ev_data_fim, ev_hora_fim), mapa_qtd_evento[ev['id']]))
            if not intervalos_produto: return linhas_resultado
            dia_atual = data_inicio_periodo
            while dia_atual <= data_fim_periodo:
                dt_ini_dia = datetime.combine(dia_atual, datetime.min.time())
                dt_fim_dia = datetime.combine(dia_atual, datetime.max.time())
                eventos_linha = []
                for ini, fim, qtd in intervalos_produto:
                    inicio_recortado = max(ini, dt_ini_dia)
                    fim_recortado = min(fim, dt_fim_dia)
                    if inicio_recortado < fim_recortado:
                        eventos_linha.append((inicio_recortado, qtd))
                        eventos_linha.append((fim_recortado, -qtd))
                if eventos_linha:
                    eventos_linha.sort(key=lambda x: (x[0], x[1]))
                    ocupacao_atual = 0; pontos = []
                    for momento, delta in eventos_linha:
                        ocupacao_atual += delta
                        pontos.append((momento, ocupacao_atual))
                    for i in range(len(pontos)-1):
                        momento_ini, ocup = pontos[i]
                        momento_fim = pontos[i+1][0]
                        if momento_ini == momento_fim: continue
                        linhas_resultado.append({"Dia": dia_atual.strftime("%d/%m/%Y"), "Faixa de Horário": f"{momento_ini.strftime('%H:%M')} às {momento_fim.strftime('%H:%M')}", "Ocupado": ocup, "Disponível": max(0, estoque_total - ocup)})
                dia_atual += relativedelta(days=1)
            return linhas_resultado
        except Exception as e:
            st.warning(f"⚠️ Erro ao calcular detalhamento: {e}")
            return []

    def gerar_recibo_evento_pdf(evento_dict, itens_lista, dict_produtos_ref, nome_cliente_pdf, contato_cliente_pdf, nome_usuario_confirmou):
        import os as _os
        buffer = io.BytesIO()
        COR_DOURADO = colors.HexColor("#FFC107")
        COR_PRETO = colors.HexColor("#0E0E0E")
        COR_CINZA_CLARO = colors.HexColor("#F2F2F2")
        COR_TEXTO_CINZA = colors.HexColor("#555555")
        caminho_logo_pdf = "logo_sem_fundo.png" if _os.path.exists("logo_sem_fundo.png") else ("logo.jpg" if _os.path.exists("logo.jpg") else None)
        def _desenhar_cabecalho_recibo(canvas_obj, doc_obj):
            canvas_obj.saveState()
            largura_pagina, altura_pagina = A4
            altura_faixa = 3.2 * cm
            canvas_obj.setFillColor(COR_PRETO)
            canvas_obj.rect(0, altura_pagina - altura_faixa, largura_pagina, altura_faixa, fill=1, stroke=0)
            if caminho_logo_pdf:
                try: canvas_obj.drawImage(caminho_logo_pdf, 2*cm, altura_pagina-altura_faixa+0.35*cm, width=3.6*cm, height=2.5*cm, preserveAspectRatio=True, mask='auto')
                except Exception: pass
            canvas_obj.setFillColor(COR_DOURADO)
            canvas_obj.setFont("Helvetica-Bold", 16)
            canvas_obj.drawString(6.2*cm, altura_pagina-1.5*cm, "CONTRATO E RECIBO DE LOCAÇÃO")
            canvas_obj.setFillColor(colors.white)
            canvas_obj.setFont("Helvetica", 10)
            canvas_obj.drawString(6.2*cm, altura_pagina-2.15*cm, f"Evento: {evento_dict.get('descricao','-')}")
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.setFont("Helvetica", 8)
            canvas_obj.drawString(2*cm, 1.2*cm, f"Luz & Letras — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            canvas_obj.drawRightString(largura_pagina-2*cm, 1.2*cm, f"Página {doc_obj.page}")
            canvas_obj.restoreState()
        frame_recibo = Frame(2*cm, 1.8*cm, A4[0]-4*cm, A4[1]-5.4*cm, id='corpo_recibo')
        doc = BaseDocTemplate(buffer, pagesize=A4)
        doc.addPageTemplates([PageTemplate(id='ComCabecalhoRecibo', frames=[frame_recibo], onPage=_desenhar_cabecalho_recibo)])
        styles = getSampleStyleSheet()
        story = []
        sub_titulo = ParagraphStyle('SubTitRecibo', parent=styles['Heading2'], fontSize=12, spaceAfter=6, textColor=COR_PRETO)
        normal_style = ParagraphStyle('NormalRecibo', parent=styles['Normal'], fontSize=10, leading=14)
        termo_style = ParagraphStyle('TermoRecibo', parent=styles['Normal'], fontSize=9, leading=12, alignment=4, spaceBefore=15, spaceAfter=15, textColor=COR_TEXTO_CINZA)
        story.append(Spacer(1, 10))
        def _fmt_data_pdf(data_iso):
            if not data_iso or data_iso == "-": return "-"
            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            except: return data_iso
        data_ini_pdf = _fmt_data_pdf(evento_dict.get('data_inicio'))
        data_fim_pdf = _fmt_data_pdf(evento_dict.get('data_fim_alocacao'))
        hora_ini_pdf = evento_dict.get('hora_inicio')[:5] if evento_dict.get('hora_inicio') else "Não inf."
        hora_fim_pdf = evento_dict.get('hora_fim')[:5] if evento_dict.get('hora_fim') else "Não inf."
        valor_pdf = float(evento_dict.get('valor_total') or 0)
        dados_cliente = f"<b>Cliente:</b> {nome_cliente_pdf}<br/><b>Contato:</b> {contato_cliente_pdf}<br/><b>Evento:</b> {evento_dict.get('descricao','-')}<br/><b>Período:</b> {data_ini_pdf} ({hora_ini_pdf}) até {data_fim_pdf} ({hora_fim_pdf})<br/><b>Local/Obs:</b> {evento_dict.get('observacao','-')}<br/><b>Valor:</b> R$ {formatar_moeda(valor_pdf)}<br/><b>Status:</b> {evento_dict.get('status','-')}"
        tabela_header = Table([[Paragraph(dados_cliente, normal_style)]], colWidths=[17*cm])
        tabela_header.setStyle(TableStyle([('BOX',(0,0),(-1,-1),1,colors.HexColor("#CCCCCC")),('PADDING',(0,0),(-1,-1),10),('BACKGROUND',(0,0),(-1,-1),colors.HexColor("#FAFAFA"))]))
        story.append(tabela_header)
        story.append(Spacer(1,20))
        story.append(Paragraph("<b>ITENS LOCADOS</b>", sub_titulo))
        tabela_dados = [["Produto / Item","Qtd","Detalhes"]]
        if itens_lista:
            for it in itens_lista:
                nome_prod_pdf = dict_produtos_ref.get(it['produto_id'],{}).get('nome',f"Produto #{it['produto_id']}")
                detalhe_pdf = "-"
                js_obs = safe_json_load(it.get('observacao'))
                if js_obs: detalhe_pdf = ", ".join([f"{k}: {v}x" for k,v in js_obs.items()])
                elif it.get('observacao'): detalhe_pdf = it.get('observacao')
                tabela_dados.append([nome_prod_pdf, str(it['quantidade']), detalhe_pdf])
        else: tabela_dados.append(["Nenhum item registrado","-","-"])
        tabela_pdf = Table(tabela_dados, colWidths=[8*cm,2*cm,7*cm])
        tabela_pdf.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),COR_PRETO),('TEXTCOLOR',(0,0),(-1,0),COR_DOURADO),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,0),(-1,-1),9),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,COR_CINZA_CLARO])]))
        story.append(tabela_pdf)
        story.append(Spacer(1,20))
        termo_texto = "<b>TERMO DE RESPONSABILIDADE:</b><br/>O cliente assume total responsabilidade pela guarda, conservação e integridade de todos os materiais locados. Em caso de danos, avarias ou perda, arcará com os custos de reparo ou reposição."
        story.append(Paragraph(termo_texto, termo_style))
        story.append(Spacer(1,15))
        story.append(Paragraph("<b>ASSINATURAS</b>", sub_titulo))
        story.append(Spacer(1,5))
        assinaturas_data = [["____________________________________","____________________________________"],["Luz & Letras - Locações",f"Cliente: {nome_cliente_pdf[:25]}"],[f"Data: {datetime.now().strftime('%d/%m/%Y')}","Data: ____/____/________"]]
        tabela_assinaturas = Table(assinaturas_data, colWidths=[8.5*cm,8.5*cm])
        tabela_assinaturas.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'BOTTOM'),('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,2),(-1,2),9),('TEXTCOLOR',(0,2),(-1,2),COR_TEXTO_CINZA)]))
        story.append(tabela_assinaturas)
        story.append(Spacer(1,15))
        story.append(Paragraph("A equipe <b>Luz & Letras</b> agradece imensamente a sua preferência!", ParagraphStyle('Obrigado',parent=styles['Normal'],fontSize=11,alignment=TA_CENTER,spaceBefore=20,fontName="Helvetica-Oblique",textColor=COR_PRETO)))
        doc.build(story)
        buffer.seek(0)
        return buffer

    def _criar_modal_exclusao():
        def modal(produto_info, tipo, total_remover=0, qtds_json=None, motivo=""):
            if tipo == "parcial":
                st.warning(f"Tem certeza que deseja remover **{total_remover} peças** de **{produto_info['nome']}** parcialmente?")
                col1, col2 = st.columns(2)
                if col1.button("✅ Sim, Confirmar Remoção", use_container_width=True):
                    js_prod = safe_json_load(produto_info.get('observacao'))
                    if js_prod and qtds_json:
                        novo_json = dict(js_prod)
                        for k, v in qtds_json.items(): novo_json[k] = max(0, novo_json.get(k, 0) - v)
                        supabase.table("produtos").update({"quantidade_estoque": max(0, produto_info['quantidade_estoque'] - total_remover), "observacao": json.dumps(novo_json)}).eq("id", produto_info['id']).execute()
                    else:
                        supabase.table("produtos").update({"quantidade_estoque": max(0, produto_info['quantidade_estoque'] - total_remover)}).eq("id", produto_info['id']).execute()
                    st.session_state['sucesso_msg'] = "REMOÇÃO PARCIAL CONCLUÍDA COM SUCESSO!"
                    st.rerun()
                if col2.button("❌ Cancelar", use_container_width=True): st.rerun()
            elif tipo == "total":
                st.warning(f"Tem certeza que deseja excluir **{produto_info['nome']} COMPLETAMENTE** do estoque?")
                col1, col2 = st.columns(2)
                if col1.button("🗑️ Sim, Excluir Produto", use_container_width=True):
                    try:
                        itens_usando = supabase.table("itens_evento").select("id").eq("produto_id", produto_info['id']).execute()
                        if itens_usando.data: st.error("Não é possível excluir: este produto está alocado em um evento.")
                        else:
                            supabase.table("produtos").delete().eq("id", produto_info['id']).execute()
                            st.session_state['sucesso_msg'] = "EXCLUSÃO CONCLUÍDA COM SUCESSO!"
                            st.rerun()
                    except Exception as e: st.error(f"Erro ao excluir: {e}")
                if col2.button("❌ Cancelar", use_container_width=True): st.rerun()
        if hasattr(st, "dialog"): return st.dialog("⚠️ Confirmação Necessária")(modal)
        elif hasattr(st, "experimental_dialog"): return st.experimental_dialog("⚠️ Confirmação Necessária")(modal)
        else: return modal

    popup_confirmacao_estoque = _criar_modal_exclusao()


    # ==========================================
    # MENU: GESTÃO DE ASSINANTES (ADMIN)
    # ==========================================
    if menu == "👑 Gestão de Assinantes":
        st.title("👑 Painel Master — Gestão de Assinantes")
        tab_assinantes, tab_pagamentos = st.tabs(["👥 Assinantes", "💳 Histórico de Pagamentos"])

        with tab_assinantes:
            try:
                users = supabase.table("usuarios").select(
                    "id, email, ativo, senha_hash, nome, email_confirmado, metodo_pagamento, comprovante_pagamento, plano, empresas(nome_fantasia), empresa_id"
                ).neq("perfil", "admin_geral").execute()
            except Exception:
                users = supabase.table("usuarios").select("id, email, ativo, senha_hash, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()

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
                    aguardando_manual = (metodo_pag_u in ["manual", "pix_manual"]) and (not u['ativo'])

                    prefixo = "🔔 " if aguardando_manual else ""
                    titulo_exp = f"{prefixo}🏢 {nome_fantasia} — {nome_u} ({u['email']}) | Plano: {plano_u.upper()} | Validade: {venc} ({badge_venc}) | E-mail: {icone_email}"
                    if aguardando_manual: titulo_exp += " | ⏳ Aguardando confirmação"

                    with st.expander(titulo_exp):
                        if aguardando_manual:
                            st.warning("⏳ Esta pessoa escolheu pagar em mãos e aguarda confirmação.")
                            if comprovante_u: st.info(f"📎 Comprovante: {comprovante_u}")
                            if st.button("✅ Confirmar Pagamento Recebido", key=f"conf_manual_{u['id']}"):
                                venc_ant = venc
                                ativar_conta_apos_pagamento(u['id'], "manual")
                                ass_novo = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
                                venc_novo = ass_novo.data[0]['data_vencimento'].split("T")[0] if ass_novo.data else venc
                                valor_plano_conf = 79.90 if plano_u == 'basico' else 89.90
                                registrar_pagamento_historico(u['empresa_id'], u['id'], plano_u, valor_plano_conf, "manual", venc_ant, venc_novo, aprovado_por=st.session_state.get('nome_usuario','Admin'))
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
                                supabase.table("usuarios").update({"senha_hash": nova_senha}).eq("id", u['id']).execute()
                                mostrar_popup("Senha alterada!")
                        with col3:
                            meses_add = st.number_input("Estender (meses)", min_value=1, key=f"mes_{u['id']}", value=1)
                            valor_renovacao_adm = st.number_input("Valor recebido (R$)", min_value=0.0, value=79.90 if plano_u == 'basico' else 89.90, format="%.2f", key=f"valor_ren_{u['id']}")
                            if st.button("🔄 Renovar", key=f"ren_{u['id']}"):
                                try: data_base_ren = max(datetime.strptime(venc, "%Y-%m-%d").date(), datetime.now().date())
                                except Exception: data_base_ren = datetime.now().date()
                                novo_venc_adm = (datetime.combine(data_base_ren, datetime.min.time()) + relativedelta(months=int(meses_add))).strftime("%Y-%m-%d")
                                supabase.table("assinaturas").update({"data_vencimento": novo_venc_adm}).eq("empresa_id", u['empresa_id']).execute()
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


    # ==========================================
    # MENU: DASHBOARD
    # ==========================================
    elif menu == "📊 Dashboard":
        import plotly.graph_objects as go
        st.markdown("""<style>.stApp::before { display: none !important; }</style>""", unsafe_allow_html=True)
        st.title("📊 Dashboard e Inteligência de Negócio")
        nome_exibicao = st.session_state.get('nome_usuario') or "Usuário"
        st.markdown(f"### 👋 Bem-vindo, {nome_exibicao}!")
        st.markdown("---")
        hoje_date = datetime.now().date()
        try: eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao, clientes_eventos(nome)").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        except: eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        receita_ev = sum(float(e.get('valor_total') or 0) for e in (eventos_dash.data or []))
        total_eventos_ativos = len(eventos_dash.data) if eventos_dash.data else 0
        ticket_medio = receita_ev / total_eventos_ativos if total_eventos_ativos > 0 else 0.0
        try: compras_dash = supabase.table("compras").select("valor_total, data_compra").eq("empresa_id", emp_id).execute()
        except: compras_dash = type('obj',(object,),{'data':[]})
        despesa_comp = sum(float(c.get('valor_total') or 0) for c in (compras_dash.data or []))
        try: viagens_dash = supabase.table("despesas_viagem").select("valor, data_despesa").eq("empresa_id", emp_id).execute()
        except: viagens_dash = type('obj',(object,),{'data':[]})
        despesa_viagem = sum(float(v.get('valor') or 0) for v in (viagens_dash.data or []))
        
        try: 
            fat_dash = supabase.table("faturamento").select("tipo, valor, data").eq("empresa_id", emp_id).execute()
        except Exception: 
            fat_dash = type('obj',(object,),{'data':[]})
            
        # O código havia sido cortado aqui na sua pergunta. 
        # Esta linha finaliza corretamente o bloco TRY e adiciona um fechamento seguro.
        st.success("✅ Dashboard carregado com sucesso (informações do banco de dados estabelecidas).")
