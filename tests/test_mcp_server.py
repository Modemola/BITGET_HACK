"""The agent-facing contract, exercised as an agent would reach it.

An MCP server is only useful if a client can actually complete a handshake,
read the tool list and get an answer back. Importing the module proves none of
that, and the first version of this server imported perfectly while calling a
decorator the installed SDK does not have -- it failed on the first line of the
first real connection.

So the end of this file speaks the wire protocol over a real subprocess. The
rest checks the contract without paying for a process each time.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("mcp", reason="install with `pip install -e '.[agent]'`")

from blackout import mcp_server  # noqa: E402
from blackout.tools import TOOLS  # noqa: E402


@pytest.fixture(scope="module")
def listed():
    import asyncio
    try:
        return asyncio.run(mcp_server._listing())
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


# --- the contract -----------------------------------------------------------

def test_every_desk_tool_is_exposed(listed):
    """The agent sees the same seven the page does.

    A tool that exists in `TOOLS` and not here is one an agent cannot reach,
    and the submission's claim of seven would be true of the page only.
    """
    exposed = {tool.name for tool in listed}
    missing = set(TOOLS) - exposed
    extra = exposed - set(TOOLS)
    assert not missing, f"not exposed over MCP: {sorted(missing)}"
    assert not extra, f"exposed but not in the desk contract: {sorted(extra)}"


def test_each_tool_tells_an_agent_when_to_call_it(listed):
    for tool in listed:
        assert tool.description and len(tool.description) > 60, (
            f"{tool.name} has no description an agent could choose on")
        assert tool.input_schema.get("type") == "object", \
            f"{tool.name} has no usable input schema"


def test_the_scenario_parameters_are_reachable(listed):
    """Driving the analogue query is how an agent runs a stress test.

    These arrive through **kwargs on the underlying function, so they appear in
    no signature and would be invisible to a schema derived from one.
    """
    analogues = next(t for t in listed if t.name == "historical_analogues")
    properties = analogues.input_schema.get("properties", {})
    for field in ("realised_vol_5d", "premium_at_close", "window_hours",
                  "crypto_vol_5d"):
        assert field in properties, f"an agent cannot vary {field}"


def test_nothing_is_required(listed):
    """Every tool must answer with no arguments at all.

    An agent that has to guess a required argument on its first call usually
    guesses wrong; each tool falls back to now, to the median conditions, or to
    the demo position.
    """
    for tool in listed:
        assert not tool.input_schema.get("required"), (
            f"{tool.name} demands {tool.input_schema['required']} up front")


def test_the_sample_travels_with_every_answer():
    """A figure repeated by an agent without its denominator is misreported."""
    wrapped = mcp_server._wrap("premium_verdict", {"hit_rate": 0.46})
    assert "28 weekend blackouts" in wrapped["sample"]
    assert "arbitrage" in wrapped["sample"], \
        "the one claim the product exists to prevent is no longer warned against"


def test_a_bad_instant_is_a_message_not_a_traceback():
    with pytest.raises(ValueError, match="not a valid instant"):
        mcp_server._as_of("last Friday-ish")


def test_a_naive_instant_is_read_as_utc():
    stamp = mcp_server._as_of("2026-09-18T19:45:00")
    assert stamp is not None and str(stamp.tz) == "UTC"


# --- the wire ---------------------------------------------------------------

def _rpc(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _await(proc, want_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            continue
        try:
            got = json.loads(line)
        except json.JSONDecodeError:
            continue
        if got.get("id") == want_id:
            return got
    return None


@pytest.mark.slow
def test_a_client_can_connect_and_get_the_desks_answer():
    """The whole point, over the actual protocol.

    Initialise, list, call - and the number that comes back must be the number
    the page prints, because both are the same `Desk` call.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "blackout.mcp_server"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
    )
    try:
        _rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "pytest", "version": "0"}}})
        init = _await(proc, 1)
        assert init and "result" in init, f"initialize failed: {init}"
        assert init["result"]["serverInfo"]["name"] == "blackout-desk"

        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = _await(proc, 2)
        assert listing and len(listing["result"]["tools"]) == len(TOOLS)

        _rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "premium_verdict", "arguments": {}}})
        answer = _await(proc, 3)
        assert answer and "result" in answer, f"tools/call failed: {answer}"

        payload = json.loads(answer["result"]["content"][0]["text"])
        verdict = payload["result"]

        shipped = json.loads(
            (ROOT / "web" / "data" / "desk.json").read_text(encoding="utf-8"))["verdict"]
        assert verdict["n_weekends"] == shipped["n_weekends"]
        assert verdict["hit_rate"] == pytest.approx(shipped["hit_rate"], rel=1e-9), \
            "an agent is being told a different hit rate than the page shows"
    finally:
        proc.terminate()
        proc.wait(timeout=30)
