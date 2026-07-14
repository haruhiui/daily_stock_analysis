import json
from types import SimpleNamespace

from src.extensions.external_tool.errors import ExternalToolExtensionError
from src.extensions.external_tool.report_bridge import compose_daily_email, report_markdown


def test_report_bridge_preserves_section_order() -> None:
    rendered = report_markdown({
        "sections": [
            {"id": "market", "markdown": "### 大盘\n\n正常"},
            {"id": "custom", "markdown": "### 自定义\n\n内容"},
        ]
    })
    assert rendered.startswith("## 自定义研究")
    assert rendered.index("### 大盘") < rendered.index("### 自定义")


def test_report_bridge_groups_methods_other_sections_and_custom_markdown() -> None:
    rendered = report_markdown(
        {
            "source": "external_tool",
            "trade_date": "2026-07-14",
            "sections": [
                {"id": "custom:markdown", "title": "自定义信息", "markdown": "自定义内容"},
                {"id": "factor:summary", "title": "其他研究", "markdown": "其他内容"},
                {"id": "method:sample", "title": "示例方法", "markdown": "方法内容"},
            ],
            "limitations": ["存在数据限制"],
            "disclaimer": "仅供研究，不构成投资建议",
        }
    )

    assert rendered.index("### 示例方法") < rendered.index("### 其他研究")
    assert rendered.index("### 其他研究") < rendered.index("### 自定义信息")
    assert rendered.index("### 自定义信息") < rendered.index("数据截止日：2026-07-14")
    assert rendered.index("数据截止日：2026-07-14") < rendered.index("### 数据限制")
    assert rendered.index("### 数据限制") < rendered.index("仅供研究，不构成投资建议")


def test_report_bridge_renders_research_pool_and_provider_usage() -> None:
    rendered = report_markdown(
        {
            "research_universe": {
                "source": "automation_config",
                "purpose": "screening_pool",
                "count": 12,
            },
            "sections": [{"id": "method:sample", "title": "筛选结果", "markdown": "候选 2 个"}],
            "data_access_usage": {
                "scope": "daily_report_run",
                "total_requests": 3,
                "providers": [
                    {
                        "provider": "baostock",
                        "measurement": "provider_request",
                        "requests": 3,
                        "operations": {"login": 1, "query_history_k_data_plus": 2},
                        "daily_quota": {"used": 18, "limit": 40000, "remaining": 39982},
                    }
                ],
            },
        }
    )

    assert "研究筛选池：12 个标的" in rendered
    assert "不会自动触发 DSA 深度分析" in rendered
    assert "### 行情访问用量" in rendered
    assert "| baostock | 3 | 渠道请求 | 18 | 40000 | 39982 |" in rendered
    assert "query_history_k_data_plus 2" in rendered
    assert rendered.index("### 筛选结果") < rendered.index("### 行情访问用量")


def test_report_bridge_fails_open_for_invalid_report() -> None:
    rendered = report_markdown({"status": "failed"})
    assert "未返回有效报告" in rendered


def test_compose_daily_email_is_noop_when_extension_is_disabled(tmp_path) -> None:
    config = SimpleNamespace(external_tool_enabled=False)

    rendered = compose_daily_email(
        ["# 大盘复盘", "# 个股分析"],
        config=config,
        output_dir=tmp_path,
    )

    assert rendered == "# 大盘复盘\n\n---\n\n# 个股分析"
    assert list(tmp_path.iterdir()) == []


