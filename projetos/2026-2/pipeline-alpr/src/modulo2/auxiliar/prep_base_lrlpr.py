#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
================================================================================
PREPARACAO DO LRLPR-26 PARA O CYCLEGAN-TURBO
================================================================================

Le a base bruta do LRLPR-26 e gera a arvore de pastas que o
train_cyclegan_turbo.py espera em --dataset_folder.

    dominio A = placas HR (nitidas)
    dominio B = placas LR (degradadas)

SEM RETIFICACAO: os cantos das anotacoes nao sao usados. A imagem inteira da
base (que ja e um recorte da placa) e redimensionada mantendo a proporcao e
centralizada em fundo cinza ate LARGURA x ALTURA. Assim funciona tambem para o
Scenario B, que nao tem cantos.

--------------------------------------------------------------------------------
AMBIENTE
--------------------------------------------------------------------------------

    conda create -n lrlpr-prep -c conda-forge python=3.11 numpy opencv pillow -y
    conda activate lrlpr-prep

Sao as unicas dependencias. Nada de torch aqui: este script so le JSON e
faz warp de imagem.

--------------------------------------------------------------------------------
COMO RODAR
--------------------------------------------------------------------------------

1) Primeiro so o relatorio (segundos, nao escreve imagem nenhuma):

    python -u prepara_lrlpr.py --relatorio

   Leia a saida antes de seguir. Ela responde: quantas placas colidem entre
   treino e validacao, quantas imagens estao sem cantos, e qual o tamanho real
   das placas na base.

2) Depois a geracao completa:

    nohup python -u prepara_lrlpr.py > prep.log 2>&1 &
    tail -f prep.log

   O -u e importante: sem ele o nohup segura a saida em buffer e voce fica sem
   ver o progresso.

--------------------------------------------------------------------------------
O QUE ESPERAR
--------------------------------------------------------------------------------

Tempo: poucos minutos em disco local. Se a base estiver em disco de rede,
pode passar de meia hora - o gargalo e abrir 20.000 arquivos JSON pequenos.

Espaco: aproximadamente 700 MB a 1 GB. Sao ~38.000 PNGs de 128x64.
PNG e proposital: JPEG adicionaria artefato de compressao no dominio A, que
justamente deveria estar limpo.

Saida:

    SAIDA/
      train_A/            ~19.000 placas HR
      train_B/            ~19.000 placas LR
      test_A/             10 placas HR   (so para inspecao visual no treino)
      test_B/             10 placas LR
      fixed_prompt_a.txt
      fixed_prompt_b.txt
      selecao.json        qual frame foi escolhido em cada track
      relatorio.txt       o mesmo relatorio impresso na tela

