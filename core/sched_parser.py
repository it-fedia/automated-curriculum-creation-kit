import re
import pandas as pd
from pathlib import Path

from .normalize import _txt, normalize_day, normalize_time, normalize_room, normalize_disc, normalize_kind_sched


def parse_subject(raw):
    if pd.isna(raw) or str(raw).strip() == "":
        return {"Дисциплина": None, "Вид_занятия": None, "Аудитория": None}

    text = " ".join(str(raw).replace("\n", " ").split())
    text = re.sub(r"\s*[/％%]\s*$", "", text)

    parts = [p.strip() for p in text.split(";") if p.strip()]
    discipline = parts[0] if parts else None

    lesson_type = None
    room = None

    lesson_type_tokens = ["лек", "лекция", "сем", "семинар", "лаб", "лр", "пр", "практика"]
    for part in parts[1:]:
        low = part.lower().replace(".", "").strip()

        if lesson_type is None and any(low.startswith(tok) for tok in lesson_type_tokens):
            lesson_type = part
            continue

        if room is None:
            m = re.search(r"(ОРД-\d+\w*|ФОК-\d+|ТУИС)", part)
            if m:
                room = m.group(1)

    return {"Дисциплина": discipline, "Вид_занятия": lesson_type, "Аудитория": room}


def read_schedule(sched_xlsx: Path, sheet_name: str = "ФМиЕН") -> tuple[pd.DataFrame, pd.DataFrame]:
    xls = pd.ExcelFile(sched_xlsx)
    df = pd.read_excel(xls, sheet_name=sheet_name)

    data = df.iloc[4:].copy()
    data = data.rename(columns={"Unnamed: 1": "День недели", "Unnamed: 2": "Пара", "Unnamed: 3": "Время"})

    rows = []
    for col in data.columns[4:]:
        col_idx = df.columns.get_loc(col)
        group_code = _txt(df.iloc[3, col_idx])
        if not group_code:
            continue

        for _, row in data.iterrows():
            raw_subject = row[col]
            if pd.isna(raw_subject) or str(raw_subject).strip() == "":
                continue

            parsed = parse_subject(raw_subject)

            pair_val = row.get("Пара")
            try:
                pair_val = int(pair_val) if not pd.isna(pair_val) else None
            except Exception:
                pair_val = None

            rows.append({
                "День недели": normalize_day(row.get("День недели")),
                "Пара": pair_val,
                "Время": normalize_time(row.get("Время")),
                "Учебная группа": group_code,
                "Дисциплина": _txt(parsed.get("Дисциплина")),
                "Вид_занятия": _txt(parsed.get("Вид_занятия")),
                "Аудитория": normalize_room(parsed.get("Аудитория")),
            })

    parsed_df = pd.DataFrame(rows)

    norm_df = parsed_df.copy()
    norm_df["Вид_занятия_норм"] = norm_df["Вид_занятия"].apply(normalize_kind_sched)
    norm_df = norm_df[norm_df["Вид_занятия_норм"].notna()].copy()
    norm_df["disc_key"] = norm_df["Дисциплина"].apply(normalize_disc)

    return parsed_df, norm_df
