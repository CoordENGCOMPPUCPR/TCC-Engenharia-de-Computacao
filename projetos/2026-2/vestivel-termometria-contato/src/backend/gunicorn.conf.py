"""Configuração do gunicorn.

O gunicorn lê este arquivo sozinho quando é iniciado nesta pasta (comando do
Render: "gunicorn app:app"). Opções passadas na linha de comando têm prioridade.
"""

import os

# O detector roda depois da resposta do POST, ainda dentro do worker. 120 s dá conta
# do recálculo da linha de base e da primeira conexão ao banco depois do cold start;
# com o padrão (30 s) o worker seria morto no meio do processamento.
timeout = 120

# Cada worker abre até 5 conexões e o Aiven gratuito aceita 20 no total,
# então 2 workers usam no máximo 10.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
