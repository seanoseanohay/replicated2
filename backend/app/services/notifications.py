"""Notification service — email and Slack alerts for critical/high findings."""
import logging
import smtplib
import urllib.request
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

log = logging.getLogger(__name__)


def send_email_notification(config, findings, bundle) -> None:
    """Send SMTP email with critical/high findings summary. Skip if SMTP_HOST empty."""
    if not settings.SMTP_HOST:
        log.debug("SMTP_HOST not configured, skipping email notification")
        return
    if not config.email_recipients:
        log.debug("No email recipients configured, skipping email notification")
        return
    if not findings:
        return

    recipients = [r.strip() for r in config.email_recipients.split(",") if r.strip()]
    if not recipients:
        return

    subject = f"[Bundle Analyzer] {len(findings)} finding(s) require attention — {bundle.original_filename}"

    lines = [
        f"Bundle: {bundle.original_filename}",
        f"Bundle ID: {bundle.id}",
        f"Total findings to review: {len(findings)}",
        "",
        "Findings:",
    ]
    for f in findings:
        lines.append(f"  [{f.severity.upper()}] {f.title} (rule: {f.rule_id})")
    lines.append("")
    lines.append(f"View details: {settings.APP_BASE_URL}/bundles/{bundle.id}")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, recipients, msg.as_string())
        log.info(f"Email notification sent for bundle {bundle.id} to {len(recipients)} recipients")
    except Exception as exc:
        log.error(f"Failed to send email notification: {exc}")


def send_slack_notification(config, findings, bundle) -> None:
    """POST to Slack webhook with rich message. Skip if webhook empty."""
    if not config.slack_webhook_url:
        log.debug("Slack webhook not configured, skipping Slack notification")
        return
    if not findings:
        return

    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    severity_summary = ", ".join(
        f"{count} {sev}" for sev, count in severity_counts.items()
    )

    finding_lines = []
    for f in findings[:10]:  # limit to 10 findings in Slack message
        finding_lines.append(f"• *[{f.severity.upper()}]* {f.title}")
    if len(findings) > 10:
        finding_lines.append(f"_...and {len(findings) - 10} more_")

    text = (
        f":alert: *Bundle Analyzer Alert*\n"
        f"Bundle: *{bundle.original_filename}*\n"
        f"Found: {severity_summary}\n\n"
        + "\n".join(finding_lines)
        + f"\n\n<{settings.APP_BASE_URL}/bundles/{bundle.id}|View Bundle>"
    )

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        config.slack_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(
                f"Slack notification sent for bundle {bundle.id}, status={resp.status}"
            )
    except Exception as exc:
        log.error(f"Failed to send Slack notification: {exc}")


def notify_bundle_findings(bundle_id: str, session) -> None:
    """
    Main entry point called after run_all_rules.
    1. Load NotificationConfig for tenant
    2. Filter findings by notify_on_severities
    3. Send email and/or Slack if enabled
    """
    from app.models.bundle import Bundle
    from app.models.finding import Finding
    from app.models.notification_config import NotificationConfig

    import uuid as _uuid
    try:
        bundle = session.get(Bundle, _uuid.UUID(str(bundle_id)))
    except Exception:
        log.warning(f"notify_bundle_findings: bundle {bundle_id} not found")
        return

    if bundle is None:
        log.warning(f"notify_bundle_findings: bundle {bundle_id} not found")
        return

    config = (
        session.query(NotificationConfig)
        .filter(NotificationConfig.tenant_id == bundle.tenant_id)
        .first()
    )
    if config is None:
        log.debug(f"No notification config for tenant {bundle.tenant_id}, skipping")
        return

    if not config.email_enabled and not config.slack_enabled:
        return

    severities = [s.strip() for s in config.notify_on_severities.split(",") if s.strip()]
    if not severities:
        return

    findings = (
        session.query(Finding)
        .filter(
            Finding.bundle_id == bundle.id,
            Finding.severity.in_(severities),
            Finding.status == "open",
        )
        .all()
    )

    if not findings:
        log.debug(f"No findings matching severities {severities} for bundle {bundle_id}")
        return

    if config.email_enabled:
        send_email_notification(config, findings, bundle)

    if config.slack_enabled:
        send_slack_notification(config, findings, bundle)
