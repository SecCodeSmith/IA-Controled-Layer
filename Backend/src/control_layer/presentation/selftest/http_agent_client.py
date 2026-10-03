from __future__ import annotations

from typing import Any

import httpx

from control_layer.application.selftest.agent_events import observations_from_events
from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.domain.exceptions import AgentUnavailableError
from control_layer.presentation.selftest.in_process_client import InProcessScenarioClient


class AgentTierScenarioClient(InProcessScenarioClient):
    def __init__(self, *args: Any, agent_url: str, timeout_s: float = 180.0) -> None:
        super().__init__(*args)
        self._agent_url = agent_url.rstrip("/")
        self._timeout_s = timeout_s

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(
                    f"{self._agent_url}/agent/chat",
                    json={"session_id": session_id, "message": prompt},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            raise AgentUnavailableError(
                f"demo agent unreachable at {self._agent_url}: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise AgentUnavailableError(f"demo agent returned {response.status_code}")
        observations = observations_from_events(response.json().get("events", []))
        self.remember_escalations(observations)
        return observations
