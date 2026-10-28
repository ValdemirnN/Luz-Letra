"""Peças visuais e de dados da tela "Meu Perfil".

Campos novos (telefone, cargo, CNPJ, endereço, Instagram...) ficam guardados em UMA coluna
JSON da tabela `usuarios`. Para ativar, rode UMA vez no Supabase (SQL Editor):

    alter table usuarios add column if not exists perfil_extra jsonb default '{}'::jsonb;

(O nome fantasia da empresa continua indo para a coluna que já existe: empresas.nome_fantasia.)
"""
import json
import re
from datetime import date, datetime
from html import escape

import streamlit as st

from modulos.log import registrar_erro

SQL_PERFIL_EXTRA = "alter table usuarios add column if not exists perfil_extra jsonb default '{}'::jsonb;"

_CSS = """
<style>
.pf-hero { display:flex; align-items:center; gap:22px; flex-wrap:wrap;
    background: linear-gradient(135deg, rgba(255,193,7,.10) 0%, rgba(27,27,29,1) 55%);
    border:1px solid rgba(255,193,7,.28); border-radius:18px; padding:22px 26px; margin: 6px 0 18px 0;
    box-shadow: 0 8px 28px rgba(0,0,0,.35); }
.pf-av { width:92px; height:92px; flex:0 0 92px; border-radius:50%; background:#1B1B1D center/cover no-repeat;
    border:3px solid #FFC107; box-shadow:0 0 0 5px rgba(255,193,7,.16);
    display:flex; align-items:center; justify-content:center; color:#FFC107; font-weight:800; font-size:38px; }
.pf-info { flex:1 1 260px; min-width:0; }
.pf-nome { font-size:1.55rem; font-weight:800; color:#F5F5F5; line-height:1.15; word-break:break-word; }
.pf-sub { color:#9A9A9A; font-size:.92rem; margin-top:3px; word-break:break-word; }
.pf-badges { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.pf-badge { font-size:.78rem; font-weight:700; padding:4px 11px; border-radius:999px;
    background:#26262A; color:#DDD; border:1px solid #3a3a40; }
.pf-badge.ouro { background:rgba(255,193,7,.14); color:#FFC107; border-color:rgba(255,193,7,.4); }
.pf-badge.verde { background:rgba(46,125,50,.20); color:#7CD67F; border-color:rgba(46,125,50,.55); }
.pf-badge.amar { background:rgba(255,193,7,.16); color:#FFD54F; border-color:rgba(255,193,7,.5); }
.pf-badge.verm { background:rgba(179,38,30,.22); color:#FF8A80; border-color:rgba(179,38,30,.6); }
.pf-prog { flex:0 0 210px; min-width:180px; }
.pf-prog .t { font-size:.8rem; color:#9A9A9A; margin-bottom:6px; display:flex; justify-content:space-between; }
.pf-prog .t b { color:#FFC107; }
.pf-bar { height:9px; border-radius:99px; background:#2a2a2e; overflow:hidden; }
.pf-bar > div { height:100%; border-radius:99px; background:linear-gradient(90deg,#FFB300,#FFE082); }
.pf-dica { font-size:.8rem; color:#8d8d93; margin-top:6px; }
</style>
"""


