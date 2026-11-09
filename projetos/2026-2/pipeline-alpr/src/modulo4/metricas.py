# metricas — levenshtein, cer e taxa de reconhecimento


def levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[m]


def calcular_metricas(resultados: list[dict]) -> dict:
    total_erros = 0
    total_chars = 0
    placas_corretas = 0
    total_placas = 0

    # por categoria
    cat_erros = {}
    cat_chars = {}
    cat_corretas = {}
    cat_totais = {}

    for r in resultados:
        pred = r["pred"].upper()
        gt = r["gt"].upper()
        cat = r.get("category", "unknown")

        dist = levenshtein(pred, gt)
        n_chars = len(gt)

        total_erros += dist
        total_chars += n_chars
        total_placas += 1
        if pred == gt:
            placas_corretas += 1

        cat_erros[cat] = cat_erros.get(cat, 0) + dist
        cat_chars[cat] = cat_chars.get(cat, 0) + n_chars
        cat_totais[cat] = cat_totais.get(cat, 0) + 1
        cat_corretas[cat] = cat_corretas.get(cat, 0) + (1 if pred == gt else 0)

    cer_global = total_erros / total_chars if total_chars > 0 else 0.0
    taxa_global = placas_corretas / total_placas if total_placas > 0 else 0.0

    por_categoria = {}
    for cat in cat_totais:
        por_categoria[cat] = {
            "cer": cat_erros[cat] / cat_chars[cat] if cat_chars[cat] > 0 else 0.0,
            "taxa_reconhecimento": cat_corretas[cat] / cat_totais[cat] if cat_totais[cat] > 0 else 0.0,
            "total": cat_totais[cat],
            "corretas": cat_corretas[cat],
        }

    return {
        "cer": cer_global,
        "taxa_reconhecimento": taxa_global,
        "total_placas": total_placas,
        "placas_corretas": placas_corretas,
        "total_erros": total_erros,
        "total_caracteres": total_chars,
        "por_categoria": por_categoria,
    }
