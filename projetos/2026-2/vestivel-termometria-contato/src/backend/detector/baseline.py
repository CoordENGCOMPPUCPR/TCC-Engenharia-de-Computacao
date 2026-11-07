"""Linha de base por membro, sensor e hora local do dia.

B(membro, sensor, h) é a mediana das leituras válidas (e não congeladas) dos
últimos `baseline_dias` dias, dentro da hora que começa às h horas locais.

Ela é calculada fora do `step` e passada a ele já pronta, neste formato:

    {"<vaca>|<membro>": {"<sensor>": {"<hora>": {"b": float, "n": int, "dias": int}}}}

Uma célula está "armada" quando tem n >= arm_min_amostras e dias >= arm_dias.
"""

from datetime import datetime, timezone
from functools import lru_cache
from statistics import median
from zoneinfo import ZoneInfo


@lru_cache(maxsize=8)
def _tz(nome):
    return ZoneInfo(nome)


def _local(ts, fuso):
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_tz(fuso))


def hora_local(ts, fuso):
    """Hora local (0 a 23) de um instante em segundos desde a época."""
    return _local(ts, fuso).hour


def dia_local(ts, fuso):
    return _local(ts, fuso).date().isoformat()


def chave(vaca_id, membro):
    return f"{vaca_id}|{membro}"


def calcular_baseline(ciclos, config, agora, horas=None):
    """Calcula a linha de base a partir dos ciclos já fechados.

    Usa os campos vaca_id, membro, ts, T e congelado de cada ciclo (T já vem com
    None nos sensores inválidos). Só entram ciclos com ts em [agora - baseline_dias, agora).
    Se `horas` for dado, calcula só essas horas locais.
    """
    inicio = agora - config.baseline_dias * 86400
    acum = {}   # chave -> sensor -> hora -> (valores, dias)
    for c in ciclos:
        if c.get("congelado") or not (inicio <= c["ts"] < agora):
            continue
        h = hora_local(c["ts"], config.fuso)
        if horas is not None and h not in horas:
            continue
        d = dia_local(c["ts"], config.fuso)
        k = chave(c["vaca_id"], c["membro"])
        for i, t in enumerate(c["T"]):
            if t is None:
                continue
            valores, dias = acum.setdefault(k, {}).setdefault(str(i + 1), {}).setdefault(str(h), ([], set()))
            valores.append(t)
            dias.add(d)

    return {
        k: {s: {h: {"b": median(v), "n": len(v), "dias": len(ds)} for h, (v, ds) in hs.items()}
            for s, hs in sensores.items()}
        for k, sensores in acum.items()
    }


def consultar(baseline, vaca_id, membro, sensor, hora, config):
    """Retorna (valor, armado) da célula, ou (None, False) se ela não existe."""
    cel = (baseline or {}).get(chave(vaca_id, membro), {}).get(str(sensor), {}).get(str(hora))
    if not cel:
        return None, False
    armado = cel["n"] >= config.arm_min_amostras and cel["dias"] >= config.arm_dias
    return cel["b"], armado