def test_compose_daily_email_preserves_native_order_and_writes_artifacts(tmp_path) -> None:
    class FakeService:
        def run_capability(self, capability, payload):
            assert capability == "daily_report"
            assert payload == {"config_path": "automation/daily-report.yaml"}
            return {
                "schema_version": 1,
                "status": "success",
                "source": "private_engine",
                "trade_date": "2026-07-14",
                "sections": [
                    {"id": "method:sample", "title": "示例方法", "markdown": "方法结果", "source": "private_engine"},
                    {"id": "custom:markdown", "title": "自定义信息", "markdown": "自定义内容", "source": "user_config"},
                ],
                "limitations": ["数据有截止日"],
                "disclaimer": "仅供研究，不构成投资建议",
                "markdown": "# PrivateEngine 原始报告\n\n方法结果",
            }

    config = SimpleNamespace(
        external_tool_enabled=True,
        external_tool_adapter_module="private_engine.adapter",
        external_tool_automation_config="automation/daily-report.yaml",
    )

    rendered = compose_daily_email(
        ["# 大盘复盘", "# 个股分析"],
        config=config,
        service=FakeService(),
        output_dir=tmp_path,
    )

    assert rendered.index("# 大盘复盘") < rendered.index("# 个股分析")
    assert rendered.index("# 个股分析") < rendered.index("### 示例方法")
    assert rendered.index("### 示例方法") < rendered.index("### 自定义信息")
    assert rendered.index("### 自定义信息") < rendered.index("数据截止日：2026-07-14")
    assert "数据有截止日" in rendered
    assert "仅供研究，不构成投资建议" in rendered
    payload = json.loads((tmp_path / "external-tool-daily.json").read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["source"] == "external_tool"
    assert payload["sections"][0]["source"] == "external_tool"
    assert payload["sections"][1]["source"] == "user_config"
    assert "private_engine" not in json.dumps(payload)
    assert "PrivateEngine" not in (tmp_path / "external-tool-daily.md").read_text(encoding="utf-8")
    assert (tmp_path / "external-tool-daily.md").read_text(encoding="utf-8").startswith(
        "# external tool 原始报告"
    )


def test_compose_daily_email_fails_open_and_sanitizes_artifact(tmp_path) -> None:
    class FailingService:
        def run_capability(self, capability, payload):
            raise ExternalToolExtensionError(
                "external_tool_daily_report_failed",
                "PrivateEngine 读取 C:\\private\\daily-report.yaml 失败",
            )

    config = SimpleNamespace(
        external_tool_enabled=True,
        external_tool_adapter_module="private_engine.adapter",
        external_tool_automation_config="automation/daily-report.yaml",
    )

    rendered = compose_daily_email(
        ["# 大盘复盘", "# 个股分析"],
        config=config,
        service=FailingService(),
        output_dir=tmp_path,
    )

    assert "# 大盘复盘" in rendered
    assert "# 个股分析" in rendered
    assert "external_tool_daily_report_failed" in rendered
    assert "PrivateEngine" not in rendered
    assert "C:\\private" not in rendered
    payload = json.loads((tmp_path / "external-tool-daily.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"]["message"] == "external tool 读取 <path> 失败"
    assert "PrivateEngine" not in json.dumps(payload)


def test_compose_daily_email_does_not_fail_when_artifact_path_is_unwritable(tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")

    class FakeService:
        def run_capability(self, capability, payload):
            return {
                "status": "success",
                "sections": [{"title": "研究结果", "markdown": "内容仍可发送"}],
            }

    config = SimpleNamespace(
        external_tool_enabled=True,
        external_tool_automation_config="automation/daily-report.yaml",
    )

    rendered = compose_daily_email(
        ["# DSA 原生报告"],
        config=config,
        service=FakeService(),
        output_dir=blocked,
    )

    assert "# DSA 原生报告" in rendered
    assert "内容仍可发送" in rendered


def test_compose_daily_email_sanitizes_partial_failure_report(tmp_path) -> None:
    local_path = "D:" + "\\private\\report.yaml"
    email = "person" + "@example.test"
    token = "github" + "_pat_example_secret"
    password = "mail" + "-code"
    api_key = "sk-" + "examplecredential"

    class PartialService:
        def run_capability(self, capability, payload):
            return {
                "status": "partial",
                "sections": [
                    {
                        "id": "method:sample",
                        "title": "示例方法",
                        "status": "failed",
                        "markdown": (
                            f"读取 {local_path} 失败；"
                            f"EMAIL_PASSWORD={password} {token}"
                        ),
                    }
                ],
                "warnings": [f"联系 {email}，api_key={api_key}"],
            }

    config = SimpleNamespace(
        external_tool_enabled=True,
        external_tool_automation_config="automation/daily-report.yaml",
    )

    rendered = compose_daily_email(
        ["# DSA 原生报告"],
        config=config,
        service=PartialService(),
        output_dir=tmp_path,
    )
    artifact = (tmp_path / "external-tool-daily.json").read_text(encoding="utf-8")
    markdown_artifact = (tmp_path / "external-tool-daily.md").read_text(encoding="utf-8")

    for sensitive in (
        local_path,
        password,
        token,
        email,
        api_key,
    ):
        assert sensitive not in rendered
        assert sensitive not in artifact
        assert sensitive not in markdown_artifact