def aplicar_css():
    st.markdown(_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Formatadores simples
# ----------------------------------------------------------------------------------
def so_digitos(s):
    return re.sub(r"\D", "", s or "")


def fmt_tel(s):
    d = so_digitos(s)
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return (s or "").strip()


def fmt_doc(s):
    d = so_digitos(s)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return (s or "").strip()


def fmt_cep(s):
    d = so_digitos(s)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else (s or "").strip()


def fmt_insta(s):
    s = (s or "").strip()
    if not s:
        return ""
    s = s.replace("https://", "").replace("http://", "").replace("www.instagram.com/", "").replace("instagram.com/", "").strip("/")
    return s if s.startswith("@") else f"@{s}"


# ----------------------------------------------------------------------------------
# Campos extras (coluna usuarios.perfil_extra)
# ----------------------------------------------------------------------------------
def carregar_extra(supabase, uid):
    cache = st.session_state.get('_perfil_extra_cache')
    if cache and cache[0] == uid:
        return dict(cache[1])
    extra = {}
    try:
        r = supabase.table("usuarios").select("perfil_extra").eq("id", uid).execute()
        if r.data:
            bruto = r.data[0].get("perfil_extra")
            if isinstance(bruto, str):
                try:
                    bruto = json.loads(bruto)
                except Exception:
                    bruto = {}
            if isinstance(bruto, dict):
                extra = bruto
    except Exception:
        registrar_erro("perfil_ui.py:carregar_extra")  # coluna ainda não criada
    st.session_state['_perfil_extra_cache'] = (uid, extra)
    return dict(extra)


def salvar_extra(supabase, uid, extra):
    """Devolve True se gravou. Em caso de falha (coluna não criada), devolve False."""
    try:
        supabase.table("usuarios").update({"perfil_extra": extra}).eq("id", uid).execute()
        st.session_state['_perfil_extra_cache'] = (uid, dict(extra))
        return True
    except Exception:
        registrar_erro("perfil_ui.py:salvar_extra")
        return False


def aviso_sql_extra():
    st.error("Não foi possível salvar os campos novos. Se for a primeira vez, crie a coluna no Supabase "
             "(SQL Editor) e tente de novo:")
    st.code(SQL_PERFIL_EXTRA, language="sql")


# ----------------------------------------------------------------------------------
# Cabeçalho do perfil
# ----------------------------------------------------------------------------------
def info_vencimento(venc):
    """Texto + classe de cor para o vencimento da assinatura."""
    if not venc:
        return "", ""
    try:
        d = datetime.strptime(str(venc).split("T")[0], "%Y-%m-%d").date()
    except Exception:
        return "", ""
    dias = (d - date.today()).days
    data_br = d.strftime("%d/%m/%Y")
    if dias < 0:
        return f"⛔ Venceu em {data_br}", "verm"
    if dias == 0:
        return "🚨 Vence hoje", "verm"
    if dias <= 5:
        return f"⚠️ Vence em {dias} dia(s) · {data_br}", "amar"
    return f"✅ Ativa até {data_br} · {dias} dias", "verde"


def completude(foto, nome, email, extra, nome_fantasia):
    itens = [
        (bool(foto), "adicionar uma foto"),
        (bool((nome or "").strip()), "o nome"),
        (bool((email or "").strip()), "o e-mail"),
        (bool(extra.get("telefone")), "seu telefone"),
        (bool(extra.get("cargo")), "sua função"),
        (bool((nome_fantasia or "").strip()), "o nome da empresa"),
        (bool(extra.get("cnpj")), "o CNPJ/CPF"),
        (bool(extra.get("emp_telefone") or extra.get("emp_whatsapp")), "o contato da empresa"),
        (bool(extra.get("endereco")), "o endereço"),
        (bool(extra.get("cidade")), "a cidade"),
        (bool(extra.get("instagram")), "o Instagram"),
    ]
    feitos = sum(1 for ok, _ in itens if ok)
    faltando = [txt for ok, txt in itens if not ok]
    return int(round(100 * feitos / len(itens))), faltando


def cabecalho(nome, email, foto, papel, plano_txt, venc_txt, venc_cls, pct, faltando, empresa=""):
    inicial = (nome or "U").strip()[:1].upper() or "U"
    if foto:
        av = f'<div class="pf-av" style="background-image:url(data:image/jpeg;base64,{foto});"></div>'
    else:
        av = f'<div class="pf-av">{escape(inicial)}</div>'
    badges = [f'<span class="pf-badge ouro">{escape(plano_txt)}</span>', f'<span class="pf-badge">{escape(papel)}</span>']
    if venc_txt:
        badges.append(f'<span class="pf-badge {venc_cls}">{escape(venc_txt)}</span>')
    sub = escape(email or "")
    if empresa:
        sub = f"🏢 {escape(empresa)} &nbsp;·&nbsp; {sub}"
    dica = f'<div class="pf-dica">Falta: {escape(", ".join(faltando[:3]))}{"…" if len(faltando) > 3 else ""}</div>' if faltando else \
           '<div class="pf-dica">Perfil completo! 🎉</div>'
    st.markdown(
        f'<div class="pf-hero">{av}'
        f'<div class="pf-info"><div class="pf-nome">{escape(nome or "Minha conta")}</div>'
        f'<div class="pf-sub">{sub}</div><div class="pf-badges">{"".join(badges)}</div></div>'
        f'<div class="pf-prog"><div class="t"><span>Perfil preenchido</span><b>{pct}%</b></div>'
        f'<div class="pf-bar"><div style="width:{pct}%"></div></div>{dica}</div></div>',
        unsafe_allow_html=True,
    )
