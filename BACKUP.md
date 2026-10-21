# Backup do Supabase

O workflow `.github/workflows/backup-supabase.yml` gera um backup toda semana (domingo) e guarda por 30 dias em **Actions → (execução) → Artifacts**. O arquivo é criptografado (AES-256).

## Configuração (uma vez só) — GitHub → Settings → Secrets and variables → Actions
- `SUPABASE_DB_URL`: no Supabase, **Connect → Session pooler** (porta 5432) e copie a URL com a senha do banco. Use o *pooler*: a conexão direta é só IPv6 e o GitHub não alcança.
- `BACKUP_PASSPHRASE`: invente uma senha longa e **guarde em local seguro** (sem ela o backup não abre).

> Mantenha o repositório **privado**. Mesmo criptografado, o backup contém dados dos clientes.

## Restaurar
```bash
gpg --decrypt backup-AAAA-MM-DD.sql.gz.gpg | gunzip | psql "URL_DO_BANCO_NOVO"
```
Teste uma restauração de vez em quando num projeto Supabase de teste.
