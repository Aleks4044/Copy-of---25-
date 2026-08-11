from datetime import datetime
from typing import TypedDict

import reflex as rx

from app.states.bsd_state import COMBO_GROUP_LABELS, BSDMatch

MAX_VISIBLE_ROWS = 60

# Филтер по конкретен избор во комбинацијата (1, X, 2, Над/Под 1.5 и 2.5).
MARKET_FILTER_LABELS: dict[str, str] = {
    "home": "1 · Домашен",
    "draw": "X · Реми",
    "away": "2 · Гостин",
    "over15": "Над 1.5 гола",
    "under15": "Под 1.5 гола",
    "over25": "Над 2.5 гола",
    "under25": "Под 2.5 гола",
}

# Чиповите за конкретен избор смеат да прикажат САМО чисти директни редови:
# единечен 1X2 исход или гол-линија. Комбинации како „1 и ГГ“, „1X и Над 2.5“
# или двоен шанс НЕ добиваат ознака и затоа не се појавуваат во тие филтри.
DIRECT_MARKET_TAGS: dict[str, str] = {
    "1": "home",
    "x": "draw",
    "2": "away",
    "o15": "over15",
    "u15": "under15",
    "o25": "over25",
    "u25": "under25",
}


def _market_tags(key: str) -> list[str]:
    """Ознака само за чист директен маркет; комбинациите остануваат без."""
    tag = DIRECT_MARKET_TAGS.get(key)
    return [tag] if tag is not None else []


class MarketRow(TypedDict):
    id: str
    match_id: str
    match_label: str
    league: str
    kickoff: str
    status: str
    label: str
    group: str
    group_label: str
    probability: float
    odds: float
    edge: float
    recommended: bool
    recommendation: str
    market_tags: list[str]


