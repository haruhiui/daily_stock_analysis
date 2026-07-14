from src.extensions.external_tool.errors import (
    ExternalToolExtensionError,
    sanitize_message,
    translate_adapter_error,
)


def test_extension_diagnostics_redact_paths_emails_and_credentials() -> None:
    local_path = "C:" + "\\private\\config.yaml"
    email = "person" + "@example.test"
    token = "github" + "_pat_example_secret"
    password = "mail" + "-code"
    api_key = "sk-" + "examplecredential"
    message = (
        f"读取 {local_path} 失败；"
        f"email={email} token={token} "
        f"EMAIL_PASSWORD={password} api_key={api_key}"
    )

    sanitized = sanitize_message(message)

    for sensitive in (local_path, email, token, password, api_key):
        assert sensitive not in sanitized
    assert "<path>" in sanitized
    assert "<email>" in sanitized
    assert sanitized.count("<redacted>") == 3


def test_extension_error_recursively_redacts_detail() -> None:
    token = "github" + "_pat_example_secret"
    local_path = "/home" + "/example/private.yaml"
    error = ExternalToolExtensionError(
        "external_tool_execution_failed",
        "执行失败",
        detail={
            "nested": [
                f"file={local_path}",
                {"credential": f"client_secret={token}"},
            ]
        },
    )

    rendered = str(error.detail)
    assert local_path not in rendered
    assert token not in rendered
    assert "<path>" in rendered
    assert "<redacted>" in rendered


def test_private_adapter_error_codes_are_mapped_to_public_codes() -> None:
    class PrivateAdapterError(RuntimeError):
        code = "private_engine_method_not_found"
        message = "方法不存在"
        details = {}

    translated = translate_adapter_error(PrivateAdapterError())

    assert translated.code == "external_tool_method_not_found"
    assert translated.status_code == 404
