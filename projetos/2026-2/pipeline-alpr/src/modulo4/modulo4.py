# modulo 4 — treino e avaliacao do comite de modelos OCR
#
# uso:
#   python3 modulo4.py --dataset ../dataset_hibrido --test_dir ../LRLPR-26/test --modelos parseq
#
# somente avaliacao:
#   python3 modulo4.py --so_avaliar --pesos parseq:caminho/pesos.pt \
#       --test_dir ../LRLPR-26/test --modelos parseq

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metricas import calcular_metricas
from mvcp import mvcp



# REGISTRO DE MODELOS -------------------------------------------------------

def _load_model_module(model_name: str):
    module_map = {
        "parseq": "modelos.parseq_ocr",
        "svtr": "modelos.svtr_ocr",
        "igtr": "modelos.igtr_ocr",
    }
    if model_name not in module_map:
        raise ValueError(f"Modelo '{model_name}' não reconhecido. Disponíveis: {list(module_map.keys())}")
    return importlib.import_module(module_map[model_name])



# LEITURA DO DATASET DE TESTE ----------------------------------------------

def load_test_tracks(test_dir: str) -> list[dict]:
    test_path = Path(test_dir)
    tracks = []

    track_dirs = sorted([d for d in test_path.iterdir() if d.is_dir()])

    for track_dir in track_dirs:
        track_id = track_dir.name
        ann_file = track_dir / "annotations.json"

        if not ann_file.exists():
            print(f"  AVISO: {ann_file} nao encontrado, pulando track {track_id}")
            continue

        with ann_file.open() as f:
            ann = json.load(f)
        gt = ann["plate_text"]
        category = ann.get("plate_layout", "unknown")

        frames = sorted([
            str(f) for f in track_dir.iterdir()
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
        ])

        if not frames:
            print(f"  AVISO: track {track_id} sem frames, pulando")
            continue

        tracks.append({
            "track_id": track_id,
            "gt": gt,
            "category": category,
            "frames": frames,
        })

    print(f"  {len(tracks)} tracks carregados de {test_dir}")
    return tracks



# TREINO --------------------------------------------------------------------

def train_models(model_names, dataset_dir, checkpoint_dir, device, hp,
                 resume=False):
    weights = {}

    for name in model_names:
        print(f"\n{'='*60}")
        print(f"  Treinando modelo: {name}")
        print(f"{'='*60}")

        mod = _load_model_module(name)
        model = mod.create_model(device)

        model_ckpt = os.path.join(checkpoint_dir, name)
        best_path = mod.train(model, dataset_dir, hp, model_ckpt, resume=resume)
        weights[name] = best_path

        print(f"  {name} concluido. pesos: {best_path}")

    return weights



# AVALIACAO -----------------------------------------------------------------

def evaluate(model_names, weights, tracks, device):
    models = {}
    for name in model_names:
        mod = _load_model_module(name)
        model = mod.create_model(device)
        if name in weights:
            mod.load_weights(model, weights[name])
        if hasattr(model, "eval"):
            model.eval()
        models[name] = (mod, model)

    resultados = []
    total = len(tracks)

    for i, track in enumerate(tracks):
        track_id = track["track_id"]
        gt = track["gt"]
        category = track["category"]

        all_predictions = []
        per_model_predictions = {name: [] for name in models}

        for name, (mod, model) in models.items():
            for frame_path in track["frames"]:
                image = cv2.imread(frame_path)
                if image is None:
                    print(f"  AVISO: nao conseguiu ler {frame_path}")
                    continue

                text, scores = mod.predict(model, image, device)
                all_predictions.append((text, scores))
                per_model_predictions[name].append((text, scores))

        pred = mvcp(all_predictions)

        # mvcp por modelo individual
        pred_por_modelo = {}
        for name, preds in per_model_predictions.items():
            pred_por_modelo[name] = mvcp(preds) if preds else ""

        resultados.append({
            "track_id": track_id,
            "pred": pred,
            "pred_por_modelo": pred_por_modelo,
            "gt": gt,
            "category": category,
            "n_frames": len(track["frames"]),
            "n_predictions": len(all_predictions),
        })

        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"  Avaliados {i + 1}/{total} tracks...")

    return resultados


# RELATORIO -------------------------------------------------------------------

