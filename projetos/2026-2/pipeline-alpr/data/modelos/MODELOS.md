# Modelos

Os pesos dos modelos nao sao distribuidos neste repositorio. Este documento reune os parametros necessarios para treinar de novo cada modelo usado no trabalho, com os links dos codigos originais. Os datasets estao descritos em [DATASETS.md](../datasets/DATASETS.md).

---

## Modulo I — Deteccao de placas e cantos (YOLO26)

Fine-tuning com a API da Ultralytics (versoes 8.4.103 e 8.4.104) a partir dos pesos pre-treinados indicados. O modelo adotado para os cantos e o YOLO26s-Pose.

| Modelo | Peso inicial | Tarefa | Dados | Epocas | Patience | imgsz | Batch |
|--------|--------------|--------|-------|--------|----------|-------|-------|
| YOLO26n | `yolo26n.pt` | placa (1 classe) | UFPR-VeSV | 15 | 3 | 640 | padrao (16) |
| YOLO26n-Pose | `yolo26n-pose.pt` | 4 cantos | UFPR-VeSV | 15 | 3 | 640 | 16 |
| YOLO26n-Pose | `yolo26n-pose.pt` | 4 cantos | UFPR-VeSV + LRLPR-26 (Cenario A) | 30 | 5 | 640 | 16 |
| YOLO26s-Pose | `yolo26s-pose.pt` | 4 cantos | UFPR-VeSV + LRLPR-26 (Cenario A) | 30 | 5 | 640 | 16 |
| YOLO26m-Pose | `yolo26m-pose.pt` | 4 cantos | UFPR-VeSV + LRLPR-26 (Cenario A) | 30 | 5 | 640 | 16 |

- **UFPR-VeSV:** split 0 (treino / validacao / teste = 14.845 / 5.025 / 5.075). A anotacao original (4 cantos) e convertida para o formato YOLO.
- **Dataset combinado:** UFPR-VeSV (split 0) + LRLPR-26 Cenario A, com split por track (70/15/15, seed 42). Treino / validacao / teste = 84.845 / 20.025 / 20.075 imagens.
- **Formato de pose:** `class x_c y_c w h kp1_x kp1_y kp1_vis ... kp4_vis`, com `kpt_shape: [4, 3]`, keypoints na ordem TL, TR, BR, BL e visibilidade 2.
- **Parada antecipada:** os treinos de 30 epocas pararam na epoca 15 (nano) e na 22 (small); o medium completou as 30.

---

## Modulo II — Geradores de degradacao

O codigo desta entrega (`src/modulo2/`) usa o CycleGAN-Turbo e a degradacao parametrica. TSIT, DMT e ADM entram apenas na comparacao feita no TCC. Todos os treinos foram feitos em uma GPU NVIDIA RTX 4090.

### CycleGAN-Turbo

Codigo: https://github.com/GaParmar/img2img-turbo (`src/train_cyclegan_turbo.py`). Modelo base: `stabilityai/sd-turbo`. Treino nao pareado: dominio A = placas HR, dominio B = placas LR (~19.000 imagens por dominio, 128x64).

Versoes validadas: `transformers==4.35.2`, `diffusers==0.25.1`, `peft==0.10.0`, `huggingface_hub==0.25.2`.

Estrutura exigida por `--dataset_folder`:

```
train_A/*.png   train_B/*.png
test_A/*.png    test_B/*.png          # 8-16 imagens de placas fora do treino
fixed_prompt_a.txt    # "sharp license plate"
fixed_prompt_b.txt    # "blurry low resolution license plate"
```

Parametros da rodada final (imagens nao retificadas):

| Parametro | Valor |
|-----------|-------|
| Passos | `max_train_steps` 25.001 |
| Batch | 6, `gradient_accumulation_steps` 1 |
| Learning rate | 1e-5 |
| `lambda_gan` / `lambda_idt` / `lambda_cycle` | 0,5 / 1 / 1 |
| `lora_rank_unet` | 32 |
| Precisao | bf16, `allow_tf32` |
| `train_img_prep` / `val_img_prep` | `no_resize` |
| `dataloader_num_workers` | 8 |
| Validacao / visualizacao / checkpoint | a cada 2000 / 1000 / 1000 passos |
| Logs | `wandb` (offline) |

A geracao usa o ultimo checkpoint salvo.

### TSIT