class MarketsState(rx.State):
    """Комбинирани маркети од сите натпревари со филтри и статистики."""

    rows_cache: list[MarketRow] = []
    combos_per_match: int = 0
    generated_at: str = "--:--:--"
    group_filter: str = "all"
    status_filter: str = "all"
    match_filter: str = "all"
    market_filter: str = "all"
    sort_key: str = "probability"
    min_probability: float = 40.0
    only_recommended: bool = False
    missing_predictions: int = 0
    error: str = ""

    @rx.event
    def sync_from_matches(
        self, matches: list[BSDMatch], generated_at: str = ""
    ) -> None:
        """Ги преслика комбинираните маркети од BSD натпреварите во табела."""
        rows: list[MarketRow] = []
        predicted = [m for m in matches if m["has_prediction"] and m["combos"]]
        self.missing_predictions = len(matches) - len(predicted)
        for match in predicted:
            label = f"{match['home']} — {match['away']}"
            for combo in match["combos"]:
                rows.append(
                    MarketRow(
                        id=f"{match['id']}-{combo['key']}",
                        match_id=match["id"],
                        match_label=label,
                        league=match["league"],
                        kickoff=match["kickoff"],
                        status=match["status"],
                        label=combo["label"],
                        group=combo["group"],
                        group_label=combo["group_label"],
                        probability=combo["probability"],
                        odds=combo["odds"],
                        edge=combo["edge"],
                        recommended=combo["recommended"],
                        recommendation=combo["recommendation"],
                        market_tags=_market_tags(combo["key"]),
                    )
                )
        self.rows_cache = rows
        self.combos_per_match = predicted[0]["combo_count"] if predicted else 0
        self.generated_at = generated_at or datetime.now().strftime("%H:%M:%S")
        if self.match_filter != "all" and all(
            (m["id"] != self.match_filter for m in matches)
        ):
            self.match_filter = "all"

    @rx.var
    def rows(self) -> list[MarketRow]:
        return self.rows_cache

    @rx.var
    def filtered_rows(self) -> list[MarketRow]:
        rows = list(self.rows_cache)
        if self.group_filter != "all":
            rows = [r for r in rows if r["group"] == self.group_filter]
        if self.status_filter != "all":
            rows = [r for r in rows if r["status"] == self.status_filter]
        if self.match_filter != "all":
            rows = [r for r in rows if r["match_id"] == self.match_filter]
        if self.market_filter != "all":
            rows = [r for r in rows if self.market_filter in r["market_tags"]]
        if self.only_recommended:
            rows = [r for r in rows if r["recommended"]]
        rows = [r for r in rows if r["probability"] >= self.min_probability]
        if self.sort_key == "edge":
            return sorted(rows, key=lambda r: -r["edge"])
        if self.sort_key == "odds":
            return sorted(rows, key=lambda r: -r["odds"])
        if self.sort_key == "match":
            return sorted(
                rows, key=lambda r: (r["match_label"], -r["probability"])
            )
        if self.sort_key == "market":
            return sorted(rows, key=lambda r: (r["label"], -r["probability"]))
        return sorted(rows, key=lambda r: -r["probability"])

    @rx.var
    def visible_rows(self) -> list[MarketRow]:
        return self.filtered_rows[:MAX_VISIBLE_ROWS]

    @rx.var
    def total_count(self) -> int:
        return len(self.rows_cache)

    @rx.var
    def filtered_count(self) -> int:
        return len(self.filtered_rows)

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def recommended_count(self) -> int:
        return len([r for r in self.filtered_rows if r["recommended"]])

    @rx.var
    def strong_count(self) -> int:
        return len([r for r in self.filtered_rows if r["probability"] >= 70.0])

    @rx.var
    def value_count(self) -> int:
        return len([r for r in self.filtered_rows if r["edge"] >= 3.0])

    @rx.var
    def avg_probability(self) -> float:
        rows = self.filtered_rows
        if not rows:
            return 0.0
        return round(sum(r["probability"] for r in rows) / len(rows), 1)

    @rx.var
    def best_row_label(self) -> str:
        rows = self.filtered_rows
        if not rows:
            return "—"
        best = max(rows, key=lambda r: r["probability"])
        return f"{best['label']} · {best['match_label']}"

    @rx.var
    def best_row_probability(self) -> float:
        rows = self.filtered_rows
        if not rows:
            return 0.0
        return max(r["probability"] for r in rows)

    @rx.var
    def group_tabs(self) -> list[dict[str, str]]:
        rows = self.rows_cache
        tabs: list[dict[str, str]] = [
            {"key": "all", "label": "Сите групи", "count": str(len(rows))}
        ]
        for key, label in COMBO_GROUP_LABELS.items():
            tabs.append(
                {
                    "key": key,
                    "label": label,
                    "count": str(len([r for r in rows if r["group"] == key])),
                }
            )
        return tabs

    @rx.var
    def match_options(self) -> list[dict[str, str]]:
        options: list[dict[str, str]] = [
            {"key": "all", "label": "Сите натпревари"}
        ]
        seen: set[str] = set()
        for row in self.rows_cache:
            if row["match_id"] in seen:
                continue
            seen.add(row["match_id"])
            options.append(
                {"key": row["match_id"], "label": row["match_label"]}
            )
        return options

    @rx.var
    def market_tabs(self) -> list[dict[str, str]]:
        """Чипови за конкретните избори (1/X/2 и Над/Под) со број комбинации."""
        rows = self.rows_cache
        tabs: list[dict[str, str]] = []
        for key, label in MARKET_FILTER_LABELS.items():
            count = len([r for r in rows if key in r["market_tags"]])
            tabs.append({"key": key, "label": label, "count": str(count)})
        return tabs

    @rx.var
    def inline_filter_tabs(self) -> list[dict[str, str]]:
        """Еден ред чипови: групите, а веднаш по нив конкретните избори.

        Групните чипови (`kind = "group"`) го менуваат `group_filter`, а
        чиповите за конкретен избор (`kind = "market"`) го менуваат
        `market_filter`. Не се создава посебен таб ниту dropdown.
        """
        tabs: list[dict[str, str]] = []
        for tab in self.group_tabs:
            tabs.append(
                {
                    "key": tab["key"],
                    "label": tab["label"],
                    "count": tab["count"],
                    "kind": "group",
                }
            )
        for tab in self.market_tabs:
            tabs.append(
                {
                    "key": tab["key"],
                    "label": tab["label"],
                    "count": tab["count"],
                    "kind": "market",
                }
            )
        return tabs

    @rx.var
    def market_filter_label(self) -> str:
        if self.market_filter == "all":
            return "Сите избори"
        return MARKET_FILTER_LABELS.get(self.market_filter, "Сите избори")

    @rx.var
    def group_summaries(self) -> list[dict[str, str]]:
        rows = self.filtered_rows
        summaries: list[dict[str, str]] = []
        for key, label in COMBO_GROUP_LABELS.items():
            group = [r for r in rows if r["group"] == key]
            if not group:
                continue
            avg = sum(r["probability"] for r in group) / len(group)
            best = max(group, key=lambda r: r["probability"])
            summaries.append(
                {
                    "key": key,
                    "label": label,
                    "count": str(len(group)),
                    "avg": f"{avg:.1f}%",
                    "avg_width": f"{round(avg, 1)}%",
                    "recommended": str(
                        len([r for r in group if r["recommended"]])
                    ),
                    "best_label": best["label"],
                    "best_probability": f"{best['probability']:.1f}%",
                }
            )
        return summaries

    @rx.var
    def min_probability_label(self) -> str:
        return f"{self.min_probability:.0f}%"

    @rx.var
    def is_truncated(self) -> bool:
        return self.filtered_count > MAX_VISIBLE_ROWS

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows_cache) > 0

    @rx.event
    async def load(self):
        yield MarketsState.sync

    @rx.event
    async def sync(self):
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        self.error = bsd.error
        self.sync_from_matches(bsd.matches, bsd.generated_at)

    @rx.event
    def set_group_filter(self, group: str):
        self.group_filter = group

    @rx.event
    def set_status_filter(self, status: str):
        self.status_filter = status

    @rx.event
    def set_match_filter(self, match_id: str):
        self.match_filter = match_id

    @rx.event
    def set_market_filter(self, market: str):
        self.market_filter = market

    @rx.event
    def toggle_market_filter(self, market: str):
        """Чиповите за конкретен избор се вклучуваат/исклучуваат со клик.

        Кога се активира конкретен избор, групниот филтер се враќа на „Сите
        групи“ за да не остане празна табела од две стеснувања одеднаш.
        """
        if self.market_filter == market:
            self.market_filter = "all"
            return
        self.market_filter = market
        self.group_filter = "all"

    @rx.event
    def apply_inline_filter(self, key: str):
        """Еден клик од редот со чипови: група или конкретен избор.

        - група (или „Сите групи“) → го поставува `group_filter`
        - конкретен избор (1, X, 2, Над/Под 1.5 и 2.5) → го поставува
          `market_filter` и ја враќа групата на „Сите групи“ за да не
          останат две стеснувања одеднаш; повторен клик го исклучува.
        """
        if key == "all":
            self.group_filter = "all"
            self.market_filter = "all"
            return
        if key in COMBO_GROUP_LABELS:
            self.group_filter = key
            return
        if key in MARKET_FILTER_LABELS:
            if self.market_filter == key:
                self.market_filter = "all"
                return
            self.market_filter = key
            self.group_filter = "all"

    @rx.event
    def set_sort_key(self, key: str):
        self.sort_key = key

    @rx.event
    def set_min_probability(self, value: str):
        try:
            self.min_probability = float(value)
        except ValueError:
            self.min_probability = 0.0

    @rx.event
    def toggle_only_recommended(self):
        self.only_recommended = not self.only_recommended

    @rx.event
    def reset_filters(self):
        self.group_filter = "all"
        self.status_filter = "all"
        self.match_filter = "all"
        self.market_filter = "all"
        self.sort_key = "probability"
        self.min_probability = 40.0
        self.only_recommended = False
        return rx.toast("Филтрите се вратени на почетни", duration=2000)
