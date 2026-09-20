"""The CI configuration itself is not exempt from checking.

A workflow with a YAML error does not fail loudly on GitHub - it simply never
runs, and every push looks fine because nothing reports. That is the worst
possible failure mode for the thing whose job is catching failures, and it is
how `refresh.yml` shipped its first draft: a commit message that broke out of a
block scalar.
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml is a dev dependency")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(doc: dict):
    # PyYAML reads the bare key `on:` as the boolean True, per the YAML 1.1 spec.
    return doc.get("on", doc.get(True))


def test_there_are_workflows_at_all():
    assert WORKFLOWS, "no workflows found; CI would be silently absent"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_yaml(path):
    doc = _load(path)
    assert isinstance(doc, dict), f"{path.name} did not parse to a mapping"
    assert doc.get("name"), f"{path.name} has no name"
    assert _triggers(doc), f"{path.name} declares no triggers and would never run"
    assert doc.get("jobs"), f"{path.name} declares no jobs"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_step_can_actually_do_something(path):
    for job_name, job in _load(path)["jobs"].items():
        steps = job.get("steps") or []
        assert steps, f"{path.name}:{job_name} has no steps"
        for i, step in enumerate(steps):
            assert "run" in step or "uses" in step, \
                f"{path.name}:{job_name} step {i} neither runs nor uses anything"


def test_ci_runs_on_windows_too():
    """The development machine is Windows and its cp1252 console has broken this
    project three times. Dropping it from the matrix removes the only thing that
    would catch the fourth."""
    ci = next((p for p in WORKFLOWS if p.name == "ci.yml"), None)
    assert ci, "ci.yml is missing"
    matrix = _load(ci)["jobs"]["test"]["strategy"]["matrix"]["os"]
    assert any("windows" in os_name for os_name in matrix), \
        "Windows was dropped from the test matrix"


def test_ci_installs_node_for_the_parity_tests():
    """Without Node those tests skip themselves, and the page's copy of the
    retrieval algorithm stops being checked against the Python it duplicates."""
    ci = next(p for p in WORKFLOWS if p.name == "ci.yml")
    steps = _load(ci)["jobs"]["test"]["steps"]
    assert any("setup-node" in str(s.get("uses", "")) for s in steps), \
        "no Node in CI; test_js_parity.py would skip and protect nothing"


def test_refresh_opens_a_review_rather_than_pushing_data_blind():
    """A scheduled job must not land unreviewed numbers on the working branch:
    prose has to be corrected by a person whenever the figures move."""
    refresh = next((p for p in WORKFLOWS if p.name == "refresh.yml"), None)
    assert refresh, "refresh.yml is missing"
    doc = _load(refresh)
    body = refresh.read_text(encoding="utf-8")

    assert "workflow_dispatch" in _triggers(doc), \
        "refresh cannot be triggered by hand, which is needed before a submission"
    assert "gh pr create" in body, "refresh does not open a pull request"
    assert doc.get("permissions", {}).get("pull-requests") == "write", \
        "refresh lacks permission to open the pull request it depends on"


def test_every_fetcher_is_wired_into_the_refresh_job():
    """A source that never refreshes silently rots, and can take others with it.

    `fetch_bitget.py` was missing from the job. Because the cross-venue figures
    are computed from the *overlap* between the Solana and Bitget books,
    extending one and not the other would have moved the overlap and broken
    `test_cross_venue.py` in a PR that had no way to fix it -- the data it needed
    was never pulled.
    """
    refresh = (ROOT / ".github" / "workflows" / "refresh.yml").read_text(encoding="utf-8")
    fetchers = sorted(p.name for p in (ROOT / "scripts").glob("*.py")
                      if p.name.startswith(("fetch_", "probe_")))
    assert fetchers, "no fetch scripts found; this guard is aimed at nothing"

    missing = [f for f in fetchers if f not in refresh]
    assert not missing, (
        "refresh.yml never runs: " + ", ".join(missing)
        + " -- add a step, or the series it pulls goes stale while the rest move"
    )
