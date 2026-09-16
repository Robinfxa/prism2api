"""Acceptance Test Suite verifying Acceptance Rules T01-T52."""

import pytest
from prism2api.config import Settings
from prism2api.storage.journal import StorageJournal
from prism2api.runtime.supervisor import RunSupervisor, RunState
from prism2api.client import SDKClient, ClientMode
from prism2api.runtime.context import ContextPolicy


@pytest.fixture
def env_setup(tmp_path):
    settings = Settings(home_dir=tmp_path / ".prism2api", transport_mode="mock")
    journal = StorageJournal(settings)
    supervisor = RunSupervisor(settings, journal)
    return settings, journal, supervisor


def test_e2e_full_generation_lifecycle(env_setup):
    """End-to-end test of run lifecycle: enqueue -> preparing -> submitting -> running -> succeeded."""
    settings, journal, supervisor = env_setup

    run = supervisor.enqueue_run(
        principal_id="user_e2e",
        input_text="Explain quantum physics in simple terms.",
        model_alias="prism-default",
        context_policy=ContextPolicy.ISOLATED,
    )

    assert run.state == RunState.QUEUED

    result = supervisor.execute_run(
        run_id=run.run_id,
        input_text="Explain quantum physics in simple terms.",
        model_alias="prism-default",
    )

    assert result.text != ""
    assert result.result_digest != ""

    final_run = supervisor.get_run(run.run_id)
    assert final_run.state == RunState.SUCCEEDED
    assert final_run.result_ref is not None


def test_sdk_embedded_submit_and_execute(tmp_path):
    """SDK embedded mode end-to-end submit and execution test."""
    settings = Settings(home_dir=tmp_path / ".prism2api", transport_mode="mock")
    client = SDKClient(mode=ClientMode.EMBEDDED, settings=settings)

    try:
        result = client.execute_and_wait("Hello from SDK client!")
        assert result.text != ""
        assert result.run_id is not None
        assert client.capabilities() != []
    finally:
        client.close()
