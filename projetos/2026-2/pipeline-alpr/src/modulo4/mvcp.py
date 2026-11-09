# mvcp — votacao majoritaria por posicao de caractere
# consolida predicoes de multiplos modelos e/ou frames em uma predicao final por track
# baseado em Nascimento et al. (2025)

from collections import Counter


def mvcp(predictions: list[tuple[str, list[float]]]) -> str:
    if not predictions:
        return ""

    # remove caracteres nao alfanumericos e normaliza para maiusculo
    clean = []
    for text, scores in predictions:
        text_clean = []
        scores_clean = []
        for char, score in zip(text, scores):
            if char.isalnum():
                text_clean.append(char.upper())
                scores_clean.append(score)
        clean.append(("".join(text_clean), scores_clean))

    if not clean:
        return ""

    # comprimento mais comum — filtra predicoes com comprimento diferente
    length = Counter(len(t) for t, _ in clean).most_common(1)[0][0]
    clean = [(t, s) for t, s in clean if len(t) == length]

    if not clean:
        return ""

    final_chars = []
    for pos in range(length):
        char_scores = []
        for text, scores in clean:
            char = text[pos]
            score = scores[pos] if pos < len(scores) else 0.0
            char_scores.append((char, score))

        vote_count = Counter(c for c, _ in char_scores)
        max_votes = max(vote_count.values())
        candidates = [c for c, v in vote_count.items() if v == max_votes]

        if len(candidates) == 1:
            final_chars.append(candidates[0])
        else:
            # desempate: maior media de confianca
            best_char = max(
                candidates,
                key=lambda c: sum(s for ch, s in char_scores if ch == c) / vote_count[c]
            )
            final_chars.append(best_char)

    return "".join(final_chars)
