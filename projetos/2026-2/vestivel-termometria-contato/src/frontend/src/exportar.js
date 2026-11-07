import { agruparEmLinhas } from './dados.js';
import { paraArquivo } from './formatar.js';

// Exportação CSV no formato que o Excel em português abre direto: separador ";",
// vírgula decimal e BOM UTF-8 (para os acentos e o "ΔT" saírem certos).
// Uma linha por pacote LoRa, em ordem cronológica. Membro e Estado ficam no fim
// para não mudar a posição das colunas antigas. Estado é o do ciclo do detector
// ("indisponível" se o ciclo ainda não fechou, por exemplo).

const fmtDataHora = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
});

function numero(v, casas) {
  return v === null || v === undefined ? '' : v.toFixed(casas).replace('.', ',');
}

function campo(v) {
  const s = String(v);
  return /[;"\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// RSSI/SNR do pacote: é o mesmo para todos os sensores, então usa o primeiro que houver.
function doPacote(leituras, chave) {
  const l = leituras.find((x) => x[chave] !== null);
  return l ? l[chave] : null;
}

export function gerarCsv(leituras, quartos, vacaId, janelaMs, estadoDoCiclo = () => null) {
  const cabecalho = [
    'Data/hora', 'Vaca',
    ...quartos.flatMap((q) => [`Sens ${q} temp. (°C)`, `Sens ${q} ΔT (°C)`]),
    'RSSI (dBm)', 'SNR (dB)', 'Membro', 'Estado',
  ];
  const linhas = agruparEmLinhas(leituras, janelaMs).reverse().map((linha) => {
    const doLinha = [...linha.porQuarto.values()];
    return [
      fmtDataHora.format(linha.ts).replace(',', ''),
      vacaId,
      ...quartos.flatMap((q) => {
        const l = linha.porQuarto.get(q);
        return [numero(l?.temp_raw, 2), numero(l?.delta_t, 2)];
      }),
      numero(doPacote(doLinha, 'rssi'), 0),
      numero(doPacote(doLinha, 'snr'), 2),
      linha.membro ?? '',
      estadoDoCiclo(linha.membro, linha.ts) ?? 'indisponível',
    ];
  });
  return '﻿' + [cabecalho, ...linhas].map((l) => l.map(campo).join(';')).join('\r\n') + '\r\n';
}

export function nomeArquivo(vacaId, de, ate) {
  const id = String(vacaId).replace(/[^\w-]+/g, '_');
  return `leituras_${id}_${paraArquivo(de)}_a_${paraArquivo(ate)}.csv`;
}

export function baixar(nome, conteudo) {
  const url = URL.createObjectURL(new Blob([conteudo], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
