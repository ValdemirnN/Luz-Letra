"""Registro de erros (logging) do sistema Luz & Letra.

Uso, dentro de um bloco `except`:
    except Exception:
        registrar_erro("modulo.py:123")
O erro vai para o log do servidor (no Streamlit Cloud: "Manage app" → logs) e o fluxo continua normalmente.
"""
import logging
import sys

logger = logging.getLogger("luz_letras")
if not logger.handlers:  # evita duplicar o handler a cada rerun do Streamlit
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def registrar_erro(local, detalhe=""):
    """Registra o erro que está sendo tratado no momento (traceback incluído)."""
    logger.warning("Erro tratado em %s%s", local, f" — {detalhe}" if detalhe else "", exc_info=True)
