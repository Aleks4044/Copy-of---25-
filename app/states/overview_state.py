"""Почетна статистика изведена исклучиво од вистински API податоци."""

from typing import TypedDict

import reflex as rx

from app.states.bsd_state import BSDMatch, BSDState, local_clock


PICKS_LIMITS: dict[str, int] = {"top5": 5, "top10": 10, "top15": 15}

# Секој приказ добива свој (различен) мешан избор: ротација на редот на
# изворите и офсет во рамките на секој извор, така што „Топ 10“ не е само
# „Топ 5“ плус пет нови редови. Се користат само реални избори и реални
# сигурности од самите извори — ништо не се измислува.
PICKS_VIEWS: dict[str, dict[str, int]] = {
    "top5": {"limit": 5, "rotation": 0, "offset": 0},
    "top10": {"limit": 10, "rotation": 1, "offset": 1},
    "top15": {"limit": 15, "rotation": 2, "offset": 2},
}

# Тежинско наизменично мешање по извор: во секој круг се земаат до толку
# избори од секој извор, а внатре во изворот редот е по реална сигурност.
SOURCE_MIX: list[tuple[str, int]] = [
    ("bzz", 2),
    ("fotmob", 1),
    ("mutating", 1),
    ("sportscore", 1),
]
SOURCE_MIX_LABELS: dict[str, str] = {
    "bzz": "BZZ API",
    "fotmob": "Fotmob",
    "mutating": "Mutating",
    "sportscore": "SportScore",
}


class MatchPick(TypedDict):
    id: str
    kickoff: str
    league: str
    home: str
    away: str
    market: str
    pick: str
    confidence: float
    odds: float
    edge: float
    status: str
    source: str
    source_label: str
    has_odds: bool


class LeagueRow(TypedDict):
    league: str
    matches: int
    accuracy: float
    value_picks: int


class TrendPoint(TypedDict):
    day: str
    accuracy: float
    baseline: float


def _parse_pct(label: object) -> float | None:
    """Реален процент од Mutating ознака; None кога изворот не го објавува."""
    if not isinstance(label, str):
        return None
    cleaned = label.replace("%", "").strip()
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value <= 0.0 or value > 100.0:
        return None
    return round(value, 1)


def _is_correct(match: BSDMatch) -> bool | None:
    """Проверува дали избраниот 1X2 исход е точен според вистински резултат."""
    if not match["has_prediction"] or match["status"] != "finished":
        return None
    parts = match["score"].split("-")
    if len(parts) != 2:
        return None
    try:
        home = int(parts[0].strip())
        away = int(parts[1].strip())
    except ValueError:
        return None
    if match["pick_side"] == "home":
        return home > away
    if match["pick_side"] == "away":
        return away > home
    if match["pick_side"] == "draw":
        return home == away
    return None


