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

st.set_page_config(page_title="Luz & Letras", page_icon="logo.jpg", layout="wide")

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

import extra_streamlit_components as stx

# Isso inicializa o novo sistema de cookies de forma mais simples
cookie_manager = stx.CookieManager()


# ==========================================
# CONTROLE DE SESSÃO
# ==========================================
def fazer_logout():
    token_atual = st.session_state.get("token_sessao")
    if token_atual:
        try: supabase.table("sessoes_ativas").delete().eq("token", token_atual).execute()
        except: pass
    try:
        cookie_manager.delete("tk", key="del_tk_logout")
        cookie_manager.delete("uid", key="del_uid_logout")
    except Exception:
        pass
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None})

def restaurar_sessao_por_token():
    try:
        tk_param = cookie_manager.get("tk")
        uid_param = cookie_manager.get("uid")
        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)
            sessao_banco = supabase.table("sessoes_ativas").select("id").eq("token", tk_param).eq("usuario_id", usuario_id_restaurar).execute()
            if not sessao_banco.data:
                try:
                    cookie_manager.delete("tk", key="del_tk_restaurar")
                    cookie_manager.delete("uid", key="del_uid_restaurar")
                except Exception:
                    pass
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
def gerar_codigo_recuperacao():
    import random
    return str(random.randint(100000, 999999))

def enviar_email_codigo_recuperacao(destinatario, nome_destinatario, codigo):
    corpo = f"""Olá {nome_destinatario},

Seu código de verificação para redefinir sua senha é: {codigo}

Este código expira em 15 minutos.

Se você não solicitou essa alteração, apenas ignore este e-mail.

Atenciosamente,
Equipe Luz & Letras
"""
    msg = MIMEText(corpo)
    msg['Subject'] = "Código de Recuperação de Senha - Luz & Letras"
    msg['From'] = GMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as servidor:
            servidor.login(GMAIL_REMETENTE, GMAIL_SENHA_APP)
            servidor.sendmail(GMAIL_REMETENTE, destinatario, msg.as_string())
        return True
    except Exception:
        return False

def validar_senha_forte(senha):
    import re
    return {
        "Mínimo de 7 caracteres": len(senha or "") >= 7,
        "Pelo menos uma letra maiúscula": bool(re.search(r'[A-Z]', senha or "")),
        "Pelo menos um número": bool(re.search(r'[0-9]', senha or "")),
    }    

