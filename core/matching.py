# import pandas as pd

# from .normalize import _txt, best_disc_match


# def dedup_un_for_merge(un_expanded: pd.DataFrame) -> pd.DataFrame:
#     u = un_expanded.copy()

#     def score_row(r):
#         k = r.get("Вид_работы_норм")
#         if k == "лек":
#             return float(r.get("Лекции_часы", 0) or 0)
#         if k == "сем":
#             return float(r.get("Практика_часы", 0) or 0)
#         if k == "лаб":
#             return float(r.get("Лабораторные_часы", 0) or 0)
#         return 0.0

#     u["_score"] = u.apply(score_row, axis=1)

#     u = (
#         u.sort_values(["Учебная группа", "disc_key", "Вид_работы_норм", "_score"], ascending=[True, True, True, False])
#         .groupby(["Учебная группа", "disc_key", "Вид_работы_норм"], as_index=False)
#         .first()
#     )

#     return u.drop(columns=["_score"], errors="ignore")


# def fuzzy_fill_unmatched(merged: pd.DataFrame, un_dedup: pd.DataFrame, threshold_ok: float = 0.55):
#     lowconf_rows = []

#     bucket = {}
#     for _, r in un_dedup.iterrows():
#         g = _txt(r.get("Учебная группа"))
#         k = _txt(r.get("Вид_работы_норм"))
#         d = _txt(r.get("disc_key"))
#         if not g or not k or not d:
#             continue
#         bucket.setdefault((g, k), []).append(d)

#     merged = merged.copy()
#     m_unmatched = merged["Преподаватель"].isna()

#     for idx in merged[m_unmatched].index:
#         g = _txt(merged.at[idx, "Учебная группа"])
#         k = _txt(merged.at[idx, "Вид_занятия_норм"])
#         disc = _txt(merged.at[idx, "disc_key"])

#         cands = bucket.get((g, k), [])
#         if not cands:
#             continue

#         best, score = best_disc_match(disc, cands)
#         if not best or score <= 0:
#             continue

#         if score >= threshold_ok:
#             hit = un_dedup[
#                 (un_dedup["Учебная группа"] == g)
#                 & (un_dedup["Вид_работы_норм"] == k)
#                 & (un_dedup["disc_key"] == best)
#             ]
#             if len(hit) > 0:
#                 merged.at[idx, "Преподаватель"] = hit.iloc[0].get("Преподаватель")
#         else:
#             lowconf_rows.append({
#                 "День недели": merged.at[idx, "День недели"],
#                 "Пара": merged.at[idx, "Пара"],
#                 "Время": merged.at[idx, "Время"],
#                 "Учебная группа": g,
#                 "disc_key_sched": disc,
#                 "disc_key_best": best,
#                 "score": score,
#             })

#     return merged, pd.DataFrame(lowconf_rows)


# def merge_schedule_with_teachers(sched_norm: pd.DataFrame, un_expanded: pd.DataFrame):
#     un_dedup = dedup_un_for_merge(un_expanded)

#     merged = sched_norm.merge(
#         un_dedup,
#         how="left",
#         left_on=["Учебная группа", "disc_key", "Вид_занятия_норм"],
#         right_on=["Учебная группа", "disc_key", "Вид_работы_норм"],
#         suffixes=("_sched", "_un"),
#     )

#     if "Преподаватель" not in merged.columns:
#         merged["Преподаватель"] = None

#     merged, lowconf = fuzzy_fill_unmatched(merged, un_dedup)
#     merged["Преподаватель"] = merged["Преподаватель"].apply(lambda x: x if _txt(x) else None)

#     return merged, lowconf


import pandas as pd

from .normalize import _txt, best_disc_match
from .ml_disc_similarity import DiscTfidfMatcher


# =========================================================
# 1. Дедупликация РУН
# =========================================================

def dedup_un_for_merge(un_expanded: pd.DataFrame) -> pd.DataFrame:
    u = un_expanded.copy()

    def score_row(r):
        k = r.get("Вид_работы_норм")
        if k == "лек":
            return float(r.get("Лекции_часы", 0) or 0)
        if k == "сем":
            return float(r.get("Практика_часы", 0) or 0)
        if k == "лаб":
            return float(r.get("Лабораторные_часы", 0) or 0)
        return 0.0

    u["_score"] = u.apply(score_row, axis=1)

    u = (
        u.sort_values(
            ["Учебная группа", "disc_key", "Вид_работы_норм", "_score"],
            ascending=[True, True, True, False],
        )
        .groupby(
            ["Учебная группа", "disc_key", "Вид_работы_норм"],
            as_index=False,
        )
        .first()
    )

    return u.drop(columns=["_score"], errors="ignore")


