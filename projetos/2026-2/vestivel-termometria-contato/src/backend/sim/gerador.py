"""Gerador de pacotes sintéticos para testar o detector.

Todos os valores abaixo são premissas, não medidas em animais:
- ruido_sd 0,03 °C: ruído branco por leitura (na bancada deu ~0,02 °C).
- offset_max 1,0 °C: desvio fixo de cada sensor, sorteado em [-1, 1].
- deriva: quedas comuns aos 5 sensores a -0,6 °C/h (taxa vista em ar parado). Modelada
  como episódios triangulares (desce por D horas e volta), em média deriva_por_dia
  episódios por membro; uma deriva contínua daria valores absurdos em poucos dias.
- kappa 0,28 °C/°C: quanto a temperatura do ar passa para a pele.
- ambiente: 20 °C ± 4 °C ao longo do dia (pico às 15 h), mais uma variação de um dia
  para o outro (AR(1), desvio de 3 °C, phi = 0,7).
- circ_amp 0,4 °C: ritmo circadiano do membro (pico às 18 h).
- decúbito: ~2 episódios por dia, de 1 a 3 h, com desvio N(0; 0,7 °C), um membro por vez.
- perda: ~22% dos pacotes, em rajadas de 2 (20% delas com 4), como no log de 20/10.
- base 32 °C: temperatura média da pele na coroa do casco.
- idio: variações lentas e independentes de cada sensor (meia senoide, 0,3 a 1,0 °C,
  1 a 6 h, ~1,5 por dia).
"""

import math
import random
from dataclasses import dataclass, field, replace

# 2026-01-05 00:00 em America/Sao_Paulo (UTC-3, sem horário de verão desde 2019)
T_INICIO = 1767582000.0
FUSO_H = -3


@dataclass(frozen=True)
class Premissas:
    base: float = 32.0
    ruido_sd: float = 0.03
    offset_max: float = 1.0
    deriva_taxa_h: float = -0.6
    deriva_por_dia: float = 1.0
    deriva_dur_h: tuple = (0.5, 2.0)
    kappa: float = 0.28
    amb_media: float = 20.0
    amb_amp: float = 4.0
    amb_ar_sd: float = 3.0
    amb_ar_phi: float = 0.7
    circ_amp: float = 0.4
    decub_por_dia: float = 2.0
    decub_dur_h: tuple = (1.0, 3.0)
    decub_sd: float = 0.7
    idio_por_dia: float = 1.5
    idio_amp: tuple = (0.3, 1.0)
    idio_dur_h: tuple = (1.0, 6.0)
    perda: float = 0.22
    rajada_p4: float = 0.2
    cadencia_s: float = 60.0
    arredondar: bool = True

    def sem(self, *ingredientes):
        """Cópia com alguns ingredientes desligados (nomes em INGREDIENTES).
        kappa não é ingrediente: sem ambiente e ambiente_dia o ar já fica constante."""
        mapa = {
            "ruido": {"ruido_sd": 0.0},
            "offset": {"offset_max": 0.0},
            "deriva": {"deriva_por_dia": 0.0},
            "ambiente_dia": {"amb_ar_sd": 0.0},
            "ambiente": {"amb_amp": 0.0},
            "circadiano": {"circ_amp": 0.0},
            "decubito": {"decub_por_dia": 0.0},
            "perda": {"perda": 0.0},
            "idio": {"idio_por_dia": 0.0},
        }
        mud = {}
        for i in ingredientes:
            mud.update(mapa[i])
        return replace(self, **mud)


INGREDIENTES = ("ruido", "offset", "deriva", "ambiente_dia", "ambiente", "circadiano", "decubito", "perda", "idio")


@dataclass
class Injecao:
    """Elevação somada a alguns sensores de um membro: sobe de 0 a `amp` em
    `rampa_h` horas (0 = degrau) e fica no patamar por `dur_h` horas."""
    membro: str
    sensores: tuple   # índices 0-based
    amp: float
    t0: float
    rampa_h: float = 0.0
    dur_h: float = 24.0

    def valor(self, t):
        if t < self.t0:
            return 0.0
        dt = t - self.t0
        r = self.rampa_h * 3600
        if dt < r:
            return self.amp * dt / r
        if dt < r + self.dur_h * 3600:
            return self.amp
        return 0.0

    @property
    def fim(self):
        return self.t0 + (self.rampa_h + self.dur_h) * 3600


def _p_inicio_rajada(p):
    """Chance de um pacote iniciar uma rajada de perda, para que a fração perdida
    seja p.perda. Vem de f = q*L / ((1 - q) + q*L), com L = tamanho médio da rajada."""
    L = 2 + 2 * p.rajada_p4
    return p.perda / (L * (1 - p.perda) + p.perda)


def hora_local(t):
    return ((t / 3600.0) + FUSO_H) % 24.0


class _Ativos:
    """Soma dos episódios (início, fim, f(t)) ativos em t. Supõe t sempre crescente,
    então só percorre os episódios ativos."""

    def __init__(self, eps):
        self.eps = sorted(eps, key=lambda e: e[0])
        self.i = 0
        self.ativos = []

    def valor(self, t):
        while self.i < len(self.eps) and self.eps[self.i][0] <= t:
            self.ativos.append(self.eps[self.i])
            self.i += 1
        if self.ativos:
            self.ativos = [e for e in self.ativos if e[1] > t]
        return sum(f(t) for _, _, f in self.ativos)


