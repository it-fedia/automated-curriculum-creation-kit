from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .normalize import normalize_disc


class DiscTfidfMatcher:
    """
        ML-модуль сопоставления дисциплин.

        Используется классический подход машинного обучения:
        TF-IDF (Term Frequency – Inverse Document Frequency) + cosine similarity.

        Назначение:
        - автоматическое сопоставление названий дисциплин,
        - устойчивость к разным формулировкам и порядку слов,
        - работа без обучающей выборки (unsupervised learning).

        Алгоритм:
        1. Названия дисциплин предварительно нормализуются
        (используется существующая функция normalize_disc).
        2. Формируется TF-IDF представление текста
        с учетом униграмм и биграмм (ngram_range=(1, 2)).
        3. Для входной строки вычисляется косинусное сходство
        со всеми дисциплинами из корпуса.
        4. Возвращается наиболее похожая дисциплина и значение сходства [0..1].

        Данный метод применяется как резервный (fallback),
        если символьное сопоставление (Jaccard) дает низкий результат.
    """

    def __init__(self, corpus: list[str]):
        self.raw = corpus
        self.norm = [normalize_disc(x) for x in corpus]

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
        )
        self.X = self.vectorizer.fit_transform(self.norm)

    def best_match(self, query: str) -> tuple[str | None, float]:
        q = normalize_disc(query)
        if not q:
            return None, 0.0

        v = self.vectorizer.transform([q])
        sims = cosine_similarity(v, self.X)[0]

        idx = int(sims.argmax())
        score = float(sims[idx])

        if score <= 0:
            return None, 0.0

        return self.raw[idx], score
