import reflex as rx

from app.components.api_status import error_banner, unavailable_note
from app.states.comparison_state import ComparisonRow, ComparisonState


def _chip(label: str, value: rx.Var | str, icon: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3.5 w-3.5 text-zinc-500"),
        rx.el.span(label, class_name="text-[11px] font-medium text-zinc-500"),
        rx.el.span(
            value,
            class_name="text-xs font-semibold text-zinc-200 tabular-nums",
        ),
        class_name="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-1.5",
    )


def _header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                "BZZ vs Fotmob",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Вчитано во {ComparisonState.generated_at} · споредени се само натпревари со реално BZZ предвидување и совпаднати Fotmob статистики",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip(
                "Споредби",
                ComparisonState.total_count.to_string(),
                "git-compare",
            ),
            _chip(
                "Согласност",
                f"{ComparisonState.agreement_rate:.1f}%",
                "handshake",
            ),
            _chip(
                "Решени",
                ComparisonState.settled_count.to_string(),
                "circle-check",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
    )


def _kpi_card(
    label: str, value: rx.Var | str, hint: rx.Var | str, icon: str, accent: str
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                label,
                class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.div(rx.icon(icon, class_name="h-4 w-4"), class_name=accent),
            class_name="flex items-start justify-between gap-3",
        ),
        rx.el.p(
            value,
            class_name="mt-3 text-2xl font-semibold tracking-tight text-white tabular-nums sm:text-3xl",
        ),
        rx.el.p(
            hint, class_name="mt-1 truncate text-xs font-medium text-zinc-500"
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 transition-colors hover:border-zinc-700",
    )


