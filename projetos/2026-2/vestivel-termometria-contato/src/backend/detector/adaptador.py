"""Converte linhas da tabela `leituras` em pacotes para o detector.

Todas as leituras de um POST são gravadas na mesma transação e recebem o mesmo
timestamp, então um pacote = (vaca_id, membro, timestamp). Uma retentativa do
gateway vira outro pacote, e a mediana do bin absorve a duplicata.
Leituras sem membro (anteriores à coluna) entram como "U".
"""

from datetime import datetime, timezone

EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _para_us(ts):
    """Timestamp -> microssegundos inteiros desde a época (usado como chave do grupo)."""
    if isinstance(ts, (int, float)):
        return round(ts * 1_000_000)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            raise ValueError("timestamp sem fuso horário")
        delta = ts.astimezone(timezone.utc) - EPOCA
        return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    raise TypeError(f"timestamp de tipo não suportado: {type(ts).__name__}")


def _aviso(tipo, chave, **extra):
    vaca_id, membro, us = chave
    return {"tipo": tipo, "vaca_id": vaca_id, "membro": membro, "ts": us / 1e6, **extra}


def linhas_para_pacotes(linhas, n_sensores=5):
    """Agrupa as leituras em pacotes. Retorna (pacotes, avisos).

    Cada linha precisa de vaca_id, quarto, temp_raw e timestamp (datetime com fuso,
    ISO 8601 ou segundos desde a época); membro é opcional.

    Cada pacote: {"vaca_id", "membro", "ts", "T": [n_sensores valores]}, em ordem de tempo.
    - quarto fora de 1..n_sensores: descartado;
    - quarto repetido no mesmo pacote: fica o primeiro;
    - quarto faltando: None (pacote incompleto).
    Todos esses casos geram aviso.
    """
    grupos = {}   # chave -> (temperaturas, quartos já vistos)
    avisos = []
    for ln in linhas:
        q = ln.get("quarto")
        chave = (str(ln["vaca_id"]), ln.get("membro") or "U", _para_us(ln["timestamp"]))
        if not isinstance(q, int) or isinstance(q, bool) or not 1 <= q <= n_sensores:
            avisos.append(_aviso("quarto_invalido", chave, quarto=q))
            continue
        T, vistos = grupos.setdefault(chave, ([None] * n_sensores, set()))
        if q in vistos:
            avisos.append(_aviso("quarto_repetido", chave, quarto=q))
            continue
        vistos.add(q)
        t = ln.get("temp_raw")
        T[q - 1] = None if t is None else float(t)

    pacotes = []
    for chave, (T, vistos) in sorted(grupos.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
        vaca_id, membro, us = chave
        if len(vistos) < n_sensores:
            faltam = sorted(set(range(1, n_sensores + 1)) - vistos)
            avisos.append(_aviso("pacote_incompleto", chave, faltam=faltam))
        pacotes.append({"vaca_id": vaca_id, "membro": membro, "ts": us / 1e6, "T": T})
    return pacotes, avisos
