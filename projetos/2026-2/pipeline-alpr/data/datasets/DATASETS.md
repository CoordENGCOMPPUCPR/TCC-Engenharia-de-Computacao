# Datasets Utilizados

Este projeto não distribui os datasets diretamente. Abaixo estão as referências, formatos e instruções de obtenção de cada um.

---

## UFPR-VeSV

| Item | Valor |
|------|-------|
| Referência | Lima, G. E.; Nascimento, V.; Santos, E.; Nascimento Jr., E.; Laroca, R.; Menotti, D. *Toward Unified Fine-Grained Vehicle Classification and Automatic License Plate Recognition*. Journal of the Brazilian Computer Society, v. 32, n. 1, p. 783-799, 2026. doi: [10.5753/jbcs.2026.5899](https://doi.org/10.5753/jbcs.2026.5899) |
| Total de imagens | 24.945 |
| Splits | 10 disponíveis (split 0 usado neste trabalho) |
| Split 0 | 14.845 treino / 5.025 val / 5.075 teste |
| Resolução | Variável (cenas completas com veículo + placa) |
| Anotações | `plate` (texto), `corners` (4 pontos `{x, y}` em pixels) |
| Formato de anotação | JSON (`annotations.json`) |
| Como obter | Disponível em [github.com/Lima001/UFPR-VeSV-Dataset](https://github.com/Lima001/UFPR-VeSV-Dataset); ver as instruções de acesso no repositório |

---

## LRLPR-26

| Item | Valor |
|------|-------|
| Referência | Laroca, R. et al. *ICPR 2026 Competition on Low-Resolution License Plate Recognition*. International Conference on Pattern Recognition (ICPR), p. 256-275, 2026. doi: [10.1007/978-3-032-31936-4_18](https://doi.org/10.1007/978-3-032-31936-4_18) |
| Treino | 20.000 tracks (10.000 Cenário A + 10.000 Cenário B), cada um com 5 LR + 5 HR = 200.000 imagens |
| Teste | 3.000 tracks do Cenário B (apenas LR): 600 legado + 2.400 Mercosul |
| Cenários | Cenário A (tracks do UFPR-SR-Plates) e Cenário B (capturas novas, inclui chuva e noturno) |
| Anotações | `plate_text`, `plate_layout` (Brazilian/Mercosur) |
| Formato de anotação | JSON (`annotations.json` por track) |
| Split oficial | `split-train-val.json` na raiz do dataset |
| Como obter | Acesso restrito a equipes de universidades ou instituições de pesquisa; instruções e acordo de licença na [página da competição](https://icpr26lrlpr.github.io/) |

### Estrutura esperada

```
LRLPR-26-5opEvJTW/
    train/
        Scenario-A/Brazilian/track_XXXXX/
            lr-001.png ... lr-005.png
            hr-001.png ... hr-005.png
            annotations.json
        Scenario-A/Mercosur/track_XXXXX/
        Scenario-B/Brazilian/track_XXXXX/
        Scenario-B/Mercosur/track_XXXXX/
    test/
        ...
    split-train-val.json
```

---

## RodoSol-ALPR

| Item | Valor |
|------|-------|
| Referência | Laroca, R.; Cardoso, E. V.; Lucio, D. R.; Estevam, V.; Menotti, D. *On the Cross-Dataset Generalization in License Plate Recognition*. International Conference on Computer Vision Theory and Applications (VISAPP), p. 166-178, 2022. doi: [10.5220/0010846800003124](https://doi.org/10.5220/0010846800003124) |
| Descrição | Imagens de câmeras fixas em praças de pedágio da rodovia ES-060 (Espírito Santo), operada pela concessionária Rodovia do Sol; inclui dia e noite, várias faixas e tempo claro e chuvoso |
| Total de imagens | 20.000 (1.280×720) |
| Composição | 10.000 de carros e 10.000 de motos; 10.000 com placa legado e 10.000 Mercosul (5.000 em cada combinação) |
| Como obter | Disponível em [github.com/raysonlaroca/rodosol-alpr-dataset](https://github.com/raysonlaroca/rodosol-alpr-dataset); ver as instruções de acesso no repositório |

---

## Templates sintéticos

| Item | Valor |
|------|-------|
| Referência | Laroca, R.; Estevam, V.; Moreira, G. J. P.; Minetto, R.; Menotti, D. *Advancing Multinational License Plate Recognition Through Synthetic and Real Data Fusion: A Comprehensive Evaluation*. IET Intelligent Transport Systems, v. 19, n. 1, 2025. doi: [10.1049/itr2.70086](https://doi.org/10.1049/itr2.70086) |
| Total gerado | 2.000 (1.000 Brazilian + 1.000 Mercosur) |
| Distribuição por tipo | Ver a documentação final do TCC |
