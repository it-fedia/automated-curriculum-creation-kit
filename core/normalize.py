import re
import pandas as pd


def _txt(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def normalize_day(day: str) -> str:
    s = _txt(day).upper()
    s = s.replace("ПОНЕДЕЛЬНИК", "ПН").replace("ВТОРНИК", "ВТ").replace("СРЕДА", "СР")
    s = s.replace("ЧЕТВЕРГ", "ЧТ").replace("ПЯТНИЦА", "ПТ").replace("СУББОТА", "СБ").replace("ВОСКРЕСЕНЬЕ", "ВС")
    return s


def normalize_time(t: str) -> str:
    s = _txt(t)
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace(",", ".")
    s = re.sub(r"\s+", "", s)
    return s


def normalize_room(room: str) -> str:
    s = _txt(room)
    s = s.replace(" ", "")
    s = s.replace("–", "-").replace("—", "-")
    return s


def normalize_disc(s: str) -> str:
    s = _txt(s).lower().replace("ё", "е")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("\\", " ").replace("/", " ")
    s = re.sub(r"^\s*[абвгде]\)\s*", "", s)
    s = re.sub(r"[.,:;!?]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def disc_tokens(s: str) -> set[str]:
    s = normalize_disc(s)
    if not s:
        return set()
    toks = [t for t in re.split(r"\s+", s) if t]
    stop = {"и", "в", "во", "на", "по", "для", "о", "об", "к", "из", "с", "со", "при", "или", "а"}
    toks = [t for t in toks if t not in stop and len(t) > 1]
    return set(toks)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0


def best_disc_match(target_disc: str, candidates: list[str]) -> tuple[str | None, float]:
    ta = disc_tokens(target_disc)
    if not ta:
        return None, 0.0

    best = None
    best_score = 0.0
    for c in candidates:
        sc = jaccard(ta, disc_tokens(c))
        if sc > best_score:
            best_score = sc
            best = c

    return best, best_score


def normalize_kind_un(kind: str):
    s = _txt(kind).lower()
    s = s.replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()

    if "лек" in s:
        return "лек"
    if "сем" in s or s == "пр" or "практ" in s:
        return "сем"
    if "лаб" in s or "лр" in s:
        return "лаб"
    return None


def normalize_kind_sched(kind: str):
    s = _txt(kind).lower()
    s = s.replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()

    if s.startswith("лек"):
        return "лек"
    if s.startswith("сем") or s.startswith("пр"):
        return "сем"
    if s.startswith("лаб") or s.startswith("лр"):
        return "лаб"
    return None