Codigo: repositorio do DMT (https://github.com/THU-LYJ-Lab/dmt), que embute o TSIT; original em https://github.com/EndlessSora/TSIT. Ambiente: Python 3.8, CUDA 11.1. O TSIT pede a pasta `sync_batchnorm` (https://github.com/vacancy/Synchronized-BatchNorm-PyTorch) copiada para `models/networks/`.

Formato dos dados (`dataset_mode aligned`): uma imagem por par, com A (HR) e B (LR) lado a lado, em `train/` e `test/`. As imagens sao levadas a **256x256** com padding cinza (128,128,128), porque o TSIT exige entrada maior que 128 px.

Treino com `train.py`:

| Parametro | Valor |
|-----------|-------|
| Batch | 8 e 16 (um treino com cada) |
| Epocas | `niter` 100 + `niter_decay` 100 |
| `load_size` / `crop_size` / `aspect_ratio` | 256 / 256 / 1.0 |
| `preprocess_mode` | `scale_width_and_crop`, com `no_flip` |

### DMT

Mesmo repositorio, dados e parametros do TSIT, treinado com `train_dmt.py` (sem discriminador, perda L2 sobre versoes ruidosas). Acrescenta:

| Parametro | Valor |
|-----------|-------|
| Batch | 8 e 16 (um treino com cada) |
| `timestep_s` / `timestep_t` | 50 / 50 |

A geracao usa o ADM ajustado (proxima secao).

### ADM

Codigo de treino: https://github.com/openai/guided-diffusion (`scripts/image_train.py`), em ambiente separado (Python 3.8, `torch==1.9.1+cu111`, `torchvision==0.10.1+cu111`).

Checkpoint de origem (modelo 256x256 nao condicional da OpenAI, ~2,1 GB): https://openaipublic.blob.core.windows.net/diffusion/jul-2021/256x256_diffusion_uncond.pt, passado em `--resume_checkpoint`.

Dados: uma pasta plana com as imagens de baixa resolucao do dominio-alvo, em 256x256, sem subpastas nem pareamento.

| Parametro | Valor |
|-----------|-------|
| Passos | 10.000 |
| Learning rate / batch | 1e-5 / 4 |
| Media movel exponencial (EMA) | 0,9999 (checkpoint final `ema_0.9999_010000.pt`) |
| Flags do modelo | `image_size 256`, `num_channels 256`, `num_res_blocks 2`, `num_head_channels 64`, `attention_resolutions 32,16,8`, `diffusion_steps 1000`, `noise_schedule linear`, `class_cond False`, `learn_sigma True`, `resblock_updown True`, `use_scale_shift_norm True`, `use_fp16 True` |

`learn_sigma True` e obrigatorio: e como a OpenAI treinou o checkpoint de origem; sem ele o carregamento falha.

---

## Modulo IV — Reconhecedores de OCR

Modelos de reconhecimento de caracteres avaliados no trabalho. O treinamento e a inferencia sao gerenciados pelo script `src/modulo4/modulo4.py`, com hiperparametros carregados automaticamente pelas configuracoes de cada modelo.

| Modelo | Framework / Repo | Peso inicial |
|--------|------------------|--------------|
| PARSeq (tiny) | PyTorch Lightning / [baudm/parseq](https://github.com/baudm/parseq) | `torch.hub` (automatico) |
| SVTRv2 (mobile) | OpenOCR / [Topdu/OpenOCR](https://github.com/Topdu/OpenOCR) | [`openocr_repsvtr_ch.pth`](https://github.com/Topdu/OpenOCR/releases/download/develop0.0.1/openocr_repsvtr_ch.pth) |
| IGTR | OpenOCR / [Topdu/OpenOCR](https://github.com/Topdu/OpenOCR) | [`igtr_synth_best.pth`](https://drive.google.com/file/d/1cfCJ-vuOx9ZoyEgGP2QtRqKMMBYTGq6Y) (gdown: `1cfCJ-vuOx9ZoyEgGP2QtRqKMMBYTGq6Y`) |

### Obtencao dos pesos pre-treinados do OpenOCR

Para treinar ou avaliar o **SVTRv2** ou o **IGTR**, clone o OpenOCR em `src/modulo4/OpenOCR` e baixe os pesos base:

1. **SVTRv2 (`openocr_repsvtr_ch.pth`):**
   ```bash
   wget -q -O src/modulo4/OpenOCR/openocr_repsvtr_ch.pth \
       https://github.com/Topdu/OpenOCR/releases/download/develop0.0.1/openocr_repsvtr_ch.pth
   ```

2. **IGTR (`igtr_synth_best.pth`):**
   ```bash
   pip install gdown
   gdown "1cfCJ-vuOx9ZoyEgGP2QtRqKMMBYTGq6Y" -O src/modulo4/OpenOCR/igtr_synth_best.pth
   ```

O **PARSeq** dispensa download manual: seus pesos pre-treinados sao baixados diretamente pelo PyTorch Hub na primeira execucao.

---

# Referencias

- **YOLO26.** Jocher, G.; Qiu, J. *Ultralytics YOLO26*. Versao 26.0.0, 2026. https://github.com/ultralytics/ultralytics
- **CycleGAN-Turbo.** Parmar, G.; Park, T.; Narasimhan, S.; Zhu, J.-Y. *One-Step Image Translation with Text-to-Image Models*. arXiv:2403.12036, 2024. https://github.com/GaParmar/img2img-turbo
- **TSIT.** Jiang, L.; Zhang, C.; Huang, M.; Liu, C.; Shi, J.; Loy, C. C. *TSIT: A Simple and Versatile Framework for Image-to-Image Translation*. ECCV 2020, pp. 206-222. https://github.com/EndlessSora/TSIT
- **DMT.** Xia, M.; Zhou, Y.; Yi, R.; Liu, Y.-J.; Wang, W. *A Diffusion Model Translator for Efficient Image-to-Image Translation*. IEEE TPAMI, v. 46, n. 12, pp. 10272-10283, 2024. doi:10.1109/TPAMI.2024.3435448. https://github.com/THU-LYJ-Lab/dmt
- **ADM.** Dhariwal, P.; Nichol, A. *Diffusion Models Beat GANs on Image Synthesis*. NeurIPS, v. 34, pp. 8780-8794, 2021. https://github.com/openai/guided-diffusion
- **PARSeq.** Bautista, D.; Atienza, R. *A Strong Baseline for Scene Text Recognition with Permutation Language Models*. ECCV, 2022. https://github.com/baudm/parseq
- **OpenOCR (SVTRv2 e IGTR).** Du, Y. et al. *OpenOCR*. 2024. https://github.com/Topdu/OpenOCR
