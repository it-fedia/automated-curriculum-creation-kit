from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import pandas as pd

from .normalize import disc_tokens, jaccard


@dataclass
class Slot:
    group: str
    disc_key: str
    kind: str


def build_candidates(
    un_expanded: pd.DataFrame,
    slot: Slot,
    top_n: int = 8,
    min_score: float = 0.20,
) -> list[dict[str, Any]]:
    u = _prep_un(un_expanded)
    if u is None or len(u) == 0:
        return []

    g = slot.group.strip()
    d = slot.disc_key.strip()
    k = slot.kind.strip()

    base = u[u["kind"] == k].copy()
    if len(base) == 0:
        return []

    cands = []

    s_exact = base[(base["group"] == g) & (base["disc_key"] == d)]
    cands += _agg_teachers(s_exact, score=0.98, reason="точное: группа+дисциплина+вид")

    s_gk = base[(base["group"] == g)]
    cands += _agg_teachers(s_gk, score=0.70, reason="группа+вид")

    s_dk = base[(base["disc_key"] == d)]
    cands += _agg_teachers(s_dk, score=0.62, reason="дисциплина+вид")

    cands += _fuzzy_disc(base, g=g, d=d, k=k)

    best = {}
    for c in cands:
        t = c["teacher"]
        if t not in best or c["score"] > best[t]["score"]:
            best[t] = c

    out = list(best.values())
    out = [x for x in out if x["score"] >= min_score]
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_n]


def _prep_un(un_expanded: pd.DataFrame) -> pd.DataFrame | None:
    if un_expanded is None or len(un_expanded) == 0:
        return None

    need = ["Учебная группа", "disc_key", "Вид_работы_норм", "Преподаватель"]
    for c in need:
        if c not in un_expanded.columns:
            return None

    u = un_expanded[need].copy()
    u = u.dropna(subset=["Преподаватель", "Учебная группа", "disc_key", "Вид_работы_норм"]).copy()

    u["teacher"] = u["Преподаватель"].astype(str).str.strip()
    u["group"] = u["Учебная группа"].astype(str).str.strip()
    u["disc_key"] = u["disc_key"].astype(str).str.strip()
    u["kind"] = u["Вид_работы_норм"].astype(str).str.strip()

    u = u[(u["teacher"] != "") & (u["group"] != "") & (u["disc_key"] != "") & (u["kind"] != "")].copy()
    return u


def _agg_teachers(df: pd.DataFrame, score: float, reason: str) -> list[dict[str, Any]]:
    if df is None or len(df) == 0:
        return []

    g = df.groupby("teacher", as_index=False).size().rename(columns={"size": "hits"})
    out = []
    for _, r in g.iterrows():
        out.append({
            "teacher": r["teacher"],
            "score": float(score),
            "reason": reason,
            "hits": int(r["hits"]),
        })
    return out


def _fuzzy_disc(base: pd.DataFrame, g: str, d: str, k: str) -> list[dict[str, Any]]:
    out = []
    tgt = disc_tokens(d)
    if not tgt:
        return out

    subset = base[base["group"] == g].copy()
    if len(subset) == 0:
        subset = base.copy()

    disc_list = subset["disc_key"].dropna().astype(str).unique().tolist()
    best_disc = None
    best_sc = 0.0
    for dd in disc_list:
        sc = jaccard(tgt, disc_tokens(dd))
        if sc > best_sc:
            best_sc = sc
            best_disc = dd

    if not best_disc or best_sc <= 0:
        return out

    hits = subset[subset["disc_key"] == best_disc]
    raw = _agg_teachers(hits, score=0.25 + 0.55 * best_sc, reason=f"похоже на дисциплину: {best_disc}")
    return raw
