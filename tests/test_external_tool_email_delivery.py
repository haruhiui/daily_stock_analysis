from email import message_from_bytes
from types import SimpleNamespace
from unittest.mock import patch

from main import _should_merge_notification
from src.notification_sender.email_sender import EmailSender


def test_external_tool_merge_mode_preserves_native_and_stocks_only_semantics() -> None:
    args = SimpleNamespace(no_market_review=False)
    native_config = SimpleNamespace(
        single_stock_notify=False,
        external_tool_enabled=False,
        merge_email_notification=False,
        market_review_enabled=True,
    )

    assert not _should_merge_notification(native_config, args)

    native_config.merge_email_notification = True
    assert _should_merge_notification(native_config, args)

    native_config.external_tool_enabled = True
    native_config.merge_email_notification = False
    args.no_market_review = True
    assert _should_merge_notification(native_config, args)

    native_config.single_stock_notify = True
    assert not _should_merge_notification(native_config, args)


def test_163_delivery_uses_existing_ssl_sender_and_authorization_code() -> None:
    sender = "sender" + "@163.com"
    receiver = "receiver" + "@example.test"
    config = SimpleNamespace(
        email_sender=sender,
        email_sender_name="股票分析助手",
        email_password="smtp-authorization-code",
        email_receivers=[receiver],
        stock_email_groups=[],
    )

    with patch("src.notification_sender.email_sender.smtplib.SMTP_SSL") as smtp_ssl:
        assert EmailSender(config).send_to_email(
            "# 大盘复盘\n\n---\n\n# 个股分析\n\n---\n\n## 自定义研究",
            subject="每日合并报告",
        )

    smtp_ssl.assert_called_once_with("smtp.163.com", 465, timeout=30)
    server = smtp_ssl.return_value
    server.login.assert_called_once_with(sender, "smtp-authorization-code")
    message = server.send_message.call_args.args[0]
    parsed = message_from_bytes(message.as_bytes())
    plain = next(part for part in parsed.walk() if part.get_content_type() == "text/plain")
    content = plain.get_payload(decode=True).decode(plain.get_content_charset())
    assert "# 大盘复盘" in content
    assert "# 个股分析" in content
    assert "## 自定义研究" in content
