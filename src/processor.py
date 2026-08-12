"""Pure event-time deduplication and rolling-window processing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from src.contract import KpEvent


WINDOW_MINUTES = 15
WINDOW_DURATION = timedelta(minutes=WINDOW_MINUTES)


class ProcessingStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    LATE_EVENT_SKIPPED = "late_event_skipped"


@dataclass(frozen=True)
class ProcessingResult:
    event: KpEvent
    rolling_15m_max_kp: float | None
    status: ProcessingStatus

    @property
    def accepted(self) -> bool:
        return self.status is ProcessingStatus.ACCEPTED


class RollingKpProcessor:
    """Maintain an inclusive rolling event-time window for an ordered Kp stream.

    Duplicate identity is ``time_tag``. A duplicate or event older than the latest
    accepted timestamp is reported but does not change any processor state.
    """

    def __init__(self, *, window: timedelta = WINDOW_DURATION) -> None:
        if window <= timedelta(0):
            raise ValueError("window must be positive")
        self._window = window
        self._events: deque[KpEvent] = deque()
        self._seen_time_tags: set[datetime] = set()
        self._latest_time_tag: datetime | None = None
        self._messages_seen = 0
        self._accepted_count = 0
        self._duplicate_count = 0
        self._late_count = 0

    @property
    def window(self) -> timedelta:
        return self._window

    @property
    def latest_time_tag(self) -> datetime | None:
        return self._latest_time_tag

    @property
    def rolling_max(self) -> float | None:
        if not self._events:
            return None
        return max(event.kp_value for event in self._events)

    @property
    def window_events(self) -> tuple[KpEvent, ...]:
        return tuple(self._events)

    @property
    def messages_seen(self) -> int:
        return self._messages_seen

    @property
    def accepted_count(self) -> int:
        return self._accepted_count

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count

    @property
    def late_count(self) -> int:
        return self._late_count

    def process(self, event: KpEvent) -> ProcessingResult:
        self._messages_seen += 1

        if event.time_tag in self._seen_time_tags:
            self._duplicate_count += 1
            return ProcessingResult(
                event=event,
                rolling_15m_max_kp=self.rolling_max,
                status=ProcessingStatus.DUPLICATE_SKIPPED,
            )

        if self._latest_time_tag is not None and event.time_tag < self._latest_time_tag:
            self._late_count += 1
            return ProcessingResult(
                event=event,
                rolling_15m_max_kp=self.rolling_max,
                status=ProcessingStatus.LATE_EVENT_SKIPPED,
            )

        self._events.append(event)
        self._seen_time_tags.add(event.time_tag)
        self._latest_time_tag = event.time_tag
        self._accepted_count += 1

        cutoff = event.time_tag - self._window
        while self._events and self._events[0].time_tag < cutoff:
            self._events.popleft()

        return ProcessingResult(
            event=event,
            rolling_15m_max_kp=self.rolling_max,
            status=ProcessingStatus.ACCEPTED,
        )