class OverviewState(rx.State):
    """Агрегати за почетниот таб врз основа на API податоците."""

    picks: list[MatchPick] = []
    league_rows: list[LeagueRow] = []
    trend: list[TrendPoint] = []
    model_health: dict[str, float] = {
        "bsd_ml": 0.0,
        "poisson": 0.0,
        "meta": 0.0,
        "consensus": 0.0,
    }
    profit: float = 0.0
    settled_bets: int = 0
    won_bets: int = 0
    missing_predictions: int = 0
    generated_at: str = "--:--:--"
    error: str = ""
    picks_view: str = "top5"

    @rx.var
    def total_picks(self) -> int:
        return len(self.picks)

    @rx.var
    def live_count(self) -> int:
        return len([p for p in self.picks if p["status"] == "live"])

    @rx.var
    def finished_count(self) -> int:
        return len([p for p in self.picks if p["status"] == "finished"])

    @rx.var
    def upcoming_count(self) -> int:
        return len([p for p in self.picks if p["status"] == "upcoming"])

    @rx.var
    def avg_confidence(self) -> float:
        if not self.picks:
            return 0.0
        return round(
            sum(p["confidence"] for p in self.picks) / len(self.picks), 1
        )

    @rx.var
    def high_confidence_count(self) -> int:
        return len([p for p in self.picks if p["confidence"] >= 72.0])

    @rx.var
    def avg_edge(self) -> float:
        rows = [p for p in self.picks if p["has_odds"]]
        if not rows:
            return 0.0
        return round(sum(p["edge"] for p in rows) / len(rows), 2)

    @rx.var
    def bzz_pick_count(self) -> int:
        return len([p for p in self.picks if p["source"] == "bzz"])

    @rx.var
    def fotmob_pick_count(self) -> int:
        return len([p for p in self.picks if p["source"] == "fotmob"])

    @rx.var
    def mutating_pick_count(self) -> int:
        return len([p for p in self.picks if p["source"] == "mutating"])

    @rx.var
    def sportscore_pick_count(self) -> int:
        return len([p for p in self.picks if p["source"] == "sportscore"])

    @rx.var
    def hit_rate(self) -> float:
        if self.settled_bets == 0:
            return 0.0
        return round(self.won_bets / self.settled_bets * 100, 1)

    @rx.var
    def roi(self) -> float:
        if self.settled_bets == 0:
            return 0.0
        return round(self.profit / self.settled_bets * 100, 2)

    def _rotate(self, rows: list[MatchPick], offset: int) -> list[MatchPick]:
        if not rows or offset <= 0:
            return rows
        shift = offset % len(rows)
        return rows[shift:] + rows[:shift]

    def _mix(self, rotation: int, offset: int) -> list[MatchPick]:
        """Наизменично (тежинско round-robin) мешање по извор.

        `rotation` ротира кој извор започнува кругот, а `offset` ротира
        редот на изборите во рамките на секој извор. Внатре во изворот
        основниот ред е по реална сигурност (најсилно прво). Ако некој
        извор нема редови, кругот продолжува од останатите — не се
        измислуваат вредности.
        """
        buckets: dict[str, list[MatchPick]] = {}
        for source, _weight in SOURCE_MIX:
            buckets[source] = self._rotate(
                sorted(
                    [p for p in self.picks if p["source"] == source],
                    key=lambda p: -p["confidence"],
                ),
                offset,
            )
        turn = rotation % len(SOURCE_MIX) if SOURCE_MIX else 0
        order = SOURCE_MIX[turn:] + SOURCE_MIX[:turn]
        ordered: list[MatchPick] = []
        while any(buckets[source] for source, _weight in order):
            for source, weight in order:
                bucket = buckets[source]
                for _ in range(weight):
                    if not bucket:
                        break
                    ordered.append(bucket.pop(0))
        known = {source for source, _weight in SOURCE_MIX}
        rest = self._rotate(
            sorted(
                [p for p in self.picks if p["source"] not in known],
                key=lambda p: -p["confidence"],
            ),
            offset,
        )
        return ordered + rest

    @rx.var
    def mixed_picks(self) -> list[MatchPick]:
        return self._mix(0, 0)

    @rx.var
    def top_picks(self) -> list[MatchPick]:
        view = PICKS_VIEWS.get(self.picks_view, PICKS_VIEWS["top5"])
        rows = self._mix(view["rotation"], view["offset"])
        return rows[: view["limit"]]

    @rx.var
    def top_picks_mix_label(self) -> str:
        rows = self.top_picks
        if not rows:
            return "Нема избори за мешање по извор"
        parts: list[str] = []
        for source, label in SOURCE_MIX_LABELS.items():
            count = len([p for p in rows if p["source"] == source])
            if count:
                parts.append(f"{count} {label}")
        if not parts:
            return "Нема избори за мешање по извор"
        return "Мешано по извор: " + " · ".join(parts)

    @rx.var
    def top10_available(self) -> int:
        return min(10, len(self.picks))

    @rx.var
    def top15_available(self) -> int:
        """Колку избори реално се достапни за приказот „Топ 15“."""
        return min(PICKS_LIMITS["top15"], len(self.picks))

    @rx.event
    def set_picks_view(self, view: str):
        self.picks_view = view if view in PICKS_LIMITS else "top5"

    @rx.var
    def confidence_label(self) -> str:
        if not self.picks:
            return "Нема предвидувања"
        if self.avg_confidence >= 74:
            return "Многу висока"
        if self.avg_confidence >= 68:
            return "Стабилна"
        return "Умерена"

    @rx.var
    def has_data(self) -> bool:
        return len(self.picks) > 0

    def _mutating_picks(
        self, rows: list[dict], covered: set[str]
    ) -> list[MatchPick]:
        """Избори од Mutating редови со реални проценти од страницата за детали.

        Не се измислува квота ниту сигурност: сигурноста е точно објавениот
        процент на најсилниот маркет, а квотата останува недостапна.
        """
        picks: list[MatchPick] = []
        for row in rows:
            if not (
                row.get("has_names")
                and row.get("has_pick")
                and row.get("has_markets")
            ):
                continue
            fixture_id = str(row.get("fixture_id") or "")
            if not fixture_id or fixture_id in covered:
                continue
            options: list[tuple[float, str]] = []
            for key, label in (
                ("btts_label", "ГГ · двата тима"),
                ("ng_label", "НГ · без ГГ"),
                ("over15_label", "Над 1.5 гола"),
                ("under15_label", "Под 1.5 гола"),
                ("over25_label", "Над 2.5 гола"),
                ("under25_label", "Под 2.5 гола"),
            ):
                value = _parse_pct(row.get(key))
                if value is not None:
                    options.append((value, label))
            if not options:
                continue
            confidence, pick_label = max(options, key=lambda item: item[0])
            published = str(row.get("pick") or "").strip()
            market = (
                f"Mutating маркет · објавен избор {published}"
                if published and published != "—"
                else "Mutating маркет од страницата за детали"
            )
            kickoff = str(row.get("kickoff") or "")
            if not kickoff or kickoff == "—":
                kickoff = str(row.get("status") or "—")
            status_kind = str(row.get("status_kind") or "upcoming")
            picks.append(
                MatchPick(
                    id=f"mutating-{fixture_id}",
                    kickoff=kickoff,
                    league=str(row.get("league_label") or "—"),
                    home=str(row.get("home") or ""),
                    away=str(row.get("away") or ""),
                    market=market,
                    pick=pick_label,
                    confidence=confidence,
                    odds=0.0,
                    edge=0.0,
                    status=status_kind,
                    source="mutating",
                    source_label="Mutating",
                    has_odds=False,
                )
            )
        return picks

    def _sportscore_picks(self, rows: list[dict]) -> list[MatchPick]:
        """Избори од SportScore само кога има реални статистики и тоа́ за
        настани непокриени од BZZ/Fotmob/Mutating. Без квоти.
        """
        picks: list[MatchPick] = []
        for row in rows:
            if row.get("covered") or not row.get("has_prediction"):
                continue
            confidence = row.get("meta_confidence") or 0.0
            if not isinstance(confidence, (int, float)) or confidence <= 0.0:
                continue
            picks.append(
                MatchPick(
                    id=str(row.get("id") or ""),
                    kickoff=str(row.get("kickoff") or "--:--"),
                    league=str(row.get("competition") or "—"),
                    home=str(row.get("home") or ""),
                    away=str(row.get("away") or ""),
                    market=str(
                        row.get("meta_market")
                        or "Meta-Ensemble · SportScore статистики"
                    ),
                    pick=str(row.get("meta_pick") or ""),
                    confidence=round(float(confidence), 1),
                    odds=0.0,
                    edge=0.0,
                    status=str(row.get("status") or "upcoming"),
                    source="sportscore",
                    source_label="SportScore",
                    has_odds=False,
                )
            )
        return picks

    def _derive(
        self,
        matches: list[BSDMatch],
        generated_at: str,
        mutating_rows: list[dict] | None = None,
        covered: set[str] | None = None,
        sportscore_rows: list[dict] | None = None,
    ) -> None:
        picks: list[MatchPick] = []
        for match in matches:
            if not match["has_prediction"]:
                continue
            is_fotmob = match["source"] == "fotmob"
            picks.append(
                MatchPick(
                    id=match["id"],
                    kickoff=match["kickoff"],
                    league=match["league"],
                    home=match["home"],
                    away=match["away"],
                    market=match["meta_market"],
                    pick=match["meta_pick"],
                    confidence=match["meta_confidence"],
                    odds=match["meta_odds"],
                    edge=match["meta_edge"],
                    status=match["status"],
                    source="fotmob" if is_fotmob else "bzz",
                    source_label="Fotmob" if is_fotmob else "BZZ API",
                    has_odds=match["meta_odds"] > 1.0,
                )
            )
        picks.extend(
            self._mutating_picks(mutating_rows or [], covered or set())
        )
        picks.extend(self._sportscore_picks(sportscore_rows or []))
        self.picks = picks
        self.missing_predictions = len(
            [m for m in matches if not m["has_prediction"]]
        )

        settled = 0
        won = 0
        profit = 0.0
        by_day: dict[str, list[bool]] = {}
        for match in matches:
            correct = _is_correct(match)
            if correct is None:
                continue
            settled += 1
            won += 1 if correct else 0
            profit += (match["meta_odds"] - 1.0) if correct else -1.0
            day = match["day_label"] or "Денес"
            by_day.setdefault(day, []).append(correct)
        self.settled_bets = settled
        self.won_bets = won
        self.profit = round(profit, 2)

        trend: list[TrendPoint] = []
        for day in sorted(by_day.keys()):
            results = by_day[day]
            trend.append(
                TrendPoint(
                    day=day[-5:],
                    accuracy=round(
                        sum(1 for r in results if r) / len(results) * 100, 1
                    ),
                    baseline=50.0,
                )
            )
        self.trend = trend

        predicted = [m for m in matches if m["has_prediction"]]
        if predicted:
            self.model_health = {
                "bsd_ml": round(
                    sum(m["ml_confidence"] for m in predicted) / len(predicted),
                    1,
                ),
                "poisson": round(
                    sum(m["poi_over25"] for m in predicted) / len(predicted), 1
                ),
                "meta": round(
                    sum(m["meta_confidence"] for m in predicted)
                    / len(predicted),
                    1,
                ),
                "consensus": round(
                    sum(m["meta_agreement"] for m in predicted)
                    / len(predicted),
                    1,
                ),
            }
        else:
            self.model_health = {
                "bsd_ml": 0.0,
                "poisson": 0.0,
                "meta": 0.0,
                "consensus": 0.0,
            }

        leagues: dict[str, list[BSDMatch]] = {}
        for match in matches:
            leagues.setdefault(match["league"], []).append(match)
        rows: list[LeagueRow] = []
        for league, group in leagues.items():
            results = [
                r for r in (_is_correct(m) for m in group) if r is not None
            ]
            rows.append(
                LeagueRow(
                    league=league,
                    matches=len(group),
                    accuracy=(
                        round(
                            sum(1 for r in results if r) / len(results) * 100, 1
                        )
                        if results
                        else 0.0
                    ),
                    value_picks=len(
                        [
                            m
                            for m in group
                            if m["has_prediction"] and m["meta_edge"] >= 2.0
                        ]
                    ),
                )
            )
        self.league_rows = sorted(rows, key=lambda r: -r["matches"])[:8]
        self.generated_at = generated_at or local_clock()

    @rx.event
    async def sync(self):
        from app.states.mutating_state import MutatingState
        from app.states.sportscore_state import SportScoreState

        bsd = await self.get_state(BSDState)
        mutating = await self.get_state(MutatingState)
        sportscore = await self.get_state(SportScoreState)
        self.error = bsd.error
        self._derive(
            bsd.matches,
            bsd.generated_at,
            [dict(row) for row in mutating.rows],
            set(mutating.covered_keys),
            [dict(row) for row in sportscore.rows],
        )

    @rx.event
    async def load(self):
        yield OverviewState.sync
