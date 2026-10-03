"""Fake CI MCP demo server.

Tools: get_run, list_pipelines.
`get_run("e2e-login", "2026-10-02")` returns a failed run caused by an auth
service key rotation, used by the demo's "why did the login tests fail"
scenario.
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("ci", "Fake CI server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def get_run(pipeline: str, date: str) -> dict[str, Any]:
    """Get a CI run. pipeline: e2e-login, e2e-checkout, nightly-build or deploy-staging. date: YYYY-MM-DD."""
    run = data.CI_RUNS.get((pipeline, date))
    if run is None and "login" in pipeline.lower():
        run = {**data.CI_RUNS[("e2e-login", "2026-10-02")], "pipeline": pipeline, "date": date}
    if run is not None:
        return dict(run)
    return {
        "pipeline": pipeline,
        "date": date,
        "status": data.CI_DEFAULT_STATUS,
        "duration_s": data.CI_DEFAULT_DURATION_S,
        "reason": data.CI_DEFAULT_REASON,
    }


@mcp.tool()
@ascii_safe
def list_pipelines() -> dict[str, Any]:
    """List the names of known CI pipelines."""
    return {"pipelines": data.CI_PIPELINES}


if __name__ == "__main__":
    mcp.run()
