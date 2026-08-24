import requests
from typing import Optional


class MemoryClient:
    """Thin client for the MemActBench memory API."""

    def __init__(
        self,
        user_id: str,
        memory_system_name: str = "mirix",
        base_url: str = "http://0.0.0.0:8000",
        session: Optional[requests.Session] = None,
        timeout: int = 300,
        budget_tokens: Optional[int] = None,
    ):
        self.user_id = str(user_id)
        self.memory_system_name = memory_system_name
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        init_payload = {"user_id": self.user_id, "memory_system_name": self.memory_system_name}
        if budget_tokens is not None:
            # Per-episode compression budget for the budget sweep (Gate D / usable-base-rate
            # search) — a fixed token cap for this user_id's memory backend, computed elsewhere
            # as a fraction of that episode's own accumulated-history size.
            init_payload["budget_tokens"] = budget_tokens
        self._post("/memory/initialize", init_payload)

    def wrap_user_prompt(self, question: str) -> str:
        """Request a prompt wrapped with memory context."""
        data = self._post(
            "/memory/wrap_user_prompt",
            {
                "user_id": self.user_id,
                "memory_system_name": self.memory_system_name,
                "question": question,
            },
        )
        return data["prompt"]

    def add(self, chunk: str) -> dict:
        """Add a chunk to the user's memory."""
        return self._post(
            "/memory/add",
            {"user_id": self.user_id, "memory_system_name": self.memory_system_name, "chunk": chunk},
        )

    def _post(self, path: str, payload: dict) -> dict:
        response = self.session.post(
            f"{self.base_url}{path}", json=payload, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
