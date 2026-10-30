"""Отслеживание связи с сервером: пауза при обрыве, пересинхронизация и проверка версии сборки."""

import time

from client.network import ServerError, ServerUnavailableError


class ConnectionMonitor:
    ONLINE = "online"
    OFFLINE = "offline"
    OUTDATED = "outdated"

    POLL_SECONDS = 1.0
    FAILURES_BEFORE_OFFLINE = 2
    GRACE_SECONDS = 10.0

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self.state = self.ONLINE
        self.build_id = None
        self._offline_since = None
        self._failures = 0
        self._poll_elapsed = self.POLL_SECONDS
        self._reconnected = False

    @property
    def is_blocking(self):
        return self.state != self.ONLINE

    def remaining_seconds(self):
        if self.state != self.OFFLINE:
            return None
        return max(0.0, self.GRACE_SECONDS - (self._clock() - self._offline_since))

    def expired(self):
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0.0

    def take_reconnected(self):
        """Истина один раз после возврата из паузы или устаревшего состояния; нужна пересинхронизация."""
        reconnected, self._reconnected = self._reconnected, False
        return reconnected

    def update(self, session, dt):
        """Опрашивает сервер раз в POLL_SECONDS. Возвращает статус сервера или None, если ответа нет."""
        if session is None or not getattr(session, "character", None):
            self._reset()
            return None
        self._poll_elapsed += max(0.0, float(dt))
        if self._poll_elapsed < self.POLL_SECONDS:
            return None
        self._poll_elapsed = 0.0
        try:
            status = session.client.get_server_status()
        except ServerUnavailableError:
            self._failures += 1
            if self.state == self.ONLINE and self._failures >= self.FAILURES_BEFORE_OFFLINE:
                self._enter(self.OFFLINE)
            return None
        except ServerError:
            # Сервер ответил, но отказал (например, сессия истекла): связь есть
            self._failures = 0
            return None
        self._failures = 0
        self._apply_build(status.get("build_id"))
        return status

    def _apply_build(self, build_id):
        if not build_id:
            # Сервер без build_id (старая версия): сравнить версию не с чем
            if self.state == self.OFFLINE:
                self._leave_pause()
            return
        if self.build_id is None:
            self.build_id = build_id
        if build_id != self.build_id:
            self._enter(self.OUTDATED)
        elif self.state != self.ONLINE:
            self._leave_pause()

    def _leave_pause(self):
        self._enter(self.ONLINE)
        self._reconnected = True

    def _enter(self, state):
        self.state = state
        if state == self.OFFLINE:
            self._offline_since = self._clock()

    def _reset(self):
        self.state = self.ONLINE
        self._offline_since = None
        self._failures = 0
        self._reconnected = False
