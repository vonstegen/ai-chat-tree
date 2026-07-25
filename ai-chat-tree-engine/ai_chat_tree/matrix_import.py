"""Matrix conversation importer for ai-chat-tree.

Handles importing a Matrix chat room (DM or group) into the ai-chat-tree
vault by fetching messages via the Matrix Client-Server API and mapping
them to Turno objects.

Designed to work with ANY Matrix homeserver, but built first for the
VIGIL Synapse instance used in the Hermes-VIGIL inference cycle.
"""
import requests
from typing import Optional, Tuple


class MatrixImporter:
    """Handles auth, message fetching, and conversation reconstruction."""

    def __init__(self,
                 homeserver: str,
                 user_id: str,
                 password: Optional[str] = None,
                 access_token: Optional[str] = None):
        """
        Args:
            homeserver: Base URL of the Matrix homeserver (e.g.
                https://gx10-b71c.tail76c714.ts.net)
            user_id: Full user ID (e.g. @vigil:gx10-b71c.tail76c714.ts.net)
            password: Password for password-based login.
            access_token: Pre-existing access token (skips login).
        """
        # Strip trailing slash to avoid double-slash issues
        self.homeserver = homeserver.rstrip('/')
        self.user_id = user_id
        self.access_token = access_token

        if not self.access_token and password:
            self._login(password)

    def _login(self, password: str) -> str:
        """Authenticate via password login and cache the token."""
        url = f"{self.homeserver}/_matrix/client/v3/login"
        resp = requests.post(url, json={
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": self.user_id},
            "password": password,
        })
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.base_url = data.get("home_server", self.homeserver)
        return self.access_token

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    def resolve_room(self, identifier: str) -> str:
        """
        Accept a room alias, room ID, or element URL and return room ID.

        Examples:
            #matrix.org
            !abc123:example.com
            https://app.element.io/#/room/!abc123:example.com
        """
        # If it looks like a room alias
        if identifier.startswith("#"):
            url = f"{self.homeserver}/_matrix/client/v3/directory/room/{identifier}"
            resp = requests.get(url, headers=self._auth_headers())
            resp.raise_for_status()
            room_data = resp.json()
            return room_data["room_id"]

        # If it's already a room ID
        if identifier.startswith("!"):
            return identifier

        # Try to extract room ID from a URL
        if "element.io" in identifier or "app." in identifier:
            parts = identifier.split("/")
            for i, part in enumerate(parts):
                if part.startswith("!") and i > 0 and parts[i-1] == "#/room":
                    return part
            # Fallback: last part after #/room/
            idx = identifier.find("/room/")
            if idx >= 0:
                candidate = identifier[idx+6:].split("#")[0]
                if candidate.startswith("!"):
                    return candidate

        raise ValueError(f"Cannot resolve room identifier: {identifier}")

    def fetch_messages(self, room_id: str,
                       from_token: Optional[str] = None,
                       limit: int = 100) -> Tuple[list, str]:
        """
        Fetch messages from a room via the /messages endpoint.

        Returns (message_records, next_token).
        Each message_record is a dict with keys:
            event_id, sender, timestamp, type, content, sender_is_ai
        """
        url = f"{self.homeserver}/_matrix/client/v3/rooms/{room_id}/messages"
        params = {
            "dir": "b",  # backwards from current point
            "limit": limit,
        }
        if from_token:
            params["from"] = from_token

        resp = requests.get(url, headers=self._auth_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("chunk", [])
        end_token = data.get("end", from_token)

        return [self._parse_event(e) for e in events], end_token

    def _parse_event(self, event: dict) -> dict:
        """Normalize a Matrix event into a conversation record."""
        sender = event.get("sender", "")
        msg = event.get("msgtype", "m.text")
        content = event.get("content", {})

        body = content.get("body", "")
        # Handle formatted_body for HTML
        formatted = content.get("formatted_body", body)

        return {
            "event_id": event.get("event_id", ""),
            "sender": sender,
            "timestamp": event.get("origin_server_ts", 0),
            "type": event.get("type", "m.room.message"),
            "msgtype": msg,
            "body": body,
            "formatted_body": formatted if formatted != body else None,
            "sender_is_ai": False,  # Set by conversation mapper later
            "mimetype": content.get("mimetype") if isinstance(content, dict) else None,
        }

    def fetch_all_conversation(self, room_id: str,
                                limit: int = 100) -> list:
        """
        Paginate through ALL messages in a room, oldest first.

        Returns a list of message records sorted chronologically.
        Caller should set sender_is_ai before passing if they have a bot ID.
        """
        all_events = []
        next_token = None

        while True:
            events, end_token = self.fetch_messages(room_id,
                                                     from_token=next_token,
                                                     limit=limit)
            if not events:
                break
            all_events.extend(events)
            if end_token == next_token:
                break
            next_token = end_token

        # Reverse to chronological order
        all_events.reverse()
        return all_events

    def fetch_rooms(self) -> list:
        """Get all rooms the authenticated user belongs to."""
        url = f"{self.homeserver}/_matrix/client/v3/joined_rooms"
        resp = requests.get(url, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json().get("joined_rooms", [])

    @staticmethod
    def extract_text_content(content: dict) -> str:
        """Extract plain text from various Matrix message content types."""
        if "body" in content:
            return content["body"]
        if "caption" in content:  # m.image, m.audio, etc.
            return content.get("body", content.get("caption", ""))
        # m.file type
        return content.get("body", f"[{content.get('msgtype', 'file')}]")
