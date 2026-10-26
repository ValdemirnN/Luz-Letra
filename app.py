import streamlit as st
import streamlit.components.v1 as components
import json
import hashlib
import hmac
import bcrypt
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
from modulos.log import registrar_erro
from modulos.login_ui import aplicar_estilo_login, cabecalho_login, rodape_login

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_DISPONIVEL = True
except ImportError:
    registrar_erro("app.py:31")
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

# --- Ajustes para "Adicionar à Tela de Início" no iPhone (web app) ---
components.html("""
<script>
(function() {
  try {
    var d = window.parent.document;
    var origem = window.parent.location.origin;
    function addMeta(nome, conteudo) {
      if (d.querySelector('meta[name="' + nome + '"]')) return;
      var m = d.createElement('meta'); m.name = nome; m.content = conteudo; d.head.appendChild(m);
    }
    addMeta('apple-mobile-web-app-capable', 'yes');
    addMeta('mobile-web-app-capable', 'yes');
    addMeta('apple-mobile-web-app-title', 'Luz & Letras');
    addMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
    addMeta('theme-color', '#0E0E0E');
    var vp = d.querySelector('meta[name="viewport"]');
    if (vp && vp.content.indexOf('viewport-fit') === -1) vp.content = vp.content + ', viewport-fit=cover';
    if (!d.querySelector('link[rel="apple-touch-icon"]')) {
      var l = d.createElement('link'); l.rel = 'apple-touch-icon';
      l.href = origem + '/app/static/apple-touch-icon.png'; d.head.appendChild(l);
    }
  } catch (e) {}
})();
</script>
""", height=0)

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

# ==========================================
# SENHAS (bcrypt) — com compatibilidade para senhas antigas em texto puro
# ==========================================
def _senha_bytes(senha):
    return (senha or "").encode("utf-8")[:72]  # limite do bcrypt

def hash_senha(senha):
    return bcrypt.hashpw(_senha_bytes(senha), bcrypt.gensalt()).decode("utf-8")

def senha_ja_hasheada(armazenado):
    return isinstance(armazenado, str) and armazenado.startswith(("$2a$", "$2b$", "$2y$"))

def verificar_senha(digitada, armazenado):
    """Aceita hash bcrypt e, enquanto houver, senhas antigas em texto puro (migradas no login)."""
    if not digitada or not armazenado: return False
    if senha_ja_hasheada(armazenado):
        try: return bcrypt.checkpw(_senha_bytes(digitada), armazenado.encode("utf-8"))
        except Exception: registrar_erro("app.py:141"); return False
    return hmac.compare_digest(digitada.encode("utf-8"), armazenado.encode("utf-8"))

def gerar_payload_pix(chave, nome_beneficiario, cidade, valor, descricao="Assinatura"):
    if not chave or not nome_beneficiario or not cidade:
        raise ValueError("Chave PIX não configurada. Defina PIX_CHAVE, PIX_NOME e PIX_CIDADE nos secrets.")
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
    except Exception: registrar_erro("app.py:225"); pass

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
PIX_CHAVE = st.secrets.get("PIX_CHAVE", "")
PIX_NOME = st.secrets.get("PIX_NOME", "")
PIX_CIDADE = st.secrets.get("PIX_CIDADE", "")

@st.cache_resource
def init_connection(): return create_client(SUPABASE_URL, SUPABASE_KEY)