test_A e test_B NAO sao conjunto de teste. O script nunca treina com eles: sao
so as amostras que ele passa pelo gerador de tempos em tempos para voce olhar,
e a base do FID de referencia. Por isso sao poucos - cada imagem ali custa
inferencia repetida ao longo do treino.
================================================================================
"""

import json
import os
import random
import shutil
import sys
from collections import Counter, defaultdict

import cv2
import numpy as np
from PIL import Image

# ==============================================================================
# CONFIGURACAO - ajustar aqui para o servidor
# ==============================================================================

# ── Ajuste estes caminhos conforme sua configuracao ──
BASE = "/caminho/para/LRLPR-26/train"
SPLIT_JSON = "/caminho/para/split-train-val.json"
SAIDA = "/caminho/para/saida/lrlpr_unpaired"

LARGURA, ALTURA = 128, 64      # tamanho final das placas
COR_PADDING = (128, 128, 128)  # cinza do padding (BGR), igual ao benchmark do grupo
N_TEST = 10                    # imagens em test_A e test_B
SEED = 0                       # semente da amostragem, para ser reproduzivel

PROMPT_A = "sharp license plate"
PROMPT_B = "blurry low resolution license plate"

EXTENSOES = (".jpg", ".jpeg", ".png", ".bmp")
ORDEM_CANTOS = ["top-left", "top-right", "bottom-right", "bottom-left"]

# ==============================================================================

SOMENTE_RELATORIO = "--relatorio" in sys.argv
linhas_relatorio = []


def log(msg=""):
    """Imprime e guarda para o relatorio.txt."""
    print(msg, flush=True)
    linhas_relatorio.append(str(msg))


# ------------------------------------------------------------------------------
# Leitura
# ------------------------------------------------------------------------------

def carregar_split():
    """Retorna {track_rel: split}, onde split e 'train' ou 'val'.

    track_rel e o caminho relativo do JSON, ex: 'Scenario-A/Brazilian/track_00001'
    """
    with open(SPLIT_JSON) as f:
        dados = json.load(f)

    split_de = {}
    for cenario in dados:
        for split, tracks in dados[cenario].items():
            for t in tracks:
                split_de[t.rstrip("/")] = split
    return split_de


def ler_track(track_rel):
    """Le uma track e devolve seus dados, ou None se nao der para usar.

    Retorna dict com: placa, layout, cenario, e listas 'hr' e 'lr' de
    (caminho_da_imagem, cantos, area).
    """
    pasta = os.path.join(BASE, track_rel)
    caminho_json = os.path.join(pasta, "annotations.json")
    if not os.path.exists(caminho_json):
        return None

    with open(caminho_json) as f:
        ann = json.load(f)

    # As chaves de 'corners' podem ter extensao diferente da do arquivo real
    # (a anotacao diz .png e o arquivo e .jpg). Por isso casamos pelo nome sem
    # extensao, nunca pela chave inteira.
    arquivos = {}
    for nome in os.listdir(pasta):
        stem, ext = os.path.splitext(nome)
        if ext.lower() in EXTENSOES:
            arquivos[stem] = os.path.join(pasta, nome)

    # Sem retificar: os cantos NAO sao usados. Cada arquivo da track entra como
    # esta, com (largura, altura) e area da propria imagem. A area serve de
    # proxy de "proximidade da camera" para escolher a HR (ver escolher_imagens).
    imagens = {"hr": [], "lr": []}
    for stem, caminho in arquivos.items():
        try:
            with Image.open(caminho) as im:
                w, h = im.size
        except Exception:
            continue
        tipo = "hr" if stem.startswith("hr") else "lr"
        imagens[tipo].append((caminho, (w, h), w * h))

    return {
        "placa": ann.get("plate_text", "").strip().upper(),
        "layout": ann.get("plate_layout", "?"),
        "cenario": track_rel.split("/")[0],
        "hr": imagens["hr"],
        "lr": imagens["lr"],
        "n_imagens": len(arquivos),
    }


def montar_cantos(cantos_dict):
    """Monta o array 4x2 na ordem que o warp espera.

    A ordem importa: precisa casar com dst_pts em crop_and_warp. Por isso
    montamos explicitamente pelos nomes, sem confiar na ordem do JSON.
    """
    try:
        pts = [cantos_dict[nome] for nome in ORDEM_CANTOS]
    except KeyError:
        return None
    return np.array(pts, dtype=np.float32)


def area_quadrilatero(pts):
    """Area pela formula do shoelace. Usada para achar o frame mais proximo."""
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def ajustar_com_padding(caminho):
    """Mantem a proporcao da imagem e completa com cinza ate LARGURA x ALTURA.

    Nao recorta, nao retifica, nao distorce: a imagem inteira da base e
    redimensionada para caber na tela e centralizada sobre fundo cinza.
    """
    img = cv2.imread(caminho)
    if img is None:
        return None
    h, w = img.shape[:2]
    escala = min(LARGURA / w, ALTURA / h)
    nw = max(1, round(w * escala))
    nh = max(1, round(h * escala))
    interp = cv2.INTER_CUBIC if escala > 1 else cv2.INTER_AREA
    redim = cv2.resize(img, (nw, nh), interpolation=interp)

    tela = np.full((ALTURA, LARGURA, 3), COR_PADDING, dtype=np.uint8)
    x0 = (LARGURA - nw) // 2
    y0 = (ALTURA - nh) // 2
    tela[y0:y0 + nh, x0:x0 + nw] = redim
    return tela


# ------------------------------------------------------------------------------
# Relatorio
# ------------------------------------------------------------------------------

def relatorio(tracks, split_de):
    """Imprime os numeros que decidem o que entra no treino.

    Retorna o conjunto de tracks de treino que devem ser descartadas por
    colidirem com a validacao.
    """
    log("=" * 78)
    log("RELATORIO")
    log("=" * 78)

    # --- contagem geral ---
    por_grupo = Counter()
    for rel, t in tracks.items():
        por_grupo[(t["cenario"], split_de[rel])] += 1

    log("\nTracks lidas:")
    for (cenario, split), n in sorted(por_grupo.items()):
        log(f"  {cenario} / {split:5s} : {n:6d}")

    # --- imagens sem cantos ---
    log("\nImagens utilizaveis (sem usar cantos):")
    for cenario in sorted({t["cenario"] for t in tracks.values()}):
        do_cenario = [t for t in tracks.values() if t["cenario"] == cenario]
        total = sum(t["n_imagens"] for t in do_cenario)
        validas = sum(len(t["hr"]) + len(t["lr"]) for t in do_cenario)
        sem_hr = sum(1 for t in do_cenario if not t["hr"])
        sem_lr = sum(1 for t in do_cenario if not t["lr"])
        pct = 100 * (total - validas) / total if total else 0
        log(f"  {cenario}: {total - validas:6d} de {total:6d} imagens ilegiveis ({pct:.1f}%)")
        log(f"    tracks sem nenhuma HR: {sem_hr}")
        log(f"    tracks sem nenhuma LR: {sem_lr}")

    # --- tamanho real das imagens ---
    log("\nTamanho das imagens da base (arquivo inteiro, ja recortado pela base):")
    for tipo in ("hr", "lr"):
        larguras, alturas = [], []
        for t in tracks.values():
            for _, (w_, h_), _ in t[tipo]:
                larguras.append(w_)
                alturas.append(h_)
        if not larguras:
            continue
        w, h = np.array(larguras), np.array(alturas)
        log(f"  {tipo.upper()}: largura mediana {np.median(w):5.1f} px "
            f"(p5 {np.percentile(w, 5):.0f} / p95 {np.percentile(w, 95):.0f})  |  "
            f"altura mediana {np.median(h):4.1f} px")
    log(f"\n  Saida configurada: {LARGURA}x{ALTURA}. Compare com as medianas acima:")
    log("  se a mediana HR for bem menor que a largura de saida, o resize esta")
    log("  fazendo upsample - o que e aceitavel, mas nao cria informacao nova.")
    log(f"  A saida tem proporcao {LARGURA / ALTURA:.1f}:1. Imagens com proporcao diferente")
    log("  recebem faixas cinza (em cima/baixo ou nas laterais), sem distorcer.")

    # --- colisao de placa ---
    tracks_da_placa = defaultdict(list)
    for rel, t in tracks.items():
        if t["placa"]:
            tracks_da_placa[t["placa"]].append(rel)

    repetidas = {p: v for p, v in tracks_da_placa.items() if len(v) > 1}
    placas_val = {t["placa"] for rel, t in tracks.items() if split_de[rel] == "val"}

    descartar = set()
    for placa in placas_val:
        for rel in tracks_da_placa.get(placa, []):
            if split_de[rel] == "train":
                descartar.add(rel)

    log("\nColisao de placa (mesmo plate_text em mais de uma track):")
    log(f"  placas unicas             : {len(tracks_da_placa)}")
    log(f"  placas em varias tracks   : {len(repetidas)}")
    log(f"  tracks de treino que compartilham placa com a validacao: {len(descartar)}")
    if descartar:
        log("  -> essas tracks serao removidas do treino, e a validacao fica intacta.")
        exemplos = sorted(descartar)[:5]
        for e in exemplos:
            log(f"     {e}  (placa {tracks[e]['placa']})")
    else:
        log("  -> nenhuma. treino e validacao nao compartilham placa.")

    return descartar


# ------------------------------------------------------------------------------
# Selecao e escrita
# ------------------------------------------------------------------------------

def escolher_imagens(track, rng):
    """Escolhe uma HR e uma LR da track.

    HR: a de maior area, ou seja o frame mais proximo da camera, que e o mais
        nitido - e a melhor referencia de dominio limpo.
    LR: sorteio aleatorio, para o dominio B representar a distribuicao real de
        degradacao em vez de so o pior caso.
    """
    hr = max(track["hr"], key=lambda x: x[2]) if track["hr"] else None
    lr = rng.choice(track["lr"]) if track["lr"] else None
    return hr, lr


def salvar(track_rel, escolha, pasta_destino, sufixo):
    """Faz o warp e grava. Retorna o nome do arquivo, ou None se falhou."""
    caminho, _, _ = escolha
    img = ajustar_com_padding(caminho)
    if img is None:
        return None
    cenario = track_rel.split("/")[0].replace("Scenario-", "")
    track_id = track_rel.split("/")[-1]
    frame = os.path.splitext(os.path.basename(caminho))[0]
    nome = f"{cenario}_{track_id}_{frame}.png"
    cv2.imwrite(os.path.join(pasta_destino, nome), img)
    return nome


def gerar(tracks, split_de, descartar):
    """Monta a arvore de pastas final."""
    rng = random.Random(SEED)

    for sub in ("train_A", "train_B", "test_A", "test_B"):
        caminho = os.path.join(SAIDA, sub)
        if os.path.exists(caminho):
            shutil.rmtree(caminho)
        os.makedirs(caminho)

    treino = sorted(rel for rel in tracks
                    if split_de[rel] == "train" and rel not in descartar)
    val = sorted(rel for rel in tracks if split_de[rel] == "val")

    # --- test_A / test_B: as mesmas tracks nos dois, para voce comparar a
    # mesma placa limpa e degradada lado a lado. Metade de cada layout.
    candidatas = [rel for rel in val if tracks[rel]["hr"] and tracks[rel]["lr"]]
    por_layout = defaultdict(list)
    for rel in candidatas:
        por_layout[tracks[rel]["layout"]].append(rel)

    selecionadas = []
    por_camada = max(1, N_TEST // max(1, len(por_layout)))
    for layout in sorted(por_layout):
        rng.shuffle(por_layout[layout])
        selecionadas += por_layout[layout][:por_camada]

    # se um layout tiver poucas candidatas, completa com o que sobrou
    if len(selecionadas) < N_TEST:
        resto = [r for r in candidatas if r not in selecionadas]
        rng.shuffle(resto)
        selecionadas += resto[:N_TEST - len(selecionadas)]

    selecionadas = selecionadas[:N_TEST]
    selecionadas_set = set(selecionadas)

    # --- escrita ---
    selecao = {}
    contagem = Counter()

    grupos = [("test", selecionadas), ("train", treino)]
    for nome_grupo, lista in grupos:
        log(f"\nGerando {nome_grupo}: {len(lista)} tracks")
        for i, rel in enumerate(lista, 1):
            if nome_grupo == "train" and rel in selecionadas_set:
                continue  # nunca acontece (val nao esta em treino), mas fica explicito
            hr, lr = escolher_imagens(tracks[rel], rng)
            registro = {}
            if hr:
                destino = f"{nome_grupo}_A"
                nome = salvar(rel, hr, os.path.join(SAIDA, destino), "hr")
                if nome:
                    registro["A"] = nome
                    contagem[destino] += 1
            if lr:
                destino = f"{nome_grupo}_B"
                nome = salvar(rel, lr, os.path.join(SAIDA, destino), "lr")
                if nome:
                    registro["B"] = nome
                    contagem[destino] += 1
            if registro:
                registro["placa"] = tracks[rel]["placa"]
                selecao[rel] = registro
            if i % 2000 == 0:
                log(f"  {i}/{len(lista)}")

    # --- prompts ---
    with open(os.path.join(SAIDA, "fixed_prompt_a.txt"), "w") as f:
        f.write(PROMPT_A)
    with open(os.path.join(SAIDA, "fixed_prompt_b.txt"), "w") as f:
        f.write(PROMPT_B)

    with open(os.path.join(SAIDA, "selecao.json"), "w") as f:
        json.dump(selecao, f, indent=1)

    log("\n" + "=" * 78)
    log("RESULTADO")
    log("=" * 78)
    for sub in ("train_A", "train_B", "test_A", "test_B"):
        n = len(os.listdir(os.path.join(SAIDA, sub)))
        log(f"  {sub:9s}: {n:6d} imagens")
    log(f"\n  prompt A: {PROMPT_A!r}")
    log(f"  prompt B: {PROMPT_B!r}")
    log(f"\n  Use no treino:  --dataset_folder {SAIDA}")
    log("  Como as imagens ja saem em 128x64, use --train_img_prep no_resize")
    log("  e --val_img_prep no_resize.")


# ------------------------------------------------------------------------------

def main():
    if not os.path.isdir(BASE):
        sys.exit(f"BASE nao encontrada: {BASE}")
    if not os.path.exists(SPLIT_JSON):
        sys.exit(f"SPLIT_JSON nao encontrado: {SPLIT_JSON}")

    split_de = carregar_split()
    log(f"Split carregado: {len(split_de)} tracks listadas.")
    log("Lendo anotacoes...")

    tracks = {}
    for i, rel in enumerate(sorted(split_de), 1):
        t = ler_track(rel)
        if t:
            tracks[rel] = t
        if i % 5000 == 0:
            log(f"  {i}/{len(split_de)}")
    log(f"Tracks validas: {len(tracks)}")

    descartar = relatorio(tracks, split_de)

    if SOMENTE_RELATORIO:
        log("\n--relatorio: nenhuma imagem foi gerada.")
    else:
        os.makedirs(SAIDA, exist_ok=True)
        gerar(tracks, split_de, descartar)

    os.makedirs(SAIDA, exist_ok=True)
    with open(os.path.join(SAIDA, "relatorio.txt"), "w") as f:
        f.write("\n".join(linhas_relatorio))


if __name__ == "__main__":
    main()