def save_report(resultados: list[dict], metricas: dict, output_path: str, args):
    with open(output_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("  Módulo IV — Relatório de Avaliação OCR\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Modelos: {', '.join(args.modelos)}\n")
        f.write(f"Dataset treino: {args.dataset}\n")
        f.write(f"Dataset teste: {args.test_dir}\n")
        f.write(f"Somente avaliação: {args.so_avaliar}\n\n")

        f.write("-" * 40 + "\n")
        f.write("  Métricas Globais\n")
        f.write("-" * 40 + "\n")
        f.write(f"CER:                   {metricas['cer']:.4f} ({metricas['cer']*100:.2f}%)\n")
        f.write(f"Taxa de Reconhecimento: {metricas['taxa_reconhecimento']:.4f} ({metricas['taxa_reconhecimento']*100:.2f}%)\n")
        f.write(f"Placas corretas:       {metricas['placas_corretas']}/{metricas['total_placas']}\n")
        f.write(f"Total de erros:        {metricas['total_erros']}\n")
        f.write(f"Total de caracteres:   {metricas['total_caracteres']}\n\n")

        if metricas["por_categoria"]:
            f.write("-" * 40 + "\n")
            f.write("  Métricas por Categoria\n")
            f.write("-" * 40 + "\n")
            for cat, m in metricas["por_categoria"].items():
                f.write(f"\n  {cat}:\n")
                f.write(f"    CER:                   {m['cer']:.4f} ({m['cer']*100:.2f}%)\n")
                f.write(f"    Taxa de Reconhecimento: {m['taxa_reconhecimento']:.4f} ({m['taxa_reconhecimento']*100:.2f}%)\n")
                f.write(f"    Corretas/Total:        {m['corretas']}/{m['total']}\n")

        f.write("\n" + "-" * 40 + "\n")
        f.write("  Detalhes por Track\n")
        f.write("-" * 40 + "\n\n")

        erros = [r for r in resultados if r["pred"] != r["gt"]]
        acertos = [r for r in resultados if r["pred"] == r["gt"]]

        f.write(f"Tracks com erro ({len(erros)}):\n")
        for r in erros:
            f.write(f"  {r['track_id']}: pred='{r['pred']}' gt='{r['gt']}' cat={r['category']}\n")

        f.write(f"\nTracks corretos ({len(acertos)}):\n")
        for r in acertos:
            f.write(f"  {r['track_id']}: '{r['gt']}' cat={r['category']}\n")

    print(f"\n  Relatório salvo em: {output_path}")


# MAIN ------------------------------------------------------------------------

def parse_weights_arg(weights_str: str) -> dict[str, str]:
    weights = {}
    for item in weights_str.split(","):
        item = item.strip()
        if ":" not in item:
            raise ValueError(f"Formato inválido em --pesos: '{item}'. Use 'modelo:caminho'.")
        name, path = item.split(":", 1)
        weights[name.strip()] = path.strip()
    return weights


def main():
    parser = argparse.ArgumentParser(description="modulo IV — treino e avaliacao do comite OCR")

    parser.add_argument("--dataset", type=str, default=None,
                        help="Caminho para dataset_hibrido/ (train/, val/, train.txt, val.txt). "
                             "Obrigatório se não usar --so_avaliar.")
    parser.add_argument("--test_dir", type=str, required=True,
                        help="Caminho para diretório de teste organizado por tracks.")
    parser.add_argument("--modelos", nargs="+", default=["parseq"],
                        help="Modelos OCR a treinar/avaliar (default: parseq).")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints",
                        help="Diretório para salvar checkpoints (default: checkpoints).")
    parser.add_argument("--so_avaliar", action="store_true",
                        help="Pula treino, apenas avalia com pesos pré-treinados.")
    parser.add_argument("--pesos", type=str, default=None,
                        help="Pesos pré-treinados no formato 'modelo:caminho,modelo2:caminho2'. "
                             "Obrigatório com --so_avaliar.")
    parser.add_argument("--output", type=str, default="modulo4_report.txt",
                        help="Caminho do relatório de saída (default: modulo4_report.txt).")

    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--max_epochs", type=int, default=10)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--resume", action="store_true",
                        help="Retoma treino do último checkpoint salvo (SVTRv2/IGTR: latest.pth, "
                             "PARSeq: last.ckpt). Útil quando o job anterior foi interrompido.")

    args = parser.parse_args()

    if args.so_avaliar and args.pesos is None:
        parser.error("--so_avaliar requer --pesos com os caminhos dos pesos pré-treinados.")
    if not args.so_avaliar and args.dataset is None:
        parser.error("--dataset é obrigatório quando não usar --so_avaliar.")

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    hp = {
        "lr": args.lr,
        "batch_size": args.batch_size,
        "max_epochs": args.max_epochs,
        "patience": args.patience,
        "num_workers": args.num_workers,
    }

    start_time = time.time()

    if args.so_avaliar:
        print("\n  Modo: somente avaliação")
        weights = parse_weights_arg(args.pesos)
        for name in args.modelos:
            if name not in weights:
                print(f"  ERRO: modelo '{name}' listado em --modelos mas sem pesos em --pesos.")
                sys.exit(1)
    else:
        print("\n  Modo: treino + avaliação")
        weights = train_models(args.modelos, args.dataset, args.checkpoint_dir, device, hp,
                               resume=args.resume)

    print(f"\n{'='*60}")
    print("  Avaliação no conjunto de teste")
    print(f"{'='*60}")

    tracks = load_test_tracks(args.test_dir)
    if not tracks:
        print("  ERRO: nenhum track encontrado no diretório de teste.")
        sys.exit(1)

    resultados = evaluate(args.modelos, weights, tracks, device)

    metricas = calcular_metricas(resultados)

    metricas_por_modelo = {}
    for name in args.modelos:
        resultados_modelo = [
            {"pred": r["pred_por_modelo"].get(name, ""), "gt": r["gt"], "category": r["category"]}
            for r in resultados
        ]
        metricas_por_modelo[name] = calcular_metricas(resultados_modelo)

    elapsed = time.time() - start_time
    print(f"\n  Tempo total: {elapsed:.1f}s")
    for name in args.modelos:
        m = metricas_por_modelo[name]
        print(f"  {name}: CER={m['cer']*100:.2f}%  Taxa={m['taxa_reconhecimento']*100:.2f}%  "
              f"({m['placas_corretas']}/{m['total_placas']})")
    print(f"  MVCP:   CER={metricas['cer']*100:.2f}%  Taxa={metricas['taxa_reconhecimento']*100:.2f}%  "
          f"({metricas['placas_corretas']}/{metricas['total_placas']})")

    save_report(resultados, metricas, args.output, args)

    json_path = args.output.replace(".txt", ".json")
    with open(json_path, "w") as f:
        json.dump({
            "metricas": metricas,
            "metricas_por_modelo": metricas_por_modelo,
            "resultados": resultados,
            "config": {
                "modelos": args.modelos,
                "dataset": args.dataset,
                "test_dir": args.test_dir,
                "so_avaliar": args.so_avaliar,
                "hp": hp,
                "device": device,
                "elapsed_seconds": elapsed,
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"  JSON salvo em: {json_path}")


if __name__ == "__main__":
    main()
