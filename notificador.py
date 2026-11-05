"""Rotina diária de notificações por e-mail (roda sozinha pelo GitHub Actions, sem depender do app aberto).

Variáveis de ambiente (vêm dos "Secrets" do GitHub — veja .github/workflows/notificacoes-diarias.yml):
    SUPABASE_URL, SUPABASE_KEY, GMAIL_REMETENTE, GMAIL_SENHA_APP
    opcionais: URL_BASE_SISTEMA, PIX_CHAVE, PIX_NOME, NOTIF_A_PARTIR_DE (AAAA-MM-DD)

Teste sem enviar nada:  python notificador.py --simular
"""
import os
import sys

from supabase import create_client

from modulos import notificacoes


def main():
    simular = "--simular" in sys.argv
    url, chave = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_KEY", "")
    if not url or not chave:
        sys.exit("Faltam SUPABASE_URL / SUPABASE_KEY nas variáveis de ambiente.")
    if not simular and not notificacoes.configurado():
        sys.exit("Faltam GMAIL_REMETENTE / GMAIL_SENHA_APP nas variáveis de ambiente.")
    sb = create_client(url, chave)
    resumo = notificacoes.rodar_rotina_diaria(sb, dry_run=simular, desde=os.environ.get("NOTIF_A_PARTIR_DE") or None)
    print(("SIMULAÇÃO — " if simular else "") + "e-mails enviados:", resumo)
    if any(v == "erro" for v in resumo.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
