# svtr_ocr — wrapper svtrv2 (repsvtr mobile), treino e inferencia via openocr
# repositorio: https://github.com/Topdu/OpenOCR
# arquitetura: RepSVTREncoder + CTCDecoder, entrada 48x320 px

import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

OPENOCR_ROOT = os.environ.get("OPENOCR_ROOT", "")

DEFAULT_HP = {
    "lr": 1e-5,
    "batch_size": 64,
    "max_epochs": 10,
    "patience": 3,
    "num_workers": 2,
}

_BASE_CONFIG = "configs/rec/svtrv2/repsvtr_ch.yml"

_IMG_SIZE = (48, 320)


def _check_openocr():
    if not OPENOCR_ROOT or not Path(OPENOCR_ROOT).exists():
        raise RuntimeError(
            f"OPENOCR_ROOT não configurado ou não existe: '{OPENOCR_ROOT}'. "
            "Clone o repositório OpenOCR ou defina a variável de ambiente OPENOCR_ROOT."
        )


def _ensure_openocr_in_path():
    _check_openocr()
    if OPENOCR_ROOT not in sys.path:
        sys.path.insert(0, OPENOCR_ROOT)


def _convert_labels(labels_file: str, output_file: str, images_dir: str):
    with open(labels_file, "r") as f_in, open(output_file, "w") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 1)
            if len(parts) == 2:
                img_name, text = parts
                f_out.write(f"{img_name}\t{text}\n")

    print(f"  Rótulos convertidos: {labels_file} → {output_file}")


def _build_config(dataset_dir: str, hp: dict, checkpoint_dir: str,
                  pretrained: str = "", resume_ckpt: str = "") -> dict:
    _check_openocr()

    base_config_path = Path(OPENOCR_ROOT) / _BASE_CONFIG
    with open(base_config_path, "r") as f:
        config = yaml.safe_load(f)

    config["Global"]["epoch_num"] = hp["max_epochs"]
    config["Global"]["save_model_dir"] = checkpoint_dir
    config["Global"]["output_dir"] = checkpoint_dir
    config["Global"]["pretrained_model"] = pretrained
    # resume: carrega modelo + optimizer + scheduler + época, retomando de onde parou
    config["Global"]["checkpoints"] = resume_ckpt if resume_ckpt else None
    config["Global"]["use_amp"] = False
    config["Global"]["distributed"] = False
    # Garante que checkpoints são salvos desde a primeira época
    config["Global"]["save_epoch_step"] = [0, 1]
    config["Global"]["eval_epoch_step"] = [0, 1]

    config["Optimizer"]["lr"] = hp["lr"]
    config["LRScheduler"]["warmup_epoch"] = 1

    train_label = os.path.join(dataset_dir, "train_openocr.txt")
    val_label = os.path.join(dataset_dir, "val_openocr.txt")

    config["Train"]["dataset"]["name"] = "SimpleDataSet"
    config["Train"]["dataset"]["data_dir"] = os.path.join(dataset_dir, "train")
    config["Train"]["dataset"]["label_file_list"] = [train_label]
    config["Train"]["loader"]["batch_size_per_card"] = hp["batch_size"]
    config["Train"]["loader"]["num_workers"] = hp["num_workers"]

    config["Eval"]["dataset"]["name"] = "SimpleDataSet"
    config["Eval"]["dataset"]["data_dir"] = os.path.join(dataset_dir, "val")
    config["Eval"]["dataset"]["label_file_list"] = [val_label]
    config["Eval"]["loader"]["num_workers"] = hp["num_workers"]


    resize_transform = {"RecTVResize": {"image_shape": [48, 320], "padding": False}}
    for split in ["Train", "Eval"]:
        transforms = config[split]["dataset"]["transforms"]
        for i, t in enumerate(transforms):
            if "DecodeImage" in t:
                transforms[i] = {"DecodeImagePIL": {"img_mode": "RGB"}}
            elif "RecTVResize" in t or "RecDynamicResize" in t:
                transforms[i] = resize_transform

    return config


def create_model(device: str):
    _ensure_openocr_in_path()

    from openrec.modeling import build_model
    from openrec.postprocess import build_post_process

    base_config_path = Path(OPENOCR_ROOT) / _BASE_CONFIG
    with open(base_config_path, "r") as f:
        config = yaml.safe_load(f)

    arch_config = config["Architecture"]

    post_config = config.get("PostProcess", {"name": "CTCLabelDecode"}).copy()
    dict_path = post_config.get("character_dict_path")
    if dict_path and not os.path.isabs(dict_path):
        post_config["character_dict_path"] = os.path.join(OPENOCR_ROOT, dict_path)
    if "use_space_char" not in post_config:
        post_config["use_space_char"] = config.get("Global", {}).get("use_space_char", False)
    post_processor = build_post_process(post_config)
    arch_config["Decoder"]["out_channels"] = post_processor.get_character_num()

    model = build_model(arch_config)
    model = model.to(device)
    model.eval()

    print("  SVTRv2 (RepSVTR mobile) carregado via OpenOCR (build_model)")

    return {
        "model": model,
        "config": config,
        "type": "svtr",
        "device": device,
        "img_size": _IMG_SIZE,
    }


