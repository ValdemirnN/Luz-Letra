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
st.set_page_config(page_title="Luz & Letras", page_icon="logo.jpg", layout="wide")

# ==========================================
# VERIFICAÇÃO DE PROPRIEDADE - GOOGLE SEARCH CONSOLE
# ==========================================
st.markdown("""
<script>
var meta = document.createElement('meta');
meta.name = "google-site-verification";
meta.content = "BLsnKznEf1epekQKo6x3onFRT5C7hTLZDLdUfnXIFG4";
document.getElementsByTagName('head')[0].appendChild(meta);
</script>
""", unsafe_allow_html=True)

# ==========================================
# PÁGINA PÚBLICA: POLÍTICA DE PRIVACIDADE (sem precisar de login)
# Acesse em: https://SEU_APP.streamlit.app/?privacidade=1
# ==========================================
if st.query_params.get("privacidade") == "1":
    st.title("Política de Privacidade - Luz & Letras Sistema")
    st.markdown("""
    **Última atualização:** 21 de julho de 2026

    O Luz & Letras Sistema ("o Sistema") é uma plataforma de gestão para
    empresas de locação de itens para eventos. Esta política explica como
    tratamos os dados dos usuários.

    ### 1. Dados que coletamos
    - Nome, e-mail e senha (para login no sistema).
    - Dados de eventos, clientes, estoque e faturamento cadastrados pelo próprio usuário.
    - Ao conectar sua Google Agenda, com sua autorização explícita, acessamos: seu e-mail
      do Google (para identificar a conta conectada) e permissão para criar e atualizar
      eventos na sua agenda.

    ### 2. Como usamos os dados do Google Agenda
    Usamos a permissão apenas para criar ou atualizar eventos na sua própria Google Agenda,
    correspondentes aos eventos que você cadastra no Sistema, com lembretes automáticos.
    Não lemos, coletamos nem compartilhamos outros dados da sua agenda além dos eventos
    que o próprio Sistema cria.

    ### 3. Compartilhamento de dados
    Não vendemos nem compartilhamos seus dados com terceiros, exceto quando exigido por lei.

    ### 4. Armazenamento
    Os dados ficam armazenados em banco de dados protegido (Supabase), com acesso
    restrito à equipe responsável pelo Sistema.

    ### 5. Seus direitos
    Você pode, a qualquer momento, desconectar sua Google Agenda pela tela de Perfil do
    Sistema, ou solicitar a exclusão da sua conta e dados entrando em contato pelo
    e-mail nvaldemir76@gmail.com.

    ### 6. Contato
    Dúvidas sobre esta política: nvaldemir76@gmail.com
    """)
    st.stop()

