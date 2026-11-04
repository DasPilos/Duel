import time

from client.background_polling import BackgroundPoller
from client.network import ServerError


class PresenceState:
    """Опрос сервера для локации: сообщения чата, кто рядом, путешествующие жители и обозы."""

    REFRESH_INTERVAL = 2.0
    TRAVEL_REFRESH_INTERVAL = 2.0

    def __init__(self, session, location, presence_provider=None, travelers_provider=None, convoys_provider=None):
        self.session = session
        self.location = location
        self.presence_provider = presence_provider
        self.travelers_provider = travelers_provider
        self.convoys_provider = convoys_provider
        self.occupants = []
        self.messages = []
        self.error = ""
        self.travelers = []
        self.travelers_refreshed_at = 0.0
        self.travelers_received_at = 0.0
        self.traveling_convoys = []
        self.convoys_refreshed_at = 0.0
        self.convoys_received_at = 0.0
        self.elapsed = 0.0
        self.background_poller = None
        if hasattr(session, "client") and hasattr(session, "social_snapshot"):
            self.background_poller = BackgroundPoller(self._fetch_remote_state)
            self.background_poller.start()
        elif hasattr(session, "social_snapshot"):
            self.refresh()

    def refresh(self):
        state, error = self._fetch_remote_state_with_error()
        if error is not None:
            self.error = str(error)
            return
        self._apply_remote_state(state)

    def update(self, dt):
        if self.background_poller is not None:
            state, error = self.background_poller.poll()
            if error is not None:
                self.error = str(error)
            elif state is not None:
                self._apply_remote_state(state)
            return
        self.elapsed += dt
        if self.elapsed >= self.REFRESH_INTERVAL:
            self.elapsed = 0
            self.refresh()

    def close(self):
        if self.background_poller is not None:
            self.background_poller.stop()

    def _fetch_remote_state(self):
        state, error = self._fetch_remote_state_with_error()
        if error is not None:
            raise error
        return state

    def _fetch_remote_state_with_error(self):
        try:
            if hasattr(self.session, "social_snapshot"):
                position = self.presence_provider() if self.presence_provider is not None else None
                if position is None:
                    state = self.session.social_snapshot(self.location)
                else:
                    state = self.session.social_snapshot(self.location, position=position)
                if self.travelers_provider is not None and time.monotonic() >= self.travelers_refreshed_at:
                    state["traveling_citizens"] = self.travelers_provider()
                    self.travelers_refreshed_at = time.monotonic() + self.TRAVEL_REFRESH_INTERVAL
                    state["travelers_received_at"] = time.monotonic()
                else:
                    state["traveling_citizens"] = self.travelers
                    state["travelers_received_at"] = self.travelers_received_at
                if self.convoys_provider is not None and time.monotonic() >= self.convoys_refreshed_at:
                    state["traveling_convoys"] = self.convoys_provider()
                    self.convoys_refreshed_at = time.monotonic() + self.TRAVEL_REFRESH_INTERVAL
                    state["convoys_received_at"] = time.monotonic()
                else:
                    state["traveling_convoys"] = self.traveling_convoys
                    state["convoys_received_at"] = self.convoys_received_at
                return state, None
            self.session.update_presence(self.location)
            occupants = sorted(self.session.list_occupants(self.location), key=lambda item: item.get("name", "").casefold())
            messages = self.session.list_messages(self.location)
            return {"occupants": occupants, "messages": messages}, None
        except ServerError as error:
            return None, error

    def _apply_remote_state(self, state):
        self.occupants = state["occupants"]
        self.travelers = state.get("traveling_citizens", self.travelers)
        self.travelers_received_at = state.get("travelers_received_at", self.travelers_received_at)
        self.messages = state["messages"]
        self.traveling_convoys = state.get("traveling_convoys", self.traveling_convoys)
        self.convoys_received_at = state.get("convoys_received_at", self.convoys_received_at)
        self.error = ""
