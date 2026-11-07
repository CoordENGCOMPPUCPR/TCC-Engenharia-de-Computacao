"""Parâmetros do detector.

Os valores padrão são os escolhidos depois das varreduras no modelo sintético
(N = 24, λ_s = 1,5 °C, λ_b = λ_c = 2,0 °C, congelamento máximo de 168 h).
Ainda não foram validados em animais.
"""

from dataclasses import asdict, dataclass, fields
from typing import Optional


@dataclass(frozen=True)
class Config:
    # Tamanho do bin, alinhado ao relógio. 300 s divide a hora, então os bins
    # também ficam alinhados à hora local.
    ciclo_s: int = 300
    n_sensores: int = 5

    # Validade de cada sensor no bin
    t_min: float = 5.0           # °C
    t_max: float = 45.0          # °C
    frio_delta: float = 3.0      # abaixo de mediana - frio_delta = perda de contato
    filtro_frio: bool = True
    n_min_validos: int = 3       # menos que isso = FALHA_SENSOR

    # Linha de base (por membro, sensor e hora local)
    baseline_dias: int = 14
    arm_dias: int = 3            # dias distintos mínimos por célula
    arm_min_amostras: int = 10   # amostras mínimas por célula
    fuso: str = "America/Sao_Paulo"

    # Congelamento: o ciclo fica fora da linha de base quando dT_b > congela_frac * lambda_b
    # ou quando há alerta aberto. Com congela_frac = None, só o alerta congela.
    congela_frac: Optional[float] = 0.5
    congelamento: bool = True
    # Limite de congelamento contínuo (None = sem limite). Depois dele:
    #   "liberar": os ciclos voltam a entrar na linha de base;
    #   "reset":   além disso, a linha de base do membro é descartada.
    congela_max_h: Optional[float] = 168.0
    congela_max_modo: str = "liberar"

    # Limiares (°C) e persistência
    lambda_s: float = 1.5        # espacial
    lambda_b: float = 2.0        # temporal
    lambda_c: float = 2.0        # contralateral
    n_persist: int = 24          # bins seguidos acima do limiar (24 x 5 min = 2 h)
    g_ausentes: int = 3          # mais bins ausentes que isso zera o contador
    histerese: float = 0.7       # fecha após n_persist bins abaixo de histerese * lambda

    # Minutos sem pacote até o membro aparecer como SEM_DADOS
    sem_dados_min: float = 30.0

    def para_dict(self):
        return asdict(self)

    @classmethod
    def de_dict(cls, d):
        nomes = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in nomes})
