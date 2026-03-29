import pandas as pd
from pathlib import Path

from .normalize import _txt, normalize_disc, normalize_kind_un


def _norm_sheet_name(s: str) -> str:
    return _txt(s).lower().replace("ё", "е").strip()


def pick_un_sheet(excel_path: Path) -> str:
    xls = pd.ExcelFile(excel_path)
    sheets = list(xls.sheet_names)
    norm_map = {_norm_sheet_name(x): x for x in sheets}

    target = _norm_sheet_name("ун сводная")
    if target in norm_map:
        return norm_map[target]

    for sh in sheets:
        n = _norm_sheet_name(sh)
        if "ун" in n and "свод" in n:
            return sh

    return sheets[0]


def expand_group_numbers(num_str: str) -> list[str]:
    s = _txt(num_str).replace(" ", "")
    if not s:
        return []

    tokens = [t for t in s.split(",") if t]
    if not tokens:
        return []

    suffix = None
    for t in tokens:
        if "-" in t:
            suffix = t.split("-", 1)[1]
            break

    out = []
    for t in tokens:
        if "-" in t:
            out.append(t)
        else:
            out.append(f"{t}-{suffix}" if suffix else t)

    return list(dict.fromkeys(out))


def read_un(run_xlsx: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sheet = pick_un_sheet(run_xlsx)
    excel_data = pd.read_excel(run_xlsx, sheet_name=sheet, header=None)

    header_rows = excel_data.iloc[:4]
    combined_headers = header_rows.fillna("").astype(str).agg(" ".join)

    df = excel_data.iloc[4:].copy()
    df.columns = combined_headers

    def find_col(pattern: str):
        for col in df.columns:
            if pattern in col:
                return col
        return None

    spec = {
        "Дисциплина": "Наименование дисциплины или вида учебной работы",
        "Семестр": "Семестр",
        "Вид_работы": "Вид учебной работы",
        "Код_группы": "Учебная группа",
        "Номер_группы": "Номер группы",
        "Количество_студентов": "Кол-во чел. в группе (потоке) Всего",
        "Кафедра": "Сведения о ППС Кафедра",
        "Должность": "должность",
        "Преподаватель": "Фамилия И.О.  преподавателя",
        "Лекции_часы": "Объём учебной работы ППС Лекции",
        "Практика_часы": "Практика / Семинары",
        "Лабораторные_часы": "Лаб. работы / Клинические занятия",
        "Всего_часов": "Всего часов",
    }

    rename_map = {}
    for new_name, pattern in spec.items():
        col = find_col(pattern)
        if col is not None:
            rename_map[col] = new_name

    df = df[list(rename_map.keys())].rename(columns=rename_map)

    numeric_cols = ["Лекции_часы", "Практика_часы", "Лабораторные_часы", "Всего_часов"]
    text_cols = [c for c in df.columns if c not in numeric_cols]

    for col in text_cols:
        df[col] = df[col].apply(_txt)
        df[col] = df[col].replace({"nan": ""})

    for col in numeric_cols:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace(" ", "", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "Преподаватель" in df.columns:
        df = df[(df["Преподаватель"] != "") & (~df["Преподаватель"].str.match(r"^\d+(\.\d+)?$", na=False))]

    un_raw = df.copy()

    un = un_raw.copy()
    un["Вид_работы_норм"] = un["Вид_работы"].apply(normalize_kind_un)
    un = un[un["Вид_работы_норм"].notna()].copy()
    un["disc_key"] = un["Дисциплина"].apply(normalize_disc)

    rows = []
    for _, row in un.iterrows():
        kod = row.get("Код_группы")
        num = row.get("Номер_группы")
        if not isinstance(kod, str) or pd.isna(num):
            continue

        group_numbers = expand_group_numbers(str(num))
        if not group_numbers:
            continue

        for gn in group_numbers:
            new_row = row.copy()
            new_row["Учебная группа"] = f"{kod.strip()}-{gn}"
            rows.append(new_row)

    un_expanded = pd.DataFrame(rows)
    return un_raw, un_expanded
