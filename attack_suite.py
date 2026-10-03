#!/usr/bin/env python
"""Judge-facing self-test: runs the shared scenario catalogue against a live control layer."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from typing import Any

import httpx

from control_layer.application.selftest.agent_events import (
    LLM_TARGET,
    observations_from_events,
)
from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.selftest.scenario_executor import (
    ScenarioExecutor,
    ScenarioResult,
    ScenarioStatus,
)
from control_layer.domain.exceptions import AgentUnavailableError
from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.selftest.scenarios import SCENARIOS, Scenario

_FAILING_NEGATIVE = {ScenarioStatus.SUCCEEDED, ScenarioStatus.ERROR}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def edit_claims(token: str, changes: dict[str, Any]) -> str:
    header, payload, signature = token.split(".")
    claims = json.loads(_unb64(payload))
    claims.update(changes)
    forged = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{header}.{forged}.{signature}"


def _stage(value: str | None) -> StageName | None:
    return StageName(value) if value else None


def _from_error_body(http_status: int, body: dict) -> StepObservation:
    error = body.get("error", {})
    return StepObservation(
        http_status=http_status,
        status=CallStatus(error.get("status") or "BLOCKED"),
        stage=_stage(error.get("stage")),
        rule_id=error.get("rule_id"),
        reason=error.get("reason"),
    )


def _from_success_body(http_status: int, body: dict) -> StepObservation:
    ext = body.get("control_layer", body)
    approval = body.get("approval") or {}
    return StepObservation(
        http_status=http_status,
        status=CallStatus(ext["status"]),
        stage=_stage(ext.get("stage")),
        rule_id=ext.get("rule_id"),
        reason=ext.get("reason"),
        approval_id=approval.get("id"),
    )


def _observation(response: httpx.Response) -> StepObservation:
    try:
        body = response.json()
    except ValueError:
        return StepObservation(
            http_status=response.status_code, status=CallStatus.BLOCKED, reason=response.text[:200]
        )
    if response.status_code >= 400:
        return _from_error_body(response.status_code, body)
    return _from_success_body(response.status_code, body)


class HttpScenarioClient:
    def __init__(self, target: str, agent_url: str, client: httpx.AsyncClient) -> None:
        self._target = target.rstrip("/")
        self._agent_url = agent_url.rstrip("/")
        self._client = client
        self._model: str | None = None
        self._escalations: dict[str, StepObservation] = {}

    async def _default_model(self) -> str:
        if self._model is None:
            health = (await self._client.get(f"{self._target}/health")).json()
            self._model = health["provider"]["model"]
        return self._model

    async def token_for(self, sub: str) -> str:
        response = await self._client.post(f"{self._target}/auth/token", json={"sub": sub})
        response.raise_for_status()
        return response.json()["access_token"]

    async def tamper(self, token: str, claim: str, value: object) -> str:
        return edit_claims(token, {claim: value})

    async def expired_token(self, sub: str) -> str:
        token = await self.token_for(sub)
        claims = json.loads(_unb64(token.split(".")[1]))
        return edit_claims(token, {"exp": claims["iat"] - 3600, "iat": claims["iat"] - 7200})

    async def chat(
        self, token: str, session_id: str, message: str, model: str | None = None
    ) -> StepObservation:
        body = {
            "model": model or await self._default_model(),
            "messages": [{"role": "user", "content": message}],
        }
        response = await self._client.post(
            f"{self._target}/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {token}", "X-Session-Id": session_id},
        )
        return _observation(response).model_copy(update={"target": LLM_TARGET})

    async def tool_call(
        self, token: str, session_id: str, server: str, tool: str, arguments: dict
    ) -> StepObservation:
        response = await self._client.post(
            f"{self._target}/v1/tools/call",
            json={"server": server, "tool": tool, "arguments": arguments, "session_id": session_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        observation = _observation(response).model_copy(update={"target": f"{server}.{tool}"})
        if observation.approval_id:
            self._escalations[observation.approval_id] = observation
        return observation

    async def approve(self, token: str, approval_id: str) -> StepObservation:
        response = await self._client.post(
            f"{self._target}/v1/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        escalation = self._escalations.pop(approval_id, None)
        executed = _observation(response).model_copy(
            update={"target": escalation.target if escalation is not None else None}
        )
        if escalation is None or executed.status == CallStatus.BLOCKED:
            return executed
        return escalation.model_copy(
            update={
                "http_status": executed.http_status,
                "approval_id": None,
                "reason": "Approved by the requesting user and executed once",
            }
        )

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]:
        try:
            response = await self._client.post(
                f"{self._agent_url}/agent/chat",
                json={"session_id": session_id, "message": prompt},
                headers={"Authorization": f"Bearer {token}"},
                timeout=180.0,
            )
        except httpx.HTTPError as exc:
            raise AgentUnavailableError(
                f"demo agent unreachable at {self._agent_url}: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise AgentUnavailableError(f"demo agent returned {response.status_code}")
        observations = observations_from_events(response.json().get("events", []))
        for observation in observations:
            if observation.approval_id:
                self._escalations[observation.approval_id] = observation
        return observations


def _provider_of(health: dict) -> dict:
    return health.get("provider") or {}


def _protection_mode(health: dict) -> str:
    return (health.get("protection") or {}).get("mode", "unknown")


def run_header(target: str, agent: str, health: dict) -> str:
    provider = _provider_of(health)
    return (
        f"target {target} · provider {provider.get('name', 'unknown')}/"
        f"{provider.get('model', 'unknown')} · protection {_protection_mode(health)} "
        f"· agent {agent}"
    )


def context_warnings(agent: str, health: dict) -> list[str]:
    warnings = []
    if _protection_mode(health) != "enforce":
        warnings.append("warning: protection is not enforce; attacks are expected to get through")
    if agent == "ollama" and _provider_of(health).get("name") != "ollama":
        warnings.append(
            "warning: the agent tier needs an Ollama model; "
            f"the active provider is {_provider_of(health).get('name', 'unknown')}"
        )
    return warnings


def _expected_text(scenario: Scenario) -> str:
    rule = f"/{scenario.expected.rule_id}" if scenario.expected.rule_id else ""
    return f"{scenario.expected.status.value}{rule}"


def _observed_text(result: ScenarioResult) -> str:
    if result.observed is None:
        return result.error or "-"
    rule = f"/{result.observed.rule_id}" if result.observed.rule_id else ""
    return f"{result.observed.status.value}{rule}"


def render_table(rows: list[tuple[Scenario, ScenarioResult]]) -> str:
    header = ("id", "name", "stage", "expected", "observed", "status", "via", "ms")
    body = [
        (
            s.id,
            s.name,
            s.stage.value,
            _expected_text(s),
            _observed_text(r),
            r.status.value,
            r.via,
            f"{r.duration_ms:.0f}",
        )
        for s, r in rows
    ]
    widths = [max(len(str(line[i])) for line in [header, *body]) for i in range(len(header))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*header), fmt.format(*("-" * w for w in widths))]
    lines.extend(fmt.format(*line) for line in body)
    return "\n".join(lines)


def summarise(rows: list[tuple[Scenario, ScenarioResult]]) -> dict[str, int]:
    negatives = [r for s, r in rows if s.kind == "negative"]
    positives = [r for s, r in rows if s.kind == "positive"]
    return {
        "stopped": sum(r.status == ScenarioStatus.STOPPED for r in negatives),
        "succeeded": sum(r.status == ScenarioStatus.SUCCEEDED for r in negatives),
        "negative_errors": sum(r.status == ScenarioStatus.ERROR for r in negatives),
        "not_attempted": sum(r.status == ScenarioStatus.NOT_ATTEMPTED for _, r in rows),
        "passed": sum(r.status == ScenarioStatus.PASSED for r in positives),
        "positive_failed": sum(
            r.status not in (ScenarioStatus.PASSED, ScenarioStatus.NOT_ATTEMPTED)
            for r in positives
        ),
    }


def exit_code(summary: dict[str, int]) -> int:
    failed = summary["succeeded"] + summary["negative_errors"] + summary["positive_failed"]
    return 0 if failed == 0 else 1


async def run_suite(args: argparse.Namespace) -> int:
    scenarios = [s for s in SCENARIOS if args.only is None or s.id == args.only]
    if not scenarios:
        print(f"unknown scenario id: {args.only}", file=sys.stderr)
        return 2
    async with httpx.AsyncClient(timeout=60.0) as http:
        try:
            health = (await http.get(f"{args.target.rstrip('/')}/health")).json()
        except (httpx.HTTPError, ValueError) as exc:
            print(f"cannot reach control layer at {args.target}: {exc}", file=sys.stderr)
            return 2
        print(run_header(args.target, args.agent, health))
        for warning in context_warnings(args.agent, health):
            print(warning, file=sys.stderr)
        executor = ScenarioExecutor(HttpScenarioClient(args.target, args.agent_url, http))
        rows = []
        warned = False
        for scenario in scenarios:
            if not args.no_reset:
                reset = await http.post(
                    f"{args.target.rstrip('/')}/api/demo/reset",
                    params={"scope": "behavior"},
                    headers={"X-Admin-Token": args.admin_token},
                )
                if reset.status_code != 200 and not warned:
                    print(
                        "warning: could not isolate scenarios "
                        f"(reset returned {reset.status_code}); "
                        "pass --admin-token or --no-reset",
                        file=sys.stderr,
                    )
                    warned = True
            rows.append((scenario, await executor.run(scenario, tier=args.agent)))

    print(render_table(rows))
    summary = summarise(rows)
    print(
        f"\n{summary['stopped']} attacks stopped · {summary['succeeded']} succeeded, "
        f"{summary['passed']} positive passed"
        + (f", {summary['not_attempted']} not attempted" if summary["not_attempted"] else "")
        + (
            f", {summary['negative_errors'] + summary['positive_failed']} errors"
            if summary["negative_errors"] + summary["positive_failed"]
            else ""
        )
    )
    if args.json:
        report = {
            "target": args.target,
            "agent": args.agent,
            "summary": summary,
            "results": [
                {
                    "id": s.id,
                    "name": s.name,
                    "kind": s.kind,
                    "stage": s.stage.value,
                    "expected": s.expected.model_dump(mode="json"),
                    **r.model_dump(mode="json"),
                }
                for s, r in rows
            ],
        }
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    return exit_code(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Control Layer attack suite")
    parser.add_argument("--target", default="http://localhost:8080")
    parser.add_argument("--agent", choices=["scripted", "ollama"], default="scripted")
    parser.add_argument("--agent-url", default="http://localhost:8090")
    parser.add_argument("--json", metavar="PATH", help="write a JSON report")
    parser.add_argument("--only", metavar="SCENARIO_ID")
    parser.add_argument(
        "--admin-token", default=os.environ.get("CTRL_ADMIN_TOKEN", "admin-dev-token")
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="do not clear rate-limit, budget and session state before each scenario",
    )
    args = parser.parse_args()
    if not args.target.startswith("http"):
        args.target = f"http://{args.target}"
    sys.exit(asyncio.run(run_suite(args)))


if __name__ == "__main__":
    main()