# =========================================================
# 2. Гибридное сопоставление (Jaccard + ML)
# =========================================================

def fuzzy_fill_unmatched(
    merged: pd.DataFrame,
    un_dedup: pd.DataFrame,
    threshold_ok: float = 0.55,
):
    lowconf_rows = []

    # (группа, вид занятия) -> список дисциплин из РУН
    bucket: dict[tuple[str, str], list[str]] = {}

    for _, r in un_dedup.iterrows():
        g = _txt(r.get("Учебная группа"))
        k = _txt(r.get("Вид_работы_норм"))
        d = _txt(r.get("disc_key"))
        if not g or not k or not d:
            continue
        bucket.setdefault((g, k), []).append(d)

    # ---------------------------------------------------------
    # ML: TF-IDF + cosine similarity
    #
    # Для каждой пары (Учебная группа, Вид занятия) строится
    # TF-IDF модель по названиям дисциплин из РУН.
    #
    # Модель обучается один раз и затем используется
    # для поиска наиболее близкой дисциплины по косинусному
    # сходству векторных представлений текста.
    #
    # ML применяется только в случае, если:
    # - символьный метод (Jaccard) дал результат ниже порога,
    # - и количество дисциплин достаточно для обучения модели.
    # ---------------------------------------------------------
    ml_models: dict[tuple[str, str], DiscTfidfMatcher] = {}
    for key, discs in bucket.items():
        uniq = list(set(discs))
        if len(uniq) >= 3:
            ml_models[key] = DiscTfidfMatcher(uniq)

    merged = merged.copy()
    m_unmatched = merged["Преподаватель"].isna()

    for idx in merged[m_unmatched].index:
        g = _txt(merged.at[idx, "Учебная группа"])
        k = _txt(merged.at[idx, "Вид_занятия_норм"])
        disc = _txt(merged.at[idx, "disc_key"])

        cands = bucket.get((g, k), [])
        if not cands:
            continue

        # Сначала применяется символьное сопоставление (Jaccard),
        # так как оно обеспечивает высокую точность при
        # незначительных различиях в строках.
        best, score = best_disc_match(disc, cands)
        method = "jaccard"

        # Если Jaccard не дал уверенного результата,
        # используется ML-подход (TF-IDF + cosine similarity),
        # позволяющий учитывать семантическую близость названий.
        if score < threshold_ok:
            model = ml_models.get((g, k))
            if model:
                best_ml, score_ml = model.best_match(disc)
                if score_ml > score:
                    best, score = best_ml, score_ml
                    method = "ml"

        if not best or score <= 0:
            continue

        if score >= threshold_ok:
            hit = un_dedup[
                (un_dedup["Учебная группа"] == g)
                & (un_dedup["Вид_работы_норм"] == k)
                & (un_dedup["disc_key"] == best)
            ]
            if len(hit) > 0:
                merged.at[idx, "Преподаватель"] = hit.iloc[0].get("Преподаватель")
        else:
            lowconf_rows.append({
                "День недели": merged.at[idx, "День недели"],
                "Пара": merged.at[idx, "Пара"],
                "Время": merged.at[idx, "Время"],
                "Учебная группа": g,
                "disc_key_sched": disc,
                "disc_key_best": best,
                "score": score,
                "method": method,
            })

    return merged, pd.DataFrame(lowconf_rows)


# =========================================================
# 3. Основная функция merge
# =========================================================

def merge_schedule_with_teachers(
    sched_norm: pd.DataFrame,
    un_expanded: pd.DataFrame,
):
    un_dedup = dedup_un_for_merge(un_expanded)

    merged = sched_norm.merge(
        un_dedup,
        how="left",
        left_on=["Учебная группа", "disc_key", "Вид_занятия_норм"],
        right_on=["Учебная группа", "disc_key", "Вид_работы_норм"],
        suffixes=("_sched", "_un"),
    )

    if "Преподаватель" not in merged.columns:
        merged["Преподаватель"] = None

    merged, lowconf = fuzzy_fill_unmatched(merged, un_dedup)

    merged["Преподаватель"] = merged["Преподаватель"].apply(
        lambda x: x if _txt(x) else None
    )

    return merged, lowconf
