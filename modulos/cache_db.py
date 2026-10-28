"""Cache curto de LEITURAS do Supabase (acelera a troca de telas).

Como funciona
- Envolve o cliente do Supabase. O código dos módulos continua igual:
  supabase.table("x").select(...).eq(...).execute()
- Leituras (select) iguais feitas em até TTL_SEGUNDOS voltam do cache, sem ir à rede.
- QUALQUER gravação (insert/update/delete/upsert) limpa o cache inteiro, então depois
  de salvar algo a próxima leitura já vem fresca.
- Tabelas de login/sessão/assinatura nunca são cacheadas (segurança).
- Chave do cache = consulta completa (tabela + filtros, inclusive empresa_id), então
  uma empresa nunca recebe dado de outra.

Limite conhecido: se OUTRA pessoa (ou o painel do Supabase) alterar um dado, quem está
logado pode demorar até TTL_SEGUNDOS para ver a mudança.
"""
import copy
import threading
import time

TTL_SEGUNDOS = 20
MAX_ENTRADAS = 400
TABELAS_SEM_CACHE = {"sessoes_ativas", "usuarios", "assinaturas", "historico_pagamentos", "notificacoes_enviadas"}
_ESCRITA = {"insert", "update", "delete", "upsert"}

_TRAVA = threading.Lock()
_CACHE = {}  # chave -> (instante, resposta)


def limpar_cache():
    with _TRAVA:
        _CACHE.clear()


class _Cadeia:
    """Grava a sequência de chamadas (.select().eq()...) e só executa no .execute()."""
    __slots__ = ("_cli", "_tab", "_ops")

    def __init__(self, cli, tab, ops=()):
        self._cli, self._tab, self._ops = cli, tab, ops

    def __getattr__(self, nome):
        if nome.startswith("__"):
            raise AttributeError(nome)
        return _Cadeia(self._cli, self._tab, self._ops + (("a", nome),))

    def __call__(self, *args, **kwargs):
        ops = self._ops + (("c", args, kwargs),)
        if len(self._ops) >= 1 and self._ops[-1] == ("a", "execute"):
            return self._executar(ops)
        return _Cadeia(self._cli, self._tab, ops)

    def _reproduzir(self, ops):
        obj = self._cli.table(self._tab)
        for op in ops:
            obj = getattr(obj, op[1]) if op[0] == "a" else obj(*op[1], **op[2])
        return obj

    def _executar(self, ops):
        escrita = any(o[0] == "a" and o[1] in _ESCRITA for o in ops)
        if escrita:
            try:
                return self._reproduzir(ops)
            finally:
                limpar_cache()
        if self._tab in TABELAS_SEM_CACHE:
            return self._reproduzir(ops)
        chave = repr((self._tab, ops[:-2]))  # sem o ".execute()" final
        agora = time.time()
        with _TRAVA:
            item = _CACHE.get(chave)
        if item and agora - item[0] < TTL_SEGUNDOS:
            return copy.deepcopy(item[1])
        resp = self._reproduzir(ops)
        try:
            guardar = copy.deepcopy(resp)
            with _TRAVA:
                if len(_CACHE) >= MAX_ENTRADAS:
                    _CACHE.clear()
                _CACHE[chave] = (time.time(), guardar)
        except Exception:
            pass
        return resp


class ClienteComCache:
    def __init__(self, cliente):
        self._cli = cliente

    def table(self, nome):
        return _Cadeia(self._cli, nome)

    from_ = table

    def __getattr__(self, nome):
        return getattr(self._cli, nome)
