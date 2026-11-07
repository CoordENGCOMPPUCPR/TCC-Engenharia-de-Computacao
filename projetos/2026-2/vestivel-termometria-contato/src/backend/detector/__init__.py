"""Detector de elevação térmica no membro pélvico.

Só usa a biblioteca padrão: não acessa banco, rede nem relógio do sistema.
"""

from .adaptador import linhas_para_pacotes
from .baseline import calcular_baseline, consultar, hora_local
from .config import Config
from .nucleo import (COMPONENTES, componentes, estado_atual, estado_inicial, fechar_vencidos,
                     step, validar)

__all__ = ["Config", "step", "fechar_vencidos", "estado_atual", "estado_inicial",
           "calcular_baseline", "consultar", "hora_local", "linhas_para_pacotes",
           "componentes", "validar", "COMPONENTES"]
