from __future__ import annotations

import asyncio

import httpx
import pytest

from control_layer.application.selftest.scenario_executor import ScenarioExecutor, ScenarioStatus
from control_layer.selftest.scenarios import SCENARIOS
from tests.conftest import ADMIN_HEADERS, read_sse

pytestmark = pytest.mark.integration

KNOWN_ISSUES: dict[str, str] = {
    "forbidden_model": "policy.yaml has no model_allowlist rule (WS3 config)",
    "pesel_in_hr_report": "catalogue uses employee emp-0231 but demo data only has E-1042",
    "secret_in_prompt": "api_key detector misses sk_live_ keys (WS3)",
    "exfiltration_to_external_email": "no role has both github and mail; HR actor cannot read github",
    "prompt_injection_via_readme": "catalogue repo legacy-service is benign; injected README is vendor-sdk",
    "historical_exploit_payload": "exploit signatures are not scoped to the prompt point (WS3)",
    "over_limit_transfer": "policy.yaml has no transaction_limit rule (WS3 config)",
    "rate_limit_burst": "quarantine takes over from rate_limit after 5 blocks; last observation differs",
    "block_burst_quarantine": "Authorization short-circuits before the Behavior quarantine check",
    "token_budget_overrun": "mock usage is too small to exhaust per_user_tokens in 20 calls",
}


def _params() -> list:
    return [
        pytest.param(
            scenario,
            marks=pytest.mark.xfail(reason=KNOWN_ISSUES[scenario.id], strict=False),
        )
        if scenario.id in KNOWN_ISSUES
        else pytest.param(scenario)
        for scenario in SCENARIOS
    ]


@pytest.mark.parametrize("scenario", _params(), ids=[s.id for s in SCENARIOS])
async def test_catalogue_scenario_in_process(shared_app, scenario) -> None:
    from control_layer.presentation.selftest.in_process_client import InProcessScenarioClient

    container = shared_app.app.state.container
    await container.reset_runtime_state()
    client = InProcessScenarioClient(
        container.chat_completion,
        container.tool_call,
        container.execute_approval,
        container.issue_token,
        container.token_verifier,
        container.model_provider,
    )
    result = await ScenarioExecutor(client).run(scenario, tier="scripted")
    expected = ScenarioStatus.STOPPED if scenario.kind == "negative" else ScenarioStatus.PASSED
    assert result.status == expected, (
        f"{scenario.id}: observed={result.observed} error={result.error}"
    )
    if scenario.expected.rule_id is not None:
        assert result.observed is not None
        assert result.observed.rule_id == scenario.expected.rule_id
    assert result.observed is not None
    assert result.observed.status == scenario.expected.status


async def test_scenarios_endpoint_lists_catalogue(api: httpx.AsyncClient) -> None:
    response = await api.get("/api/attack-suite/scenarios", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    items = response.json()["scenarios"]
    assert [s["id"] for s in items] == [s.id for s in SCENARIOS]
    assert {"id", "name", "kind", "actor", "stage", "expected", "owasp"} <= set(items[0])


async def test_run_endpoint_completes_and_streams(shared_app, api: httpx.AsyncClient) -> None:
    started = await api.post(
        "/api/attack-suite/run", params={"agent": "scripted"}, headers=ADMIN_HEADERS
    )
    assert started.status_code == 200
    run = started.json()
    assert run["run_id"].startswith("run_")
    assert run["agent"] == "scripted"
    assert len(run["scenarios"]) == len(SCENARIOS)
    assert {s["status"] for s in run["scenarios"]} <= {"PENDING", "RUNNING"}

    events = await read_sse(
        shared_app.app,
        f"/api/attack-suite/runs/{run['run_id']}/stream?admin_token=admin-dev-token",
        until=lambda seen: any(name == "run_complete" for name, _ in seen),
        timeout_s=180,
    )
    names = {name for name, _ in events}
    assert {"scenario", "run_complete"} <= names

    detail = None
    for _ in range(50):
        detail = (
            await api.get(f"/api/attack-suite/runs/{run['run_id']}", headers=ADMIN_HEADERS)
        ).json()
        if detail["summary"]["running"] == 0 and detail["summary"]["pending"] == 0:
            break
        await asyncio.sleep(0.2)
    assert detail is not None
    assert detail["summary"]["running"] == 0
    assert detail["summary"]["pending"] == 0
    assert detail["summary"]["stopped"] + detail["summary"]["passed"] > 0

    unknown = await api.get("/api/attack-suite/runs/run_9999", headers=ADMIN_HEADERS)
    assert unknown.status_code == 404

    bad_agent = await api.post(
        "/api/attack-suite/run", params={"agent": "gpt"}, headers=ADMIN_HEADERS
    )
    assert bad_agent.status_code == 422


@pytest.mark.xfail(
    reason="catalogue/config defects listed in KNOWN_ISSUES still make some scenarios fail",
    strict=False,
)
async def test_scripted_run_all_negatives_stopped_all_positives_passed(
    api: httpx.AsyncClient, shared_app
) -> None:
    run = (
        await api.post("/api/attack-suite/run", params={"agent": "scripted"}, headers=ADMIN_HEADERS)
    ).json()
    await shared_app.app.state.container.attack_runs.wait(run["run_id"])
    detail = (
        await api.get(f"/api/attack-suite/runs/{run['run_id']}", headers=ADMIN_HEADERS)
    ).json()
    for scenario in detail["scenarios"]:
        expected = "STOPPED" if scenario["kind"] == "negative" else "PASSED"
        assert scenario["status"] == expected, scenario["id"]
