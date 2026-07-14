from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/00-daily-analysis.yml")
SETUP_ACTION = Path(".github/actions/setup-external-tool/action.yml")


def test_private_checkout_is_read_only_pinned_and_fail_open() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    setup_action = SETUP_ACTION.read_text(encoding="utf-8")

    assert "uses: ./.github/actions/setup-external-tool" in workflow
    assert "repository: ${{ vars.EXTERNAL_TOOL_REPOSITORY }}" in workflow
    assert "ref: ${{ vars.EXTERNAL_TOOL_REF }}" in workflow
    assert "token: ${{ secrets.EXTERNAL_TOOL_REPO_TOKEN }}" in workflow
    assert "package-path: ${{ secrets.EXTERNAL_TOOL_PACKAGE_PATH }}" in workflow
    assert "import-module: ${{ secrets.EXTERNAL_TOOL_ADAPTER_MODULE }}" in workflow
    assert "persist-credentials: false" in setup_action
    assert "/${{ inputs.package-path }}/" in setup_action
    assert "^[0-9a-fA-F]{40}$" in setup_action
    assert "name: Setup External Tool" in setup_action
    assert "id: external_tool_setup" in workflow
    assert "continue-on-error: true" in workflow


def test_workflow_and_composite_action_have_expected_trust_boundaries() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    setup_action = yaml.safe_load(SETUP_ACTION.read_text(encoding="utf-8"))

    triggers = workflow.get("on") or workflow.get(True)
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert setup_action["runs"]["using"] == "composite"

    steps = setup_action["runs"]["steps"]
    checkout = next(step for step in steps if step.get("uses") == "actions/checkout@v5")
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["path"] == ".external/external-tool"
    assert checkout["with"]["sparse-checkout-cone-mode"] is False
    assert checkout["with"]["token"] == "${{ inputs.token }}"

    command_text = "\n".join(str(step.get("run") or "") for step in steps)
    assert "inputs.token" not in command_text
    assert "--no-cache-dir" in command_text


def test_workflow_installs_package_and_maps_report_inputs() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    setup_action = SETUP_ACTION.read_text(encoding="utf-8")

    assert 'python -m pip install --no-cache-dir "./.external/external-tool/$EXTERNAL_TOOL_PACKAGE_PATH"' in setup_action
    assert "EXTERNAL_TOOL_ENABLED: ${{ vars.EXTERNAL_TOOL_ENABLED || 'false' }}" in workflow
    assert "EXTERNAL_TOOL_DATA_DIR: ./data/external-tool" in workflow
    assert "EXTERNAL_TOOL_AUTOMATION_CONFIG:" in workflow
    assert "MERGE_EMAIL_NOTIFICATION:" not in workflow
    assert "SINGLE_STOCK_NOTIFY: ${{ vars.EXTERNAL_TOOL_ENABLED == 'true' && 'false'" in workflow
    assert "reports/" in workflow
    assert ".external/" not in _artifact_paths(workflow)


def _artifact_paths(workflow: str) -> str:
    marker = "- name: 上传分析报告"
    start = workflow.index(marker)
    return workflow[start:]