def _kpi_grid() -> rx.Component:
    return rx.el.div(
        _kpi_card(
            "Согласни избори",
            ComparisonState.agree_count.to_string(),
            f"{ComparisonState.disagree_count} различни избори",
            "handshake",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        _kpi_card(
            "Средна сигурност BZZ",
            f"{ComparisonState.avg_bzz_confidence:.1f}%",
            "Meta избор од BZZ API",
            "database",
            "flex size-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        ),
        _kpi_card(
            "Средна сигурност Fotmob",
            f"{ComparisonState.avg_fotmob_confidence:.1f}%",
            "Форма + Poisson од Fotmob",
            "database-zap",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        _kpi_card(
            "Решени точни",
            f"{ComparisonState.bzz_wins} : {ComparisonState.fotmob_wins}",
            "BZZ : Fotmob по вистински резултат",
            "trophy",
            "flex size-8 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400",
        ),
        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
    )


def _filter_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                ComparisonState.filter_mode == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: ComparisonState.set_filter_mode(tab["key"]),
        class_name=rx.cond(
            ComparisonState.filter_mode == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.foreach(ComparisonState.filter_tabs, _filter_tab),
            class_name="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
        ),
        rx.el.div(
            rx.el.select(
                rx.el.option("Сигурност", value="confidence"),
                rx.el.option("Предност", value="edge"),
                rx.el.option("Натпревар", value="match"),
                default_value=ComparisonState.sort_key,
                on_change=ComparisonState.set_sort_key,
                class_name="w-full appearance-none rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 pr-9 text-xs font-semibold text-zinc-300 outline-hidden transition-colors hover:border-zinc-700 focus:border-blue-500/50 sm:text-sm",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500",
            ),
            class_name="relative w-full sm:w-52",
        ),
        class_name="mt-4 flex w-full flex-col gap-2 sm:flex-row sm:items-center",
    )


def _side_panel(
    source: str,
    icon: str,
    market: rx.Var,
    pick: rx.Var,
    confidence: rx.Var,
    edge: rx.Var,
    is_winner: rx.Var,
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon(icon, class_name="h-3.5 w-3.5"),
                rx.el.span(
                    source,
                    class_name="text-[10px] font-bold uppercase tracking-wider",
                ),
                class_name=rx.cond(
                    is_winner,
                    "flex w-fit items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-blue-300",
                    "flex w-fit items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-zinc-400",
                ),
            ),
            rx.el.span(
                f"{confidence:.1f}%",
                class_name=rx.cond(
                    is_winner,
                    "text-sm font-semibold text-blue-300 tabular-nums",
                    "text-sm font-semibold text-zinc-300 tabular-nums",
                ),
            ),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.p(
            pick,
            class_name="mt-2 truncate text-sm font-semibold text-white",
        ),
        rx.el.p(
            market,
            class_name="truncate text-[10px] font-medium text-zinc-600",
        ),
        rx.el.div(
            rx.el.div(
                class_name=rx.cond(
                    is_winner,
                    "h-full rounded-full bg-blue-500 transition-all duration-700",
                    "h-full rounded-full bg-zinc-600 transition-all duration-700",
                ),
                style={"width": f"{confidence}%"},
            ),
            class_name="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.p(
            f"предност {edge:.2f} п.п.",
            class_name="mt-1.5 text-[10px] font-medium text-zinc-500 tabular-nums",
        ),
        class_name="flex w-full min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 p-3",
    )


def _verdict(row: ComparisonRow) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            row["verdict_label"],
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            row["winner_label"],
            class_name=rx.match(
                row["winner"],
                (
                    "bzz",
                    "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
                ),
                (
                    "fotmob",
                    "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
                ),
                (
                    "none",
                    "w-fit whitespace-nowrap rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300",
                ),
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
        ),
        class_name="mt-3 flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _status_pill(row: ComparisonRow) -> rx.Component:
    return rx.el.span(
        rx.match(
            row["status"],
            ("live", "Во тек"),
            ("finished", "Завршен"),
            row["kickoff"],
        ),
        class_name=rx.match(
            row["status"],
            (
                "live",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
            ),
            (
                "finished",
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _comparison_card(row: ComparisonRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    row["match_label"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.div(
                    rx.el.span(
                        row["league"],
                        class_name="truncate text-[10px] font-medium text-zinc-600",
                    ),
                    _status_pill(row),
                    rx.el.span(
                        row["score"],
                        class_name="whitespace-nowrap text-[10px] font-semibold text-zinc-400 tabular-nums",
                    ),
                    class_name="mt-1 flex flex-wrap items-center gap-2",
                ),
                class_name="min-w-0 flex-1",
            ),
            rx.el.span(
                rx.cond(row["agree"], "Согласни", "Различни"),
                class_name=rx.cond(
                    row["agree"],
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
                ),
            ),
            class_name="flex items-start gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.el.div(
                _side_panel(
                    "BZZ API",
                    "database",
                    row["bzz_market"],
                    row["bzz_pick"],
                    row["bzz_confidence"],
                    row["bzz_edge"],
                    row["winner"] == "bzz",
                ),
                _side_panel(
                    "Fotmob",
                    "database-zap",
                    row["fm_market"],
                    row["fm_pick"],
                    row["fm_confidence"],
                    row["fm_edge"],
                    row["winner"] == "fotmob",
                ),
                class_name="grid grid-cols-1 gap-3 sm:grid-cols-2",
            ),
            _verdict(row),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def comparison_view() -> rx.Component:
    return rx.el.div(
        _header(),
        error_banner(ComparisonState.error),
        rx.cond(
            ComparisonState.has_data,
            rx.el.div(
                _kpi_grid(),
                _controls(),
                rx.cond(
                    ComparisonState.visible_count > 0,
                    rx.el.div(
                        rx.foreach(
                            ComparisonState.filtered_rows, _comparison_card
                        ),
                        class_name="mt-4 grid w-full grid-cols-1 gap-4 2xl:grid-cols-2",
                    ),
                    rx.el.div(
                        rx.icon("filter-x", class_name="h-6 w-6 text-zinc-600"),
                        rx.el.p(
                            "Нема споредби за избраниот филтер",
                            class_name="mt-2 text-sm font-medium text-zinc-500",
                        ),
                        class_name="mt-4 flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
                    ),
                ),
                class_name="w-full",
            ),
            unavailable_note(
                rx.cond(
                    ComparisonState.notice != "",
                    ComparisonState.notice,
                    "Нема совпаднати Fotmob статистики за BZZ натпреварите, па споредбата не е достапна",
                )
            ),
        ),
        class_name="w-full",
    )