def _triangulo(t0, dur, taxa_h):
    def f(t):
        tau = t - t0
        return taxa_h * (tau if tau < dur else 2 * dur - tau) / 3600.0
    return f


def _constante(v):
    return lambda t: v


def _meia_senoide(t0, dur, amp):
    return lambda t: amp * math.sin(math.pi * (t - t0) / dur)


def _episodios(rng, dias, por_dia, dur_h, t_inicio):
    """Sorteia episódios como um processo de Poisson: lista de (início, duração em s)."""
    eps = []
    if por_dia <= 0:
        return eps
    t = t_inicio
    fim = t_inicio + dias * 86400
    while True:
        t += rng.expovariate(por_dia / 86400.0)
        if t >= fim:
            return eps
        eps.append((t, rng.uniform(*dur_h) * 3600))


def gerar(premissas, semente, dias, membros=("E", "D"), vaca_id="sim01",
          injecoes=(), extras=None, t_inicio=T_INICIO):
    """Gera os pacotes de uma vaca, em ordem de tempo.

    `extras(membro, t, T) -> T` permite alterar as leituras (erro de sensor,
    perda de contato etc.).
    """
    p = premissas
    rng = random.Random(semente)
    n = 5

    offsets = {m: [rng.uniform(-p.offset_max, p.offset_max) for _ in range(n)] for m in membros}

    # Ambiente: desvio diário AR(1), interpolado entre os meios-dias
    inov = p.amb_ar_sd * math.sqrt(1 - p.amb_ar_phi ** 2)
    d = [rng.gauss(0, p.amb_ar_sd)]
    for _ in range(int(dias) + 2):
        d.append(p.amb_ar_phi * d[-1] + rng.gauss(0, inov))

    def ambiente(t):
        dias_desde = (t - t_inicio) / 86400.0 - 0.5  # 0 = meio-dia do 1º dia
        k = math.floor(dias_desde)
        f = dias_desde - k
        a = d[max(k, 0)] if k >= 0 else d[0]
        b = d[max(k + 1, 0)]
        desvio = a + (b - a) * f if k >= 0 else d[0]
        return p.amb_media + p.amb_amp * math.sin(2 * math.pi * (hora_local(t) - 9) / 24) + desvio

    # Deriva comum a todos os sensores do membro
    derivas = {m: _Ativos([(t0, t0 + 2 * dur, _triangulo(t0, dur, p.deriva_taxa_h))
                           for t0, dur in _episodios(rng, dias, p.deriva_por_dia, p.deriva_dur_h, t_inicio)])
               for m in membros}

    # Decúbito: um membro por vez
    decub = {m: [] for m in membros}
    ocupado_ate = -1.0
    for t0, dur in _episodios(rng, dias, p.decub_por_dia * len(membros), p.decub_dur_h, t_inicio):
        if t0 < ocupado_ate:
            continue
        m, v = rng.choice(membros), rng.gauss(0, p.decub_sd)
        decub[m].append((t0, t0 + dur, _constante(v)))
        ocupado_ate = t0 + dur
    decub = {m: _Ativos(eps) for m, eps in decub.items()}

    # Variação própria de cada sensor
    idio = {}
    for m in membros:
        for i in range(n):
            eps = []
            for t0, dur in _episodios(rng, dias, p.idio_por_dia, p.idio_dur_h, t_inicio):
                amp = rng.uniform(*p.idio_amp) * rng.choice((-1, 1))
                eps.append((t0, t0 + dur, _meia_senoide(t0, dur, amp)))
            idio[(m, i)] = _Ativos(eps)

    pacotes = []
    for j, m in enumerate(membros):
        fase = j * p.cadencia_s / len(membros)
        perdidos = 0
        t = t_inicio + fase
        fim = t_inicio + dias * 86400
        while t < fim:
            if perdidos > 0:
                perdidos -= 1
            elif p.perda > 0 and rng.random() < _p_inicio_rajada(p):
                perdidos = (4 if rng.random() < p.rajada_p4 else 2) - 1
            else:
                comum = (p.base + p.circ_amp * math.sin(2 * math.pi * (hora_local(t) - 12) / 24)
                         + p.kappa * (ambiente(t) - p.amb_media) + derivas[m].valor(t) + decub[m].valor(t))
                T = []
                for i in range(n):
                    v = comum + offsets[m][i] + idio[(m, i)].valor(t)
                    if p.ruido_sd:
                        v += rng.gauss(0, p.ruido_sd)
                    for inj in injecoes:
                        if inj.membro == m and i in inj.sensores:
                            v += inj.valor(t)
                    T.append(round(v, 2) if p.arredondar else v)
                if extras:
                    T = extras(m, t, T)
                pacotes.append({"vaca_id": vaca_id, "membro": m, "ts": t, "T": T})
            t += p.cadencia_s
    pacotes.sort(key=lambda x: (x["ts"], x["membro"]))
    return pacotes