try: supabase: Client = init_connection()
except Exception as e:
    registrar_erro("app.py:249")
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
        except Exception: registrar_erro("app.py:266"); pass
    try:
        cookie_manager.delete("tk", key="del_tk_logout")
        cookie_manager.delete("uid", key="del_uid_logout")
    except Exception:
        registrar_erro("app.py:271")
        pass
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None, 'tentativas_restauro': 99})

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
                    registrar_erro("app.py:287")
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
    except Exception: registrar_erro("app.py:304"); pass

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
        registrar_erro("app.py:319")
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
    except Exception: registrar_erro("app.py:335"); pass

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
        st.cache_data.clear()
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
  • PIX: {PIX_CHAVE} ({PIX_NOME})
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
    except Exception: registrar_erro("app.py:414"); return False

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
            except Exception: registrar_erro("app.py:432"); continue
            dias_restantes = (venc_date - hoje).days
            marcos = [7, 3, 1]
            if dias_restantes not in marcos: continue
            try:
                ja_enviou = supabase.table("notificacoes_enviadas").select("id").eq("usuario_id", u['id']).eq("tipo", f"expiracao_{dias_restantes}d").eq("referencia", venc_str).execute()
                if ja_enviou.data: continue
            except Exception: registrar_erro("app.py:439"); pass
            nome_dest = u.get('nome') or u['email']
            venc_fmt = datetime.strptime(venc_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            sucesso = enviar_email_expiracao(u['email'], nome_dest, dias_restantes, venc_fmt)
            if sucesso:
                try:
                    supabase.table("notificacoes_enviadas").insert({"usuario_id": u['id'], "tipo": f"expiracao_{dias_restantes}d", "referencia": venc_str, "enviado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}).execute()
                except Exception: registrar_erro("app.py:446"); pass
    except Exception: registrar_erro("app.py:447"); pass

@st.cache_data(ttl=60, show_spinner=False)
def _buscar_vencimento_cache(empresa_id):
    r = supabase.table("assinaturas").select("data_vencimento").eq("empresa_id", empresa_id).order("data_vencimento", desc=True).limit(1).execute()
    return r.data[0]['data_vencimento'] if r.data else None

def verificar_acesso_e_bloquear():
    if st.session_state.get('perfil') == 'admin_geral': return 'ok'
    empresa_id = st.session_state.get('empresa_id')
    if not empresa_id: return 'ok'
    try:
        venc_bruto = _buscar_vencimento_cache(empresa_id)
        if not venc_bruto: return 'ok'
        venc_str = venc_bruto.split("T")[0]
        venc_date = datetime.strptime(venc_str, "%Y-%m-%d").date()
        hoje = datetime.now().date()
        dias_restantes = (venc_date - hoje).days
        if dias_restantes < -1:
            supabase.table("usuarios").update({"ativo": False}).eq("id", st.session_state['usuario_id']).execute()
            return 'bloqueado'
        elif dias_restantes <= 0: return 'aviso_vencendo'
        elif dias_restantes in [1, 2, 3, 7]: return f'aviso_{dias_restantes}_dias'
        else: return 'ok'
    except Exception: registrar_erro("app.py:471"); return 'ok'

def registrar_pagamento_historico(empresa_id, usuario_id, plano, valor, metodo, venc_anterior, venc_novo, aprovado_por="Sistema"):
    try:
        supabase.table("historico_pagamentos").insert({
            "empresa_id": empresa_id, "usuario_id": usuario_id, "plano": plano,
            "valor": valor, "metodo_pagamento": metodo,
            "data_pagamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vencimento_anterior": venc_anterior, "vencimento_novo": venc_novo,
            "aprovado_por": aprovado_por
        }).execute()
    except Exception: registrar_erro("app.py:482"); pass

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
                except Exception: registrar_erro("app.py:509"); email_google_conectado = ""
                supabase.table("usuarios").update({"google_refresh_token": refresh_token_novo, "google_email_conectado": email_google_conectado}).eq("id", usuario_id_google).execute()
                st.session_state['sucesso_msg'] = "GOOGLE AGENDA CONECTADA COM SUCESSO!"
            else:
                st.session_state['erro_google_msg'] = "Não recebemos permissão de acesso contínuo do Google. Remova o acesso em myaccount.google.com/permissions e tente conectar novamente."
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        registrar_erro("app.py:517")
        st.session_state['erro_google_msg'] = f"Erro ao conectar Google Agenda: {e}"
        try: st.query_params.clear()
        except Exception: registrar_erro("app.py:520"); pass

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
    except Exception: registrar_erro("app.py:557"); return None

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
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None, 'tentativas_restauro': 0})

# Ao atualizar a página (F5) os cookies só chegam do navegador na 2ª execução do script.
# Por isso tentamos restaurar a sessão por mais de uma execução, até os cookies carregarem.
if not st.session_state['logado'] and st.session_state.get('tentativas_restauro', 0) < 3:
    st.session_state['tentativas_restauro'] = st.session_state.get('tentativas_restauro', 0) + 1
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
        registrar_erro("app.py:605")
        return False

def validar_senha_forte(senha):
    import re
    return {
        "Mínimo de 7 caracteres": len(senha or "") >= 7,
        "Pelo menos uma letra maiúscula": bool(re.search(r'[A-Z]', senha or "")),
        "Pelo menos um número": bool(re.search(r'[0-9]', senha or "")),
    }    

# ==========================================
# LIMITE DE TENTATIVAS DE LOGIN (por e-mail, no servidor)
# Fica na memória do servidor (não no session_state), então recarregar a página
# ou abrir outra aba NÃO zera o contador. Reinicia se o app reiniciar.
# ==========================================
LOGIN_MAX_TENTATIVAS = 5      # falhas seguidas permitidas
LOGIN_JANELA_SEG = 15 * 60    # falhas mais antigas que isso são esquecidas
LOGIN_BLOQUEIO_SEG = 5 * 60   # tempo de bloqueio após estourar o limite

@st.cache_resource
def _registro_tentativas_login():
    return {}  # {email: {"falhas": [timestamps], "bloqueado_ate": ts}}

def _chave_login(email):
    return (email or "").strip().lower()

def login_segundos_bloqueado(email):
    reg = _registro_tentativas_login().get(_chave_login(email))
    if not reg: return 0
    return max(0, int(reg.get("bloqueado_ate", 0) - time.time()))

def login_registrar_falha(email):
    registro = _registro_tentativas_login()
    agora = time.time()
    reg = registro.setdefault(_chave_login(email), {"falhas": [], "bloqueado_ate": 0})
    reg["falhas"] = [t for t in reg["falhas"] if agora - t < LOGIN_JANELA_SEG] + [agora]
    if len(reg["falhas"]) >= LOGIN_MAX_TENTATIVAS:
        reg["bloqueado_ate"] = agora + LOGIN_BLOQUEIO_SEG
        reg["falhas"] = []
    if len(registro) > 5000:  # evita crescer sem limite
        for k in [k for k, v in registro.items() if v["bloqueado_ate"] < agora and not v["falhas"]]: registro.pop(k, None)

def login_limpar_falhas(email):
    _registro_tentativas_login().pop(_chave_login(email), None)

# ==========================================
# TELA DE LOGIN
# ==========================================
if not st.session_state['logado']:
    aplicar_estilo_login()
    cabecalho_login()

    with st.form("form_login"):
        email_login = st.text_input("E-mail", placeholder="voce@suaempresa.com")
        senha_login = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if entrar:
        _espera = login_segundos_bloqueado(email_login)
        if _espera > 0:
            mostrar_popup(f"Muitas tentativas incorretas. Aguarde {max(1, -(-_espera // 60))} minuto(s) e tente novamente.", tipo="erro")
            entrar = False

    if entrar:
      with st.spinner("Entrando..."):
        try:
            try: resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, nome, plano").eq("email", email_login).execute()
            except Exception: registrar_erro("app.py:635"); resultado = supabase.table("usuarios").select("id, senha_hash, perfil, empresa_id, ativo, plano").eq("email", email_login).execute()
            if not resultado.data:
                login_registrar_falha(email_login)  # conta também e-mail inexistente (evita enumeração/força bruta)
                mostrar_popup("E-mail ou senha incorretos.", tipo="erro")
            else:
                usuario = resultado.data[0]
                if not usuario['ativo']: mostrar_popup("Usuário bloqueado. Fale com o administrador.", tipo="erro")
                elif not verificar_senha(senha_login, usuario['senha_hash']):
                    login_registrar_falha(email_login)
                    mostrar_popup("E-mail ou senha incorretos.", tipo="erro")
                else:
                    login_limpar_falhas(email_login)
                    if not senha_ja_hasheada(usuario['senha_hash']):  # migra senha antiga para bcrypt
                        try: supabase.table("usuarios").update({"senha_hash": hash_senha(senha_login)}).eq("id", usuario['id']).execute()
                        except Exception: registrar_erro("app.py:650"); pass
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
                        cookie_manager.set("tk", novo_token, key="set_tk_login", expires_at=datetime.now() + relativedelta(days=7), same_site="lax")
                        cookie_manager.set("uid", str(usuario['id']), key="set_uid_login", expires_at=datetime.now() + relativedelta(days=7), same_site="lax")
                        time.sleep(1.5)  # dá tempo do navegador gravar o cookie antes de recarregar a tela
                        st.rerun()
        except Exception as e: registrar_erro("app.py:673"); mostrar_popup(f"Erro ao tentar logar: {e}", tipo="erro")

    if st.session_state.get('bloqueio_usuario_id'):
        st.warning("⚠️ Você já possui aparelhos conectados no seu limite.")
        if st.button("Desconectar aparelhos antigos à força"):
            uid_bloqueado = st.session_state['bloqueio_usuario_id']
            supabase.table("sessoes_ativas").delete().eq("usuario_id", uid_bloqueado).execute()
            del st.session_state['bloqueio_usuario_id']
            mostrar_popup("Aparelhos antigos desconectados! Faça login novamente.")
            st.rerun()

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
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
                            registrar_erro("app.py:719")
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
                            except Exception: registrar_erro("app.py:739"); expirado = True
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
                        "senha_hash": hash_senha(nova_senha_recup),
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
                            try: supabase.table("usuarios").insert({"email": email_cadastro, "senha_hash": hash_senha(senha_cadastro), "perfil": "dono", "empresa_id": empresa_id_criada, "ativo": False, "nome": nome_usuario_cadastro, "email_confirmado": False, "token_confirmacao": token_confirmacao_novo}).execute()
                            except Exception: registrar_erro("app.py:824"); supabase.table("usuarios").insert({"email": email_cadastro, "senha_hash": hash_senha(senha_cadastro), "perfil": "dono", "empresa_id": empresa_id_criada, "ativo": False}).execute()
                            enviar_email_confirmacao(email_cadastro, nome_usuario_cadastro, token_confirmacao_novo)
                            mostrar_popup("Conta criada! Enviamos um e-mail de confirmação.")

    rodape_login()

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
        CHAVE_PIX = PIX_CHAVE
        NOME_PIX = PIX_NOME
        CIDADE_PIX = PIX_CIDADE
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
                        except Exception: registrar_erro("app.py:858"); supabase.table("usuarios").update({"metodo_pagamento": "pix_manual", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                        mostrar_popup("Comprovante enviado! Ativaremos sua conta em breve.")
                        del st.session_state['conta_criada_id']
            except Exception as e: registrar_erro("app.py:861"); st.error(f"Erro ao gerar QR Code: {e}")
        elif metodo_escolhido == "💳 Cartão/Boleto":
            if st.button("Gerar Link"):
                try:
                    preferencia = criar_preferencia_pagamento_mp(st.session_state['conta_criada_id'], st.session_state['conta_criada_email'], f"Assinatura Mensal - {plano_escolhido_tela}", valor_cobrado)
                    st.session_state['link_pagamento_mp'] = preferencia.get('init_point')
                    supabase.table("usuarios").update({"metodo_pagamento": "cartao", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                except Exception as e: registrar_erro("app.py:868"); mostrar_popup(f"Erro ao gerar link: {e}", tipo="erro")
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
                    except Exception: registrar_erro("app.py:883"); supabase.table("usuarios").update({"metodo_pagamento": "manual", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
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
    except Exception: registrar_erro("app.py:909"); check_user = supabase.table("usuarios").select("ativo").eq("id", st.session_state['usuario_id']).execute()

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
        CHAVE_PIX_BLOQ = PIX_CHAVE
        NOME_PIX_BLOQ = PIX_NOME
        CIDADE_PIX_BLOQ = PIX_CIDADE
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
            except Exception as e: registrar_erro("app.py:951"); st.error(f"Erro ao gerar QR Code: {e}")
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
            except Exception: registrar_erro("app.py:969"); dias_aviso = 0
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

    # 🚧 Módulo em desenvolvimento: só o admin_geral usa por enquanto (para testes)
    MODULOS_EM_CONSTRUCAO = ["🧳 Orçamento"]
    _eh_admin_geral = st.session_state.get('perfil') == 'admin_geral'

    def _rotulo_menu(opcao):
        if opcao in MODULOS_EM_CONSTRUCAO and not _eh_admin_geral:
            return f"{opcao} 🚧 (em breve)"
        if opcao in MODULOS_EM_CONSTRUCAO and _eh_admin_geral:
            return f"{opcao} 🧪 (teste)"
        return opcao

    menu = st.sidebar.radio("Módulos do Sistema", opcoes_menu, format_func=_rotulo_menu)

    # Ao trocar de módulo, esconde o conteúdo da tela anterior (ainda "stale") enquanto a nova carrega,
    # em vez de mostrá-lo transparente/misturado com a tela nova.
    if st.session_state.get('_menu_anterior') != menu:
        st.session_state['_menu_anterior'] = menu
        st.markdown(
            """<style>
            [data-testid="stMain"] [data-stale="true"],
            section.main [data-stale="true"] { display: none !important; }
            </style>""",
            unsafe_allow_html=True,
        )
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
                if not verificar_senha(senha_atual_perfil, senha_hash_atual): mostrar_popup("Senha incorreta.", tipo="erro")
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
            if not verificar_senha(senha_atual_troca, senha_hash_atual2): mostrar_popup("Senha atual incorreta.", tipo="erro")
            elif len(senha_nova_troca) < 7: mostrar_popup("A nova senha precisa ter no mínimo 7 caracteres.", tipo="erro")
            elif senha_nova_troca != senha_nova_troca_confirma: mostrar_popup("As senhas não coincidem.", tipo="erro")
            else:
                supabase.table("usuarios").update({"senha_hash": hash_senha(senha_nova_troca)}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("SENHA ALTERADA COM SUCESSO!")

        st.markdown("---")
        with st.expander("💳 Minha Assinatura", expanded=False):
            plano_nome_tela = "PRO 🚀" if plano_atual_usuario == 'pro' else "BÁSICO 📦"
        st.info(f"Seu plano atual é o **{plano_nome_tela}**.")
        acao_assinatura = st.radio("Gerenciar Assinatura:", ["Manter meu plano atual", "🔄 Renovar meu plano atual", "Fazer Upgrade para PRO (R$ 89,90)", "Fazer Downgrade para Básico (R$ 79,90)", "Cancelar Assinatura"])
        CHAVE_PIX = PIX_CHAVE
        NOME_PIX = PIX_NOME
        CIDADE_PIX = PIX_CIDADE
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
                except Exception as e: registrar_erro("app.py:1113"); st.error(f"Erro ao gerar QR Code: {e}")
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
                    except Exception as e: registrar_erro("app.py:1143"); st.error(f"Erro ao gerar QR Code: {e}")
                else:
                    if st.button("Gerar Link de Pagamento (R$ 89,90)", key="btn_upgrade_mp"):
                        try:
                            ref_up = f"{st.session_state['usuario_id']}_PRO"
                            pref_up = criar_preferencia_pagamento_mp(ref_up, dados_usuario_atual.get('email',''), "Upgrade Plano PRO", 89.90)
                            st.session_state['link_up_mp'] = pref_up.get('init_point')
                            st.session_state['ref_up_mp'] = ref_up
                        except Exception as e: registrar_erro("app.py:1151"); st.error(f"Erro ao gerar link: {e}")
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
                    except Exception as e: registrar_erro("app.py:1182"); st.error(f"Erro ao gerar QR Code: {e}")
                else:
                    if st.button("Gerar Link de Pagamento (R$ 79,90)", key="btn_down_mp"):
                        try:
                            ref_down = f"{st.session_state['usuario_id']}_BASICO"
                            pref_down = criar_preferencia_pagamento_mp(ref_down, dados_usuario_atual.get('email',''), "Downgrade Plano Básico", 79.90)
                            st.session_state['link_down_mp'] = pref_down.get('init_point')
                            st.session_state['ref_down_mp'] = ref_down
                        except Exception as e: registrar_erro("app.py:1190"); st.error(f"Erro: {e}")
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
            except Exception: registrar_erro("app.py:1230"); return None
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
                except Exception: registrar_erro("app.py:1285"); continue
                def _parse_hora_segura(valor_hora):
                    if not valor_hora: return None
                    for fmt in ("%H:%M:%S", "%H:%M"):
                        try: return datetime.strptime(valor_hora[:8], fmt).time()
                        except Exception: registrar_erro("app.py:1290"); continue
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
            registrar_erro("app.py:1328")
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
                    except Exception: registrar_erro("app.py:1344"); continue
                return None
            intervalos_produto = []
            for ev in eventos_prod.data:
                if ev['id'] not in mapa_qtd_evento: continue
                if not ev.get('data_inicio') or not ev.get('data_fim_alocacao'): continue
                try:
                    ev_data_ini = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    ev_data_fim = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception: registrar_erro("app.py:1353"); continue
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
            registrar_erro("app.py:1383")
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
                except Exception: registrar_erro("app.py:1403"); pass
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
            except Exception: registrar_erro("app.py:1427"); return data_iso
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
                except Exception: registrar_erro("app.py:1485"); pass
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
            except Exception: registrar_erro("app.py:1511"); return d
    
        data_criacao_fmt = _fmt_data(orc.get('data_criacao')) if orc.get('data_criacao') else datetime.now().strftime("%d/%m/%Y")
        try:
            data_validade = (datetime.now() + relativedelta(days=int(orc.get('validade_dias') or 7))).strftime("%d/%m/%Y")
        except Exception:
            registrar_erro("app.py:1517")
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

    def buscar_devolucoes_pendentes():
        """Retorna lista de eventos já encerrados (data fim < hoje) com itens ainda não
        marcados como devolvidos ao estoque."""
        pendentes = []
        try:
            hoje_dev = datetime.now().date()
            eventos_enc = supabase.table("eventos").select("id, descricao, data_fim_alocacao, cliente_id, status").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
            if not eventos_enc.data: return pendentes
            ids_encerrados = []
            mapa_ev_enc = {}
            for ev_e in eventos_enc.data:
                if not ev_e.get('data_fim_alocacao'): continue
                try:
                    d_fim_e = datetime.strptime(ev_e['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception: registrar_erro("app.py:1577"); continue
                if d_fim_e < hoje_dev:
                    ids_encerrados.append(ev_e['id'])
                    mapa_ev_enc[ev_e['id']] = {**ev_e, 'data_fim_dt': d_fim_e}
            if not ids_encerrados: return pendentes
            try:
                itens_enc = supabase.table("itens_evento").select("id, evento_id, produto_id, quantidade, devolvido").in_("evento_id", ids_encerrados).execute()
            except Exception:
                # coluna 'devolvido' pode não existir ainda no banco
                registrar_erro("app.py:1586")
                itens_enc = supabase.table("itens_evento").select("id, evento_id, produto_id, quantidade").in_("evento_id", ids_encerrados).execute()
            if not itens_enc.data: return pendentes
            por_evento = {}
            for it_e in (itens_enc.data or []):
                if not it_e.get('devolvido'):
                    por_evento.setdefault(it_e['evento_id'], []).append(it_e)
            for ev_id, itens_pend in por_evento.items():
                info_ev = mapa_ev_enc.get(ev_id, {})
                dias_atraso_dev = (hoje_dev - info_ev.get('data_fim_dt', hoje_dev)).days
                pendentes.append({
                    'evento_id': ev_id,
                    'descricao': info_ev.get('descricao') or 'Evento',
                    'dias_atraso': dias_atraso_dev,
                    'itens': itens_pend
                })
            return pendentes
        except Exception:
            registrar_erro("app.py:1604")
            return pendentes

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
                    except Exception as e: registrar_erro("app.py:1634"); st.error(f"Erro ao excluir: {e}")
                if col2.button("❌ Cancelar", use_container_width=True): st.rerun()
        if hasattr(st, "dialog"): return st.dialog("⚠️ Confirmação Necessária")(modal)
        elif hasattr(st, "experimental_dialog"): return st.experimental_dialog("⚠️ Confirmação Necessária")(modal)
        else: return modal

    popup_confirmacao_estoque = _criar_modal_exclusao()


    # ==========================================
    # ESQUELETO DE CARREGAMENTO (some quando a tela termina de montar)
    # ==========================================
    _esqueleto_carregando = st.empty()
    _esqueleto_carregando.markdown("""
<style>
@keyframes ll-pulso {0%,100%{opacity:.35} 50%{opacity:.8}}
.ll-sk{background:rgba(128,128,128,.28);border-radius:8px;animation:ll-pulso 1.2s ease-in-out infinite;margin-bottom:12px}
</style>
<div class="ll-sk" style="height:34px;width:40%"></div>
<div style="display:flex;gap:12px;flex-wrap:wrap">
  <div class="ll-sk" style="height:90px;flex:1;min-width:140px"></div>
  <div class="ll-sk" style="height:90px;flex:1;min-width:140px"></div>
  <div class="ll-sk" style="height:90px;flex:1;min-width:140px"></div>
</div>
<div class="ll-sk" style="height:220px;width:100%"></div>
<div class="ll-sk" style="height:16px;width:70%"></div>
<div class="ll-sk" style="height:16px;width:55%"></div>
""", unsafe_allow_html=True)

    # ==========================================
    # MENU: GESTÃO DE ASSINANTES (ADMIN)
    # ==========================================
    if menu == "👑 Gestão de Assinantes":
        from modulos import gestao_assinantes
        gestao_assinantes.render(
            supabase=supabase,
            formatar_moeda=formatar_moeda,
            mostrar_popup=mostrar_popup,
            hash_senha=hash_senha,
            enviar_email_expiracao=enviar_email_expiracao,
            ativar_conta_apos_pagamento=ativar_conta_apos_pagamento,
            registrar_pagamento_historico=registrar_pagamento_historico,
        )


    # ==========================================
    # MENU: DASHBOARD
    # ==========================================
    elif menu == "📊 Dashboard":
        from modulos import dashboard
        dashboard.render(
            supabase=supabase,
            emp_id=emp_id,
            formatar_moeda=formatar_moeda,
            buscar_devolucoes_pendentes=buscar_devolucoes_pendentes,
        )


    # ==========================================
    # MENU: AGENDAMENTO
    # ==========================================
    elif menu == "📅 Agendamento":
        from modulos import agendamento
        agendamento.render(
            supabase=supabase,
            emp_id=emp_id,
            formatar_moeda=formatar_moeda,
            mostrar_popup=mostrar_popup,
            safe_json_load=safe_json_load,
            buscar_devolucoes_pendentes=buscar_devolucoes_pendentes,
            calcular_disponibilidade_periodo=calcular_disponibilidade_periodo,
            definir_categoria=definir_categoria,
            formatar_telefone_br=formatar_telefone_br,
            gerar_recibo_evento_pdf=gerar_recibo_evento_pdf,
            sincronizar_evento_google_agenda_silencioso=sincronizar_evento_google_agenda_silencioso,
            REPORTLAB_DISPONIVEL=REPORTLAB_DISPONIVEL,
        )


    # ==========================================
    # MENU: ESTOQUE
    # ==========================================
    elif menu == "📦 Estoque":
        from modulos import estoque
        estoque.render(
            supabase=supabase,
            emp_id=emp_id,
            formatar_moeda=formatar_moeda,
            mostrar_popup=mostrar_popup,
            safe_json_load=safe_json_load,
            calcular_detalhamento_periodo_produto=calcular_detalhamento_periodo_produto,
            calcular_disponibilidade_periodo=calcular_disponibilidade_periodo,
            definir_categoria=definir_categoria,
            formatar_telefone_br=formatar_telefone_br,
            prever_icone=prever_icone,
            status_cor=status_cor,
            popup_confirmacao_estoque=popup_confirmacao_estoque,
        )


    # ==========================================
    # MENU: COMPRAS
    # ==========================================
    elif menu == "🛒 Compras":
        from modulos import compras
        compras.render(
            supabase=supabase,
            emp_id=emp_id,
            mostrar_popup=mostrar_popup,
        )


    # ==========================================
    # MENU: FATURAMENTO
    # ==========================================
    elif menu == "💰 Faturamento":
        from modulos import faturamento
        faturamento.render(
            supabase=supabase,
            emp_id=emp_id,
            formatar_moeda=formatar_moeda,
            mostrar_popup=mostrar_popup,
        )

    # ==========================================
    # MENU: ORÇAMENTO
    # ==========================================
    elif menu == "🧳 Orçamento":
        st.title("🧳 Orçamento de Evento")

        # 🚧 Bloqueio temporário: só admin_geral enxerga o módulo enquanto está em criação
        if st.session_state.get('perfil') != 'admin_geral':
            st.warning("🚧 **Módulo em criação!** O Orçamento de Eventos está sendo desenvolvido e ficará disponível em breve.")
            st.info("Assim que estiver pronto, você poderá montar orçamentos, gerar o PDF e converter em evento com um clique. Enquanto isso, use o **📅 Agendamento** normalmente.")
            _esqueleto_carregando.empty()
            st.stop()
        else:
            st.caption("🧪 Modo de teste: este módulo está visível apenas para a conta admin.")

        from modulos import orcamento
        orcamento.render(
            supabase=supabase, emp_id=emp_id,
            formatar_moeda=formatar_moeda, mostrar_popup=mostrar_popup, safe_json_load=safe_json_load,
            calcular_distancia_google_maps=calcular_distancia_google_maps,
            gerar_pdf_orcamento=gerar_pdf_orcamento, REPORTLAB_DISPONIVEL=REPORTLAB_DISPONIVEL,
        )

    _esqueleto_carregando.empty()  # terminou de montar a tela
