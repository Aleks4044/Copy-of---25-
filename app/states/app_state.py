import asyncio
from datetime import datetime

import reflex as rx


class AppState(rx.State):
    """Навигација помеѓу главните табови и автоматско освежување."""

    active_tab: str = "home"
    auto_refresh: bool = True
    base_interval: int = 45
    backoff_interval: int = 180
    refresh_interval: int = 45
    seconds_until_refresh: int = 45
    backoff_active: bool = False
    is_refreshing: bool = False
    loop_active: bool = False
    last_updated: str = "--:--:--"

    @rx.var
    def refresh_progress(self) -> float:
        if self.refresh_interval <= 0:
            return 0.0
        elapsed = self.refresh_interval - self.seconds_until_refresh
        return round(elapsed / self.refresh_interval * 100, 1)

    @rx.var
    def refresh_label(self) -> str:
        if not self.auto_refresh:
            return "Автоматско освежување: исклучено"
        if self.backoff_active:
            return (
                "Ограничено од API-то · следно освежување за "
                f"{self.seconds_until_refresh}с"
            )
        return f"Следно освежување за {self.seconds_until_refresh}с"

    async def _apply_backoff(self) -> None:
        """Го зголемува интервалот кога API-то врати 429."""
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        self.backoff_active = bsd.rate_limited
        self.refresh_interval = (
            self.backoff_interval if bsd.rate_limited else self.base_interval
        )
        if self.seconds_until_refresh > self.refresh_interval:
            self.seconds_until_refresh = self.refresh_interval

    @rx.event
    def set_tab(self, tab: str):
        self.active_tab = tab

    @rx.event
    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        self.seconds_until_refresh = self.refresh_interval
        message = (
            "Автоматското освежување е вклучено"
            if self.auto_refresh
            else "Автоматското освежување е паузирано"
        )
        return rx.toast(message, duration=2000)

    @rx.event
    async def refresh_now(self):
        from app.states.bsd_state import BSDState
        from app.states.comparison_state import ComparisonState
        from app.states.markets_state import MarketsState
        from app.states.models_state import ModelsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState

        self.is_refreshing = True
        self.seconds_until_refresh = self.refresh_interval
        yield
        # Прво BZZ/Fotmob, потоа Mutating покриеноста, и на крај агрегатите.
        yield BSDState.refresh_data
        yield MutatingState.refresh
        yield MutatingState.sync_coverage
        yield OverviewState.sync
        yield MarketsState.sync
        yield ComparisonState.sync
        yield ModelsState.sync
        await self._apply_backoff()
        self.last_updated = datetime.now().strftime("%H:%M:%S")
        self.is_refreshing = False

    @rx.event(background=True)
    async def start_clock(self):
        async with self:
            if self.loop_active:
                return
            self.loop_active = True
            self.last_updated = datetime.now().strftime("%H:%M:%S")

        while True:
            await asyncio.sleep(1)
            do_refresh = False
            async with self:
                if not self.auto_refresh:
                    continue
                self.seconds_until_refresh -= 1
                if self.seconds_until_refresh <= 0:
                    self.seconds_until_refresh = self.refresh_interval
                    self.is_refreshing = True
                    do_refresh = True

            if not do_refresh:
                continue

            from app.states.bsd_state import BSDState
            from app.states.comparison_state import ComparisonState
            from app.states.markets_state import MarketsState
            from app.states.models_state import ModelsState
            from app.states.mutating_state import MutatingState
            from app.states.overview_state import OverviewState

            yield BSDState.refresh_data
            yield MutatingState.refresh
            yield MutatingState.sync_coverage
            yield OverviewState.sync
            yield MarketsState.sync
            yield ComparisonState.sync
            yield ModelsState.sync

            async with self:
                await self._apply_backoff()
                self.last_updated = datetime.now().strftime("%H:%M:%S")
                self.is_refreshing = False
