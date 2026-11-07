"""Aplica as migrações SQL da pasta migrations/, em ordem de nome.

Sem --aplicar, só mostra o SQL. Num banco do Aiven (produção) também é preciso
passar --confirmo-producao.

As migrações podem rodar mais de uma vez sem problema; a tabela schema_migrations
guarda as que já foram aplicadas, e essas são puladas.

Uso:
  python scripts/migrar.py                              # mostra o SQL (usa DATABASE_URL)
  python scripts/migrar.py --dsn postgresql://... --aplicar
"""

import argparse
import os
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1] / "migrations"

CONTROLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    versao        TEXT PRIMARY KEY,
    aplicada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def migracoes():
    return sorted(PASTA.glob("*.sql"))


def eh_producao(dsn):
    return "aivencloud.com" in (dsn or "")


def aplicar(conn, mostrar=print):
    """Aplica as migrações pendentes, uma transação para cada. Retorna as aplicadas."""
    aplicadas = []
    with conn.cursor() as cur:
        cur.execute(CONTROLE)
        cur.execute("SELECT versao FROM schema_migrations")
        feitas = {r[0] for r in cur.fetchall()}
    conn.commit()
    for arq in migracoes():
        if arq.name in feitas:
            continue
        with conn.cursor() as cur:
            cur.execute(arq.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations (versao) VALUES (%s) ON CONFLICT DO NOTHING", (arq.name,))
        conn.commit()
        mostrar(f"aplicada: {arq.name}")
        aplicadas.append(arq.name)
    return aplicadas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--confirmo-producao", action="store_true")
    a = ap.parse_args()

    if not a.aplicar:
        for arq in migracoes():
            print(f"-- ===== {arq.name} =====")
            print(arq.read_text(encoding="utf-8"))
        print("-- (nada executado; use --aplicar)")
        return 0
    if not a.dsn:
        print("DATABASE_URL ou --dsn é obrigatório", file=sys.stderr)
        return 2
    if eh_producao(a.dsn) and not a.confirmo_producao:
        print("Banco de produção (Aiven): confira o SQL e rode de novo com "
              "--confirmo-producao.", file=sys.stderr)
        return 3

    import psycopg2
    conn = psycopg2.connect(a.dsn)
    try:
        feitas = aplicar(conn)
        print("nada pendente" if not feitas else f"{len(feitas)} migração(ões) aplicada(s)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