def train(model, dataset_dir: str, hp: dict, checkpoint_dir: str, resume: bool = False) -> str:
    _check_openocr()

    if "model" in model:
        model["model"].cpu()
        del model["model"]
        torch.cuda.empty_cache()

    checkpoint_dir = os.path.abspath(checkpoint_dir)
    os.makedirs(checkpoint_dir, exist_ok=True)

    _convert_labels(
        os.path.join(dataset_dir, "train.txt"),
        os.path.join(dataset_dir, "train_openocr.txt"),
        os.path.join(dataset_dir, "train"),
    )
    _convert_labels(
        os.path.join(dataset_dir, "val.txt"),
        os.path.join(dataset_dir, "val_openocr.txt"),
        os.path.join(dataset_dir, "val"),
    )

    # usar openocr_repsvtr_ch.pth (mobile), NAO openocr_svtrv2_ch.pth (server)
    pretrained = ""
    candidates = [
        Path(OPENOCR_ROOT) / "openocr_repsvtr_ch.pth",
        Path.home() / ".cache" / "openocr" / "openocr_repsvtr_ch.pth",
    ]
    for p in candidates:
        if p.exists():
            pretrained = str(p)
            print(f"  SVTRv2 fine-tuning a partir de: {p}")
            break
    if not pretrained:
        print("  AVISO: pesos pré-treinados do SVTRv2 (RepSVTR) não encontrados. Treinando do zero.")

    resume_ckpt = ""
    if resume:
        latest = os.path.join(checkpoint_dir, "latest.pth")
        if os.path.exists(latest):
            resume_ckpt = latest
            print(f"  SVTRv2 retomando treino de: {latest}")
        else:
            print("  AVISO: --resume pedido mas latest.pth não encontrado. Treinando normalmente.")

    config = _build_config(dataset_dir, hp, checkpoint_dir, pretrained, resume_ckpt=resume_ckpt)

    config_path = os.path.abspath(os.path.join(checkpoint_dir, "svtr_train_config.yml"))
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    cmd = [
        sys.executable,
        os.path.join(OPENOCR_ROOT, "tools", "train_rec.py"),
        "--c", config_path,
    ]

    print(f"  Executando treino SVTRv2: {' '.join(cmd)}")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    result = subprocess.run(cmd, cwd=OPENOCR_ROOT, env=env)

    if result.returncode != 0:
        raise RuntimeError(f"Treino SVTRv2 falhou com código {result.returncode}")

    best_path = os.path.join(checkpoint_dir, "best.pth")
    if not os.path.exists(best_path):
        ckpts = sorted(Path(checkpoint_dir).glob("*.pth"))
        if ckpts:
            best_path = str(ckpts[-1])
        else:
            raise FileNotFoundError(f"Nenhum checkpoint encontrado em {checkpoint_dir}")

    print(f"  Melhores pesos SVTRv2 salvos em: {best_path}")
    return best_path


def load_weights(model, weights_path: str):
    device = model["device"]
    state_dict = torch.load(weights_path, map_location=device)

    if "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]

    model["model"].load_state_dict(state_dict, strict=False)
    model["model"].eval()
    print(f"  Pesos SVTRv2 carregados de: {weights_path}")


def predict(model, image: np.ndarray, device: str) -> tuple[str, list[float]]:
    _ensure_openocr_in_path()

    from openrec.postprocess import build_post_process
    from PIL import Image
    from torchvision import transforms as T

    net = model["model"]
    config = model["config"]
    img_h, img_w = _IMG_SIZE

    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    transform = T.Compose([
        T.Resize((img_h, img_w), T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])
    inp = transform(pil).unsqueeze(0).to(device)

    net.eval()
    with torch.no_grad():
        output = net(inp)

    if isinstance(output, (list, tuple)):
        output = output[0]

    post_config = config.get("PostProcess", {"name": "CTCLabelDecode"}).copy()
    dict_path = post_config.get("character_dict_path")
    if dict_path and not os.path.isabs(dict_path):
        post_config["character_dict_path"] = os.path.join(OPENOCR_ROOT, dict_path)
    if "use_space_char" not in post_config:
        post_config["use_space_char"] = config.get("Global", {}).get("use_space_char", False)
    post_processor = build_post_process(post_config)
    result = post_processor(output)

    if not result or not result[0]:
        return "", []

    text = result[0][0]
    score = result[0][1] if len(result[0]) > 1 else 0.0

    # score global replicado por posicao (compatibilidade com mvcp)
    scores = [score] * len(text)

    return text, scores