# ==========================================
# CUSTOMIZAÇÃO DE INTERFACE (CSS)
# ==========================================
st.markdown("""
<style>
/* Oculta a mensagem 'Press Enter to submit form' */
div[data-testid="InputInstructions"] { 
    display: none !important; 
}

/* Oculta os botões de + e - nativos do navegador */
input[type="number"]::-webkit-inner-spin-button, 
input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
input[type="number"] {
    -moz-appearance: textfield;
}

/* Oculta os botões de + e - customizados do Streamlit */
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"] {
    display: none !important;
}

/* --------------------------------------------------- */
/* MÁGICA: AVISO DE ESTOQUE INSUFICIENTE EM TEMPO REAL */
/* --------------------------------------------------- */

/* 1. Pinta a caixinha de vermelho imediatamente quando passa do limite (max_value) */
div[data-testid="stNumberInput"] input[type="number"]:out-of-range {
    background-color: #3b0a0a !important; /* Fundo vermelho escuro */
    color: #ff4b4b !important; /* Texto vermelho brilhante */
    border: 2px solid #ff4b4b !important; /* Borda vermelha chamativa */
    border-radius: 6px;
}

/* 2. Mostra a mensagem customizada abaixo do campo em tempo real */
div[data-testid="stNumberInput"]:has(input:out-of-range)::after {
    content: "⚠️ A QUANTIDADE EM ESTOQUE É INSUFICIENTE!";
    color: #ff4b4b;
    font-size: 13px;
    font-weight: bold;
    display: block;
    margin-top: 6px;
    animation: piscarErro 1s infinite; /* Efeito chamativo opcional */
}

/* Efeito para a mensagem piscar suavemente */
@keyframes piscarErro {
    0% { opacity: 1; }
    50% { opacity: 0.6; }
    100% { opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

# Função auxiliar para formatar moeda
def formatar_moeda(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# SISTEMA DE POP-UP CENTRALIZADO
# ==========================================
def mostrar_popup(mensagem, tipo="sucesso", tempo=1.5):
    if tipo == "erro":
        st.error(f"⚠️ {mensagem}")
    else:
        alerta = st.empty()
        alerta.markdown(f"""
        <style>
        .popup-overlay {{
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-color: rgba(0, 0, 0, 0.7); z-index: 999999;
            display: flex; align-items: center; justify-content: center;
        }}
        .popup-box {{
            background-color: #1B5E20; color: white; padding: 40px 60px;
            border-radius: 12px; font-size: 24px; font-weight: bold; text-align: center;
            box-shadow: 0px 8px 30px rgba(0,0,0,0.8);
            animation: fadeInScale 0.3s ease-out forwards;
        }}
        @keyframes fadeInScale {{
            0% {{ opacity: 0; transform: scale(0.7); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
        </style>
        <div class="popup-overlay"><div class="popup-box"><span style="font-size: 40px;">🎉</span><br><br>{mensagem}</div></div>
        """, unsafe_allow_html=True)
        time.sleep(tempo)
        alerta.empty()

# ==========================================
# LOGO DE FUNDO ANIMADA (MARCA D'ÁGUA)
# ==========================================
def aplicar_fundo_com_logo(caminho_logo="logo.jpg"):
    try:
        with open(caminho_logo, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode()

        st.markdown(f"""
        <style>
        .stApp {{ position: relative; }}
        .stApp::before {{
            content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background-image: url("data:image/jpg;base64,{logo_base64}");
            background-repeat: no-repeat; background-position: center;
            background-size: min(45vw, 480px); opacity: 0.07; z-index: 0;
            pointer-events: none; animation: brilhoPulsante 4s ease-in-out infinite;
        }}
        @keyframes brilhoPulsante {{
            0%   {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
            50%  {{ opacity: 0.11; filter: drop-shadow(0 0 35px #FFD700); }}
            100% {{ opacity: 0.05; filter: drop-shadow(0 0 10px #FFD700); }}
        }}
        .stApp > * {{ position: relative; z-index: 1; }}
        [data-testid="stSidebar"] img {{ animation: brilhoSidebar 3s ease-in-out infinite; border-radius: 12px; }}
        @keyframes brilhoSidebar {{
            0%   {{ filter: drop-shadow(0 0 6px rgba(255, 215, 0, 0.35)); }}
            50%  {{ filter: drop-shadow(0 0 18px rgba(255, 215, 0, 0.75)); }}
            100% {{ filter: drop-shadow(0 0 6px rgba(255, 215, 0, 0.35)); }}
        }}
        </style>
        """, unsafe_allow_html=True)
    except Exception: pass

aplicar_fundo_com_logo()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://eootqeatgqcnenngnexp.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# ==========================================
# CONFIGURAÇÕES DE E-MAIL E PAGAMENTO
# ==========================================
GMAIL_REMETENTE = st.secrets.get("GMAIL_REMETENTE", "SEU_EMAIL_AQUI@gmail.com")
GMAIL_SENHA_APP = st.secrets.get("GMAIL_SENHA_APP", "SUA_SENHA_DE_APP_DE_16_DIGITOS")
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "COLOQUE_SEU_ACCESS_TOKEN_DO_MERCADO_PAGO_AQUI")
URL_BASE_SISTEMA = st.secrets.get("URL_BASE_SISTEMA", "http://localhost:8501")
VALOR_ASSINATURA_MENSAL = 300.00

# ==========================================
# CONFIGURAÇÕES GOOGLE (MAPS + AGENDA)
# ==========================================
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

# ==========================================
# INICIALIZAÇÃO DE COOKIES
# ==========================================
from streamlit_cookies_manager import EncryptedCookieManager

cookies = EncryptedCookieManager(
    prefix="luzletras/",
    password=st.secrets.get("COOKIES_PASSWORD", "luz-letras-senha-super-secreta-2026"),
)
if not cookies.ready():
    st.stop()

# ==========================================
# 2. CONTROLE DE SESSÃO E SEGURANÇA NO BANCO
# ==========================================

def fazer_logout():
    token_atual = st.session_state.get("token_sessao")
    if token_atual:
        try: supabase.table("sessoes_ativas").delete().eq("token", token_atual).execute()
        except: pass
    
    # Deleta os cookies de login
    if "tk" in cookies: del cookies["tk"]
    if "uid" in cookies: del cookies["uid"]
    cookies.save()
    
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None})

def restaurar_sessao_por_token():
    try:
        # Puxa o token e UID que estão escondidos e salvos no navegador (Cookie)
        tk_param = cookies.get("tk")
        uid_param = cookies.get("uid")

        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)

            # Valida no banco se essa sessão ainda existe
            sessao_banco = supabase.table("sessoes_ativas").select("id").eq("token", tk_param).eq("usuario_id", usuario_id_restaurar).execute()
            if not sessao_banco.data:
                # Se não existe, limpa o cookie inútil
                del cookies["tk"]; del cookies["uid"]; cookies.save()
                return

            # Puxa dados do usuário para entrar
            resultado = supabase.table("usuarios").select("id, perfil, empresa_id, ativo, nome").eq("id", usuario_id_restaurar).execute()
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
                        st.session_state.update({
                            'logado': True, 'perfil': usuario['perfil'], 'empresa_id': usuario['empresa_id'],
                            'usuario_id': usuario['id'], 'nome_usuario': usuario.get('nome') or 'Usuário',
                            'token_sessao': tk_param
                        })
    except Exception:
        pass

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
# INTEGRAÇÃO COM GOOGLE AGENDA (OAuth2 por usuário)
# ==========================================
def gerar_url_autorizacao_google(usuario_id):
    from urllib.parse import urlencode
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": URL_BASE_SISTEMA,
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": str(usuario_id),
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def processar_callback_google():
    try:
        code_param = st.query_params.get("code")
        state_param = st.query_params.get("state")
        if code_param and state_param:
            resp = requests.post("https://oauth2.googleapis.com/token", data={
                "code": code_param, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": URL_BASE_SISTEMA, "grant_type": "authorization_code"
            }, timeout=15)
            dados_token = resp.json()
            refresh_token_novo = dados_token.get("refresh_token")
            usuario_id_google = int(state_param)
            if refresh_token_novo and dados_token.get("access_token"):
                try:
                    info_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {dados_token.get('access_token')}"}, timeout=15)
                    email_google_conectado = info_resp.json().get("email", "")
                except Exception:
                    email_google_conectado = ""
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
        "client_secret": GOOGLE_CLIENT_SECRET, "grant_type": "refresh_token"
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]

def criar_ou_atualizar_evento_google_agenda(refresh_token, evento_dict, google_event_id=None):
    access_token = obter_access_token_google(refresh_token)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data_inicio_ev = str(evento_dict['data_inicio']).split("T")[0]
    data_fim_ev = str(evento_dict.get('data_fim_alocacao') or data_inicio_ev).split("T")[0]
    data_fim_evento_dt = (datetime.strptime(data_fim_ev, "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
    body = {
        "summary": f"🎉 Evento: {evento_dict.get('descricao', 'Evento')}",
        "description": (evento_dict.get('observacao') or ""),
        "start": {"date": data_inicio_ev},
        "end": {"date": data_fim_evento_dt},
        "reminders": {"useDefault": False, "overrides": [
            {"method": "email", "minutes": 24 * 60},
            {"method": "email", "minutes": 60},
            {"method": "popup", "minutes": 60},
        ]}
    }
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
        if not u.data or not u.data[0].get("google_refresh_token"):
            st.warning("DEBUG: usuário não tem refresh_token salvo.")
            return None
        refresh_token_u = u.data[0]["google_refresh_token"]
        return criar_ou_atualizar_evento_google_agenda(refresh_token_u, evento_dict, google_event_id_existente)
    except Exception as e:
        st.warning(f"DEBUG erro Google Agenda: {e}")
        return None

# ==========================================
# GOOGLE MAPS - DISTÂNCIA E ROTA (para Orçamento)
# ==========================================
def calcular_distancia_google_maps(origem, destino):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": origem, "destinations": destino, "key": GOOGLE_MAPS_API_KEY, "language": "pt-BR", "units": "metric"}
    resp = requests.get(url, params=params, timeout=15)
    dados = resp.json()
    if dados.get("status") != "OK":
        raise Exception(dados.get("error_message") or f"Erro na API do Google Maps: {dados.get('status')}")
    elemento = dados["rows"][0]["elements"][0]
    if elemento.get("status") != "OK":
        raise Exception(f"Não foi possível calcular a rota entre '{origem}' e '{destino}'.")
    km = elemento["distance"]["value"] / 1000
    duracao_min = elemento["duration"]["value"] / 60
    return km, duracao_min

def montar_url_embed_rota_google_maps(origem, destino, waypoints=None):
    from urllib.parse import quote
    url = f"https://www.google.com/maps/embed/v1/directions?key={GOOGLE_MAPS_API_KEY}&origin={quote(origem)}&destination={quote(destino)}&mode=driving"
    if waypoints:
        url += "&waypoints=" + quote("|".join(waypoints))
    return url

if 'logado' not in st.session_state:
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': '', 'token_sessao': None})
    restaurar_sessao_por_token() # Adicione esta linha!

def fazer_logout():
    st.session_state.update({'logado': False, 'perfil': '', 'empresa_id': None, 'usuario_id': None, 'nome_usuario': ''})
    st.query_params.clear()

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

            if resultado.data:
                usuario = resultado.data[0]
                if not usuario['ativo']: 
                    mostrar_popup("Usuário bloqueado. Fale com o administrador.", tipo="erro")
                elif usuario['senha_hash'] == senha_login:
                    
                    # === VERIFICAÇÃO DE LIMITE DE APARELHOS ===
                    plano_usuario = usuario.get('plano') or 'basico'
                    limite_aparelhos = 3 if plano_usuario == 'pro' else 1
                    
                    sessoes_ativas = supabase.table("sessoes_ativas").select("id").eq("usuario_id", usuario['id']).execute()
                    qtd_logados = len(sessoes_ativas.data) if sessoes_ativas.data else 0
                    
                    if qtd_logados >= limite_aparelhos:
                        mostrar_popup(f"Limite de {limite_aparelhos} aparelho(s) atingido.", tipo="erro")
                        st.session_state['bloqueio_usuario_id'] = usuario['id']
                    else:
                        # Tudo a partir daqui tem que ter mais espaço à esquerda que o 'else:'
                        novo_token = secrets.token_urlsafe(24)
                        data_exp = (datetime.now() + relativedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                        supabase.table("sessoes_ativas").insert({"usuario_id": usuario['id'], "token": novo_token, "data_expiracao": data_exp}).execute()

                        nome_usuario_login = usuario.get('nome') or usuario.get('email', 'Usuário')
                        
                        st.session_state.update({'logado': True, 'perfil': usuario['perfil'], 'empresa_id': usuario['empresa_id'], 'usuario_id': usuario['id'], 'nome_usuario': nome_usuario_login, 'token_sessao': novo_token})
                        
                        if 'bloqueio_usuario_id' in st.session_state:
                            del st.session_state['bloqueio_usuario_id']
                            
                        # === GRAVA NO COOKIE ===
                        cookies["tk"] = novo_token
                        cookies["uid"] = str(usuario['id'])
                        cookies.save()
                        
                        st.query_params.clear()
                        st.rerun()
                else: 
                    mostrar_popup("Senha incorreta.", tipo="erro")
            else: 
                mostrar_popup("E-mail não encontrado.", tipo="erro")
        except Exception as e: 
            mostrar_popup(f"Erro ao tentar logar: {e}", tipo="erro")

    # === BOTÃO SALVA-VIDAS (Fora do formulário) ===
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
        
        # O CLIENTE ESCOLHE O PLANO AQUI
        col_plano1, col_plano2 = st.columns(2)
        with col_plano1:
            st.info("📦 **PLANO BÁSICO - R$ 100,00/mês**\nAcesso ao Estoque, Agendamento e Dashboard Básico.")
        with col_plano2:
            st.success("🚀 **PLANO PRO - R$ 180,00/mês**\nAcesso COMPLETO (Faturamento, Compras, Orçamentos, PDF e Google Agenda).")
            
        plano_escolhido_tela = st.radio("Selecione o plano desejado:", ["Plano Básico (R$ 100)", "Plano Pro (R$ 180)"])
        
        # Define os valores baseados na escolha
        valor_cobrado = 100.00 if "Básico" in plano_escolhido_tela else 180.00
        nome_plano_bd = "basico" if "Básico" in plano_escolhido_tela else "pro"

        st.markdown("---")
        metodo_escolhido = st.radio("Como quer pagar?", ["📱 Pix", "💳 Cartão de Crédito", "🤝 Pagar em mãos"])
        
        if metodo_escolhido.startswith("🤝"):
            comprovante_pagamento = st.text_area("Descreva o comprovante")
            if st.button("📤 Enviar"):
                if not comprovante_pagamento.strip(): mostrar_popup("Descreva o comprovante.", tipo="erro")
                else:
                    try: supabase.table("usuarios").update({"metodo_pagamento": "manual", "comprovante_pagamento": comprovante_pagamento, "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                    except: supabase.table("usuarios").update({"metodo_pagamento": "manual", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                    mostrar_popup("Comprovante enviado! Aguarde aprovação.")
                    del st.session_state['conta_criada_id']
        else:
            if st.button("Gerar Link"):
                try:
                    preferencia = criar_preferencia_pagamento_mp(st.session_state['conta_criada_id'], st.session_state['conta_criada_email'], f"Assinatura Mensal - {plano_escolhido_tela}", valor_cobrado)
                    st.session_state['link_pagamento_mp'] = preferencia.get('init_point')
                    supabase.table("usuarios").update({"metodo_pagamento": "pix" if "Pix" in metodo_escolhido else "cartao", "plano": nome_plano_bd}).eq("id", st.session_state['conta_criada_id']).execute()
                except Exception as e: mostrar_popup(f"Erro ao gerar link: {e}", tipo="erro")
            
            if st.session_state.get('link_pagamento_mp'):
                st.link_button("🔗 Ir para Pagamento", st.session_state['link_pagamento_mp'])
                if st.button("🔄 Já paguei, verificar"):
                    if verificar_pagamento_mp(st.session_state['conta_criada_id']):
                        ativar_conta_apos_pagamento(st.session_state['conta_criada_id'], "pix")
                        mostrar_popup("Pagamento confirmado!")
                        del st.session_state['conta_criada_id']
                    else: mostrar_popup("Pagamento não identificado.", tipo="erro")
# ==========================================
# 4. ÁREA LOGADA (SISTEMA COMPLETO)
# ==========================================
else:
    if 'sucesso_msg' in st.session_state:
        mostrar_popup(st.session_state['sucesso_msg'])
        del st.session_state['sucesso_msg']

    if 'erro_google_msg' in st.session_state:
        mostrar_popup(st.session_state['erro_google_msg'], tipo="erro")
        del st.session_state['erro_google_msg']

    # === NOVO: VIGIA DE SESSÃO CONTÍNUA ===
    # Se o token não estiver mais no banco, significa que alguém apertou o "Botão Salva-Vidas" em outro PC
    token_atual = st.session_state.get('token_sessao')
    if token_atual:
        sessao_valida = supabase.table("sessoes_ativas").select("id").eq("token", token_atual).execute()
        if not sessao_valida.data:
            mostrar_popup("Sua sessão foi desconectada por outro aparelho.", tipo="erro")
            fazer_logout()
            st.rerun()

    # Busca o usuário e puxa a coluna "plano" recém-criada
    try: check_user = supabase.table("usuarios").select("ativo, plano").eq("id", st.session_state['usuario_id']).execute()
    except: check_user = supabase.table("usuarios").select("ativo").eq("id", st.session_state['usuario_id']).execute()
    
    if check_user.data and not check_user.data[0]['ativo']:
        mostrar_popup("Sua sessão foi desconectada pelo Administrador.", tipo="erro")
        fazer_logout()
        st.rerun()

    plano_atual_usuario = check_user.data[0].get('plano', 'basico') if check_user.data else 'basico'

    st.sidebar.image("logo.jpg", use_container_width=True)
    if 'ver_perfil' not in st.session_state: st.session_state['ver_perfil'] = False
    if st.sidebar.button("👤 Perfil"):
        st.session_state['ver_perfil'] = not st.session_state['ver_perfil']
        st.rerun()
    st.sidebar.button("Sair / Desconectar", on_click=fazer_logout) 
    st.sidebar.markdown("---")

    # Controle de Acesso Dinâmico baseado no Plano
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
        
        # Novo botão que leva direto para a tela de Perfil
        if st.sidebar.button("🚀 Fazer Upgrade Agora", use_container_width=True):
            st.session_state['ver_perfil'] = True
            st.rerun()

    # ==========================================
    # PÁGINA DE PERFIL (dados do usuário + Google Agenda)
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
            if not novo_nome_perfil.strip() or not novo_email_perfil.strip():
                mostrar_popup("Preencha nome e e-mail.", tipo="erro")
            elif not senha_atual_perfil:
                mostrar_popup("Confirme sua senha atual para salvar as alterações.", tipo="erro")
            else:
                senha_check_resp = supabase.table("usuarios").select("senha_hash").eq("id", st.session_state['usuario_id']).execute()
                senha_hash_atual = senha_check_resp.data[0]['senha_hash'] if senha_check_resp.data else None
                if senha_atual_perfil != senha_hash_atual:
                    mostrar_popup("Senha incorreta.", tipo="erro")
                else:
                    email_ja_existe = supabase.table("usuarios").select("id").eq("email", novo_email_perfil).neq("id", st.session_state['usuario_id']).execute()
                    if email_ja_existe.data:
                        mostrar_popup("Já existe outra conta usando esse e-mail.", tipo="erro")
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
            if senha_atual_troca != senha_hash_atual2:
                mostrar_popup("Senha atual incorreta.", tipo="erro")
            elif len(senha_nova_troca) < 7:
                mostrar_popup("A nova senha precisa ter no mínimo 7 caracteres.", tipo="erro")
            elif senha_nova_troca != senha_nova_troca_confirma:
                mostrar_popup("As senhas não coincidem.", tipo="erro")
            else:
                supabase.table("usuarios").update({"senha_hash": senha_nova_troca}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("SENHA ALTERADA COM SUCESSO!")

        st.markdown("---")
        st.subheader("💳 Minha Assinatura")
        
        plano_nome_tela = "PRO 🚀" if plano_atual_usuario == 'pro' else "BÁSICO 📦"
        st.info(f"Seu plano atual é o **{plano_nome_tela}**.")

        acao_assinatura = st.radio("Gerenciar Assinatura:", ["Manter meu plano atual", "Fazer Upgrade para PRO (R$ 180)", "Fazer Downgrade para Básico (R$ 100)", "Cancelar Assinatura"])

        if acao_assinatura == "Fazer Upgrade para PRO (R$ 180)":
            if plano_atual_usuario == 'pro':
                st.success("Você já está no melhor plano do sistema!")
            else:
                st.warning("Ao gerar o link e efetuar o pagamento, as abas PRO e o Contrato em PDF serão liberados automaticamente.")
                if st.button("Gerar Link de Pagamento (R$ 180)"):
                    try:
                        # Adiciona '_PRO' para o Mercado Pago não confundir com o primeiro pagamento que a pessoa fez
                        ref_up = f"{st.session_state['usuario_id']}_PRO"
                        pref_up = criar_preferencia_pagamento_mp(ref_up, dados_usuario_atual.get('email', ''), "Upgrade Plano PRO", 180.00)
                        st.session_state['link_up_mp'] = pref_up.get('init_point')
                        st.session_state['ref_up_mp'] = ref_up
                    except Exception as e: st.error(f"Erro ao gerar link: {e}")
                
                if st.session_state.get('link_up_mp'):
                    st.link_button("🔗 Ir para Pagamento do Upgrade", st.session_state['link_up_mp'])
                    if st.button("🔄 Já paguei o Upgrade, verificar"):
                        if verificar_pagamento_mp(st.session_state['ref_up_mp']):
                            supabase.table("usuarios").update({"plano": "pro"}).eq("id", st.session_state['usuario_id']).execute()
                            mostrar_popup("UPGRADE REALIZADO COM SUCESSO! 🎉")
                            del st.session_state['link_up_mp']
                            st.rerun()
                        else:
                            mostrar_popup("Pagamento não identificado ainda. O Mercado Pago pode levar alguns minutos.", tipo="erro")
        
        elif acao_assinatura == "Fazer Downgrade para Básico (R$ 100)":
            if plano_atual_usuario == 'basico':
                st.success("Seu plano já é o básico.")
            else:
                st.warning("Atenção: O downgrade bloqueará seu acesso ao Faturamento, Compras e Contratos em PDF imediatamente após a confirmação do pagamento.")
                if st.button("Gerar Link de Pagamento (R$ 100)"):
                    try:
                        ref_down = f"{st.session_state['usuario_id']}_BASICO"
                        pref_down = criar_preferencia_pagamento_mp(ref_down, dados_usuario_atual.get('email', ''), "Downgrade Plano Básico", 100.00)
                        st.session_state['link_down_mp'] = pref_down.get('init_point')
                        st.session_state['ref_down_mp'] = ref_down
                    except Exception as e: st.error(f"Erro: {e}")
                
                if st.session_state.get('link_down_mp'):
                    st.link_button("🔗 Ir para Pagamento do Downgrade", st.session_state['link_down_mp'])
                    if st.button("🔄 Já paguei o Downgrade, verificar"):
                        if verificar_pagamento_mp(st.session_state['ref_down_mp']):
                            supabase.table("usuarios").update({"plano": "basico"}).eq("id", st.session_state['usuario_id']).execute()
                            mostrar_popup("DOWNGRADE REALIZADO.")
                            del st.session_state['link_down_mp']
                            st.rerun()
                        else:
                            mostrar_popup("Pagamento não identificado ainda.", tipo="erro")

        elif acao_assinatura == "Cancelar Assinatura":
            st.error("⚠️ CUIDADO: Ao confirmar o cancelamento, seu acesso ao sistema será bloqueado imediatamente. Seus dados não serão apagados, mas você não poderá mais entrar na conta.")
            col_canc1, col_canc2 = st.columns(2)
            if col_canc1.button("🚨 Confirmar Cancelamento da Conta"):
                supabase.table("usuarios").update({"ativo": False}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("Conta cancelada. Desconectando do sistema...")
                fazer_logout()
                st.rerun()
        
        st.subheader("📅 Google Agenda")
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            st.warning("⚠️ Integração com Google Agenda ainda não configurada pelo administrador do sistema (faltam GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET nos secrets).")
        elif dados_usuario_atual.get('google_refresh_token'):
            st.success(f"✅ Conectado como **{dados_usuario_atual.get('google_email_conectado') or 'conta Google'}**. Seus eventos serão adicionados automaticamente à sua Google Agenda, com lembrete 1 dia antes e no dia.")
            if st.button("🔌 Desconectar Google Agenda"):
                supabase.table("usuarios").update({"google_refresh_token": None, "google_email_conectado": None}).eq("id", st.session_state['usuario_id']).execute()
                mostrar_popup("GOOGLE AGENDA DESCONECTADA.")
                st.rerun()
        else:
            st.info("Conecte sua Google Agenda para receber lembretes automáticos (e-mail e pop-up) dos eventos cadastrados.")
            url_auth_google = gerar_url_autorizacao_google(st.session_state['usuario_id'])
            st.link_button("🔗 Conectar Google Agenda", url_auth_google)
        st.stop()

    def safe_json_load(val):
        if val and isinstance(val, str) and val.startswith('{'):
            try: return json.loads(val)
            except: return None
        return None

    # ==========================================
    # ARMAZENAMENTO DE DOCUMENTOS (Comprovante e Contrato Assinado)
    # ==========================================
    BUCKET_DOCUMENTOS = "documentos-eventos"

    def upload_documento_evento(evento_id, arquivo, tipo_doc):
        """tipo_doc: 'comprovante' ou 'contrato_assinado'"""
        extensao = arquivo.name.split(".")[-1]
        caminho_storage = f"evento_{evento_id}/{tipo_doc}_{int(time.time())}.{extensao}"
        supabase.storage.from_(BUCKET_DOCUMENTOS).upload(
            caminho_storage, arquivo.getvalue(),
            file_options={"content-type": arquivo.type}
        )
        return caminho_storage

    def gerar_url_assinada_documento(caminho_storage, validade_segundos=3600):
        if not caminho_storage: return None
        try:
            resultado = supabase.storage.from_(BUCKET_DOCUMENTOS).create_signed_url(caminho_storage, validade_segundos)
            return resultado.get("signedURL") or resultado.get("signedUrl")
        except Exception:
            return None

    def remover_documento_evento(caminho_storage):
        if not caminho_storage: return
        try:
            supabase.storage.from_(BUCKET_DOCUMENTOS).remove([caminho_storage])
        except Exception:
            pass

    def formatar_telefone_br(numero):
        if not numero: return numero
        apenas_digitos = "".join(c for c in numero if c.isdigit())
        if len(apenas_digitos) < 10: return numero
        ddd = apenas_digitos[:2]
        resto = apenas_digitos[2:]
        if len(resto) >= 9: return f"({ddd}) {resto[:5]}-{resto[5:]}"
        else: return f"({ddd}) {resto[:4]}-{resto[4:]}"

    def gerar_recibo_evento_pdf(evento_dict, itens_lista, dict_produtos_ref, nome_cliente_pdf, contato_cliente_pdf, nome_usuario_confirmou):
        import os as _os
        buffer = io.BytesIO()

        COR_DOURADO = colors.HexColor("#FFC107")
        COR_PRETO = colors.HexColor("#0E0E0E")
        COR_CINZA_CLARO = colors.HexColor("#F2F2F2")
        COR_TEXTO_CINZA = colors.HexColor("#555555")

        caminho_logo_pdf = "logo_sem_fundo.png" if _os.path.exists("logo_sem_fundo.png") else ("logo.jpg" if _os.path.exists("logo.jpg") else None)

        # ===== CABEÇALHO (faixa preta com a logo + título dourado, repete em toda página) =====
        def _desenhar_cabecalho_recibo(canvas_obj, doc_obj):
            canvas_obj.saveState()
            largura_pagina, altura_pagina = A4
            altura_faixa = 3.2 * cm
            canvas_obj.setFillColor(COR_PRETO)
            canvas_obj.rect(0, altura_pagina - altura_faixa, largura_pagina, altura_faixa, fill=1, stroke=0)
            if caminho_logo_pdf:
                try:
                    canvas_obj.drawImage(caminho_logo_pdf, 2 * cm, altura_pagina - altura_faixa + 0.35 * cm, width=3.6 * cm, height=2.5 * cm, preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass
            canvas_obj.setFillColor(COR_DOURADO)
            canvas_obj.setFont("Helvetica-Bold", 16)
            canvas_obj.drawString(6.2 * cm, altura_pagina - 1.5 * cm, "CONTRATO E RECIBO DE LOCAÇÃO")
            canvas_obj.setFillColor(colors.white)
            canvas_obj.setFont("Helvetica", 10)
            canvas_obj.drawString(6.2 * cm, altura_pagina - 2.15 * cm, f"Evento: {evento_dict.get('descricao', '-')}")
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.setFont("Helvetica", 8)
            canvas_obj.drawString(2 * cm, 1.2 * cm, f"Luz & Letras — Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            canvas_obj.drawRightString(largura_pagina - 2 * cm, 1.2 * cm, f"Página {doc_obj.page}")
            canvas_obj.restoreState()

        frame_recibo = Frame(2 * cm, 1.8 * cm, A4[0] - 4 * cm, A4[1] - 5.4 * cm, id='corpo_recibo')
        doc = BaseDocTemplate(buffer, pagesize=A4)
        doc.addPageTemplates([PageTemplate(id='ComCabecalhoRecibo', frames=[frame_recibo], onPage=_desenhar_cabecalho_recibo)])

        styles = getSampleStyleSheet()
        story = []

        sub_titulo = ParagraphStyle('SubTitRecibo', parent=styles['Heading2'], fontSize=12, spaceAfter=6, textColor=COR_PRETO)
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        normal_style.leading = 14

        termo_style = ParagraphStyle('TermoRecibo', parent=styles['Normal'], fontSize=9, leading=12, alignment=4,
                                     spaceBefore=15, spaceAfter=15, textColor=COR_TEXTO_CINZA)

        agradecimento_style = ParagraphStyle('ObrigadoRecibo', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER,
                                             spaceBefore=20, fontName="Helvetica-Oblique", textColor=COR_PRETO)

        assinatura_nome_style = ParagraphStyle('AssNome', parent=normal_style, alignment=TA_CENTER, spaceBefore=4, fontName="Helvetica-Bold")
        assinatura_data_style = ParagraphStyle('AssData', parent=normal_style, alignment=TA_CENTER, spaceBefore=2, fontSize=9, textColor=COR_TEXTO_CINZA)

        story.append(Spacer(1, 10))

        # DADOS DO CLIENTE E EVENTO
        def _fmt_data_pdf(data_iso):
            if not data_iso or data_iso == "-": return "-"
            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            except: return data_iso

        data_ini_pdf = _fmt_data_pdf(evento_dict.get('data_inicio'))
        data_fim_pdf = _fmt_data_pdf(evento_dict.get('data_fim_alocacao'))
        hora_ini_pdf = evento_dict.get('hora_inicio')[:5] if evento_dict.get('hora_inicio') else "Não inf."
        hora_fim_pdf = evento_dict.get('hora_fim')[:5] if evento_dict.get('hora_fim') else "Não inf."
        valor_pdf = float(evento_dict.get('valor_total') or 0)

        dados_cliente = f"""
        <b>Cliente:</b> {nome_cliente_pdf}<br/>
        <b>Contato:</b> {contato_cliente_pdf}<br/>
        <b>Evento:</b> {evento_dict.get('descricao', '-')}<br/>
        <b>Período da Locação:</b> {data_ini_pdf} ({hora_ini_pdf}) até {data_fim_pdf} ({hora_fim_pdf})<br/>
        <b>Local/Observações:</b> {evento_dict.get('observacao', '-')}<br/>
        <b>Valor Acordado:</b> R$ {formatar_moeda(valor_pdf)}<br/>
        <b>Status:</b> {evento_dict.get('status', '-')}
        """

        tabela_header = Table([[Paragraph(dados_cliente, normal_style)]], colWidths=[17*cm])
        tabela_header.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CCCCCC")),
            ('PADDING', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAFAFA"))
        ]))
        story.append(tabela_header)
        story.append(Spacer(1, 20))

        # ITENS LOCADOS
        story.append(Paragraph("<b>ITENS LOCADOS</b>", sub_titulo))

        tabela_dados = [["Produto / Item", "Qtd", "Detalhes (Letras/Números)"]]
        if itens_lista:
            for it in itens_lista:
                nome_prod_pdf = dict_produtos_ref.get(it['produto_id'], {}).get('nome', f"Produto #{it['produto_id']}")
                detalhe_pdf = "-"
                js_obs = safe_json_load(it.get('observacao'))
                if js_obs:
                    detalhe_pdf = ", ".join([f"{k}: {v}x" for k, v in js_obs.items()])
                elif it.get('observacao'):
                    detalhe_pdf = it.get('observacao')
                tabela_dados.append([nome_prod_pdf, str(it['quantidade']), detalhe_pdf])
        else:
            tabela_dados.append(["Nenhum item registrado", "-", "-"])

        tabela_pdf = Table(tabela_dados, colWidths=[8 * cm, 2 * cm, 7 * cm])
        tabela_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COR_PRETO),
            ('TEXTCOLOR', (0, 0), (-1, 0), COR_DOURADO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COR_CINZA_CLARO])
        ]))
        story.append(tabela_pdf)
        story.append(Spacer(1, 20))

        # TERMO DE RESPONSABILIDADE
        termo_texto = "<b>TERMO DE RESPONSABILIDADE E COMPROMISSO:</b><br/>O cliente acima identificado assume total e irrestrita responsabilidade pela guarda, conservação e integridade de todos os materiais e equipamentos locados durante todo o período do evento. O cliente declara estar ciente de que, em caso de danos, avarias, mau uso, perda ou furto de qualquer item fornecido, será de sua extrema e única responsabilidade arcar com os custos integrais de manutenção, reparo ou reposição do produto ao seu estado original. Ao confirmar esta locação e receber os materiais, o cliente concorda plenamente com estas condições."
        story.append(Paragraph(termo_texto, termo_style))
        story.append(Spacer(1, 15)) # Espaço reduzido

        # ===== ASSINATURAS LADO A LADO (Economiza muito espaço vertical) =====
        story.append(Paragraph("<b>ASSINATURAS</b>", sub_titulo))
        story.append(Spacer(1, 5))

        # Tenta carregar a imagem da assinatura da empresa, se existir
        img_assinatura = ""
        caminho_assinatura_empresa = "assinatura_empresa.png" if _os.path.exists("assinatura_empresa.png") else None
        if caminho_assinatura_empresa:
            try:
                img_assinatura = RLImage(caminho_assinatura_empresa, width=4 * cm, height=1.5 * cm, preserveAspectRatio=True)
            except Exception: pass

        # Estrutura da tabela lado a lado
        assinaturas_data = [
            [img_assinatura, ""], # Linha invisível para a imagem da empresa ficar em cima da linha
            ["____________________________________", "____________________________________"],
            ["Luz & Letras - Locações", f"Cliente: {nome_cliente_pdf[:25]}"], 
            [f"Data: {datetime.now().strftime('%d/%m/%Y')}", "Data: ____/____/________"]
        ]
        
        tabela_assinaturas = Table(assinaturas_data, colWidths=[8.5*cm, 8.5*cm])
        tabela_assinaturas.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 10),
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica'),
            ('FONTSIZE', (0, 3), (-1, 3), 9),
            ('TEXTCOLOR', (0, 3), (-1, 3), COR_TEXTO_CINZA),
            ('BOTTOMPADDING', (0,0), (-1,0), 0),
            ('BOTTOMPADDING', (0,1), (-1,1), 2),
            ('TOPPADDING', (0,2), (-1,2), 2),
            ('TOPPADDING', (0,3), (-1,3), 0),
        ]))
        story.append(tabela_assinaturas)

        # AGRADECIMENTO
        story.append(Spacer(1, 15)) 
        story.append(Paragraph("A equipe <b>Luz & Letras</b> agradece imensamente a sua preferência!<br/>É um grande privilégio fazer parte deste momento tão especial.", agradecimento_style))

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

    # ==========================================================================
    # ✅ CORREÇÃO APLICADA AQUI (22/07/2026)
    # PROBLEMA: "Soma cega" — dois eventos no mesmo dia em horários diferentes
    # (ex: 08h-12h e 14h-18h) estavam tendo suas quantidades somadas uma em
    # cima da outra, mesmo sem nunca coincidirem no tempo. Isso fazia o
    # sistema achar que o estoque tinha "estourado" quando na prática nunca
    # saiu mais do que o pico real de uso simultâneo.
    #
    # SOLUÇÃO: em vez de somar a quantidade de TODOS os eventos que tocam o
    # período pesquisado, agora calculamos o PICO DE OCUPAÇÃO SIMULTÂNEA
    # (técnica de "sweep-line" / linha de varredura): percorremos a linha do
    # tempo somando quando um evento "entra em uso" e subtraindo quando
    # "sai de uso", guardando o maior valor acumulado. Dois eventos que não
    # se cruzam no tempo nunca mais se somam entre si.
    # ==========================================================================
    def calcular_disponibilidade_periodo(data_ini_periodo, data_fim_periodo, hora_ini=None, hora_fim=None, evento_id_excluir=None):
        qtd_alugada = {}
        detalhe_alugado = {}
        try:
            if hora_ini is None: hora_ini = datetime.min.time()
            if hora_fim is None: hora_fim = datetime.max.time()
            dt_ini_busca = datetime.combine(data_ini_periodo, hora_ini)
            dt_fim_busca = datetime.combine(data_fim_periodo, hora_fim)

            eventos_check = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, hora_inicio, hora_fim").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
            if not eventos_check.data:
                return qtd_alugada, detalhe_alugado

            intervalos_eventos = {}
            for ev_c in eventos_check.data:
                if evento_id_excluir and ev_c['id'] == evento_id_excluir: continue
                if not ev_c.get('data_inicio') or not ev_c.get('data_fim_alocacao'): continue

                try:
                    ev_data_inicio_c = datetime.strptime(ev_c['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    ev_data_fim_c = datetime.strptime(ev_c['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception:
                    continue

                def _parse_hora_segura(valor_hora):
                    if not valor_hora: return None
                    for fmt in ("%H:%M:%S", "%H:%M"):
                        try:
                            return datetime.strptime(valor_hora[:8], fmt).time()
                        except Exception:
                            continue
                    return None

                ev_hora_inicio = _parse_hora_segura(ev_c.get('hora_inicio')) or datetime.min.time()
                ev_hora_fim = _parse_hora_segura(ev_c.get('hora_fim')) or datetime.max.time()

                dt_inicio_ev = datetime.combine(ev_data_inicio_c, ev_hora_inicio)
                dt_fim_ev = datetime.combine(ev_data_fim_c, ev_hora_fim)

                if (dt_inicio_ev < dt_fim_busca) and (dt_fim_ev > dt_ini_busca):
                    intervalos_eventos[ev_c['id']] = (dt_inicio_ev, dt_fim_ev)

            if not intervalos_eventos:
                return qtd_alugada, detalhe_alugado

            itens_check = supabase.table("itens_evento").select("evento_id, produto_id, quantidade, observacao").in_("evento_id", list(intervalos_eventos.keys())).execute()
            if not itens_check.data:
                return qtd_alugada, detalhe_alugado

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
                atual = 0
                pico = 0
                for _, delta in eventos_linha:
                    atual += delta
                    pico = max(pico, atual)
                return pico

            for pid_c, intervalos in ocupacao_produto.items():
                qtd_alugada[pid_c] = _pico_maximo(intervalos)

            for (pid_c, k_c), intervalos in ocupacao_subitem.items():
                detalhe_alugado.setdefault(pid_c, {})[k_c] = _pico_maximo(intervalos)

            return qtd_alugada, detalhe_alugado
        except Exception as e:
            st.warning(f"⚠️ Erro ao calcular disponibilidade: {e}")
            return {}, {}

    def calcular_timeline_disponibilidade_produto(data_ref, produto_id, estoque_total):
        eventos_dia = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, hora_inicio, hora_fim").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        intervalos = []

        if eventos_dia.data:
            itens_produto = supabase.table("itens_evento").select("evento_id, quantidade").eq("produto_id", produto_id).execute()
            mapa_qtd_evento = {i['evento_id']: i['quantidade'] for i in (itens_produto.data or [])}

            dt_ini_dia = datetime.combine(data_ref, datetime.min.time())
            dt_fim_dia = datetime.combine(data_ref, datetime.max.time())

            def _parse_hora_segura_tl(valor_hora):
                if not valor_hora: return None
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        return datetime.strptime(valor_hora[:8], fmt).time()
                    except Exception:
                        continue
                return None

            for ev in eventos_dia.data:
                if ev['id'] not in mapa_qtd_evento: continue
                if not ev.get('data_inicio') or not ev.get('data_fim_alocacao'): continue

                try:
                    ev_data_ini = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    ev_data_fim = datetime.strptime(ev['data_fim_alocacao'].split("T")[0], "%Y-%m-%d").date()
                except Exception:
                    continue

                ev_hora_ini = _parse_hora_segura_tl(ev.get('hora_inicio')) or datetime.min.time()
                ev_hora_fim = _parse_hora_segura_tl(ev.get('hora_fim')) or datetime.max.time()

                dt_ini_ev = datetime.combine(ev_data_ini, ev_hora_ini)
                dt_fim_ev = datetime.combine(ev_data_fim, ev_hora_fim)

                inicio_recortado = max(dt_ini_ev, dt_ini_dia)
                fim_recortado = min(dt_fim_ev, dt_fim_dia)
                if inicio_recortado < fim_recortado:
                    intervalos.append((inicio_recortado, fim_recortado, mapa_qtd_evento[ev['id']]))
    def _criar_modal_exclusao():
        def modal(produto_info, tipo, total_remover=0, qtds_json=None, motivo=""):
            if tipo == "parcial":
                st.warning(f"Tem certeza que deseja remover **{total_remover} peças** de **{produto_info['nome']}** parcialmente?")
                col1, col2 = st.columns(2)
                if col1.button("✅ Sim, Confirmar Remoção", use_container_width=True):
                    js_prod = safe_json_load(produto_info.get('observacao'))
                    if js_prod and qtds_json:
                        novo_json = dict(js_prod)
                        for k, v in qtds_json.items():
                            novo_json[k] = max(0, novo_json.get(k, 0) - v)
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

    if menu == "👑 Gestão de Assinantes":
        st.title("Painel Master")
        try: users = supabase.table("usuarios").select("id, email, ativo, senha_hash, nome, email_confirmado, metodo_pagamento, comprovante_pagamento, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()
        except: users = supabase.table("usuarios").select("id, email, ativo, senha_hash, empresas(nome_fantasia), empresa_id").neq("perfil", "admin_geral").execute()

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
                            mostrar_popup("Conta ativada com sucesso!")
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
                            mostrar_popup("Senha alterada!")
                    with col3:
                        meses_add = st.number_input("Estender plano (meses)", min_value=1, key=f"mes_{u['id']}", value=1)
                        if st.button("Renovar", key=f"ren_{u['id']}"):
                            novo_venc = datetime.strptime(venc, "%Y-%m-%d") + relativedelta(months=meses_add)
                            supabase.table("assinaturas").update({"data_vencimento": novo_venc.strftime("%Y-%m-%d")}).eq("empresa_id", u['empresa_id']).execute()
                            st.rerun()
        else: st.info("Nenhuma empresa comprou o sistema ainda.")

    elif menu == "📊 Dashboard":
        import plotly.graph_objects as go
        
        # Oculta a marca d'água apenas nesta página específica
        st.markdown("""
        <style>
        .stApp::before { display: none !important; }
        </style>
        """, unsafe_allow_html=True)

        st.title("📊 Dashboard e Inteligência de Negócio")
        nome_exibicao = st.session_state.get('nome_usuario') or "Usuário"
        st.markdown(f"### 👋 Bem-vindo, {nome_exibicao}!")
        st.markdown("---")

        hoje_date = datetime.now().date()

        # ==========================================
        # 1. COLETA E PROCESSAMENTO DE DADOS GERAIS
        # ==========================================
        try: eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao, clientes_eventos(nome)").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        except: eventos_dash = supabase.table("eventos").select("id, data_inicio, data_fim_alocacao, valor_total, status, descricao").eq("empresa_id", emp_id).neq("status", "Cancelado").execute()
        
        receita_ev = sum(float(e.get('valor_total') or 0) for e in (eventos_dash.data or []))
        total_eventos_ativos = len(eventos_dash.data) if eventos_dash.data else 0
        ticket_medio = receita_ev / total_eventos_ativos if total_eventos_ativos > 0 else 0.0

        try: compras_dash = supabase.table("compras").select("valor_total, data_compra").eq("empresa_id", emp_id).execute()
        except: compras_dash = type('obj', (object,), {'data': []})
        despesa_comp = sum(float(c.get('valor_total') or 0) for c in (compras_dash.data or []))

        try: viagens_dash = supabase.table("despesas_viagem").select("valor, data_despesa").eq("empresa_id", emp_id).execute()
        except: viagens_dash = type('obj', (object,), {'data': []})
        despesa_viagem = sum(float(v.get('valor') or 0) for v in (viagens_dash.data or []))

        try: fat_dash = supabase.table("faturamento").select("tipo, valor, data_pagamento").eq("empresa_id", emp_id).execute()
        except: fat_dash = type('obj', (object,), {'data': []})
        receita_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'receita')
        despesa_manual = sum(float(f.get('valor') or 0) for f in (fat_dash.data or []) if f.get('tipo') == 'despesa')

        total_receitas = receita_ev + receita_manual
        total_despesas = despesa_comp + despesa_viagem + despesa_manual
        lucro_liquido = total_receitas - total_despesas

        # ==========================================
        # 2. CARDS DE KPI (Indicadores Principais)
        # ==========================================
        col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
        col_kpi1.metric("💰 Receita Total", f"R$ {formatar_moeda(total_receitas)}")
        col_kpi2.metric("📉 Despesas Totais", f"R$ {formatar_moeda(total_despesas)}")
        col_kpi3.metric("✨ Lucro Líquido", f"R$ {formatar_moeda(lucro_liquido)}", delta="Positivo" if lucro_liquido >= 0 else "Atenção", delta_color="normal" if lucro_liquido >= 0 else "inverse")
        col_kpi4.metric("💳 Ticket Médio", f"R$ {formatar_moeda(ticket_medio)}")
        col_kpi5.metric("🎉 Eventos Ativos", total_eventos_ativos)
        
        st.markdown("---")

        # ==========================================
        # 3. PAINEL DE ALERTAS (Manutenção e Estoque)
        # ==========================================
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

        # ==========================================
        # 4. EVOLUÇÃO FINANCEIRA E STATUS
        # ==========================================
        col_g1, col_g2 = st.columns([2, 1])

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
                
                # Correção do erro: soma apenas as colunas numéricas especificas
                df_agrupado = df_tl.groupby('Mês/Ano')[['Receita', 'Despesa']].sum().reset_index()
                df_agrupado['sort_date'] = pd.to_datetime(df_agrupado['Mês/Ano'], format='%m/%Y')
                df_agrupado = df_agrupado.sort_values('sort_date')

                fig_evolucao = px.area(df_agrupado, x="Mês/Ano", y=["Receita", "Despesa"], 
                                       template="plotly_dark", color_discrete_map={"Receita": "#2E7D32", "Despesa": "#C62828"})
                fig_evolucao.update_layout(
                    plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                    yaxis=dict(title="", showgrid=True, gridcolor="#333"), xaxis=dict(title="", showgrid=False),
                    legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=40, b=0, l=0, r=0)
                )
                st.plotly_chart(fig_evolucao, use_container_width=True, height=350)
            else:
                st.info("Aguardando lançamentos financeiros para gerar a linha do tempo.")

        with col_g2:
            st.subheader("📊 Status dos Eventos")
            if eventos_dash.data:
                df_status = pd.DataFrame(eventos_dash.data)
                status_counts = df_status["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                mapa_cores_status = {"Concluído": "#2E7D32", "Agendado": "#FFC107", "Cancelado": "#C62828", "Em Andamento": "#0277BD"}
                
                fig_status = px.pie(status_counts, names="Status", values="Quantidade", hole=0.6,
                                    color="Status", color_discrete_map=mapa_cores_status, template="plotly_dark")
                fig_status.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color=COR_FUNDO_GRAFICO, width=3)))
                fig_status.add_annotation(text=f"<b>{total_eventos_ativos}</b><br>Eventos", x=0.5, y=0.5, font_size=18, showarrow=False, align="center")
                fig_status.update_layout(showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=20, b=20, l=0, r=0))
                st.plotly_chart(fig_status, use_container_width=True, height=350)
            else:
                st.info("Sem eventos para analisar.")

        st.markdown("---")

        # ==========================================
        # 5. INTELIGÊNCIA DE ESTOQUE E PRÓXIMOS EVENTOS
        # ==========================================
        col_g3, col_g4, col_g5 = st.columns([1.2, 1.2, 1])

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
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = taxa_ocupacao,
                number = {'suffix': "%", 'font': {'size': 36, 'color': '#FFC107'}},
                title = {'text': f"{itens_alocados_hoje} de {total_estoque_fisico} itens na rua", 'font': {'size': 13}},
                gauge = {
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "#FFC107"},
                    'bgcolor': "#333",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, 40], 'color': "rgba(46, 125, 50, 0.3)"},
                        {'range': [40, 80], 'color': "rgba(255, 193, 7, 0.3)"},
                        {'range': [80, 100], 'color': "rgba(198, 40, 40, 0.3)"}],
                }
            ))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO, margin=dict(t=40, b=0, l=20, r=20), height=280)
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_g4:
            st.subheader("🏆 Ranking de Produtos")
            st.caption("O que mais sai e o que dá mais lucro.")
            
            # CRIANDO ABAS PARA NÃO POLUIR A TELA
            tab_qtd, tab_lucro = st.tabs(["Por Quantidade", "Por Rentabilidade (R$)"])
            
            try: itens_dash = supabase.table("itens_evento").select("evento_id, produto_id, quantidade").eq("empresa_id", emp_id).execute()
            except: itens_dash = type('obj', (object,), {'data': []})

            if itens_dash.data and prods_ref_data:
                mapa_nomes = {p['id']: p['nome'] for p in prods_ref_data}
                
                # --- ABA 1: GRÁFICO POR QUANTIDADE (O que mais sai) ---
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
                        fig_top.update_layout(
                            showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                            xaxis=dict(showgrid=False, showticklabels=False, title="", zeroline=False),
                            yaxis=dict(title="", showgrid=False, tickfont=dict(size=12, color='white')), margin=dict(t=10, b=0, l=0, r=0)
                        )
                        st.plotly_chart(fig_top, use_container_width=True, height=230)
                
                # --- ABA 2: GRÁFICO POR RENTABILIDADE (O que dá mais dinheiro) ---
                with tab_lucro:
                    mapa_valor_evento = {e['id']: float(e.get('valor_total') or 0) for e in (eventos_dash.data or [])}
                    
                    # 1. Conta quantos itens totais tem em cada evento para saber o "peso"
                    itens_por_evento = {}
                    for item in itens_dash.data:
                        eid = item['evento_id']
                        itens_por_evento[eid] = itens_por_evento.get(eid, 0) + item['quantidade']

                    # 2. Divide a receita proporcionalmente para os produtos do evento
                    receita_por_produto = {}
                    for item in itens_dash.data:
                        eid = item['evento_id']
                        pid = item['produto_id']
                        qtd = item['quantidade']
                        
                        valor_evento = mapa_valor_evento.get(eid, 0)
                        total_itens_ev = itens_por_evento.get(eid, 1) # evita divisão por zero
                        
                        peso_receita = (qtd / total_itens_ev) * valor_evento
                        receita_por_produto[pid] = receita_por_produto.get(pid, 0) + peso_receita

                    if receita_por_produto:
                        df_lucro = pd.DataFrame([{"Produto": mapa_nomes.get(pid, f"Prod {pid}"), "Receita": valor} for pid, valor in receita_por_produto.items() if valor > 0])
                        if not df_lucro.empty:
                            df_lucro = df_lucro.sort_values(by="Receita", ascending=True).tail(5)
                            
                            def fmt_moeda(x): return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            df_lucro['Label'] = df_lucro['Receita'].apply(fmt_moeda)

                            # Usa cor verde para representar dinheiro/rentabilidade
                            fig_lucro = px.bar(df_lucro, x="Receita", y="Produto", orientation='h', template="plotly_dark", text="Label", color_discrete_sequence=["#2E7D32"])
                            fig_lucro.update_traces(textposition='inside', textfont_size=12, textfont_color="white")
                            fig_lucro.update_layout(
                                showlegend=False, plot_bgcolor=COR_FUNDO_GRAFICO, paper_bgcolor=COR_FUNDO_GRAFICO,
                                xaxis=dict(showgrid=False, showticklabels=False, title="", zeroline=False),
                                yaxis=dict(title="", showgrid=False, tickfont=dict(size=12, color='white')), margin=dict(t=10, b=0, l=0, r=0)
                            )
                            st.plotly_chart(fig_lucro, use_container_width=True, height=230)
                        else:
                            st.info("Nenhuma receita gerada ainda.")
                    else:
                        st.info("Nenhuma receita gerada ainda.")

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
                            eventos_futuros.append({
                                'Data': d_ini, 
                                'DataStr': d_ini.strftime("%d/%m"), 
                                'Cliente': ev.get('clientes_eventos', {}).get('nome', 'Cliente') if ev.get('clientes_eventos') else 'Cliente',
                                'Evento': ev.get('descricao', 'Evento')[:15] + "..."
                            })
                    except: pass
                
                eventos_futuros = sorted(eventos_futuros, key=lambda x: x['Data'])[:4]
                
                if eventos_futuros:
                    for evf in eventos_futuros:
                        st.markdown(f"🟢 **{evf['DataStr']}** - {evf['Cliente']}<br><span style='color:gray; font-size:12px;'>{evf['Evento']}</span>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin: 8px 0px; border-color: #333;'>", unsafe_allow_html=True)
                else:
                    st.info("Agenda livre! Nenhum evento futuro programado.")
            else:
                st.info("Nenhum evento cadastrado.")
    elif menu == "📅 Agendamento":
        st.title("📅 Gestão de Agendamentos")
        
        produtos_disp = supabase.table("produtos").select("id, nome, quantidade_estoque, observacao").eq("empresa_id", emp_id).execute()
        dict_produtos = {p['id']: p for p in produtos_disp.data} if produtos_disp.data else {}

        # 1. PUXANDO DADOS E CLIENTES
        eventos_cadastrados = supabase.table("eventos").select("*").eq("empresa_id", emp_id).order("data_inicio", desc=False).execute()
        lista_todos_eventos = eventos_cadastrados.data or []
        
        try: clientes_resultado = supabase.table("clientes_eventos").select("id, nome, contato").eq("empresa_id", emp_id).execute()
        except: clientes_resultado = supabase.table("clientes_eventos").select("id, nome").eq("empresa_id", emp_id).execute()
        mapa_clientes = {c['id']: c for c in clientes_resultado.data} if clientes_resultado.data else {}

        hoje_dt = datetime.now().date()

        # ==========================================
        # 2. KPIs SUPERIORES (Resumo Operacional)
        # ==========================================
        eventos_hoje = 0
        eventos_proximos_7_dias = 0
        
        for ev_kpi in lista_todos_eventos:
            if ev_kpi.get('status') not in ["Cancelado", "Concluído"] and ev_kpi.get('data_inicio'):
                try:
                    d_ini_kpi = datetime.strptime(ev_kpi['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if d_ini_kpi == hoje_dt:
                        eventos_hoje += 1
                    elif hoje_dt < d_ini_kpi <= (hoje_dt + relativedelta(days=7)):
                        eventos_proximos_7_dias += 1
                except: pass

        st.markdown("#### 📊 Visão Operacional")
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("📍 Eventos Hoje", eventos_hoje)
        col_k2.metric("🔜 Próximos 7 Dias", eventos_proximos_7_dias)
        col_k3.metric("📑 Total na Base", len(lista_todos_eventos))

        st.markdown("---")
        
        # ==========================================
        # 3. FILTROS INTELIGENTES
        # ==========================================
        st.markdown("#### 🔍 Filtrar Eventos")
        col_f1, col_f2, col_f3 = st.columns([1, 1.2, 1.5])
        
        with col_f1:
            filtro_status = st.multiselect("Status", ["Agendado", "Em Andamento", "Concluído", "Cancelado"], default=["Agendado", "Em Andamento"])
        with col_f2:
            filtro_data = st.date_input("Período (Início e Fim)", value=[hoje_dt, hoje_dt + relativedelta(days=30)], format="DD/MM/YYYY")
        with col_f3:
            filtro_busca = st.text_input("Buscar Cliente ou Título", placeholder="Digite o nome...")

        # Aplicando as regras de filtro na lista de eventos
        eventos_filtrados = []
        for ev in lista_todos_eventos:
            passa_status = (ev.get('status') in filtro_status) if filtro_status else True
            
            passa_data = True
            if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                try:
                    d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if not (filtro_data[0] <= d_ini_ev <= filtro_data[1]):
                        passa_data = False
                except: passa_data = False
            elif isinstance(filtro_data, tuple) and len(filtro_data) == 1:
                try:
                    d_ini_ev = datetime.strptime(ev['data_inicio'].split("T")[0], "%Y-%m-%d").date()
                    if d_ini_ev != filtro_data[0]:
                        passa_data = False
                except: passa_data = False

            passa_busca = True
            if filtro_busca.strip():
                termo = filtro_busca.lower()
                titulo = (ev.get('descricao') or "").lower()
                nome_cli = (mapa_clientes.get(ev.get('cliente_id'), {}).get('nome', "")).lower()
                if termo not in titulo and termo not in nome_cli:
                    passa_busca = False
            
            if passa_status and passa_data and passa_busca:
                eventos_filtrados.append(ev)

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
                
                # Formata a hora para HH:MM, ou define padrão se não houver
                hora_ini_fmt = ev.get('hora_inicio')[:5] if ev.get('hora_inicio') else "00:00"
                hora_fim_fmt = ev.get('hora_fim')[:5] if ev.get('hora_fim') else "23:59"

                with st.expander(f"🎉 {titulo_ev} — {nome_cliente_ev} | {data_ini_br} ({hora_ini_fmt}) até {data_fim_br} ({hora_fim_fmt}) | Status: {status_ev}"):
                    itens_ev = supabase.table("itens_evento").select("id, produto_id, quantidade, observacao").eq("evento_id", ev['id']).execute()
                    tab_detalhes, tab_add, tab_rem, tab_editar, tab_hist = st.tabs(["📋 Detalhes & Recibo", "➕ Adicionar Itens", "➖ Remover Itens", "✏️ Editar Evento", "🕒 Histórico"])

                    with tab_detalhes:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            valor_ev = float(ev.get('valor_total') or 0)
                            st.write(f"**Data e Hora:** {data_ini_br} às {hora_ini_fmt} — {data_fim_br} às {hora_fim_fmt}")
                            
                            # Mantendo apenas UM valor na tela
                            st.write(f"**Valor:** R$ {formatar_moeda(valor_ev)}")
                            st.write(f"**Contato do Cliente:** {contato_cliente_ev}")
                            
                            # Separando "Observações" e "Local" em linhas diferentes
                            obs_bd = ev.get('observacao') or '-'
                            obs_formatada = obs_bd.replace("Local:", "\n\n**Local:**")
                            st.write(f"**Observações:** {obs_formatada}")
                        with col_b:
                            opcoes_status = ["Agendado", "Em Andamento", "Concluído", "Cancelado"]
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
                            col_pag_v, col_pag_r = st.columns([3, 1])
                            with col_pag_v:
                                if ev.get('comprovante_pagamento_url'):
                                    url_comprovante = gerar_url_assinada_documento(ev['comprovante_pagamento_url'])
                                    if url_comprovante: st.link_button("📎 Ver Comprovante de Pagamento", url_comprovante)
                            with col_pag_r:
                                if st.button("🗑️ Remover", key=f"del_comp_{ev['id']}"):
                                    remover_documento_evento(ev.get('comprovante_pagamento_url'))
                                    supabase.table("eventos").update({
                                        "pagamento_confirmado": False,
                                        "metodo_confirmacao_pagamento": None,
                                        "comprovante_pagamento_url": None,
                                        "data_confirmacao_pagamento": None
                                    }).eq("id", ev['id']).execute()
                                    mostrar_popup("COMPROVANTE REMOVIDO COM SUCESSO!")
                                    st.rerun()
                        else:
                            metodo_confirmacao = st.radio(
                                "Como confirmar o pagamento?",
                                ["📎 Anexar comprovante", "✅ Confirmar sem comprovante (ex: pago em mãos)"],
                                key=f"metodo_pag_{ev['id']}"
                            )
                            if metodo_confirmacao.startswith("📎"):
                                arquivo_comprovante = st.file_uploader("Envie o comprovante (imagem ou PDF)", type=["png", "jpg", "jpeg", "pdf"], key=f"upload_comp_{ev['id']}")
                                if st.button("💾 Confirmar Pagamento com Comprovante", key=f"btn_conf_pag_comp_{ev['id']}"):
                                    if not arquivo_comprovante:
                                        mostrar_popup("Selecione o arquivo do comprovante.", tipo="erro")
                                    else:
                                        try:
                                            caminho_salvo = upload_documento_evento(ev['id'], arquivo_comprovante, "comprovante")
                                            supabase.table("eventos").update({
                                                "pagamento_confirmado": True,
                                                "metodo_confirmacao_pagamento": "Comprovante anexado",
                                                "comprovante_pagamento_url": caminho_salvo,
                                                "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")
                                            }).eq("id", ev['id']).execute()
                                            mostrar_popup("PAGAMENTO CONFIRMADO COM SUCESSO!")
                                            st.rerun()
                                        except Exception as e:
                                            mostrar_popup(f"Erro ao salvar comprovante: {e}", tipo="erro")
                            else:
                                if st.button("✅ Confirmar Pagamento", key=f"btn_conf_pag_sem_{ev['id']}"):
                                    supabase.table("eventos").update({
                                        "pagamento_confirmado": True,
                                        "metodo_confirmacao_pagamento": "Confirmado manualmente",
                                        "data_confirmacao_pagamento": datetime.now().strftime("%d/%m/%Y às %H:%M")
                                    }).eq("id", ev['id']).execute()
                                    mostrar_popup("PAGAMENTO CONFIRMADO COM SUCESSO!")
                                    st.rerun()

                        st.markdown("---")
                        st.subheader("📝 Contrato Assinado")
                        if ev.get('contrato_assinado_url'):
                            col_cont_v, col_cont_r = st.columns([3, 1])
                            with col_cont_v:
                                url_contrato = gerar_url_assinada_documento(ev['contrato_assinado_url'])
                                if url_contrato: st.link_button("📎 Ver Contrato Assinado", url_contrato)
                            with col_cont_r:
                                if st.button("🗑️ Remover", key=f"del_contrato_{ev['id']}"):
                                    remover_documento_evento(ev.get('contrato_assinado_url'))
                                    supabase.table("eventos").update({"contrato_assinado_url": None}).eq("id", ev['id']).execute()
                                    mostrar_popup("CONTRATO REMOVIDO COM SUCESSO!")
                                    st.rerun()
                            st.caption("Enviou um novo por engano? Suba o arquivo certo abaixo para substituir.")
                        arquivo_contrato_assinado = st.file_uploader("Envie o contrato assinado (PDF ou foto)", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_contrato_{ev['id']}")
                        if st.button("💾 Salvar Contrato Assinado", key=f"btn_contrato_{ev['id']}"):
                            if not arquivo_contrato_assinado:
                                mostrar_popup("Selecione o arquivo do contrato assinado.", tipo="erro")
                            else:
                                try:
                                    caminho_contrato = upload_documento_evento(ev['id'], arquivo_contrato_assinado, "contrato_assinado")
                                    supabase.table("eventos").update({"contrato_assinado_url": caminho_contrato}).eq("id", ev['id']).execute()
                                    mostrar_popup("CONTRATO ASSINADO SALVO COM SUCESSO!")
                                    st.rerun()
                                except Exception as e:
                                    mostrar_popup(f"Erro ao salvar contrato: {e}", tipo="erro")

                        if ev.get('google_event_id'):
                            st.caption("📅 Este evento já está sincronizado com a sua Google Agenda.")
                        if st.button("📅 Sincronizar com Google Agenda", key=f"sync_google_{ev['id']}"):
                            novo_id_google = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], ev, ev.get('google_event_id'))
                            if novo_id_google:
                                try: supabase.table("eventos").update({"google_event_id": novo_id_google}).eq("id", ev['id']).execute()
                                except Exception: pass
                                mostrar_popup("EVENTO SINCRONIZADO COM A GOOGLE AGENDA!")
                                st.rerun()
                            else:
                                mostrar_popup("Conecte sua Google Agenda em 'Perfil' primeiro.", tipo="erro")
                    
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
                            if not adicoes_selecionadas: mostrar_popup("Selecione ao menos 1 item.", tipo="erro")
                            elif not motivo_alteracao.strip(): mostrar_popup("Informe o motivo da alteração.", tipo="erro")
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
                                            val_rem = cols_rem[idxr % 6].number_input(f"{k} (Aloc:{qtd_alocada})", min_value=0, max_value=qtd_alocada, value=None, key=f"rem_{ev['id']}_{it['id']}_{k}")
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
                                    mostrar_popup("REMOÇÃO CONCLUÍDA COM SUCESSO!")
                                    st.rerun()
                        else: st.caption("Nenhum item alocado.")

                    with tab_editar:
                        def _parse_data_edit(data_iso):
                            if not data_iso: return datetime.now().date()
                            try: return datetime.strptime(data_iso.split("T")[0], "%Y-%m-%d").date()
                            except: return datetime.now().date()
                            
                        # Nova função para interpretar a hora salva no banco de dados
                        def _parse_time_edit(time_str):
                            if not time_str: return datetime.min.time()
                            try: return datetime.strptime(time_str[:5], "%H:%M").time()
                            except: return datetime.min.time()

                        # Alterado para 4 colunas para organizar datas e horas lado a lado
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
                                    supabase.table("eventos").update({
                                        "data_inicio": str(nova_data_inicio_edit), 
                                        "data_fim": str(nova_data_fim_edit), 
                                        "data_fim_alocacao": str(nova_data_fim_edit), 
                                        "hora_inicio": str(nova_hora_inicio_edit),
                                        "hora_fim": str(nova_hora_fim_edit),
                                        "valor_total": novo_valor_edit, 
                                        "observacao": novo_local_edit
                                    }).eq("id", ev['id']).execute()
                                    
                                    if ev.get('cliente_id'): supabase.table("clientes_eventos").update({"nome": novo_nome_cliente_edit, "contato": novo_contato_cliente_edit}).eq("id", ev['cliente_id']).execute()
                                    
                                    evento_atualizado_google = dict(ev)
                                    evento_atualizado_google.update({"data_inicio": str(nova_data_inicio_edit), "data_fim_alocacao": str(nova_data_fim_edit), "observacao": novo_local_edit})
                                    novo_id_google_edit = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], evento_atualizado_google, ev.get('google_event_id'))
                                    
                                    if novo_id_google_edit and not ev.get('google_event_id'):
                                        try: supabase.table("eventos").update({"google_event_id": novo_id_google_edit}).eq("id", ev['id']).execute()
                                        except Exception: pass
                                    
                                    data_hora_edit = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": ev['id'], "descricao": f"✏️ EDIÇÃO DE DADOS. Justificativa: {justificativa_edit}", "data_registro": data_hora_edit}).execute()
                                    mostrar_popup("EDIÇÃO CONCLUÍDA COM SUCESSO!")
                                    st.rerun()

                        with col_btn_edit2:
                            if st.button("🗑️ Excluir Evento", key=f"btn_excluir_evento_{ev['id']}"):
                                try:
                                    # Removemos as dependências primeiro para evitar erros no banco de dados
                                    supabase.table("itens_evento").delete().eq("evento_id", ev['id']).execute()
                                    supabase.table("historico_eventos").delete().eq("evento_id", ev['id']).execute()
                                    
                                    # Em seguida, apagamos o evento principal
                                    supabase.table("eventos").delete().eq("id", ev['id']).execute()
                                    
                                    mostrar_popup("EVENTO EXCLUÍDO COM SUCESSO!")
                                    st.rerun()
                                except Exception as e:
                                    mostrar_popup(f"Erro ao excluir: {e}", tipo="erro")

                    with tab_hist:
                        historico_ev = supabase.table("historico_eventos").select("descricao, data_registro").eq("evento_id", ev['id']).order("data_registro", desc=True).execute()
                        if historico_ev.data:
                            for h in historico_ev.data: st.write(f"🕒 **{h['data_registro']}** — {h['descricao']}")
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
                        mostrar_popup("Por favor, preencha todos os campos obrigatórios!", tipo="erro")
                    else:
                        # --- 🛡️ VALIDAÇÃO DE SEGURANÇA CONTRA ESTOQUE NEGATIVO ---
                        estoque_insuficiente = False
                        msg_erro_estoque = ""
                        alocacoes_agrupadas = {}
                        
                        for key, qtd in quantidades_selecionadas.items():
                            if qtd > 0:
                                p_id_str, sub_item = key.split("_", 1)
                                p_id_int = int(p_id_str)
                                
                                # Busca os dados reais do produto
                                prod_info = next((p for p in produtos_disp.data if p['id'] == p_id_int), None)
                                if not prod_info: continue
                                
                                # Verifica o limite se for produto normal
                                if sub_item == "NORMAL":
                                    disp = max(0, prod_info['quantidade_estoque'] - qtd_alugada_form.get(p_id_int, 0))
                                    if qtd > disp:
                                        estoque_insuficiente = True
                                        msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']}. Você pediu {qtd}, mas só temos {disp} livres nesse horário."
                                        break
                                # Verifica o limite se for sub-item (letras/números)
                                else:
                                    js_est = safe_json_load(prod_info.get('observacao')) or {}
                                    disp_sub = js_est.get(sub_item, 0) - detalhe_alugado_form.get(p_id_int, {}).get(sub_item, 0)
                                    disp_sub = max(0, disp_sub)
                                    if qtd > disp_sub:
                                        estoque_insuficiente = True
                                        msg_erro_estoque = f"Estoque insuficiente para {prod_info['nome']} ({sub_item}). Você pediu {qtd}, mas só temos {disp_sub} livres."
                                        break
                                
                                # Agrupa se passar na validação
                                if p_id_int not in alocacoes_agrupadas: alocacoes_agrupadas[p_id_int] = {'total': 0, 'detalhes': {}}
                                alocacoes_agrupadas[p_id_int]['total'] += qtd
                                if sub_item != "NORMAL": alocacoes_agrupadas[p_id_int]['detalhes'][sub_item] = qtd

                        # Se der erro no estoque, bloqueia tudo e avisa
                        if estoque_insuficiente:
                            mostrar_popup(msg_erro_estoque, tipo="erro")
                        else:
                            try:
                                contato_cliente_formatado = formatar_telefone_br(contato_cliente)
                                novo_cliente = supabase.table("clientes_eventos").insert({"empresa_id": emp_id, "nome": nome_cliente, "contato": contato_cliente_formatado}).execute()
                                cliente_id_gerado = novo_cliente.data[0]['id']
                                
                                novo_evento = supabase.table("eventos").insert({
                                    "empresa_id": emp_id, "cliente_id": cliente_id_gerado, "titulo": nome_evento,
                                    "descricao": nome_evento, "data_inicio": str(data_inicio), 
                                    "data_fim": str(data_fim), "data_fim_alocacao": str(data_fim), 
                                    "hora_inicio": str(hora_inicio), "hora_fim": str(hora_fim),
                                    "status": status_evento, "observacao": f"Local: {local_evento} - {rua_evento}, {numero_evento} - {bairro_evento} - {obs_evento_geral}",
                                    "valor_total": valor_evento
                                }).execute()
                                evento_id_gerado = novo_evento.data[0]['id']

                                google_event_id_novo = sincronizar_evento_google_agenda_silencioso(st.session_state['usuario_id'], novo_evento.data[0])
                                if google_event_id_novo:
                                    try: supabase.table("eventos").update({"google_event_id": google_event_id_novo}).eq("id", evento_id_gerado).execute()
                                    except Exception: pass

                                data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                for p_id, info in alocacoes_agrupadas.items():
                                    obs_json_evento = json.dumps(info['detalhes']) if info['detalhes'] else ""
                                    supabase.table("itens_evento").insert({"empresa_id": emp_id, "evento_id": evento_id_gerado, "produto_id": p_id, "quantidade": info['total'], "observacao": obs_json_evento}).execute()
                                    supabase.table("historico_eventos").insert({"empresa_id": emp_id, "evento_id": evento_id_gerado, "descricao": f"🟢 ALOCAÇÃO INICIAL: Adicionou {info['total']}x Produto {p_id}.", "data_registro": data_hora}).execute()

                                mostrar_popup("CADASTRO DE EVENTO CONCLUÍDO COM SUCESSO!")
                                st.rerun()
                            except Exception as e: 
                                mostrar_popup(f"Erro: {e}", tipo="erro")

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

                # ==========================================================================
                # ✅ CORREÇÃO: antes este bloco tinha sua PRÓPRIA lógica de soma
                # (sem considerar hora, e somando "cegamente" eventos que não se cruzam).
                # Agora ele usa a MESMA função corrigida usada no resto do sistema,
                # que calcula o pico real de ocupação simultânea.
                # ==========================================================================
                try:
                    qtd_alugada, detalhe_alugado = calcular_disponibilidade_periodo(data_inicio_f, data_fim_f)
                except Exception as e:
                    st.exception(e)
                    qtd_alugada, detalhe_alugado = {}, {}

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

                # ===== DETALHAMENTO AUTOMÁTICO POR DIA E HORÁRIO (só itens com reserva no período) =====
                if data_fim_f > data_inicio_f or qtd_alugada:
                    st.markdown("#### 🕐 Detalhamento por Dia e Horário (apenas itens com reserva)")
                    produtos_com_reserva = df_produtos[df_produtos['Reservado na Data'] > 0]
                    if produtos_com_reserva.empty:
                        st.caption("Nenhum item reservado neste período.")
                    else:
                        for _, prod_row in produtos_com_reserva.iterrows():
                            linhas_detalhe = calcular_detalhamento_periodo_produto(data_inicio_f, data_fim_f, prod_row['id'], prod_row['Estoque Total'])
                            if linhas_detalhe:
                                with st.expander(f"{prod_row['Ícone']} {prod_row['nome']}", expanded=False):
                                    st.dataframe(pd.DataFrame(linhas_detalhe), use_container_width=True, hide_index=True)
            else: st.info("Nenhum produto cadastrado no estoque ainda.")

        with st.expander("➕ Adicionar Novo Item ou Kit", expanded=False):
            tipo_cadastro = st.radio("O que você vai cadastrar?", ["Produto Normal", "🔠 Kit Letras (A-Z)", "🔢 Kit Números (0 a 9)"])
            with st.form("form_estoque_add"):
                if tipo_cadastro == "Produto Normal":
                    nome_prod = st.text_input("Nome do Item (Ex: CADEIRA DE FERRO)")
                    qtd_prod = st.number_input("Quantidade Total Físico", min_value=0, value=None)
                    obs_prod = st.text_input("Observação Simples (Opcional)")
                    if st.form_submit_button("Salvar Produto Normal"):
                        if nome_prod.strip():
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": (qtd_prod or 0), "observacao": obs_prod}).execute()
                            mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                            st.rerun()    
                elif tipo_cadastro == "🔠 Kit Letras (A-Z)":
                    nome_prod = st.text_input("Nome do Kit", value="LETRAS ILUMINADAS")
                    # Lista com emojis padronizados para cada letra
                    letras = [f"🔠 {l}" for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
                    cols_l = st.columns(6)
                    qtd_letras = {}
                    
                    for i, l in enumerate(letras):
                        qtd_letras[l] = cols_l[i%6].number_input(l, min_value=0, value=None)
                    
                    if st.form_submit_button("Salvar Kit Letras"):
                        total_letras = sum((v or 0) for v in qtd_letras.values())
                        if total_letras == 0: 
                            mostrar_popup("Coloque pelo menos 1 letra!", tipo="erro")
                        else:
                            obs_json = json.dumps({k: (v or 0) for k, v in qtd_letras.items() if (v or 0) > 0})
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": total_letras, "observacao": obs_json}).execute()
                            mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
                            st.rerun()

                elif tipo_cadastro == "🔢 Kit Números (0 a 9)":
                    nome_prod = st.text_input("Nome do Kit", value="NÚMEROS ILUMINADOS")
                    # Emojis nativos em formato de bloco para números de 0 a 9
                    numeros = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
                    cols_n = st.columns(10)
                    qtd_numeros = {}
                    
                    for i, num in enumerate(numeros):
                        qtd_numeros[num] = cols_n[i%10].number_input(num, min_value=0, value=None)
                    
                    if st.form_submit_button("Salvar Kit Números"):
                        total_numeros = sum((v or 0) for v in qtd_numeros.values())
                        if total_numeros == 0: 
                            mostrar_popup("Coloque pelo menos 1 número!", tipo="erro")
                        else:
                            obs_json = json.dumps({k: (v or 0) for k, v in qtd_numeros.items() if (v or 0) > 0})
                            supabase.table("produtos").insert({"empresa_id": emp_id, "nome": nome_prod.upper(), "quantidade_estoque": total_numeros, "observacao": obs_json}).execute()
                            mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
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
                        if st.button("➖ Solicitar Remoção", key=f"btn_solicita_pex_{produto_id_excluir}"):
                            if total_remover_pex > 0 and motivo_pex.strip():
                                popup_confirmacao_estoque(produto_selecionado_info, "parcial", total_remover=total_remover_pex, qtds_json=qtds_remover_parcial, motivo=motivo_pex)
                            else:
                                mostrar_popup("Preencha a quantidade e o motivo da remoção.", tipo="erro")
                    else:
                        qtd_disponivel_pex = produto_selecionado_info['quantidade_estoque']
                        qtd_remover_normal = st.number_input(f"Quanto deseja remover de {produto_selecionado_info['nome']}? (Tem: {qtd_disponivel_pex})", min_value=0, max_value=qtd_disponivel_pex, value=None, key=f"pex_normal_{produto_id_excluir}")
                        motivo_pex_normal = st.text_input("Motivo da remoção", key=f"motivo_pex_normal_{produto_id_excluir}")
                        
                        if st.button("➖ Solicitar Remoção", key=f"btn_solicita_pex_normal_{produto_id_excluir}"):
                            if (qtd_remover_normal or 0) > 0 and motivo_pex_normal.strip():
                                popup_confirmacao_estoque(produto_selecionado_info, "parcial", total_remover=qtd_remover_normal, motivo=motivo_pex_normal)
                            else:
                                mostrar_popup("Preencha a quantidade e o motivo da remoção.", tipo="erro")

                else:
                    if st.button("🗑️ Solicitar Exclusão", key="btn_solicita_excluir_produto"):
                        popup_confirmacao_estoque(produto_selecionado_info, "total")
            else: st.info("Nenhum produto cadastrado para excluir.")
# 1. ADICIONAR QUANTIDADE A PRODUTO EXISTENTE
        with st.expander("⬆️ Adicionar Quantidade a Produto Existente", expanded=False):
            if produtos_lista.data:
                opcoes_add = {f"{p['nome']} (Estoque Atual: {p['quantidade_estoque']})": p for p in produtos_lista.data}
                prod_selecionado_add = st.selectbox("Selecione o produto para aumentar o estoque", list(opcoes_add.keys()), key="select_add_qtd")
                prod_alvo_add = opcoes_add[prod_selecionado_add]

                # Verifica se o produto é um Kit (possui JSON na observação)
                js_estoque_add = safe_json_load(prod_alvo_add.get('observacao'))

                if js_estoque_add:
                    st.markdown(f"**Especifique a quantidade recebida para cada item de {prod_alvo_add['nome']}:**")
                    cols_add_kit = st.columns(10)
                    idx_add = 0
                    qtds_adicionar_kit = {}
                    
                    for k, v_atual in js_estoque_add.items():
                        val_add_k = cols_add_kit[idx_add % 10].number_input(f"{k} (Tem: {v_atual})", min_value=0, value=0, key=f"add_kit_{prod_alvo_add['id']}_{k}")
                        if val_add_k > 0:
                            qtds_adicionar_kit[k] = val_add_k
                        idx_add += 1
                    
                    if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_kit_estoque"):
                        if not qtds_adicionar_kit:
                            mostrar_popup("Adicione quantidade em pelo menos um item.", tipo="erro")
                        else:
                            novo_json_add = dict(js_estoque_add)
                            total_adicionado = 0
                            # Atualiza o JSON e soma o total geral
                            for k, v in qtds_adicionar_kit.items():
                                novo_json_add[k] = novo_json_add.get(k, 0) + v
                                total_adicionado += v
                            
                            qtd_final = prod_alvo_add['quantidade_estoque'] + total_adicionado
                            
                            supabase.table("produtos").update({
                                "quantidade_estoque": qtd_final,
                                "observacao": json.dumps(novo_json_add)
                            }).eq("id", prod_alvo_add['id']).execute()
                            
                            mostrar_popup("Estoque atualizado com sucesso!")
                            st.rerun()
                else:
                    # Comportamento normal para produtos sem sub-itens
                    nova_qtd_add = st.number_input("Quantidade de peças adquiridas/adicionadas", min_value=1, step=1, key="num_add_qtd_normal")
                    
                    if st.button("➕ Confirmar Adição ao Estoque", key="btn_add_normal_estoque"):
                        qtd_final = prod_alvo_add['quantidade_estoque'] + nova_qtd_add
                        supabase.table("produtos").update({"quantidade_estoque": qtd_final}).eq("id", prod_alvo_add['id']).execute()
                        mostrar_popup("Estoque atualizado com sucesso!")
                        st.rerun()

        # 2. CONTROLE DE MANUTENÇÃO
        with st.expander("🔧 Controle de Manutenção", expanded=False):
            tab_enviar_manut, tab_extrato_manut = st.tabs(["Enviar para Manutenção", "Extrato de Manutenção"])
            
            with tab_enviar_manut:
                if produtos_lista.data:
                    opcoes_manut = {p['nome']: p for p in produtos_lista.data}
                    prod_manut_nome = st.selectbox("Selecione o Produto", list(opcoes_manut.keys()), key="sel_manut")
                    prod_manut = opcoes_manut[prod_manut_nome]
                    
                    col_m1, col_m2 = st.columns(2)
                    with col_m1: qtd_manut = st.number_input("Qtd para Manutenção", min_value=1, max_value=prod_manut['quantidade_estoque'], step=1)
                    with col_m2: motivo_manut = st.text_input("Motivo / Defeito")
                    
                    if st.button("🔧 Registrar Manutenção"):
                        if not motivo_manut.strip():
                            mostrar_popup("Informe o motivo da manutenção.", tipo="erro")
                        else:
                            # Tira do estoque
                            novo_estoque = prod_manut['quantidade_estoque'] - qtd_manut
                            supabase.table("produtos").update({"quantidade_estoque": novo_estoque}).eq("id", prod_manut['id']).execute()
                            # Registra na tabela de manutenção
                            supabase.table("manutencao").insert({
                                "empresa_id": emp_id, "produto_id": prod_manut['id'],
                                "quantidade": qtd_manut, "motivo": motivo_manut,
                                "status": "Em Manutenção", "data_envio": str(datetime.now().date())
                            }).execute()
                            mostrar_popup("Produto enviado para manutenção!")
                            st.rerun()
            
            with tab_extrato_manut:
                # Carrega manutenção da empresa
                try:
                    manut_lista = supabase.table("manutencao").select("*, produtos(nome)").eq("empresa_id", emp_id).execute()
                    if manut_lista.data:
                        for m in manut_lista.data:
                            nome_p = m['produtos']['nome'] if m.get('produtos') else f"Produto #{m['produto_id']}"
                            st.write(f"🛠️ **{nome_p}** — {m['quantidade']} un. | Data: {m['data_envio']} | Status: {m['status']}")
                            st.caption(f"Motivo: {m['motivo']}")
                            
                            if m['status'] == "Em Manutenção":
                                if st.button(f"✅ Retornar ao Estoque (ID {m['id']})", key=f"ret_manut_{m['id']}"):
                                    # Devolve pro estoque
                                    prod_atual = supabase.table("produtos").select("quantidade_estoque").eq("id", m['produto_id']).execute()
                                    if prod_atual.data:
                                        estq_atualizado = prod_atual.data[0]['quantidade_estoque'] + m['quantidade']
                                        supabase.table("produtos").update({"quantidade_estoque": estq_atualizado}).eq("id", m['produto_id']).execute()
                                        # Atualiza status
                                        supabase.table("manutencao").update({"status": "Concluído"}).eq("id", m['id']).execute()
                                        mostrar_popup("Produto devolvido ao estoque principal!")
                                        st.rerun()
                            st.markdown("---")
                    else:
                        st.info("Nenhum item em manutenção.")
                except Exception as e:
                    st.error(f"Erro ao carregar manutenção: {e}")

        # 3. CONTROLE DE ITENS QUEBRADOS
        with st.expander("🗑️ Controle de Itens Quebrados", expanded=False):
            tab_reg_quebrado, tab_lista_quebrados = st.tabs(["Registrar Itens Quebrados", "Histórico de Quebrados"])
            
            with tab_reg_quebrado:
                if produtos_lista.data:
                    opcoes_quebrado = {p['nome']: p for p in produtos_lista.data}
                    prod_quebra_nome = st.selectbox("Selecione o Produto", list(opcoes_quebrado.keys()), key="sel_quebrado")
                    prod_quebrado = opcoes_quebrado[prod_quebra_nome]
                    
                    col_q1, col_q2 = st.columns(2)
                    with col_q1: qtd_quebrada = st.number_input("Quantidade Quebrada/Perdida", min_value=1, max_value=prod_quebrado['quantidade_estoque'], step=1)
                    with col_q2: motivo_quebra = st.text_input("Detalhes (Ex: Quebrou na festa X)")
                    
                    if st.button("🗑️ Registrar Baixa por Quebra"):
                        if not motivo_quebra.strip():
                            mostrar_popup("Informe os detalhes da quebra.", tipo="erro")
                        else:
                            # Tira do estoque permanentemente
                            novo_estoque_q = prod_quebrado['quantidade_estoque'] - qtd_quebrada
                            supabase.table("produtos").update({"quantidade_estoque": novo_estoque_q}).eq("id", prod_quebrado['id']).execute()
                            # Registra no histórico
                            supabase.table("itens_quebrados").insert({
                                "empresa_id": emp_id, "produto_id": prod_quebrado['id'],
                                "quantidade": qtd_quebrada, "motivo": motivo_quebra,
                                "data_registro": str(datetime.now().date())
                            }).execute()
                            mostrar_popup("Baixa de estoque registrada com sucesso!")
                            st.rerun()
            
            with tab_lista_quebrados:
                try:
                    quebrados_lista = supabase.table("itens_quebrados").select("*, produtos(nome)").eq("empresa_id", emp_id).order("data_registro", desc=True).execute()
                    if quebrados_lista.data:
                        for q in quebrados_lista.data:
                            nome_pq = q['produtos']['nome'] if q.get('produtos') else f"Produto #{q['produto_id']}"
                            st.error(f"❌ **{nome_pq}** — {q['quantidade']} un. perdidas em {q['data_registro']}")
                            st.caption(f"Motivo: {q['motivo']}")
                            st.markdown("---")
                    else:
                        st.info("Nenhum item quebrado registrado.")
                except Exception as e:
                    st.error(f"Erro ao carregar itens quebrados: {e}")
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
                if not nome_produto_compra.strip() or not fornecedor.strip():
                    mostrar_popup("Informe o nome do produto e a loja.", tipo="erro")
                else:
                    qtd_calc = quantidade_compra or 0
                    vlr_calc = valor_unit_compra or 0.0
                    valor_total_calc = qtd_calc * vlr_calc

                    supabase.table("compras").insert({
                        "empresa_id": emp_id, "nome_produto": nome_produto_compra, "fornecedor": fornecedor, "tipo_aquisicao": tipo_aquisicao, "local_detalhe": fornecedor,
                        "quantidade": qtd_calc, "valor_total": valor_total_calc, "data_compra": str(data_compra_input), "data_prevista_chegada": str(data_chegada_input),
                        "status_chegada": "Aguardando", "forma_pagamento": forma_pagamento_compra, "numero_pedido": numero_pedido_compra, "observacao": observacao_compra
                    }).execute()
                    mostrar_popup("COMPRA CADASTRADA COM SUCESSO!")
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
                        mostrar_popup("ITEM MARCADO COMO CHEGOU!")
                        st.rerun()
                else:
                    st.caption("Nenhuma compra pendente de chegada.")

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
                        if not edit_nome_c.strip() or not edit_loja_c.strip(): mostrar_popup("Informe o nome e loja.", tipo="erro")
                        else:
                            novo_tot_c = edit_qtd_c * edit_vunit_c
                            supabase.table("compras").update({
                                "nome_produto": edit_nome_c, "fornecedor": edit_loja_c, "local_detalhe": edit_loja_c,
                                "quantidade": edit_qtd_c, "valor_total": novo_tot_c, "tipo_aquisicao": edit_tipo_c,
                                "data_compra": str(edit_dt_c), "data_prevista_chegada": str(edit_dt_prev),
                                "forma_pagamento": edit_forma_pg, "numero_pedido": edit_num_ped,
                                "observacao": edit_obs_c
                            }).eq("id", compra_id_sel).execute()
                            mostrar_popup("COMPRA ATUALIZADA COM SUCESSO!")
                            st.rerun()
                with col_b2:
                    if st.button("🗑️ Excluir Compra", key="btn_excluir_edit_compra"):
                        supabase.table("compras").delete().eq("id", compra_id_sel).execute()
                        mostrar_popup("COMPRA EXCLUÍDA!")
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
                    if (valor_despesa or 0.0) <= 0: mostrar_popup("Informe um valor maior que zero.", tipo="erro")
                    else:
                        supabase.table("despesas_viagem").insert({
                            "empresa_id": emp_id, "categoria": categoria_despesa, "valor": (valor_despesa or 0.0),
                            "observacao": obs_despesa, "data_despesa": str(data_despesa_input)
                        }).execute()
                        mostrar_popup("CADASTRO CONCLUÍDO COM SUCESSO!")
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
                        if not motivo_edit_desp.strip(): mostrar_popup("Informe o motivo da edição.", tipo="erro")
                        else:
                            data_hora_edit_desp = datetime.now().strftime("%d/%m/%Y às %H:%M")
                            nova_obs_desp = f"{obs_edit_desp} [Editado em {data_hora_edit_desp} — Motivo: {motivo_edit_desp}]".strip()
                            supabase.table("despesas_viagem").update({
                                "categoria": categoria_edit_desp, "valor": valor_edit_desp,
                                "observacao": nova_obs_desp, "data_despesa": str(data_edit_desp)
                            }).eq("id", desp_selecionada['id']).execute()
                            mostrar_popup("ALTERAÇÃO CONCLUÍDA COM SUCESSO!")
                            st.rerun()
                with col_btn_d2:
                    if st.button("🗑️ Excluir Lançamento", key="btn_excluir_despesa"):
                        supabase.table("despesas_viagem").delete().eq("id", desp_selecionada['id']).execute()
                        mostrar_popup("LANÇAMENTO EXCLUÍDO!")
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
                    mostrar_popup("LANÇAMENTO CONCLUÍDO COM SUCESSO!")
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
                        if not motivo_edit_fat.strip(): mostrar_popup("Informe o motivo da edição.", tipo="erro")
                        else:
                            data_hora_edit_fat = datetime.now().strftime("%d/%m/%Y às %H:%M")
                            nova_desc_fat = f"{desc_edit_fat} [Editado em {data_hora_edit_fat} — Motivo: {motivo_edit_fat}]"
                            supabase.table("faturamento").update({
                                "descricao": nova_desc_fat, "tipo": tipo_edit_fat,
                                "valor": valor_edit_fat, "data_pagamento": str(data_edit_fat)
                            }).eq("id", fat_selecionado['id']).execute()
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
                
    elif menu == "🧳 Orçamento":
        st.title("🧳 Orçamento de Viagem / Evento")

        def _popup_aviso_orcamento():
            st.warning("🚧 Esta funcionalidade ainda está em produção.\n\nEstamos trabalhando nela — em breve você poderá montar orçamentos de viagem direto por aqui!")
            if st.button("Entendi, voltar"):
                st.rerun()

        if hasattr(st, "dialog"):
            st.dialog("🚧 Funcionalidade em Produção")(_popup_aviso_orcamento)()
        elif hasattr(st, "experimental_dialog"):
            st.experimental_dialog("🚧 Funcionalidade em Produção")(_popup_aviso_orcamento)()
        else:
            st.warning("🚧 Funcionalidade em produção, aguarde atualizações!")

        st.stop()
