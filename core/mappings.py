import json
from pathlib import Path
from typing import Any
import pandas as pd


def load_mappings(path: Path) -> dict:
    if not path.exists():
        return {"rules": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"rules": []}
        if "rules" not in data or not isinstance(data["rules"], list):
            data["rules"] = []
        return data
    except Exception:
        return {"rules": []}


def save_mappings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def add_rule(path: Path, when: dict, assign: dict) -> dict:
    data = load_mappings(path)

    rule = {"when": dict(when), "assign": dict(assign)}
    _normalize_rule(rule)

    rules = data.get("rules", [])
    rules = [r for r in rules if not _same_rule(r, rule)]
    rules.append(rule)

    data["rules"] = rules
    save_mappings(path, data)
    return data


def apply_mappings(merged: pd.DataFrame, mappings: dict, override: bool = False) -> pd.DataFrame:
    df = merged.copy()

    if "rules" not in mappings or not isinstance(mappings["rules"], list):
        return df

    rules = []
    for r in mappings["rules"]:
        if not isinstance(r, dict):
            continue
        rr = {"when": dict(r.get("when", {})), "assign": dict(r.get("assign", {}))}
        _normalize_rule(rr)
        if not rr["assign"].get("teacher"):
            continue
        rules.append(rr)

    if not rules:
        return df

    if "Учебная группа" not in df.columns:
        return df
    if "disc_key" not in df.columns:
        return df
    if "Вид_занятия_норм" not in df.columns:
        return df
    if "Преподаватель" not in df.columns:
        df["Преподаватель"] = None

    df["_g"] = df["Учебная группа"].astype(str)
    df["_d"] = df["disc_key"].astype(str)
    df["_k"] = df["Вид_занятия_норм"].astype(str)

    if not override:
        target_mask = df["Преподаватель"].isna()
    else:
        target_mask = pd.Series(True, index=df.index)

    df["_assigned"] = df["Преподаватель"]

    for key_fields in _priority_patterns():
        map_df = _rules_to_df(rules, key_fields)
        if map_df is None or len(map_df) == 0:
            continue

        tmp = df.loc[target_mask, ["_g", "_d", "_k"]].copy()
        tmp = tmp.join(
            tmp.merge(
                map_df,
                how="left",
                left_on=[f"_{f}" for f in key_fields],
                right_on=[f"_{f}" for f in key_fields],
            )[["teacher"]]
        )

        got = tmp["teacher"].notna()
        idxs = tmp.index[got]
        df.loc[idxs, "_assigned"] = tmp.loc[idxs, "teacher"]
        target_mask.loc[idxs] = False

        if not target_mask.any():
            break

    df["Преподаватель"] = df["_assigned"]
    return df.drop(columns=["_g", "_d", "_k", "_assigned"], errors="ignore")


def _priority_patterns():
    return [
        ("g", "d", "k"),
        ("g", "k"),
        ("d", "k"),
        ("k",),
    ]


def _rules_to_df(rules: list[dict], key_fields: tuple[str, ...]) -> pd.DataFrame | None:
    rows = []
    for r in rules:
        w = r.get("when", {})
        a = r.get("assign", {})
        if "teacher" not in a:
            continue

        ok = True
        row = {"teacher": a.get("teacher")}
        for f in key_fields:
            val = w.get(_field_name(f))
            if val is None or str(val).strip() == "":
                ok = False
                break
            row[f"_{f}"] = str(val).strip()
        if ok:
            rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["teacher"]).copy()
    df["teacher"] = df["teacher"].astype(str).str.strip()
    df = df[df["teacher"] != ""].copy()

    df = df.drop_duplicates(subset=[f"_{f}" for f in key_fields], keep="last")
    return df


def _field_name(short: str) -> str:
    return {"g": "group", "d": "disc_key", "k": "kind"}[short]


def _normalize_rule(rule: dict) -> None:
    when = rule.get("when", {})
    assign = rule.get("assign", {})

    if not isinstance(when, dict):
        when = {}
    if not isinstance(assign, dict):
        assign = {}

    when2 = {
        "group": _clean(when.get("group")),
        "disc_key": _clean(when.get("disc_key")),
        "kind": _clean(when.get("kind")),
    }

    assign2 = {
        "teacher": _clean(assign.get("teacher")),
    }

    rule["when"] = {k: v for k, v in when2.items() if v}
    rule["assign"] = {k: v for k, v in assign2.items() if v}


def _clean(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None


def _same_rule(a: dict, b: dict) -> bool:
    return (a.get("when") == b.get("when")) and (a.get("assign") == b.get("assign"))
