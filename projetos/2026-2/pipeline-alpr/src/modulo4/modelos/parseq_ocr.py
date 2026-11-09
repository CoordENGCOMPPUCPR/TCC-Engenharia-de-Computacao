# parseq_ocr — wrapper parseq tiny, treino e inferencia via pytorch lightning
# repositorio: https://github.com/baudm/parseq
# carregamento: torch.hub.load('baudm/parseq', 'parseq_tiny', pretrained=True)

import os

import cv2
import numpy as np
import torch
import pytorch_lightning as pl
from PIL import Image
from pytorch_lightning.callbacks import ModelCheckpoint
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms as T

DEFAULT_HP = {
    "lr": 1e-5,
    "batch_size": 64,
    "max_epochs": 10,
    "patience": 3,
    "num_workers": 2,
}


# DATASET ---------------------------------------------------------------------

class OCRDataset(Dataset):
    def __init__(self, images_dir: str, labels_file: str, transform, img_size: tuple):
        self.images_dir = images_dir
        self.transform = transform
        self.img_size = img_size
        self.data = []

        with open(labels_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",", 1)
                if len(parts) == 2:
                    self.data.append((parts[0], parts[1]))

        print(f"  {len(self.data)} amostras de {labels_file}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        img_name, text = self.data[idx]
        img_path = os.path.join(self.images_dir, img_name)

        try:
            image = Image.open(img_path).convert("RGB")
        except FileNotFoundError:
            image = Image.new("RGB", (self.img_size[1], self.img_size[0]), color="black")
            text = "ERROR"

        if self.transform:
            image = self.transform(image)

        return image, text


def _collate_fn(batch):
    images, texts = zip(*batch)
    return torch.stack(images, 0), texts


# INTERFACE PUBLICA -----------------------------------------------------------

def create_model(device: str):
    print("  Carregando PARSeq Tiny via torch.hub...")
    model = torch.hub.load("baudm/parseq", "parseq_tiny", pretrained=True)
    model = model.to(device)
    return model


def train(model, dataset_dir: str, hp: dict, checkpoint_dir: str, resume: bool = False) -> str:
    device = "cuda" if next(model.parameters()).is_cuda else "cpu"
    img_size = model.hparams.img_size

    transform = T.Compose([
        T.Resize(img_size, T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])

    train_set = OCRDataset(
        os.path.join(dataset_dir, "train"),
        os.path.join(dataset_dir, "train.txt"),
        transform, img_size,
    )
    val_set = OCRDataset(
        os.path.join(dataset_dir, "val"),
        os.path.join(dataset_dir, "val.txt"),
        transform, img_size,
    )

    train_loader = DataLoader(
        train_set, batch_size=hp["batch_size"], shuffle=True,
        num_workers=hp["num_workers"], collate_fn=_collate_fn,
    )
    val_loader = DataLoader(
        val_set, batch_size=hp["batch_size"], shuffle=False,
        num_workers=hp["num_workers"], collate_fn=_collate_fn,
    )

    model.hparams.lr = hp["lr"]
    model.train()

    os.makedirs(checkpoint_dir, exist_ok=True)

    ckpt_callback = ModelCheckpoint(
        dirpath=checkpoint_dir,
        filename="parseq-{epoch:02d}-{val_loss:.4f}",
        save_top_k=3,
        monitor="val_loss",
        mode="min",
        save_last=True,
    )

    trainer = pl.Trainer(
        max_epochs=hp["max_epochs"],
        accelerator=device,
        devices=1,
        log_every_n_steps=10,
        logger=False,
        callbacks=[
            pl.callbacks.EarlyStopping(
                monitor="val_loss", patience=hp["patience"], mode="min"
            ),
            ckpt_callback,
        ],
    )

    last_ckpt = os.path.join(checkpoint_dir, "last.ckpt")
    if os.path.exists(last_ckpt):
        print(f"  Retomando treino do checkpoint: {last_ckpt}")
        trainer.fit(model, train_loader, val_loader, ckpt_path=last_ckpt)
    else:
        trainer.fit(model, train_loader, val_loader)

    best_path = os.path.join(checkpoint_dir, "parseq_best.pt")
    torch.save(model.model.state_dict(), best_path)
    print(f"  Melhores pesos salvos em: {best_path}")

    return best_path


def load_weights(model, weights_path: str):
    device = "cuda" if next(model.parameters()).is_cuda else "cpu"
    state_dict = torch.load(weights_path, map_location=device)

    if any(k.startswith("model.") for k in model.state_dict()):
        if not any(k.startswith("model.") for k in state_dict):
            state_dict = {"model." + k: v for k, v in state_dict.items()}

    model.load_state_dict(state_dict, strict=False)
    model.eval()
    print(f"  Pesos carregados de: {weights_path}")


def predict(model, image: np.ndarray, device: str) -> tuple[str, list[float]]:
    img_size = model.hparams.img_size
    transform = T.Compose([
        T.Resize(img_size, T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])

    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    inp = transform(pil).unsqueeze(0).to(device)

    model.eval()
    with torch.no_grad():
        logits = model(inp)

    probs = logits.softmax(-1)
    preds, confidence = model.tokenizer.decode(probs)

    text = preds[0]
    scores = confidence[0].cpu().tolist()

    return text, scores