# ==========================================
# TELA DE LOGIN
# ==========================================
if not st.session_state['logado']:
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
                        cookie_manager.set("tk", novo_token, key="set_tk_login")
                        cookie_manager.set("uid", str(usuario['id']), key="set_uid_login")
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
    with st.expander("🔑 Esqueceu a senha? Clique aqui"):
        if 'recuperacao_etapa' not in st.session_state:
            st.session_state['recuperacao_etapa'] = 'email'

        # ---------- ETAPA 1: INFORMAR E-MAIL ----------
        if st.session_state['recuperacao_etapa'] == 'email':
            st.caption("Informe o e-mail cadastrado na sua conta. Enviaremos um código de verificação para você redefinir a senha.")
            with st.form("form_recuperar_email"):
                email_recuperacao = st.text_input("Seu E-mail", key="input_email_recuperacao")
                enviar_codigo_btn = st.form_submit_button("📨 Enviar Código de Verificação")
            if enviar_codigo_btn:
                if not email_recuperacao.strip():
                    mostrar_popup("Informe o e-mail cadastrado.", tipo="erro")
                else:
                    usuario_recup = supabase.table("usuarios").select("id, nome, email").eq("email", email_recuperacao.strip()).execute()
                    if not usuario_recup.data:
                        mostrar_popup("Não encontramos nenhuma conta com esse e-mail.", tipo="erro")
                    else:
                        dados_usuario_recup = usuario_recup.data[0]
                        codigo_gerado = gerar_codigo_recuperacao()
                        expira_em = (datetime.now() + relativedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                        try:
                            supabase.table("usuarios").update({
                                "codigo_recuperacao": codigo_gerado,
                                "codigo_recuperacao_expira": expira_em
                            }).eq("id", dados_usuario_recup['id']).execute()
                            nome_dest_recup = dados_usuario_recup.get('nome') or dados_usuario_recup['email']
                            if enviar_email_codigo_recuperacao(dados_usuario_recup['email'], nome_dest_recup, codigo_gerado):
                                st.session_state['recuperacao_usuario_id'] = dados_usuario_recup['id']
                                st.session_state['recuperacao_email'] = dados_usuario_recup['email']
                                st.session_state['recuperacao_etapa'] = 'codigo'
                                mostrar_popup("Código enviado! Verifique sua caixa de entrada.")
                                st.rerun()
                        except Exception as e:
                            mostrar_popup(f"Erro ao gerar o código de recuperação: {e}", tipo="erro")

        # ---------- ETAPA 2: CONFIRMAR CÓDIGO ----------
        elif st.session_state['recuperacao_etapa'] == 'codigo':
            st.caption(f"Digite o código de 6 dígitos enviado para **{st.session_state.get('recuperacao_email','')}**.")
            codigo_digitado = st.text_input("Código de Verificação", max_chars=6, key="input_codigo_recuperacao")
            col_rc1, col_rc2, col_rc3 = st.columns(3)
            with col_rc1:
                if st.button("✅ Verificar Código"):
                    if not codigo_digitado.strip():
                        mostrar_popup("Digite o código recebido por e-mail.", tipo="erro")
                    else:
                        checagem = supabase.table("usuarios").select("codigo_recuperacao, codigo_recuperacao_expira").eq("id", st.session_state['recuperacao_usuario_id']).execute()
                        if not checagem.data or not checagem.data[0].get('codigo_recuperacao'):
                            mostrar_popup("Código não encontrado. Solicite um novo.", tipo="erro")
                        else:
                            codigo_salvo = checagem.data[0]['codigo_recuperacao']
                            expira_salvo = checagem.data[0].get('codigo_recuperacao_expira')
                            try: expirado = (not expira_salvo) or (datetime.strptime(expira_salvo, "%Y-%m-%d %H:%M:%S") < datetime.now())
                            except Exception: expirado = True
                            if expirado:
                                mostrar_popup("Este código expirou. Solicite um novo.", tipo="erro")
                            elif codigo_digitado.strip() != codigo_salvo:
                                mostrar_popup("Código incorreto. Confira e tente novamente.", tipo="erro")
                            else:
                                st.session_state['recuperacao_etapa'] = 'nova_senha'
                                mostrar_popup("Código confirmado! Agora crie sua nova senha.")
                                st.rerun()
            with col_rc2:
                if st.button("🔄 Reenviar Código"):
                    checagem_email = supabase.table("usuarios").select("nome, email").eq("id", st.session_state['recuperacao_usuario_id']).execute()
                    nome_dest_reenvio = (checagem_email.data[0].get('nome') or st.session_state['recuperacao_email']) if checagem_email.data else st.session_state['recuperacao_email']
                    codigo_novo = gerar_codigo_recuperacao()
                    expira_novo = (datetime.now() + relativedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                    supabase.table("usuarios").update({"codigo_recuperacao": codigo_novo, "codigo_recuperacao_expira": expira_novo}).eq("id", st.session_state['recuperacao_usuario_id']).execute()
                    if enviar_email_codigo_recuperacao(st.session_state['recuperacao_email'], nome_dest_reenvio, codigo_novo):
                        mostrar_popup("Novo código enviado!")
            with col_rc3:
                if st.button("↩️ Cancelar"):
                    for chave_limpar in ['recuperacao_etapa', 'recuperacao_usuario_id', 'recuperacao_email']:
                        if chave_limpar in st.session_state: del st.session_state[chave_limpar]
                    st.rerun()

        # ---------- ETAPA 3: CRIAR NOVA SENHA ----------
        elif st.session_state['recuperacao_etapa'] == 'nova_senha':
            st.caption("Crie sua nova senha. Todos os requisitos abaixo precisam ser atendidos para poder salvar.")
            nova_senha_recup = st.text_input("Nova Senha", type="password", key="nova_senha_recuperacao")
            confirma_senha_recup = st.text_input("Confirme a Nova Senha", type="password", key="confirma_senha_recuperacao")

            requisitos_senha = validar_senha_forte(nova_senha_recup)
            st.markdown("**Requisitos da senha:**")
            for descricao_req, atendido in requisitos_senha.items():
                st.markdown(f"{'✅' if atendido else '❌'} {descricao_req}")

            senhas_preenchidas = bool(nova_senha_recup) or bool(confirma_senha_recup)
            senhas_coincidem = bool(nova_senha_recup) and (nova_senha_recup == confirma_senha_recup)
            if senhas_preenchidas:
                st.markdown(f"{'✅' if senhas_coincidem else '❌'} As senhas digitadas coincidem")

            todos_requisitos_ok = all(requisitos_senha.values()) and senhas_coincidem

            col_ns1, col_ns2 = st.columns(2)
            with col_ns1:
                if st.button("💾 Confirmar Nova Senha", disabled=not todos_requisitos_ok):
                    supabase.table("usuarios").update({
                        "senha_hash": nova_senha_recup,
                        "codigo_recuperacao": None,
                        "codigo_recuperacao_expira": None
                    }).eq("id", st.session_state['recuperacao_usuario_id']).execute()
                    for chave_limpar in ['recuperacao_etapa', 'recuperacao_usuario_id', 'recuperacao_email']:
                        if chave_limpar in st.session_state: del st.session_state[chave_limpar]
                    mostrar_popup("SENHA REDEFINIDA COM SUCESSO! Faça login com sua nova senha.")
                    st.rerun()
            with col_ns2:
                if st.button("↩️ Cancelar", key="cancelar_nova_senha"):
                    for chave_limpar in ['recuperacao_etapa', 'recuperacao_usuario_id', 'recuperacao_email']:
                        if chave_limpar in st.session_state: del st.session_state[chave_limpar]
                    st.rerun()
            if not todos_requisitos_ok and senhas_preenchidas:
                st.info("Atenda a todos os requisitos acima para conseguir salvar a nova senha.")
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

        with st.expander("📇 Meus Dados Cadastrados", expanded=False):
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
        with st.expander("🔑 Alterar Senha", expanded=False):
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
        with st.expander("💳 Minha Assinatura", expanded=False):
            plano_nome_tela = "PRO 🚀" if plano_atual_usuario == 'pro' else "BÁSICO 📦"
        st.info(f"Seu plano atual é o **{plano_nome_tela}**.")
        acao_assinatura = st.radio("Gerenciar Assinatura:", ["Manter meu plano atual", "🔄 Renovar meu plano atual", "Fazer Upgrade para PRO (R$ 89,90)", "Fazer Downgrade para Básico (R$ 79,90)", "Cancelar Assinatura"])
        CHAVE_PIX = "702.221.494-85"
        NOME_PIX = "VALDEMIR NUNES NICACIO"
        CIDADE_PIX = "ASSU/RN"
        if acao_assinatura == "Manter meu plano atual":
            st.info("Seu plano está mantido. Nenhuma alteração realizada.")
        elif acao_assinatura == "🔄 Renovar meu plano atual":
            valor_renovar = 89.90 if plano_atual_usuario == 'pro' else 79.90
            nome_plano_renovar = plano_atual_usuario
            st.info(f"Renovação do plano **{plano_atual_usuario.upper()}** — R$ {formatar_moeda(valor_renovar)}/mês")
            metodo_renovacao = st.radio("Como quer pagar?", ["💠 Pix (QR Code)", "🤝 Pagar em mãos"], key="metodo_renovacao")
            if metodo_renovacao == "💠 Pix (QR Code)":
                try:
                    payload_pix = gerar_payload_pix(CHAVE_PIX, NOME_PIX, CIDADE_PIX, valor_renovar, "Renovacao")
                    qr_buffer = gerar_qrcode_pix(payload_pix)
                    col_qr1, col_qr2 = st.columns([1,1])
                    with col_qr1: st.image(qr_buffer, caption="📱 Escaneie com seu banco", width=250)
                    with col_qr2:
                        st.markdown(f"**Chave PIX:** `{CHAVE_PIX}`")
                        st.markdown(f"**Titular:** {NOME_PIX}")
                        st.markdown(f"**Valor:** R$ {formatar_moeda(valor_renovar)}")
                    comp_renovacao = st.text_area("Cole o comprovante aqui após pagar", key="comp_renovacao_pix")
                    if st.button("📤 Enviar Comprovante", key="btn_comp_renovacao"):
                        if not comp_renovacao.strip(): mostrar_popup("Cole o comprovante antes de enviar.", tipo="erro")
                        else:
                            supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "comprovante_pagamento": comp_renovacao, "plano": nome_plano_renovar}).eq("id", st.session_state['usuario_id']).execute()
                            mostrar_popup("Comprovante enviado! Renovaremos seu plano em breve.")
                except Exception as e: st.error(f"Erro ao gerar QR Code: {e}")
            else:
                comp_maos_ren = st.text_area("Descreva o comprovante / acordo", key="comp_maos_renovacao")
                if st.button("📤 Enviar", key="btn_maos_renovacao"):
                    if not comp_maos_ren.strip(): mostrar_popup("Descreva o comprovante.", tipo="erro")
                    else:
                        supabase.table("usuarios").update({"metodo_pagamento": "manual", "comprovante_pagamento": comp_maos_ren, "plano": nome_plano_renovar}).eq("id", st.session_state['usuario_id']).execute()
                        mostrar_popup("Enviado! Aguarde aprovação do administrador.")
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
                
        with st.expander("📅 Google Agenda", expanded=False):
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
            
    def gerar_pdf_orcamento(orc, itens_lista, nome_cliente_pdf, contato_cliente_pdf):
        import os as _os
        buffer = io.BytesIO()
        COR_DOURADO = colors.HexColor("#FFC107")
        COR_PRETO = colors.HexColor("#0E0E0E")
        COR_CINZA_CLARO = colors.HexColor("#F2F2F2")
        COR_TEXTO_CINZA = colors.HexColor("#555555")
        caminho_logo_pdf = "logo_sem_fundo.png" if _os.path.exists("logo_sem_fundo.png") else ("logo.jpg" if _os.path.exists("logo.jpg") else None)

        def _desenhar_cabecalho(canvas_obj, doc_obj):
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
            canvas_obj.drawString(6.2*cm, altura_pagina-1.5*cm, "PROPOSTA DE ORÇAMENTO")
            canvas_obj.setFillColor(colors.white)
            canvas_obj.setFont("Helvetica", 10)
            canvas_obj.drawString(6.2*cm, altura_pagina-2.15*cm, f"Evento: {orc.get('titulo_evento','-')}")
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.setFont("Helvetica", 8)
            canvas_obj.drawString(2*cm, 1.2*cm, f"Luz & Letras — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            canvas_obj.drawRightString(largura_pagina-2*cm, 1.2*cm, f"Página {doc_obj.page}")
            canvas_obj.restoreState()

        frame = Frame(2*cm, 1.8*cm, A4[0]-4*cm, A4[1]-5.4*cm, id='corpo_orc')
        doc = BaseDocTemplate(buffer, pagesize=A4)
        doc.addPageTemplates([PageTemplate(id='ComCabecalhoOrc', frames=[frame], onPage=_desenhar_cabecalho)])
        styles = getSampleStyleSheet()
        story = []
        sub_titulo = ParagraphStyle('SubTitOrc', parent=styles['Heading2'], fontSize=12, spaceAfter=6, textColor=COR_PRETO)
        normal_style = ParagraphStyle('NormalOrc', parent=styles['Normal'], fontSize=10, leading=14)
    
        story.append(Spacer(1, 10))
    
        def _fmt_data(d):
            if not d: return "-"
            try: return datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            except: return d
    
        data_criacao_fmt = _fmt_data(orc.get('data_criacao')) if orc.get('data_criacao') else datetime.now().strftime("%d/%m/%Y")
        try:
            data_validade = (datetime.now() + relativedelta(days=int(orc.get('validade_dias') or 7))).strftime("%d/%m/%Y")
        except Exception:
            data_validade = "-"
    
        dados_cliente = (f"<b>Cliente:</b> {nome_cliente_pdf}<br/><b>Contato:</b> {contato_cliente_pdf}<br/>"
            f"<b>Evento:</b> {orc.get('titulo_evento','-')}<br/>"
            f"<b>Período:</b> {_fmt_data(orc.get('data_inicio'))} até {_fmt_data(orc.get('data_fim'))}<br/>"
            f"<b>Local:</b> {orc.get('endereco_evento','-')}<br/>"
            f"<b>Proposta válida até:</b> {data_validade}")
        tabela_header = Table([[Paragraph(dados_cliente, normal_style)]], colWidths=[17*cm])
        tabela_header.setStyle(TableStyle([('BOX',(0,0),(-1,-1),1,colors.HexColor("#CCCCCC")),('PADDING',(0,0),(-1,-1),10),('BACKGROUND',(0,0),(-1,-1),colors.HexColor("#FAFAFA"))]))
        story.append(tabela_header)
        story.append(Spacer(1,20))
    
        story.append(Paragraph("<b>ITENS ORÇADOS</b>", sub_titulo))
        tabela_dados = [["Item","Qtd","Valor Unit.","Subtotal"]]
        for it in itens_lista:
            tabela_dados.append([it.get('nome','-'), str(it.get('quantidade',0)), f"R$ {formatar_moeda(it.get('valor_unit',0))}", f"R$ {formatar_moeda(it.get('valor_total',0))}"])
        tabela_pdf = Table(tabela_dados, colWidths=[8*cm,2*cm,3.5*cm,3.5*cm])
        tabela_pdf.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),COR_PRETO),('TEXTCOLOR',(0,0),(-1,0),COR_DOURADO),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,0),(-1,-1),9),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,COR_CINZA_CLARO])]))
        story.append(tabela_pdf)
        story.append(Spacer(1,15))
    
        resumo_dados = [
            ["Valor dos Itens", f"R$ {formatar_moeda(orc.get('valor_itens',0))}"],
            ["Frete/Deslocamento", f"R$ {formatar_moeda(orc.get('valor_frete',0))}"],
            ["Desconto", f"- R$ {formatar_moeda(orc.get('desconto',0))}"],
            ["VALOR TOTAL", f"R$ {formatar_moeda(orc.get('valor_total',0))}"],
        ]
        tabela_resumo = Table(resumo_dados, colWidths=[13*cm,4*cm])
        tabela_resumo.setStyle(TableStyle([('ALIGN',(1,0),(1,-1),'RIGHT'),('FONTSIZE',(0,0),(-1,-1),10),
            ('FONTNAME',(0,3),(-1,3),'Helvetica-Bold'),('FONTSIZE',(0,3),(-1,3),12),
            ('LINEABOVE',(0,3),(-1,3),1,COR_PRETO),('TOPPADDING',(0,3),(-1,3),8)]))
        story.append(tabela_resumo)
        story.append(Spacer(1,20))
    
        if orc.get('observacoes'):
            story.append(Paragraph(f"<b>Observações:</b> {orc['observacoes']}", ParagraphStyle('Obs', parent=normal_style, textColor=COR_TEXTO_CINZA)))
            story.append(Spacer(1,15))
    
        story.append(Paragraph("Proposta sujeita à disponibilidade de estoque na data de confirmação. A equipe <b>Luz & Letras</b> agradece a preferência!",
            ParagraphStyle('Rodape', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=COR_TEXTO_CINZA)))
    
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
                    aguardando_manual = (metodo_pag_u in ["manual", "pix_manual"]) and (not u['ativo'] or u.get('comprovante_pagamento'))

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
        try: fat_dash = supabase.table("faturamento").select("tipo, valor, data_pagamento").eq("empresa_id", emp_id).execute()
        except: fat_dash = type('obj',(object,),{'data':[]})
        receita_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'receita')
        despesa_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'despesa')
        total_receitas = receita_ev + receita_manual
        total_despesas = despesa_comp + despesa_viagem + despesa_manual
        lucro_liquido = total_receitas - total_despesas
        col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
        col_kpi1.metric("💰 Receita Total", f"R$ {formatar_moeda(total_receitas)}")
        col_kpi2.metric("📉 Despesas Totais", f"R$ {formatar_moeda(total_despesas)}")
        col_kpi3.metric("✨ Lucro Líquido", f"R$ {formatar_moeda(lucro_liquido)}", delta="Positivo" if lucro_liquido >= 0 else "Atenção", delta_color="normal" if lucro_liquido >= 0 else "inverse")
        col_kpi4.metric("💳 Ticket Médio", f"R$ {formatar_moeda(ticket_medio)}")
        col_kpi5.metric("🎉 Eventos Ativos", total_eventos_ativos)
        st.markdown("---")
        col_alerta1, col_alerta2 = st.columns(2)
        with col_alerta1:
            try:
                manutencao_check = supabase.table("manutencao").select("quantidade, produtos(nome)").eq("empresa_id", emp_id).eq("status", "Em Manutenção").execute()
                if manutencao_check.data:
                    for m in manutencao_check.data:
                        nome_p = m['produtos']['nome'] if m.get('produtos') else "Item"
                        st.warning(f"🔧 **Reparo Pendente:** {m['quantidade']}x {nome_p} fora de circulação.")
            except: pass
        with col_alerta2:
            try:
                estoque_check = supabase.table("produtos").select("nome, quantidade_estoque").eq("empresa_id", emp_id).execute()
                if estoque_check.data:
                    zerados = [p['nome'] for p in estoque_check.data if p['quantidade_estoque'] <= 0]
                    for z in zerados: st.error(f"⚠️ **Atenção:** {z} com estoque ZERADO.")
            except: pass
        st.markdown("<br>", unsafe_allow_html=True)
        COR_FUNDO_GRAFICO = "#161618"
        col_g1, col_g2 = st.columns([2,1])
        with col_g1:
            st.subheader("📈 Evolução Financeira")
            timeline_data = []
            for e in (eventos_dash.data or []):
                if e.get('data_inicio'): timeline_data.append({'Data': e['data_inicio'].split("T")[0], 'Receita': float(e.get('valor_total') or 0), 'Despesa': 0.0})
            for f in (fat_dash.data or []):
                if f.get('data_pagamento') and f.get('tipo') == 'receita': timeline_data.append({'Data': f['data_pagamento'].split("T")[0], 'Receita': float(f.get('valor') or 0), 'Despesa': 0.0})
            for c in (compras_dash.data or []):
                if c.get('data_compra'): timeline_data.append({'Data': c['data_compra'].split("T")[0], 'Receita': 0.0, 'Despesa': float(c.get('valor_total') or 0)})
            for v in (viagens_dash.data or []):
                if v.get('data_despesa'): timeline_data.append({'Data': v['data_despesa'].split("T")[0], 'Receita': 0.0, 'Despesa': float(v.get('valor') or 0)})
            for f in (fat_dash.data or []):
                if f.get('data_pagamento') and f.get('tipo') == 'despesa': timeline_data.append({'Data': f['data_pagamento'].split("T")[0], 'Receita': 0.0, 'Despesa': float(f.get('valor') or 0)})
            if timeline_data:
                df_tl = pd.DataFrame(timeline_data)
                df_tl['Data'] = pd.to_datetime(df_tl['Data'])
                df_tl['Mês/Ano'] = df_tl['Data'].dt.to_period('M').dt.strftime('%m/%Y')
                df_agrupado = df_tl.groupby('Mês/Ano')[['Receita','Despesa']].sum().reset_index()
                df_agrupado['sort_date'] = pd.to_datetime(df_agrupado['Mês/Ano'], format='%m/%Y')
                df_agrupado = df_agrupado.sort_values('sort_date')
                fig_evolucao = px.area(df_agrupado, x="Mês/Ano", y=["Receita","Despesa"], template="plotly_dark", color_discrete_map={"Receita":"#2E7D32","Despesa":"#C62828"})
                fig_evolucao.update_layout(plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                    yaxis=dict(title="", showgrid=True, gridcolor="#333"), xaxis=dict(title="", showgrid=False),
                    legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=40,b=0,l=0,r=0))
                st.plotly_chart(fig_evolucao, use_container_width=True, height=350, config={'displayModeBar': False})
            else: st.info("Aguardando lançamentos financeiros para gerar a linha do tempo.")
        with col_g2:
            st.subheader("📊 Status dos Eventos")
            if eventos_dash.data:
                df_status = pd.DataFrame(eventos_dash.data)
                status_counts = df_status["status"].value_counts().reset_index()
                status_counts.columns = ["Status","Quantidade"]
                mapa_cores_status = {"Concluído":"#2E7D32","Agendado":"#FFC107","Cancelado":"#C62828","Em Andamento":"#0277BD"}
                fig_status = px.pie(status_counts, names="Status", values="Quantidade", hole=0.6, color="Status", color_discrete_map=mapa_cores_status, template="plotly_dark")
                fig_status.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color=COR_FUNDO_GRAFICO, width=3)))
                fig_status.add_annotation(text=f"<b>{total_eventos_ativos}</b><br>Eventos", x=0.5, y=0.5, font_size=18, showarrow=False, align="center")
                fig_status.update_layout(showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=20,b=20,l=0,r=0))
                st.plotly_chart(fig_status, use_container_width=True, height=350)
            else: st.info("Sem eventos para analisar.")
        st.markdown("---")
        col_g3, col_g4, col_g5 = st.columns([1.2,1.2,1])
        ids_ativos_hoje = []
        if eventos_dash.data:
            for ev in eventos_dash.data:
                try:
                    d_ini = datetime.strptime(ev['data_inicio'].split('T')[0], "%Y-%m-%d").date()
                    d_fim = datetime.strptime(ev['data_fim_alocacao'].split('T')[0], "%Y-%m-%d").date()
                    if d_ini <= hoje_date <= d_fim: ids_ativos_hoje.append(ev['id'])
                except: pass
        itens_alocados_hoje = 0
        if ids_ativos_hoje:
            try:
                it_hoje = supabase.table("itens_evento").select("quantidade").in_("evento_id", ids_ativos_hoje).execute()
                itens_alocados_hoje = sum(i['quantidade'] for i in (it_hoje.data or []))
            except: pass
        total_estoque_fisico = 1
        prods_ref_data = []
        try:
            prod_all = supabase.table("produtos").select("id, nome, quantidade_estoque").eq("empresa_id", emp_id).execute()
            if prod_all.data:
                total_estoque_fisico = max(1, sum(p['quantidade_estoque'] for p in prod_all.data))
                prods_ref_data = prod_all.data
        except: pass
        taxa_ocupacao = (itens_alocados_hoje / total_estoque_fisico) * 100
        with col_g3:
            st.subheader("🎯 Taxa de Ocupação Hoje")
            st.caption("Volume do estoque total alugado no momento.")
            fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=taxa_ocupacao,
                number={'suffix':"%",'font':{'size':36,'color':'#FFC107'}},
                title={'text':f"{itens_alocados_hoje} de {total_estoque_fisico} itens na rua",'font':{'size':13}},
                gauge={'axis':{'range':[None,100]},'bar':{'color':"#FFC107"},'bgcolor':"#333",'borderwidth':0,
                    'steps':[{'range':[0,40],'color':"rgba(46,125,50,0.3)"},{'range':[40,80],'color':"rgba(255,193,7,0.3)"},{'range':[80,100],'color':"rgba(198,40,40,0.3)"}]}))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=40,b=0,l=20,r=20), height=280)
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})
        with col_g4:
            st.subheader("🏆 Ranking de Produtos")
            st.caption("O que mais sai e o que dá mais lucro.")
            tab_qtd, tab_lucro = st.tabs(["Por Quantidade","Por Rentabilidade (R$)"])
            try:
                itens_dash = supabase.table("itens_evento").select(
                    "evento_id, produto_id, quantidade, valor_cobrado"
                ).eq("empresa_id", emp_id).execute()
            except Exception:
                itens_dash = type('obj', (object,), {'data': []})

            # Monta o mapa de eventos com valor_total E soma de itens calculada
            eventos_dash_map = {}
            try:
                ev_ids = list({i['evento_id'] for i in (itens_dash.data or [])})
                if ev_ids:
                    ev_resp = supabase.table("eventos").select(
                        "id, valor_total"
                    ).in_("id", ev_ids).execute()
                    # Calcula quantidade_total somando os itens que já temos
                    qtd_por_evento = {}
                    for i in (itens_dash.data or []):
                        qtd_por_evento[i['evento_id']] = qtd_por_evento.get(i['evento_id'], 0) + i['quantidade']
                    for e in (ev_resp.data or []):
                        eventos_dash_map[e['id']] = {
                            'valor_total': e.get('valor_total') or 0,
                            'quantidade_total': qtd_por_evento.get(e['id'], 0)
                        }
            except Exception:
                pass

            if itens_dash.data and prods_ref_data:
                mapa_nomes = {p['id']: p['nome'] for p in prods_ref_data}
                mapa_valor_locacao = {p['id']: float(p.get('valor_locacao') or 0) for p in prods_ref_data}

                with tab_qtd:
                    uso_produtos = {}
                    for item in itens_dash.data:
                        pid = item['produto_id']
                        uso_produtos[pid] = uso_produtos.get(pid, 0) + item['quantidade']
                    total_alugueis_historico = sum(uso_produtos.values())
                    if uso_produtos:
                        df_top = pd.DataFrame([{"Produto": mapa_nomes.get(pid, f"Prod {pid}"), "Locações": qtd} for pid, qtd in uso_produtos.items()])
                        df_top = df_top.sort_values(by="Locações", ascending=True).tail(5)
                        df_top['Porcentagem'] = (df_top['Locações'] / total_alugueis_historico) * 100
                        df_top['Label'] = df_top['Locações'].astype(str) + " (" + df_top['Porcentagem'].round(1).astype(str) + "%)"
                        fig_top = px.bar(df_top, x="Locações", y="Produto", orientation='h', template="plotly_dark", text="Label", color_discrete_sequence=["#FFC107"])
                        fig_top.update_traces(textposition='inside', textfont_size=12, textfont_color="black")
                        fig_top.update_layout(showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                            xaxis=dict(showgrid=False,showticklabels=False,title="",zeroline=False),
                            yaxis=dict(title="",showgrid=False,tickfont=dict(size=12,color='white')), margin=dict(t=10,b=0,l=0,r=0))
                        st.plotly_chart(fig_top, use_container_width=True, height=230, config={'displayModeBar': False})

                with tab_lucro:
                    itens_por_evento = {}
                    for item in itens_dash.data:
                        ev_id = item['evento_id']
                        itens_por_evento.setdefault(ev_id, []).append(item)

                    receita_por_produto = {}
                    for item in itens_dash.data:
                        pid = item['produto_id']
                        valor_item = float(item.get('valor_cobrado') or 0)

                        if valor_item == 0:
                            valor_item = mapa_valor_locacao.get(pid, 0) * item['quantidade']

                        if valor_item == 0:
                            try:
                                ev_id = item['evento_id']
                                evento_ref = eventos_dash_map.get(ev_id, {})
                                valor_geral = float(evento_ref.get('valor_total') or 0)
                                quantidade_geral = int(evento_ref.get('quantidade_total') or 0)
                                preco_unitario = float(valor_geral) / quantidade_geral if quantidade_geral > 0 else 0.0
                                valor_item = preco_unitario * item['quantidade']
                            except Exception:
                                pass

                        receita_por_produto[pid] = receita_por_produto.get(pid, 0) + valor_item

                    dados_lucro = [{"Produto": mapa_nomes.get(pid, f"Prod {pid}"), "Receita": v}
                                   for pid, v in receita_por_produto.items() if v > 0]
                    if dados_lucro:
                        df_lucro = pd.DataFrame(dados_lucro)
                        df_lucro = df_lucro.sort_values(by="Receita", ascending=True).tail(5)
                        df_lucro['Label'] = df_lucro['Receita'].apply(
                            lambda x: f"R$ {x:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                        )
                        fig_lucro = px.bar(df_lucro, x="Receita", y="Produto", orientation='h',
                            template="plotly_dark", text="Label", color_discrete_sequence=["#2E7D32"])
                        fig_lucro.update_traces(textposition='inside', textfont_size=12, textfont_color="white")
                        fig_lucro.update_layout(showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                            xaxis=dict(showgrid=False,showticklabels=False,title="",zeroline=False),
                            yaxis=dict(title="",showgrid=False,tickfont=dict(size=12,color='white')), margin=dict(t=10,b=0,l=0,r=0))
                        st.plotly_chart(fig_lucro, use_container_width=True, height=230, config={'displayModeBar': False})
                    else:
                        st.info("Nenhuma receita encontrada. Cadastre o valor de locação dos produtos no Estoque.")
            else:
                st.info("Dados insuficientes para ranking.")
        with col_g5:
            st.subheader("🗓️ Próximos Eventos")
            st.caption("Seus compromissos iminentes.")
            if eventos_dash.data:
                eventos_futuros = []
                for ev in eventos_dash.data:
                    try:
                        d_ini = datetime.strptime(ev['data_inicio'].split('T')[0], "%Y-%m-%d").date()
                        if d_ini >= hoje_date and ev['status'] != "Concluído":
                            eventos_futuros.append({'Data': d_ini, 'DataStr': d_ini.strftime("%d/%m"),
                                'Cliente': ev.get('clientes_eventos',{}).get('nome','Cliente') if ev.get('clientes_eventos') else 'Cliente',
                                'Evento': ev.get('descricao','Evento')[:15] + "..."})
                    except: pass
                eventos_futuros = sorted(eventos_futuros, key=lambda x: x['Data'])[:4]
                if eventos_futuros:
                    for evf in eventos_futuros:
                        st.markdown(f"🟢 **{evf['DataStr']}** - {evf['Cliente']}<br><span style='color:gray;font-size:12px;'>{evf['Evento']}</span>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin:8px 0px;border-color:#333;'>", unsafe_allow_html=True)
                else: st.info("Agenda livre! Nenhum evento futuro programado.")
            else: st.info("Nenhum evento cadastrado.")


    # ==========================================
    # MENU: AGENDAMENTO
    # ==========================================
    elif menu == "📅 Agendamento":
        st.title("📅 Gestão de Agendamentos")
        produtos_disp = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).execute()
        dict_produtos = {p['id']: p for p in produtos_disp.data} if produtos_disp.data else {}
        mapa_valor_ref = {p['id']: float(p.get('valor_locacao') or 0) for p in produtos_disp.data} if produtos_disp.data else {}
        eventos_cadastrados = supabase.table("eventos").select("*").eq("empresa_id", emp_id).order("data_inicio", desc=False).execute()
        lista_todos_eventos = eventos_cadastrados.data or []
        try: clientes_resultado = supabase.table("clientes_eventos").select("id, nome, contato").eq("empresa_id", emp_id).execute()
        except: clientes_resultado = supabase.table("clientes_eventos").select("id, nome").eq("empresa_id", emp_id).execute()
        mapa_clientes = {c['id']: c for c in clientes_resultado.data} if clientes_resultado.data else {}
        hoje_dt = datetime.now().date()

        eventos_hoje = 0
        eventos_proximos_7_dias = 0
        for ev_kpi in lista_todos_eventos:
            if ev_kpi.get('status') not in ["Cancelado","Concluído"] and ev_kpi.get('data_inicio'):
                try:
                    d_ini_kpi = datetime.strptime(ev_kpi['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if d_ini_kpi == hoje_dt: eventos_hoje += 1
                    elif hoje_dt < d_ini_kpi <= (hoje_dt + relativedelta(days=7)): eventos_proximos_7_dias += 1
                except: pass

        st.markdown("#### 📊 Visão Operacional")
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("📍 Eventos Hoje", eventos_hoje)
        col_k2.metric("🔜 Próximos 7 Dias", eventos_proximos_7_dias)
        col_k3.metric("📑 Total na Base", len(lista_todos_eventos))
        st.markdown("---")

        st.markdown("#### 🔍 Filtrar Eventos")
        col_f1, col_f2, col_f3 = st.columns([1,1.2,1.5])
        with col_f1: filtro_status = st.multiselect("Status", ["Agendado","Em Andamento","Concluído","Cancelado"], default=["Agendado","Em Andamento"])
        with col_f2: filtro_data = st.date_input("Período (Início e Fim)", value=[hoje_dt, hoje_dt + relativedelta(days=30)], format="DD/MM/YYYY")
        with col_f3: filtro_busca = st.text_input("Buscar Cliente ou Título", placeholder="Digite o nome...")

        eventos_filtrados = []
        for ev in lista_todos_eventos:
            passa_status = (ev.get('status') in filtro_status) if filtro_status else True
            passa_data = True
            if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                try:
                    d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if not (filtro_data[0] <= d_ini_ev <= filtro_data[1]): passa_data = False
                except: passa_data = False
            elif isinstance(filtro_data, tuple) and len(filtro_data) == 1:
                try:
                    d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if d_ini_ev != filtro_data[0]: passa_data = False
                except: passa_data = False
            passa_busca = True
            if filtro_busca.strip():
                termo = filtro_busca.lower()
                titulo_b = (ev.get('descricao') or "").lower()
                nome_cli_b = (mapa_clientes.get(ev.get('cliente_id'), {}).get('nome', "")).lower()
                if termo not in titulo_b and termo not in nome_cli_b: passa_busca = False
            if passa_status and passa_data and passa_busca: eventos_filtrados.append(ev)

        st.markdown("---")
        st.subheader(f"📋 Eventos Encontrados ({len(eventos_filtrados)})")

        if eventos_filtrados:
            for ev in eventos_filtrados:
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
                hora_ini_fmt = ev.get('hora_inicio')[:5] if ev.get('hora_inicio') else "00:00"
                hora_fim_fmt = ev.get('hora_fim')[:5] if ev.get('hora_fim') else "23:59"

                with st.expander(f"🎉 {titulo_ev} — {nome_cliente_ev} | {data_ini_br} ({hora_ini_fmt}) até {data_fim_br} ({hora_fim_fmt}) | Status: {status_ev}"):
                    itens_ev = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado").eq("evento_id", ev['id']).execute()
                    tab_detalhes, tab_add, tab_rem, tab_valores, tab_editar, tab_hist = st.tabs(["📋 Detalhes & Recibo","➕ Adicionar Itens","➖ Remover Itens","💲 Valores","✏️ Editar Evento","🕒 Histórico"])

                    with tab_detalhes:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            valor_ev = float(ev.get('valor_total') or 0)
                            st.write(f"**Data e Hora:** {data_ini_br} às {hora_ini_fmt} — {data_fim_br} às {hora_fim_fmt}")
                            st.write(f"**Valor:** R$ {formatar_moeda(valor_ev)}")
                            st.write(f"**Contato do Cliente:** {contato_cliente_ev}")
                            st.write(f"**Observações:** {ev.get('observacao') or '-'}")
                        with col_b:
                            opcoes_status = ["Agendado","Em Andamento","Concluído","Cancelado"]
                            idx_status = opcoes_status.index(status_ev) if status_ev in opcoes_status else 0
                            novo_status = st.selectbox("Alterar Status", opcoes_status, index=idx_status, key=f"status_ev_{ev['id']}")
                            if st.button("Atualizar Status", key=f"btn_status_ev_{ev['id']}"):
                                supabase.table("eventos").update({"status": novo_status}).eq("id", ev['id']).execute()
                                mostrar_popup("STATUS ATUALIZADO COM SUCESSO!")
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

                        st.markdown("---")
                        if ev.get('pagamento_confirmado'):
                            st.success(f"✅ Pagamento confirmado via **{ev.get('metodo_confirmacao_pagamento','-')}** em {ev.get('data_confirmacao_pagamento','-')}")
                            if st.button("🗑️ Desfazer Confirmação", key=f"del_pag_{ev['id']}"):
                                supabase.table("eventos").update({"pagamento_confirmado": False, "metodo_confirmacao_pagamento": None, "data_confirmacao_pagamento": None}).eq("id", ev['id']).execute()
                                mostrar_popup("CONFIRMAÇÃO REMOVIDA!")
                                st.rerun()
                        else:
                            st.warning("⏳ Pagamento ainda não confirmado.")
                            metodo_confirmacao = st.selectbox("Como foi feito o pagamento?", ["Pix","Dinheiro","Cartão","Boleto","Outro"], key=f"metodo_pag_{ev['id']}")
                            if st.button("✅ Confirmar Pagamento", key=f"btn_conf_pag_{ev['id']}"):
                                supabase.table("eventos").update({"pagamento_confirmado": True, "metodo_confirmacao_pagamento": metodo_confirmacao, "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")}).eq("id", ev['id']).execute()
                                mostrar_popup("PAGAMENTO CONFIRMADO COM SUCESSO!")
                                st.rerun()

                        if ev.get('google_event_id'): st.caption("📅 Este evento já está sincronizado com a sua Google Agenda.")
                        if st.button("📅 Sincronizar com Google Agenda", key=f"sync_google_{ev['id']}"):
                            novo_id_google = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], ev, ev.get('google_event_id'))
                            if novo_id_google:
                                try: supabase.table("eventos").update({"google_event_id": novo_id_google}).eq("id", ev['id']).execute()
                                except Exception: pass
                                mostrar_popup("EVENTO SINCRONIZADO COM A GOOGLE AGENDA!")
                                st.rerun()
                            else: mostrar_popup("Conecte sua Google Agenda em 'Perfil' primeiro.", tipo="erro")


                    with tab_add:
                        produtos_disp_edit = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).execute()
                        mapa_valor_ref_add = {p['id']: float(p.get('valor_locacao') or 0) for p in produtos_disp_edit.data} if produtos_disp_edit.data else {}
                        adicoes_selecionadas = {}
                        ev_data_inicio_add = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_inicio') else datetime.now().date()
                        ev_data_fim_add = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date() if ev.get('data_fim_alocacao') else ev_data_inicio_add
                        qtd_alugada_add, detalhe_alugado_add = calcular_disponibilidade_periodo(ev_data_inicio_add, ev_data_fim_add, evento_id_excluir=ev['id'])
                        if produtos_disp_edit.data:
                            for p in produtos_disp_edit.data:
                                js_p = safe_json_load(p.get('observacao'))
                                if js_p:
                                    ja_alugado_kit = detalhe_alugado_add.get(p['id'], {})
                                    if any((max_v - ja_alugado_kit.get(k,0)) > 0 for k,max_v in js_p.items()):
                                        st.markdown(f"🔠 *{p['nome']}:*")
                                        cols_add = st.columns(6)
                                        idxp = 0
                                        for k, max_v in js_p.items():
                                            disp_k = max(0, max_v - ja_alugado_kit.get(k,0))
                                            if disp_k > 0:
                                                val_add = cols_add[idxp%6].number_input(f"{k} (Disp:{disp_k})", min_value=0, max_value=disp_k, value=None, key=f"add_{ev['id']}_{p['id']}_{k}")
                                                if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_{k}"] = val_add
                                                idxp += 1
                                else:
                                    disp_normal = max(0, p['quantidade_estoque'] - qtd_alugada_add.get(p['id'],0))
                                    if disp_normal > 0:
                                        val_add = st.number_input(f"{p['nome']} (Disp: {disp_normal})", min_value=0, max_value=disp_normal, value=None, key=f"add_{ev['id']}_{p['id']}_NORMAL")
                                        if (val_add or 0) > 0: adicoes_selecionadas[f"{p['id']}_NORMAL"] = val_add
                        motivo_alteracao = st.text_input("Motivo da Alteração", key=f"motivo_{ev['id']}")
                        if st.button("💾 Registrar Alteração", key=f"btn_add_{ev['id']}"):
                            if not adicoes_selecionadas: mostrar_popup("Selecione ao menos 1 item.", tipo="erro")
                            elif not motivo_alteracao.strip(): mostrar_popup("Informe o motivo da alteração.", tipo="erro")
                            else:
                                try:
                                    agrupado = {}
                                    for key, qtd in adicoes_selecionadas.items():
                                        p_id_str, sub = key.split("_", 1)
                                        if int(p_id_str) not in agrupado: agrupado[int(p_id_str)] = {'total':0,'detalhes':{}}
                                        agrupado[int(p_id_str)]['total'] += qtd
                                        if sub != "NORMAL": agrupado[int(p_id_str)]['detalhes'][sub] = qtd
                                    data_hora_alt = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    resumo_itens = []
                                    for p_id, info in agrupado.items():
                                        qtd_total = info['total']
                                        valor_sugerido_add = qtd_total * mapa_valor_ref_add.get(p_id, 0)
                                        obs_json_add = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                        item_existente = supabase.table("itens_evento").select("id, quantidade, observacao, valor_cobrado").eq("evento_id", ev['id']).eq("produto_id", p_id).execute()
                                        if item_existente.data:
                                            item_atual = item_existente.data[0]
                                            nova_qtd_item = item_atual['quantidade'] + qtd_total
                                            novo_valor_item = float(item_atual.get('valor_cobrado') or 0) + valor_sugerido_add
                                            obs_atual_item = safe_json_load(item_atual.get('observacao'))
                                            if obs_atual_item and info['detalhes']:
                                                for k, v in info['detalhes'].items(): obs_atual_item[k] = obs_atual_item.get(k,0) + v
                                                nova_obs_item = json.dumps(obs_atual_item)
                                            elif info['detalhes']: nova_obs_item = obs_json_add
                                            else: nova_obs_item = item_atual.get('observacao','')
                                            supabase.table("itens_evento").update({"quantidade": nova_qtd_item,"observacao": nova_obs_item,"valor_cobrado": novo_valor_item}).eq("id", item_atual['id']).execute()
                                        else:
                                            supabase.table("itens_evento").insert({"empresa_id": emp_id,"evento_id": ev['id'],"produto_id": p_id,"quantidade": qtd_total,"observacao": obs_json_add,"valor_cobrado": valor_sugerido_add}).execute()
                                        resumo_itens.append(f"{qtd_total}x Produto {p_id}")
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"✏️ ALTERAÇÃO: Adicionou {', '.join(resumo_itens)}. Motivo: {motivo_alteracao}","data_registro": data_hora_alt}).execute()
                                    mostrar_popup("ADIÇÃO CONCLUÍDA COM SUCESSO!")
                                    st.rerun()
                                except Exception as e: mostrar_popup(f"Erro: {e}", tipo="erro")

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
                                            val_rem = cols_rem[idxr%6].number_input(f"{k} (Aloc:{qtd_alocada})", min_value=0, max_value=qtd_alocada, value=None, key=f"rem_{ev['id']}_{it['id']}_{k}")
                                            if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_{k}"] = val_rem
                                            idxr += 1
                                else:
                                    val_rem = st.number_input(f"{nome_prod_it} (Aloc: {it['quantidade']})", min_value=0, max_value=it['quantidade'], value=None, key=f"rem_{ev['id']}_{it['id']}_NORMAL")
                                    if (val_rem or 0) > 0: remocoes_selecionadas[f"{it['id']}_{it['produto_id']}_NORMAL"] = val_rem
                            motivo_remocao = st.text_input("Motivo da Remoção", key=f"motivo_rem_{ev['id']}")
                            if st.button("🗑️ Registrar Remoção", key=f"btn_rem_{ev['id']}"):
                                if not remocoes_selecionadas: mostrar_popup("Selecione algum item.", tipo="erro")
                                elif not motivo_remocao.strip(): mostrar_popup("Informe o motivo da remoção.", tipo="erro")
                                else:
                                    data_hora_rem = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    dict_itens_ev = {it['id']: it for it in itens_ev.data}
                                    resumo_remocao = []
                                    agrupado_rem = {}
                                    for key, qtd in remocoes_selecionadas.items():
                                        item_id_str, p_id_str, sub = key.split("_", 2)
                                        item_id = int(item_id_str)
                                        if item_id not in agrupado_rem: agrupado_rem[item_id] = {'produto_id': int(p_id_str),'total':0,'detalhes':{}}
                                        agrupado_rem[item_id]['total'] += qtd
                                        if sub != "NORMAL": agrupado_rem[item_id]['detalhes'][sub] = qtd
                                    for item_id, info_rem in agrupado_rem.items():
                                        item_atual_rem = dict_itens_ev[item_id]
                                        qtd_remover = info_rem['total']
                                        qtd_antiga_rem = item_atual_rem['quantidade']
                                        valor_antigo_rem = float(item_atual_rem.get('valor_cobrado') or 0)
                                        valor_unit_medio_rem = (valor_antigo_rem / qtd_antiga_rem) if qtd_antiga_rem > 0 else 0
                                        nova_qtd_item_rem = qtd_antiga_rem - qtd_remover
                                        novo_valor_item_rem = max(0, valor_antigo_rem - (valor_unit_medio_rem * qtd_remover))
                                        obs_item_atual = safe_json_load(item_atual_rem.get('observacao'))
                                        if obs_item_atual and info_rem['detalhes']:
                                            for k, v in info_rem['detalhes'].items(): obs_item_atual[k] = max(0, obs_item_atual.get(k,0) - v)
                                            nova_obs_item_rem = json.dumps(obs_item_atual)
                                        else: nova_obs_item_rem = item_atual_rem.get('observacao','')
                                        if nova_qtd_item_rem <= 0: supabase.table("itens_evento").delete().eq("id", item_id).execute()
                                        else: supabase.table("itens_evento").update({"quantidade": nova_qtd_item_rem,"observacao": nova_obs_item_rem,"valor_cobrado": novo_valor_item_rem}).eq("id", item_id).execute()
                                        resumo_remocao.append(f"{qtd_remover}x Removidos")
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"🔻 REMOÇÃO: Retirou {', '.join(resumo_remocao)}. Motivo: {motivo_remocao}","data_registro": data_hora_rem}).execute()
                                    mostrar_popup("REMOÇÃO CONCLUÍDA COM SUCESSO!")
                                    st.rerun()
                        else: st.caption("Nenhum item alocado.")

                    with tab_valores:
                        st.caption("Ajuste o valor final cobrado por item neste evento.")
                        if itens_ev.data:
                            for it in itens_ev.data:
                                nome_prod_v = dict_produtos.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                                valor_ref_item = it['quantidade'] * mapa_valor_ref.get(it['produto_id'], 0)
                                valor_atual_v = float(it.get('valor_cobrado') or 0)
                                col_v1, col_v2 = st.columns([2,1])
                                with col_v1:
                                    st.write(f"**{nome_prod_v}** — {it['quantidade']}x")
                                    st.caption(f"Valor de referência: R$ {formatar_moeda(valor_ref_item)}")
                                with col_v2:
                                    novo_valor_item_v = st.number_input("Valor cobrado (R$)", min_value=0.0, value=valor_atual_v, format="%.2f", key=f"val_item_{it['id']}")
                                    if st.button("💾 Salvar", key=f"btn_val_item_{it['id']}"):
                                        supabase.table("itens_evento").update({"valor_cobrado": novo_valor_item_v}).eq("id", it['id']).execute()
                                        mostrar_popup("VALOR ATUALIZADO COM SUCESSO!")
                                        st.rerun()
                                st.markdown("---")
                        else: st.caption("Nenhum item alocado.")

                    with tab_editar:
                        def _parse_data_edit(data_iso):
                            if not data_iso: return datetime.now().date()
                            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").date()
                            except: return datetime.now().date()
                        def _parse_time_edit(time_str):
                            if not time_str: return datetime.min.time()
                            try: return datetime.strptime(time_str[:5], "%H:%M").time()
                            except: return datetime.min.time()
                        col_ed1, col_ed2, col_ed3, col_ed4 = st.columns(4)
                        with col_ed1: nova_data_inicio_edit = st.date_input("Data de Início", value=_parse_data_edit(ev.get('data_inicio')), format="DD/MM/YYYY", key=f"edit_data_ini_{ev['id']}")
                        with col_ed2: nova_data_fim_edit = st.date_input("Data Fim", value=_parse_data_edit(ev.get('data_fim_alocacao')), format="DD/MM/YYYY", key=f"edit_data_fim_{ev['id']}")
                        with col_ed3: nova_hora_inicio_edit = st.time_input("Hora Início", value=_parse_time_edit(ev.get('hora_inicio')), key=f"edit_hora_ini_{ev['id']}")
                        with col_ed4: nova_hora_fim_edit = st.time_input("Hora Fim", value=_parse_time_edit(ev.get('hora_fim')), key=f"edit_hora_fim_{ev['id']}")
                        novo_valor_edit = st.number_input("Valor Cobrado (R$)", min_value=0.0, step=50.0, value=float(ev.get('valor_total') or 0), format="%.2f", key=f"edit_valor_{ev['id']}")
                        novo_local_edit = st.text_area("Local/Observações", value=ev.get('observacao') or "", key=f"edit_local_{ev['id']}")
                        col_ec1, col_ec2 = st.columns(2)
                        with col_ec1: novo_nome_cliente_edit = st.text_input("Nome do Cliente", value=nome_cliente_ev, key=f"edit_nome_cli_{ev['id']}")
                        with col_ec2: novo_contato_cliente_edit = st.text_input("Contato do Cliente", value=contato_cliente_ev if contato_cliente_ev != "-" else "", key=f"edit_contato_cli_{ev['id']}")
                        justificativa_edit = st.text_input("Justificativa (obrigatório)", key=f"edit_just_{ev['id']}")
                        col_btn_edit1, col_btn_edit2 = st.columns(2)
                        with col_btn_edit1:
                            if st.button("💾 Salvar Alterações", key=f"btn_edit_evento_{ev['id']}"):
                                if not justificativa_edit.strip(): mostrar_popup("Informe a justificativa da alteração.", tipo="erro")
                                else:
                                    supabase.table("eventos").update({"data_inicio": str(nova_data_inicio_edit),"data_fim": str(nova_data_fim_edit),"data_fim_alocacao": str(nova_data_fim_edit),"hora_inicio": str(nova_hora_inicio_edit),"hora_fim": str(nova_hora_fim_edit),"valor_total": novo_valor_edit,"observacao": novo_local_edit}).eq("id", ev['id']).execute()
                                    if ev.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": novo_nome_cliente_edit,"contato": novo_contato_cliente_edit}).eq("id", ev['cliente_id']).execute()
                                    evento_atualizado_google = dict(ev)
                                    evento_atualizado_google.update({"data_inicio": str(nova_data_inicio_edit),"data_fim_alocacao": str(nova_data_fim_edit),"observacao": novo_local_edit})
                                    novo_id_google_edit = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], evento_atualizado_google, ev.get('google_event_id'))
                                    if novo_id_google_edit and not ev.get('google_event_id'):
                                        try: supabase.table("eventos").update({"google_event_id": novo_id_google_edit}).eq("id", ev['id']).execute()
                                        except Exception: pass
                                    data_hora_edit = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": ev['id'],"descricao": f"✏️ EDIÇÃO DE DADOS. Justificativa: {justificativa_edit}","data_registro": data_hora_edit}).execute()
                                    mostrar_popup("EDIÇÃO CONCLUÍDA COM SUCESSO!")
                                    st.rerun()
                        with col_btn_edit2:
                            if st.button("🗑️ Excluir Evento", key=f"btn_excluir_evento_{ev['id']}"):
                                try:
                                    supabase.table("itens_evento").delete().eq("evento_id", ev['id']).execute()
                                    supabase.table("historico_eventos").delete().eq("evento_id", ev['id']).execute()
                                    supabase.table("eventos").delete().eq("id", ev['id']).execute()
                                    mostrar_popup("EVENTO EXCLUÍDO COM SUCESSO!")
                                    st.rerun()
                                except Exception as e: mostrar_popup(f"Erro ao excluir: {e}", tipo="erro")

                    with tab_hist:
                        historico_ev = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev['id']).order("data_registro", desc=True).execute()
                        if historico_ev.data:
                            for h in historico_ev.data: st.write(f"🕒 **{h['data_registro']}** — {h['descricao']}")
                        else: st.caption("Nenhuma alteração registrada.")

        # ==========================================
        # HISTÓRICO DE EVENTOS PASSADOS
        # ==========================================
        st.markdown("---")
        with st.expander("🕒 Histórico de Todos os Eventos", expanded=False):
            st.caption("Todos os eventos cadastrados — inclusive os que ficaram com status em aberto (Agendado/Em Andamento sem conclusão).")
            col_hf1, col_hf2 = st.columns(2)
            with col_hf1: hist_busca = st.text_input("Buscar no histórico", placeholder="Nome do cliente ou evento...", key="hist_busca_ev")
            with col_hf2: hist_status_sel = st.multiselect(
                "Status",
                ["Concluído", "Cancelado", "Agendado", "Em Andamento"],
                default=["Concluído", "Cancelado", "Agendado", "Em Andamento"],
                key="hist_status_ev"
            )
            # Mostra TODOS os eventos que batem com o filtro de status,
            # independente de data — assim eventos esquecidos/abertos aparecem
            todos_status_validos = hist_status_sel or ["Concluído", "Cancelado", "Agendado", "Em Andamento"]
            eventos_historico = [ev for ev in lista_todos_eventos if ev.get('status') in todos_status_validos]
            if hist_busca.strip():
                termo_h = hist_busca.lower()
                eventos_historico = [ev for ev in eventos_historico if termo_h in (ev.get('descricao') or '').lower() or termo_h in (mapa_clientes.get(ev.get('cliente_id'),{}).get('nome','') or '').lower()]
            eventos_historico = sorted(eventos_historico, key=lambda x: x.get('data_inicio') or '', reverse=True)
            st.markdown(f"**{len(eventos_historico)} evento(s) encontrado(s)**")
            if eventos_historico:
                for ev_h in eventos_historico:
                    cliente_h = mapa_clientes.get(ev_h.get('cliente_id'), {})
                    nome_cli_h = cliente_h.get('nome', 'Cliente não informado')
                    titulo_h = ev_h.get('descricao') or 'Evento sem título'
                    status_h = ev_h.get('status') or '-'
                    def _fmt_h(d):
                        try: return datetime.strptime(d.split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                        except Exception: return d or '-'
                    data_ini_h = _fmt_h(ev_h.get('data_inicio') or '')
                    data_fim_h = _fmt_h(ev_h.get('data_fim_alocacao') or '')
                    valor_h = float(ev_h.get('valor_total') or 0)
                    icone_h = "✅" if status_h == "Concluído" else ("❌" if status_h == "Cancelado" else "🟡")
                    with st.expander(f"{icone_h} {titulo_h} — {nome_cli_h} | {data_ini_h} → {data_fim_h} | R$ {formatar_moeda(valor_h)} | {status_h}"):
                        itens_h = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao, valor_cobrado").eq("evento_id", ev_h['id']).execute()
                        contato_h = cliente_h.get('contato') or '-'

                        tab_det_h, tab_status_h, tab_pag_h, tab_edit_h, tab_log_h = st.tabs([
                            "📋 Detalhes", "🔄 Alterar Status", "💳 Pagamento", "✏️ Editar Dados", "🕒 Log"
                        ])

                        # --- ABA DETALHES ---
                        with tab_det_h:
                            col_h1, col_h2 = st.columns(2)
                            with col_h1:
                                st.write(f"**Cliente:** {nome_cli_h}")
                                st.write(f"**Contato:** {contato_h}")
                                st.write(f"**Período:** {data_ini_h} até {data_fim_h}")
                                st.write(f"**Valor:** R$ {formatar_moeda(valor_h)}")
                                st.write(f"**Local/Obs:** {ev_h.get('observacao') or '-'}")
                            with col_h2:
                                st.write(f"**Status:** {status_h}")
                                pag_h = "✅ Confirmado" if ev_h.get('pagamento_confirmado') else "⏳ Pendente"
                                st.write(f"**Pagamento:** {pag_h}")
                                if ev_h.get('metodo_confirmacao_pagamento'): st.write(f"**Método:** {ev_h['metodo_confirmacao_pagamento']}")
                                if ev_h.get('data_confirmacao_pagamento'): st.write(f"**Confirmado em:** {ev_h['data_confirmacao_pagamento']}")
                            if itens_h.data:
                                st.markdown("**Itens alocados:**")
                                for it_h in itens_h.data:
                                    nome_p_h = dict_produtos.get(it_h['produto_id'],{}).get('nome',f"Produto #{it_h['produto_id']}")
                                    det_h = ""
                                    js_h = safe_json_load(it_h.get('observacao'))
                                    if js_h: det_h = " — " + ", ".join([f"{k}: {v}x" for k,v in js_h.items()])
                                    st.write(f"  • {it_h['quantidade']}x {nome_p_h}{det_h}")
                            if REPORTLAB_DISPONIVEL:
                                nome_usuario_pdf_h = st.session_state.get('nome_usuario') or 'Usuário'
                                buffer_pdf_h = gerar_recibo_evento_pdf(ev_h, itens_h.data or [], dict_produtos, nome_cli_h, contato_h, nome_usuario_pdf_h)
                                st.download_button("📄 Baixar Recibo (PDF)", data=buffer_pdf_h, file_name=f"recibo_historico_{ev_h['id']}.pdf", mime="application/pdf", key=f"pdf_hist_{ev_h['id']}")

                        # --- ABA ALTERAR STATUS ---
                        with tab_status_h:
                            st.caption("Corrija o status deste evento caso tenha ficado em aberto por engano.")
                            opcoes_status_h = ["Agendado","Em Andamento","Concluído","Cancelado"]
                            idx_status_h = opcoes_status_h.index(status_h) if status_h in opcoes_status_h else 0
                            novo_status_h = st.selectbox("Novo Status", opcoes_status_h, index=idx_status_h, key=f"hist_status_sel_{ev_h['id']}")
                            just_status_h = st.text_input("Justificativa (obrigatório)", key=f"hist_just_status_{ev_h['id']}")
                            if st.button("✅ Salvar Status", key=f"hist_btn_status_{ev_h['id']}"):
                                if not just_status_h.strip():
                                    mostrar_popup("Informe a justificativa.", tipo="erro")
                                else:
                                    supabase.table("eventos").update({"status": novo_status_h}).eq("id", ev_h['id']).execute()
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev_h['id'], "descricao": f"🔄 STATUS ALTERADO para '{novo_status_h}' via Histórico. Motivo: {just_status_h}", "data_registro": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}).execute()
                                    mostrar_popup("STATUS ATUALIZADO COM SUCESSO!")
                                    st.rerun()

                        # --- ABA PAGAMENTO ---
                        with tab_pag_h:
                            if ev_h.get('pagamento_confirmado'):
                                st.success(f"✅ Pagamento confirmado via **{ev_h.get('metodo_confirmacao_pagamento','-')}** em {ev_h.get('data_confirmacao_pagamento','-')}")
                                if st.button("🗑️ Desfazer Confirmação", key=f"hist_del_pag_{ev_h['id']}"):
                                    supabase.table("eventos").update({"pagamento_confirmado": False, "metodo_confirmacao_pagamento": None, "data_confirmacao_pagamento": None}).eq("id", ev_h['id']).execute()
                                    mostrar_popup("CONFIRMAÇÃO REMOVIDA!")
                                    st.rerun()
                            else:
                                st.warning("⏳ Pagamento ainda não confirmado.")
                                metodo_pag_h = st.selectbox("Como foi feito o pagamento?", ["Pix","Dinheiro","Cartão","Boleto","Outro"], key=f"hist_metodo_pag_{ev_h['id']}")
                                if st.button("✅ Confirmar Pagamento", key=f"hist_btn_pag_{ev_h['id']}"):
                                    supabase.table("eventos").update({"pagamento_confirmado": True, "metodo_confirmacao_pagamento": metodo_pag_h, "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")}).eq("id", ev_h['id']).execute()
                                    mostrar_popup("PAGAMENTO CONFIRMADO!")
                                    st.rerun()

                        # --- ABA EDITAR DADOS ---
                        with tab_edit_h:
                            st.caption("Corrija datas, valor, local ou dados do cliente.")
                            def _pd(d):
                                if not d: return datetime.now().date()
                                try: return datetime.strptime(d.split("T")[0], "%Y-%m-%d").date()
                                except: return datetime.now().date()
                            def _pt(t):
                                if not t: return datetime.min.time()
                                try: return datetime.strptime(t[:5], "%H:%M").time()
                                except: return datetime.min.time()
                            col_he1, col_he2, col_he3, col_he4 = st.columns(4)
                            with col_he1: nd_ini_h = st.date_input("Data Início", value=_pd(ev_h.get('data_inicio')), format="DD/MM/YYYY", key=f"hedit_ini_{ev_h['id']}")
                            with col_he2: nd_fim_h = st.date_input("Data Fim", value=_pd(ev_h.get('data_fim_alocacao')), format="DD/MM/YYYY", key=f"hedit_fim_{ev_h['id']}")
                            with col_he3: nh_ini_h = st.time_input("Hora Início", value=_pt(ev_h.get('hora_inicio')), key=f"hedit_hini_{ev_h['id']}")
                            with col_he4: nh_fim_h = st.time_input("Hora Fim", value=_pt(ev_h.get('hora_fim')), key=f"hedit_hfim_{ev_h['id']}")
                            nval_h = st.number_input("Valor (R$)", min_value=0.0, step=50.0, value=float(ev_h.get('valor_total') or 0), format="%.2f", key=f"hedit_val_{ev_h['id']}")
                            nobs_h = st.text_area("Local/Observações", value=ev_h.get('observacao') or "", key=f"hedit_obs_{ev_h['id']}")
                            col_hec1, col_hec2 = st.columns(2)
                            with col_hec1: nnome_cli_h = st.text_input("Nome do Cliente", value=nome_cli_h, key=f"hedit_nome_{ev_h['id']}")
                            with col_hec2: ncont_cli_h = st.text_input("Contato", value=contato_h if contato_h != "-" else "", key=f"hedit_cont_{ev_h['id']}")
                            njust_h = st.text_input("Justificativa (obrigatório)", key=f"hedit_just_{ev_h['id']}")
                            col_hbtn1, col_hbtn2 = st.columns(2)
                            with col_hbtn1:
                                if st.button("💾 Salvar Alterações", key=f"hedit_btn_{ev_h['id']}"):
                                    if not njust_h.strip(): mostrar_popup("Informe a justificativa.", tipo="erro")
                                    else:
                                        supabase.table("eventos").update({"data_inicio": str(nd_ini_h), "data_fim": str(nd_fim_h), "data_fim_alocacao": str(nd_fim_h), "hora_inicio": str(nh_ini_h), "hora_fim": str(nh_fim_h), "valor_total": nval_h, "observacao": nobs_h}).eq("id", ev_h['id']).execute()
                                        if ev_h.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": nnome_cli_h, "contato": ncont_cli_h}).eq("id", ev_h['cliente_id']).execute()
                                        supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev_h['id'], "descricao": f"✏️ EDIÇÃO via Histórico. Justificativa: {njust_h}", "data_registro": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}).execute()
                                        mostrar_popup("ALTERAÇÃO SALVA COM SUCESSO!")
                                        st.rerun()
                            with col_hbtn2:
                                if st.button("🗑️ Excluir Evento", key=f"hedit_del_{ev_h['id']}"):
                                    try:
                                        supabase.table("itens_evento").delete().eq("evento_id", ev_h['id']).execute()
                                        supabase.table("historico_eventos").delete().eq("evento_id", ev_h['id']).execute()
                                        supabase.table("eventos").delete().eq("id", ev_h['id']).execute()
                                        mostrar_popup("EVENTO EXCLUÍDO!")
                                        st.rerun()
                                    except Exception as e: mostrar_popup(f"Erro ao excluir: {e}", tipo="erro")

                        # --- ABA LOG ---
                        with tab_log_h:
                            hist_alt = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev_h['id']).order("data_registro", desc=True).execute()
                            if hist_alt.data:
                                for h_alt in hist_alt.data: st.write(f"🕒 **{h_alt['data_registro']}** — {h_alt['descricao']}")
                            else: st.caption("Nenhuma alteração registrada.")

            else: st.info("Nenhum evento histórico encontrado com esses filtros.")

        st.markdown("---")
        with st.expander("📝 Cadastrar Novo Evento", expanded=False):
            st.markdown("**🗓️ Primeiro, escolha as datas e horários do evento:**")
            col_data1, col_data2, col_hora1, col_hora2 = st.columns(4)
            with col_data1: data_inicio = st.date_input("Data Início", format="DD/MM/YYYY", key="novo_evento_data_inicio")
            with col_data2: data_fim = st.date_input("Data Fim", value=data_inicio, min_value=data_inicio, format="DD/MM/YYYY", key="novo_evento_data_fim")
            with col_hora1: hora_inicio = st.time_input("Hora Início", key="novo_evento_hora_inicio")
            with col_hora2: hora_fim = st.time_input("Hora Fim", key="novo_evento_hora_fim")
            qtd_alugada_form, detalhe_alugado_form = calcular_disponibilidade_periodo(data_inicio, data_fim, hora_inicio, hora_fim)
            with st.form("form_evento"):
                col_1, col_2, col_3, col_3b = st.columns(4)
                with col_1: nome_evento = st.text_input("Título do Evento")
                with col_2: nome_cliente = st.text_input("Nome do Cliente")
                with col_3: contato_cliente = st.text_input("Contato (Telefone/WhatsApp)", placeholder="(84) 99999-9999")
                with col_3b: status_evento = st.selectbox("Status", ["Agendado","Em Andamento","Concluído","Cancelado"])
                st.info(f"📅 Datas selecionadas: **{data_inicio.strftime('%d/%m/%Y')}** até **{data_fim.strftime('%d/%m/%Y')}**")
                valor_evento = st.number_input("Valor Cobrado pelo Evento (R$)", min_value=0.0, step=50.0, value=None, format="%.2f")
                st.markdown("**📍 Localização do Evento**")
                col_7, col_8, col_9, col_10 = st.columns([2,2,1.5,0.5])
                with col_7: local_evento = st.text_input("Local do Evento")
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
                                            qtd_item = cols_k[idx%10].number_input(f"{k} (Livre:{max(0,disponivel_k)})", min_value=0, max_value=max(0,disponivel_k), value=None, key=f"aloc_{prod['id']}_{k}")
                                            quantidades_selecionadas[f"{prod['id']}_{k}"] = qtd_item or 0
                                            idx += 1
                                    st.markdown("---")
                                else:
                                    with colunas[index%3]:
                                        disponivel_normal = max(0, prod['quantidade_estoque'] - qtd_alugada_form.get(prod['id'],0))
                                        qtd_item_normal = st.number_input(f"{prod['nome']} (Livre: {disponivel_normal})", min_value=0, max_value=disponivel_normal, value=None, key=f"form_prod_{prod['id']}")
                                        quantidades_selecionadas[f"{prod['id']}_NORMAL"] = qtd_item_normal or 0
                if st.form_submit_button("Salvar Evento e Alocar Itens"):
                    if not nome_evento or not nome_cliente or not contato_cliente or not local_evento or not rua_evento or not bairro_evento or not numero_evento or valor_evento is None:
                        mostrar_popup("Por favor, preencha todos os campos obrigatórios!", tipo="erro")
                    else:
                        estoque_insuficiente = False
                        msg_erro_estoque = ""
                        alocacoes_agrupadas = {}
                        for key, qtd in quantidades_selecionadas.items():
                            if qtd > 0:
                                p_id_str, sub_item = key.split("_", 1)
                                p_id_int = int(p_id_str)
                                prod_info = next((p for p in produtos_disp.data if p['id'] == p_id_int), None)
                                if not prod_info: continue
                                if sub_item == "NORMAL":
                                    disp = max(0, prod_info['quantidade_estoque'] - qtd_alugada_form.get(p_id_int,0))
                                    if qtd > disp:
                                        estoque_insuficiente = True
                                        msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']}. Pediu {qtd}, temos {disp} livres."
                                        break
                                else:
                                    js_est = safe_json_load(prod_info.get('observacao')) or {}
                                    disp_sub = max(0, js_est.get(sub_item,0) - detalhe_alugado_form.get(p_id_int,{}).get(sub_item,0))
                                    if qtd > disp_sub:
                                        estoque_insuficiente = True
                                        msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']} ({sub_item}). Pediu {qtd}, temos {disp_sub} livres."
                                        break
                                if p_id_int not in alocacoes_agrupadas: alocacoes_agrupadas[p_id_int] = {'total':0,'detalhes':{}}
                                alocacoes_agrupadas[p_id_int]['total'] += qtd
                                if sub_item != "NORMAL": alocacoes_agrupadas[p_id_int]['detalhes'][sub_item] = qtd
                        if estoque_insuficiente:
                            mostrar_popup(msg_erro_estoque, tipo="erro")
                        else:
                            try:
                                contato_cliente_formatado = formatar_telefone_br(contato_cliente)
                                novo_cliente = supabase.table("clientes_eventos").insert({"empresa_id": emp_id,"nome": nome_cliente,"contato": contato_cliente_formatado}).execute()
                                cliente_id_gerado = novo_cliente.data[0]['id']
                                novo_evento = supabase.table("eventos").insert({"empresa_id": emp_id,"cliente_id": cliente_id_gerado,"titulo": nome_evento,"descricao": nome_evento,"data_inicio": str(data_inicio),"data_fim": str(data_fim),"data_fim_alocacao": str(data_fim),"hora_inicio": str(hora_inicio),"hora_fim": str(hora_fim),"status": status_evento,"observacao": f"Local: {local_evento} - {rua_evento}, {numero_evento} - {bairro_evento} - {obs_evento_geral}","valor_total": valor_evento}).execute()
                                evento_id_gerado = novo_evento.data[0]['id']
                                google_event_id_novo = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], novo_evento.data[0])
                                if google_event_id_novo:
                                    try: supabase.table("eventos").update({"google_event_id": google_event_id_novo}).eq("id", evento_id_gerado).execute()
                                    except Exception: pass
                                data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                for p_id, info in alocacoes_agrupadas.items():
                                    obs_json_evento = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                    valor_sugerido = info['total'] * mapa_valor_ref.get(p_id, 0)
                                    supabase.table("itens_evento").insert({"empresa_id": emp_id,"evento_id": evento_id_gerado,"produto_id": p_id,"quantidade": info['total'],"observacao": obs_json_evento,"valor_cobrado": valor_sugerido}).execute()
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id,"evento_id": evento_id_gerado,"descricao": f"🟢 ALOCAÇÃO INICIAL: Adicionou {info['total']}x Produto {p_id}.","data_registro": data_hora}).execute()
                                mostrar_popup("CADASTRO DE EVENTO CONCLUÍDO COM SUCESSO!")
                                st.rerun()
                            except Exception as e: mostrar_popup(f"Erro: {e}", tipo="erro")


    # ==========================================
    # MENU: ESTOQUE
    # ==========================================
    elif menu == "📦 Estoque":
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
                df_produtos['Item'] = df_produtos['Ícone'] + " " + df_produtos['nome']
                df_produtos['Estoque Total'] = df_produtos['quantidade_estoque']
                def format_obs(val):
                    js = safe_json_load(val)
                    if js: return ", ".join([f"{k}: {v}x" for k,v in js.items()])
                    return val if val else ""
                df_produtos['Detalhes/Inventário'] = df_produtos['observacao'].apply(format_obs)
                df_produtos['Status'] = df_produtos['quantidade_estoque'].apply(status_cor)
                try: qtd_alugada, detalhe_alugado = calcular_disponibilidade_periodo(data_inicio_f, data_fim_f)
                except Exception as e:
                    st.exception(e)
                    qtd_alugada, detalhe_alugado = {}, {}
                def calcular_disponivel(row): return row['quantidade_estoque'] - qtd_alugada.get(row['id'],0)
                def calc_livres_detalhe(row):
                    js_estoque = safe_json_load(row['observacao'])
                    if js_estoque:
                        alugados = detalhe_alugado.get(row['id'],{})
                        livres = []
                        for k, v in js_estoque.items():
                            restante = v - alugados.get(k,0)
                            if restante > 0: livres.append(f"{k}: {restante}x")
                        return ", ".join(livres) if livres else "Tudo alugado"
                    return ""
                df_produtos['Reservado na Data'] = df_produtos['id'].map(lambda x: qtd_alugada.get(x,0))
                df_produtos['Disponível Livre'] = df_produtos.apply(calcular_disponivel, axis=1)
                df_produtos['Sub-Itens Livres na Data'] = df_produtos.apply(calc_livres_detalhe, axis=1)
                colunas_mostrar = ['Item','Status','Detalhes/Inventário','Estoque Total','Reservado na Data','Disponível Livre','Sub-Itens Livres na Data']
                total_geral_estoque = int(df_produtos['Estoque Total'].sum())
                total_geral_reservado = int(df_produtos['Reservado na Data'].sum())
                total_geral_livre = int(df_produtos['Disponível Livre'].sum())
                st.markdown("#### 📊 Resumo Geral do Período Selecionado")
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("📦 Estoque Total", total_geral_estoque)
                col_m2.metric("🔒 Reservado no Período", total_geral_reservado)
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
                    produtos_cat_com_reserva = df_cat[df_cat['Reservado na Data'] > 0]
                    if not produtos_cat_com_reserva.empty:
                        st.caption("🕐 Detalhamento por dia e horário:")
                        for _, prod_row in produtos_cat_com_reserva.iterrows():
                            linhas_detalhe = calcular_detalhamento_periodo_produto(data_inicio_f, data_fim_f, prod_row['id'], prod_row['Estoque Total'])
                            if linhas_detalhe:
                                with st.expander(f"{prod_row['Ícone']} {prod_row['nome']}", expanded=False):
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
                        val_add_k = cols_add_kit[idx_add%10].number_input(f"{k} (Tem: {v_atual})", min_value=0, value=0, key=f"add_kit_{prod_alvo_add['id']}_{k}")
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
                                "detalhes_kit": json.dumps(qtds_manut_kit) if qtds_manut_kit else None
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

                                prazo_vencido = False
                                dias_atraso = 0
                                if data_prev_m and data_prev_m != '-':
                                    try:
                                        dt_prev = datetime.strptime(data_prev_m, "%Y-%m-%d").date()
                                        if hoje_manut > dt_prev:
                                            prazo_vencido = True
                                            dias_atraso = (hoje_manut - dt_prev).days
                                    except Exception:
                                        pass

                                detalhes_kit_m = ""
                                if m.get('detalhes_kit'):
                                    try:
                                        dk = json.loads(m['detalhes_kit'])
                                        detalhes_kit_m = " | Peças: " + ", ".join([f"{k}: {v}x" for k, v in dk.items()])
                                    except Exception:
                                        pass

                                # Cabeçalho do item
                                if prazo_vencido:
                                    st.error(f"⚠️ **{nome_p}** — {m['quantidade']} un. | Enviado: {data_envio_m} | Previsão: {data_prev_m} — **ATRASADO {dias_atraso} dia(s)**{detalhes_kit_m}")
                                else:
                                    st.warning(f"🔧 **{nome_p}** — {m['quantidade']} un. | Enviado: {data_envio_m} | Retorno previsto: {data_prev_m}{detalhes_kit_m}")
                                st.caption(f"Motivo: {m['motivo']}")

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
                                        st.caption("Use se o item não tiver mais conserto. Será registrado no histórico de quebrados.")
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
                                                    "motivo": f"[Veio da manutenção] {motivo_quebra_manut}",
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

                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button("✅ Confirmar Retorno ao Estoque", key=f"ret_manut_{m['id']}", use_container_width=True, type="primary"):
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
                                                    supabase.table("produtos").update({"quantidade_estoque": estq_novo_ret}).eq("id", m['produto_id']).execute()
                                            else:
                                                supabase.table("produtos").update({"quantidade_estoque": estq_novo_ret}).eq("id", m['produto_id']).execute()

                                            supabase.table("manutencao").update({
                                                "status": "Concluído",
                                                "data_retorno_real": str(datetime.now().date())
                                            }).eq("id", m['id']).execute()
                                            mostrar_popup("Produto devolvido ao estoque com sucesso!")
                                            st.rerun()

                                st.markdown("---")
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
                                        pass
                                data_retorno_real = mc.get('data_retorno_real', '-')

                                with st.expander(
                                    f"✅ {nome_pc} — {mc['quantidade']} un. | "
                                    f"Enviado: {mc.get('data_envio','-')} | "
                                    f"Retornou: {data_retorno_real}{detalhes_kit_c}",
                                    expanded=False
                                ):
                                    st.caption(f"Motivo: {mc['motivo']}")

                                    col_btn_mc1, col_btn_mc2 = st.columns(2)
                                    with col_btn_mc1:
                                        if st.button("✏️ Editar Registro", key=f"toggle_edit_mc_{mc['id']}"):
                                            chave = f"editando_mc_{mc['id']}"
                                            st.session_state[chave] = not st.session_state.get(chave, False)
                                            st.rerun()
                                    with col_btn_mc2:
                                        if st.button("🗑️ Excluir do Histórico", key=f"del_hist_mc_{mc['id']}"):
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
                                                val_data_ret = datetime.now().date()
                                            nova_data_retorno_mc = st.date_input(
                                                "Data de Retorno Real",
                                                value=val_data_ret,
                                                format="DD/MM/YYYY",
                                                key=f"edit_retorno_mc_{mc['id']}"
                                            )

                                        if st.button("💾 Salvar Edição", key=f"salvar_edit_mc_{mc['id']}"):
                                            supabase.table("manutencao").update({
                                                "motivo": novo_motivo_mc,
                                                "data_envio": str(nova_data_envio_mc),
                                                "data_retorno_real": str(nova_data_retorno_mc)
                                            }).eq("id", mc['id']).execute()
                                            st.session_state[f"editando_mc_{mc['id']}"] = False
                                            mostrar_popup("Registro atualizado com sucesso!")
                                            st.rerun()
                                            
                                        with col_btn_mc2:
                                        st.warning("Excluir remove apenas o registro histórico.")
                                        if st.button("🗑️ Excluir do Histórico", key=f"del_hist_mc_{mc['id']}"):
                                            supabase.table("manutencao").delete().eq("id", mc['id']).execute()
                                            mostrar_popup("Registro excluído do histórico.")
                                            st.rerun()
                    else:
                        st.info("Nenhum registro de manutenção ainda.")
                except Exception as e:
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
                    st.error(f"Erro ao carregar itens quebrados: {e}")


    # ==========================================
    # MENU: COMPRAS
    # ==========================================
    elif menu == "🛒 Compras":
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


    # ==========================================
    # MENU: FATURAMENTO
    # ==========================================
    elif menu == "💰 Faturamento":
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
            except Exception: return False
        eventos_fat = supabase.table("eventos").select("id, data_inicio, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status","Cancelado").execute()
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
            except Exception: return str(d)
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
                        except Exception: pass
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

    # ==========================================
    # MENU: ORÇAMENTO
    # ==========================================
    elif menu == "🧳 Orçamento":
        st.title("🧳 Orçamento de Evento")

        ENDERECO_BASE_EMPRESA = st.secrets.get("ENDERECO_BASE_EMPRESA", "")

        produtos_orc = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao, valor_locacao").eq("empresa_id", emp_id).order("nome").execute()
        dict_produtos_orc = {p['id']: p for p in produtos_orc.data} if produtos_orc.data else {}

        tab_criar_orc, tab_lista_orc = st.tabs(["📝 Criar Orçamento", "📋 Orçamentos Salvos"])

        # ==========================================
        # CRIAR NOVO ORÇAMENTO
        # ==========================================
        with tab_criar_orc:
            st.markdown("#### 👤 Dados do Cliente e Evento")
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

            st.markdown("---")
            st.markdown("#### 🛒 Itens do Orçamento")
            st.caption("Quantidades aproximadas. O detalhamento exato (ex: letras específicas) é feito na hora de confirmar o evento.")
            itens_selecionados_orc = {}
            if produtos_orc.data:
                for p in produtos_orc.data:
                    js_p = safe_json_load(p.get('observacao'))
                    valor_ref = float(p.get('valor_locacao') or 0)
                    col_p1, col_p2 = st.columns([2,1])
                    with col_p1:
                        qtd_p = st.number_input(f"{p['nome']} (Estoque: {p['quantidade_estoque']})", min_value=0, value=0, key=f"orc_qtd_{p['id']}")
                    with col_p2:
                        valor_unit_p = st.number_input("Valor unit. (R$)", min_value=0.0, value=valor_ref, format="%.2f", key=f"orc_valor_{p['id']}")
                    if qtd_p > 0:
                        itens_selecionados_orc[p['id']] = {"nome": p['nome'], "quantidade": qtd_p, "valor_unit": valor_unit_p, "valor_total": qtd_p * valor_unit_p, "kit": bool(js_p)}

            valor_itens_orc = sum(it['valor_total'] for it in itens_selecionados_orc.values())
            st.info(f"💲 Subtotal dos Itens: **R$ {formatar_moeda(valor_itens_orc)}**")

            st.markdown("---")
            st.markdown("#### 🚗 Frete / Deslocamento")
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
            with col_c1: distancia_manual = st.number_input("Distância (km, ida)", min_value=0.0, value=float(km_atual), format="%.1f", key="orc_dist_manual")
            with col_c2: consumo_veic = st.number_input("Consumo do veículo (km/l)", min_value=0.1, value=10.0, format="%.1f", key="orc_consumo")
            with col_c3: preco_comb = st.number_input("Preço do combustível (R$/l)", min_value=0.0, value=6.20, format="%.2f", key="orc_preco_comb")

            valor_frete_sugerido = (distancia_manual * 2 / consumo_veic) * preco_comb if consumo_veic > 0 else 0.0
            st.caption(f"⛽ Sugestão automática (ida e volta): R$ {formatar_moeda(valor_frete_sugerido)}")
            valor_frete_orc = st.number_input("Valor final do Frete (R$)", min_value=0.0, value=valor_frete_sugerido, format="%.2f", key="orc_frete_final")

            st.markdown("---")
            col_d1, col_d2 = st.columns(2)
            with col_d1: desconto_orc = st.number_input("Desconto (R$)", min_value=0.0, value=0.0, format="%.2f", key="orc_desconto")
            with col_d2: validade_orc = st.number_input("Validade da Proposta (dias)", min_value=1, value=7, key="orc_validade")
            obs_orc = st.text_area("Observações", key="orc_obs")

            valor_total_orc = max(0.0, valor_itens_orc + valor_frete_orc - desconto_orc)
            st.success(f"### 💰 Valor Total do Orçamento: R$ {formatar_moeda(valor_total_orc)}")

            col_sv1, col_sv2 = st.columns(2)
            with col_sv1:
                if st.button("💾 Salvar Orçamento", key="btn_salvar_orc", use_container_width=True):
                    if not nome_cliente_orc.strip() or not titulo_orc.strip():
                        mostrar_popup("Preencha ao menos o nome do cliente e o título do evento.", tipo="erro")
                    elif not itens_selecionados_orc:
                        mostrar_popup("Selecione ao menos um item.", tipo="erro")
                    else:
                        try:
                            supabase.table("orcamentos").insert({
                                "empresa_id": emp_id, "nome_cliente": nome_cliente_orc, "contato_cliente": contato_cliente_orc,
                                "titulo_evento": titulo_orc, "endereco_evento": endereco_evento_orc,
                                "data_inicio": str(data_ini_orc), "data_fim": str(data_fim_orc),
                                "hora_inicio": str(hora_ini_orc), "hora_fim": str(hora_fim_orc),
                                "itens_json": json.dumps(itens_selecionados_orc), "valor_itens": valor_itens_orc,
                                "origem_endereco": origem_orc, "distancia_km": distancia_manual, "duracao_min": dur_atual,
                                "consumo_veiculo": consumo_veic, "preco_combustivel": preco_comb, "valor_frete": valor_frete_orc,
                                "desconto": desconto_orc, "valor_total": valor_total_orc, "validade_dias": int(validade_orc),
                                "status": "Rascunho", "observacoes": obs_orc
                            }).execute()
                            mostrar_popup("ORÇAMENTO SALVO COM SUCESSO!")
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
