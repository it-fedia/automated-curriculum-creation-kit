from __future__ import annotations

from pathlib import Path

import pandas as pd

from .export import build_teacher_timetable
from .matching import merge_schedule_with_teachers
from .mappings import apply_mappings, load_mappings
from .sched_parser import read_schedule
from .un_parser import read_un


def build_timetable_bundle(run_path: Path, sched_path: Path, out_dir: Path, mappings_path: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_path = Path(run_path)
    sched_path = Path(sched_path)
    mappings_path = Path(mappings_path)

    # 1) парсим рун и расписание
    un_raw, un_expanded = read_un(run_path)
    sched_parsed, sched_norm = read_schedule(sched_path)

    # 2) автосопоставление
    merged, lowconf = merge_schedule_with_teachers(sched_norm, un_expanded)

    # 3) применяем сохранённые правила (если есть)
    mappings = load_mappings(mappings_path)
    merged = apply_mappings(merged, mappings, override=False)

    # 4) пути вывода
    schedule_with_teachers = out_dir / "schedule_with_teachers.xlsx"
    timetable_by_teachers = out_dir / "timetable_by_teachers.xlsx"
    unmatched_slots = out_dir / "unmatched_slots.xlsx"
    un_expanded_path = out_dir / "un_svodnaya_expanded.xlsx"

    # доп. диагностика (не обязательно, но полезно)
    lowconf_path = out_dir / "lowconf_matches.xlsx"
    conflicts_path = out_dir / "teacher_conflicts.xlsx"
    un_raw_path = out_dir / "un_svodnaya.xlsx"
    sched_parsed_path = out_dir / "расписание_по_группам_разобранное.xlsx"
    sched_norm_path = out_dir / "расписание_по_группам_norm.xlsx"

    # 5) сохраняем промежуточные (нужны для candidates)
    un_raw.to_excel(un_raw_path, index=False)
    un_expanded.to_excel(un_expanded_path, index=False)
    sched_parsed.to_excel(sched_parsed_path, index=False)
    sched_norm.to_excel(sched_norm_path, index=False)

    # merged как "расписание с преподавателями" (до pivot)
    merged.to_excel(schedule_with_teachers, index=False)

    # unmatched
    unmatched = merged.copy()
    if "Преподаватель" not in unmatched.columns:
        unmatched["Преподаватель"] = pd.NA
    unmatched = unmatched[unmatched["Преподаватель"].isna()].copy()
    cols = [
        "День недели",
        "Пара",
        "Время",
        "Учебная группа",
        "Дисциплина",
        "Вид_занятия",
        "Аудитория",
        "disc_key",
        "Вид_занятия_норм",
    ]
    cols = [c for c in cols if c in unmatched.columns]
    unmatched[cols].to_excel(unmatched_slots, index=False)

    # low confidence
    if isinstance(lowconf, pd.DataFrame) and len(lowconf) > 0:
        lowconf.to_excel(lowconf_path, index=False)
    else:
        if lowconf_path.exists():
            lowconf_path.unlink(missing_ok=True)

    # pivot + conflicts
    pivot, conflicts = build_teacher_timetable(merged)
    pivot.to_excel(timetable_by_teachers, index=False)

    if isinstance(conflicts, pd.DataFrame) and len(conflicts) > 0:
        conflicts.to_excel(conflicts_path, index=False)
    else:
        if conflicts_path.exists():
            conflicts_path.unlink(missing_ok=True)

    total = int(len(merged))
    matched = int(merged["Преподаватель"].notna().sum()) if "Преподаватель" in merged.columns else 0
    unmatched_n = int(total - matched)
    lowconf_n = int(len(lowconf)) if isinstance(lowconf, pd.DataFrame) else 0
    conflicts_n = int(len(conflicts)) if isinstance(conflicts, pd.DataFrame) else 0

    return {
        "stats": {
            "total_slots": total,
            "matched": matched,
            "unmatched": unmatched_n,
            "lowconf": lowconf_n,
            "conflicts": conflicts_n,
        },
        "files": {
            "out": str(timetable_by_teachers),
            "unmatched": str(unmatched_slots),
            "un_expanded": str(un_expanded_path),
            "schedule_with_teachers": str(schedule_with_teachers),
        },
    }
