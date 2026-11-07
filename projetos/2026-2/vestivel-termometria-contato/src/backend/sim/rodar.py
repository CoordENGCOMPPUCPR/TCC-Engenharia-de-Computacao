"""Roda o detector sobre uma lista de pacotes, do mesmo jeito que o backend.

A linha de base é recalculada no primeiro pacote de cada hora local, a partir dos
ciclos já fechados, e só para aquela hora (as outras só são usadas no próprio horário).
Um evento reset_baseline apaga os ciclos e as células do membro, que volta a armar.

`Simulador.copia()` guarda um instantâneo para continuar depois com outra série;
é assim que se faz o controle pareado (mesma semente, com e sem injeção).
"""

import copy
from dataclasses import dataclass, field

from detector import Config, calcular_baseline, estado_inicial, fechar_vencidos, step
from detector.baseline import chave, hora_local


@dataclass
class Resultado:
    ciclos: list = field(default_factory=list)
    aberturas: list = field(default_factory=list)
    fechamentos: list = field(default_factory=list)
    resets: list = field(default_factory=list)
    atrasados: int = 0
    estado: dict = None
    baseline: dict = None
    baseline_agora: dict = field(default_factory=dict)  # hora local -> instante do último recálculo


class Simulador:
    def __init__(self, config=None, baseline_fixo=None, estado=None, guardar_ciclos=True):
        self.config = config or Config()
        self.estado = estado or estado_inicial()
        self.fixo = baseline_fixo is not None
        self.baseline = baseline_fixo if self.fixo else {}
        self.por_hora = {}
        self.hora_atual = None
        self.guardar_ciclos = guardar_ciclos
        self.res = Resultado()

    def copia(self):
        return copy.deepcopy(self)

    def _consumir(self, eventos):
        res = self.res
        for e in eventos:
            t = e["tipo"]
            if t == "ciclo":
                if self.guardar_ciclos:
                    res.ciclos.append(e)
                if not self.fixo:
                    self.por_hora.setdefault(e["hora_local"], []).append(e)
            elif t == "abertura":
                res.aberturas.append(e)
            elif t == "fechamento":
                res.fechamentos.append(e)
            elif t == "atrasado":
                res.atrasados += 1
            elif t == "reset_baseline":
                res.resets.append(e)
                if not self.fixo:
                    self._resetar(e["vaca_id"], e["membro"], e["ts"])

    def _resetar(self, vaca_id, membro, ts):
        for h, lista in self.por_hora.items():
            self.por_hora[h] = [c for c in lista
                                if not (c["vaca_id"] == vaca_id and c["membro"] == membro and c["ts"] < ts)]
        self.baseline.pop(chave(vaca_id, membro), None)

    def _recalcular(self, ts):
        cfg = self.config
        h = hora_local(ts, cfg.fuso)
        if h == self.hora_atual:
            return
        self.hora_atual = h
        lim = ts - cfg.baseline_dias * 86400
        lista = self.por_hora[h] = [c for c in self.por_hora.get(h, []) if c["ts"] >= lim]
        novo = calcular_baseline(lista, cfg, ts, horas={h})
        self.res.baseline_agora[h] = ts
        for kk in list(self.baseline):
            for s in self.baseline[kk]:
                self.baseline[kk][s].pop(str(h), None)
        for kk, sens in novo.items():
            for s, hs in sens.items():
                self.baseline.setdefault(kk, {}).setdefault(s, {}).update(hs)

    def alimentar(self, pacotes, interromper_em=None, ao_interromper=None):
        for k, pac in enumerate(pacotes):
            if interromper_em is not None and k == interromper_em:
                self.estado = ao_interromper(self.estado)
            if not self.fixo:
                self._recalcular(pac["ts"])
            self.estado, ev = step(self.estado, pac, self.config, self.baseline, copiar=False)
            self._consumir(ev)
        return self

    def fechar(self, fim):
        self.estado, ev = fechar_vencidos(self.estado, fim, self.config, self.baseline, copiar=False)
        self._consumir(ev)
        self.res.estado = self.estado
        self.res.baseline = self.baseline
        return self.res


def executar(pacotes, config=None, baseline_fixo=None, fim=None, estado=None, interromper_em=None,
             ao_interromper=None):
    """Roda o detector. Com `baseline_fixo`, usa sempre essa linha de base;
    senão, aprende a linha de base com os próprios ciclos.

    Se `interromper_em` for dado, no pacote com esse índice o estado passa por
    ao_interromper(estado) antes de continuar (serve para testar a serialização).
    """
    sim = Simulador(config, baseline_fixo, estado)
    sim.alimentar(pacotes, interromper_em, ao_interromper)
    if fim is not None:
        return sim.fechar(fim)
    sim.res.estado, sim.res.baseline = sim.estado, sim.baseline
    return sim.res


def baseline_constante(vaca_id, membros, valores, config=None, n=100, dias=14):
    """Linha de base já armada, com o mesmo valor em todas as horas.
    `valores`: {membro: [B1..B5]}."""
    return {
        chave(vaca_id, m): {str(i + 1): {str(h): {"b": valores[m][i], "n": n, "dias": dias} for h in range(24)}
                            for i in range(len(valores[m]))}
        for m in membros
    }
