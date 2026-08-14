from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from jinja2 import Environment
from jinja2 import FileSystemLoader


# ==========================================================
# Email Configuration
# ==========================================================

@dataclass(slots=True)
class EmailSettings:

    smtp_host: str = "localhost"

    smtp_port: int = 587

    smtp_username: str = ""

    smtp_password: str = ""

    smtp_use_tls: bool = True

    smtp_use_ssl: bool = False

    sender_name: str = "Boost Rankers"

    sender_email: str = "noreply@boostrankers.com"

    reply_to: str | None = None

    template_directory: str = "templates/emails"

    company_name: str = "Boost Rankers"

    base_url: str = "http://localhost:5173"

    verify_expiry_minutes: int = 60

    password_reset_expiry_minutes: int = 30

    magic_link_expiry_minutes: int = 15


DEFAULT_SETTINGS = EmailSettings()


# ==========================================================
# Email Service
# ==========================================================

class EmailService:

    def __init__(
        self,
        settings: EmailSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.environment = Environment(

            loader=FileSystemLoader(

                Path(

                    self.settings.template_directory

                )

            ),

            autoescape=True,

        )


# ==========================================================
# Create Email
# ==========================================================

    def create_message(

        self,

        *,

        recipient: str,

        subject: str,

        html: str,

        text: str,

    ) -> EmailMessage:

        message = EmailMessage()

        message["Subject"] = subject

        message["From"] = (

            f"{self.settings.sender_name} "

            f"<{self.settings.sender_email}>"

        )

        message["To"] = recipient

        if self.settings.reply_to:

            message["Reply-To"] = self.settings.reply_to

        message.set_content(text)

        message.add_alternative(

            html,

            subtype="html",

        )

        return message


# ==========================================================
# Render Template
# ==========================================================

    def render_template(

        self,

        template: str,

        **context: Any,

    ) -> str:

        return (

            self.environment

            .get_template(template)

            .render(

                **context,

            )

        )


# ==========================================================
# Plain Text Fallback
# ==========================================================

    @staticmethod
    def plain_text(

        html: str,

    ) -> str:

        import re

        return re.sub(

            "<[^>]+>",

            "",

            html,

        )


# ==========================================================
# SMTP Connection
# ==========================================================

    def smtp_connection(

        self,

    ):

        if self.settings.smtp_use_ssl:

            connection = smtplib.SMTP_SSL(

                self.settings.smtp_host,

                self.settings.smtp_port,

                context=ssl.create_default_context(),

            )

        else:

            connection = smtplib.SMTP(

                self.settings.smtp_host,

                self.settings.smtp_port,

            )

            if self.settings.smtp_use_tls:

                connection.starttls(

                    context=ssl.create_default_context()

                )

        if self.settings.smtp_username:

            connection.login(

                self.settings.smtp_username,

                self.settings.smtp_password,

            )

        return connection


# ==========================================================
# Send Email
# ==========================================================

    def send(

        self,

        message: EmailMessage,

    ) -> bool:

        connection = self.smtp_connection()

        try:

            connection.send_message(message)

            return True

        finally:

            connection.quit()


# ==========================================================
# Generic Email
# ==========================================================

    def send_email(

        self,

        *,

        recipient: str,

        subject: str,

        template: str,

        **context,

    ) -> bool:

        html = self.render_template(

            template,

            **context,

        )

        text = self.plain_text(html)

        message = self.create_message(

            recipient=recipient,

            subject=subject,

            html=html,

            text=text,

        )

        return self.send(message)
        
        from datetime import UTC
from datetime import datetime
from datetime import timedelta
from secrets import token_urlsafe


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Secure Token
# ==========================================================

    @staticmethod
    def generate_token(
        length: int = 48,
    ) -> str:

        return token_urlsafe(length)


# ==========================================================
# Email Verification
# ==========================================================

    def send_email_verification(

        self,

        recipient: str,

        name: str,

        token: str,

    ) -> bool:

        verification_url = (

            f"{self.settings.base_url}"

            f"/verify-email?token={token}"

        )

        return self.send_email(

            recipient=recipient,

            subject="Verify Your Email Address",

            template="verify_email.html",

            company=self.settings.company_name,

            name=name,

            verification_url=verification_url,

            expires_at=(

                self.now()

                +

                timedelta(

                    minutes=self.settings.verify_expiry_minutes

                )

            ),

        )


# ==========================================================
# Password Reset
# ==========================================================

    def send_password_reset(

        self,

        recipient: str,

        name: str,

        token: str,

    ) -> bool:

        reset_url = (

            f"{self.settings.base_url}"

            f"/reset-password?token={token}"

        )

        return self.send_email(

            recipient=recipient,

            subject="Reset Your Password",

            template="password_reset.html",

            company=self.settings.company_name,

            name=name,

            reset_url=reset_url,

            expires_at=(

                self.now()

                +

                timedelta(

                    minutes=self.settings.password_reset_expiry_minutes

                )

            ),

        )


# ==========================================================
# Magic Login Link
# ==========================================================

    def send_magic_link(

        self,

        recipient: str,

        name: str,

        token: str,

    ) -> bool:

        login_url = (

            f"{self.settings.base_url}"

            f"/magic-login?token={token}"

        )

        return self.send_email(

            recipient=recipient,

            subject="Your Secure Login Link",

            template="magic_link.html",

            company=self.settings.company_name,

            name=name,

            login_url=login_url,

            expires_at=(

                self.now()

                +

                timedelta(

                    minutes=self.settings.magic_link_expiry_minutes

                )

            ),

        )


# ==========================================================
# MFA Email
# ==========================================================

    def send_mfa_code(

        self,

        recipient: str,

        name: str,

        code: str,

    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Your Verification Code",

            template="mfa_code.html",

            company=self.settings.company_name,

            name=name,

            code=code,

        )


# ==========================================================
# Welcome Email
# ==========================================================

    def send_welcome(

        self,

        recipient: str,

        name: str,

    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Welcome to Boost Rankers AI SEO OS",

            template="welcome.html",

            company=self.settings.company_name,

            name=name,

            dashboard_url=self.settings.base_url,

        )


# ==========================================================
# Invitation Email
# ==========================================================

    def send_invitation(

        self,

        recipient: str,

        inviter: str,

        organisation: str,

        token: str,

    ) -> bool:

        invitation_url = (

            f"{self.settings.base_url}"

            f"/accept-invite?token={token}"

        )

        return self.send_email(

            recipient=recipient,

            subject=f"Invitation to Join {organisation}",

            template="organisation_invite.html",

            company=self.settings.company_name,

            inviter=inviter,

            organisation=organisation,

            invitation_url=invitation_url,

        )
        
        # ==========================================================
# Password Changed Notification
# ==========================================================

    def send_password_changed(
        self,
        recipient: str,
        name: str,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Your Password Was Changed",

            template="password_changed.html",

            company=self.settings.company_name,

            name=name,

            support_email=self.settings.sender_email,

        )


# ==========================================================
# New Device Login Alert
# ==========================================================

    def send_new_device_alert(
        self,
        recipient: str,
        name: str,
        device_name: str,
        browser: str,
        operating_system: str,
        ip_address: str,
        location: str | None,
        login_time: datetime,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="New Device Login Detected",

            template="new_device_alert.html",

            company=self.settings.company_name,

            name=name,

            device_name=device_name,

            browser=browser,

            operating_system=operating_system,

            ip_address=ip_address,

            location=location,

            login_time=login_time,

        )


# ==========================================================
# Suspicious Login Alert
# ==========================================================

    def send_suspicious_login_alert(
        self,
        recipient: str,
        name: str,
        ip_address: str,
        location: str | None,
        browser: str,
        operating_system: str,
        login_time: datetime,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Suspicious Login Attempt",

            template="suspicious_login.html",

            company=self.settings.company_name,

            name=name,

            ip_address=ip_address,

            location=location,

            browser=browser,

            operating_system=operating_system,

            login_time=login_time,

            support_email=self.settings.sender_email,

        )


# ==========================================================
# API Key Created
# ==========================================================

    def send_api_key_created(
        self,
        recipient: str,
        name: str,
        key_name: str,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="API Key Created",

            template="api_key_created.html",

            company=self.settings.company_name,

            name=name,

            key_name=key_name,

        )


# ==========================================================
# API Key Revoked
# ==========================================================

    def send_api_key_revoked(
        self,
        recipient: str,
        name: str,
        key_name: str,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="API Key Revoked",

            template="api_key_revoked.html",

            company=self.settings.company_name,

            name=name,

            key_name=key_name,

        )


# ==========================================================
# Role Changed
# ==========================================================

    def send_role_changed(
        self,
        recipient: str,
        name: str,
        role_name: str,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Your Account Permissions Changed",

            template="role_changed.html",

            company=self.settings.company_name,

            name=name,

            role_name=role_name,

        )


# ==========================================================
# Account Locked
# ==========================================================

    def send_account_locked(
        self,
        recipient: str,
        name: str,
        until: datetime | None = None,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Account Temporarily Locked",

            template="account_locked.html",

            company=self.settings.company_name,

            name=name,

            locked_until=until,

        )


# ==========================================================
# Account Unlocked
# ==========================================================

    def send_account_unlocked(
        self,
        recipient: str,
        name: str,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject="Your Account Has Been Unlocked",

            template="account_unlocked.html",

            company=self.settings.company_name,

            name=name,

        )


# ==========================================================
# Generic Security Event
# ==========================================================

    def send_security_event(
        self,
        recipient: str,
        name: str,
        title: str,
        description: str,
        event_time: datetime,
    ) -> bool:

        return self.send_email(

            recipient=recipient,

            subject=title,

            template="security_event.html",

            company=self.settings.company_name,

            name=name,

            title=title,

            description=description,

            event_time=event_time,

        )


# ==========================================================
# Audit Email
# ==========================================================

    def send_audit_email(
        self,
        recipient: str,
        subject: str,
        template: str,
        **context,
    ) -> bool:

        context.setdefault(

            "company",

            self.settings.company_name,

        )

        return self.send_email(

            recipient=recipient,

            subject=subject,

            template=template,

            **context,

        )
        
        from collections import deque


# ==========================================================
# Email Queue
# ==========================================================

    def __init__(
        self,
        settings: EmailSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.environment = Environment(

            loader=FileSystemLoader(
                Path(self.settings.template_directory)
            ),

            autoescape=True,

        )

        self.queue: deque[EmailMessage] = deque()

        self.delivery_log: list[dict[str, Any]] = []

        self.failed_log: list[dict[str, Any]] = []


# ==========================================================
# Queue Email
# ==========================================================

    def enqueue(
        self,
        message: EmailMessage,
    ) -> None:

        self.queue.append(message)


# ==========================================================
# Queue Length
# ==========================================================

    def queue_size(
        self,
    ) -> int:

        return len(self.queue)


# ==========================================================
# Process Queue
# ==========================================================

    def process_queue(
        self,
    ) -> dict[str, int]:

        delivered = 0

        failed = 0

        while self.queue:

            message = self.queue.popleft()

            try:

                self.send(message)

                delivered += 1

                self.delivery_log.append(

                    {

                        "recipient": message["To"],

                        "subject": message["Subject"],

                        "status": "delivered",

                        "timestamp": self.now(),

                    }

                )

            except Exception as exc:

                failed += 1

                self.failed_log.append(

                    {

                        "recipient": message["To"],

                        "subject": message["Subject"],

                        "error": str(exc),

                        "timestamp": self.now(),

                    }

                )

        return {

            "delivered": delivered,

            "failed": failed,

        }


# ==========================================================
# Retry Failed Emails
# ==========================================================

    def retry_failed(
        self,
        retries: int = 3,
    ) -> int:

        retried = 0

        remaining = []

        for item in self.failed_log:

            if item.get("attempts", 0) >= retries:

                remaining.append(item)

                continue

            try:

                message = self.create_message(

                    recipient=item["recipient"],

                    subject=item["subject"],

                    html=item.get("html", ""),

                    text=item.get("text", ""),

                )

                self.send(message)

                retried += 1

            except Exception:

                item["attempts"] = item.get("attempts", 0) + 1

                remaining.append(item)

        self.failed_log = remaining

        return retried


# ==========================================================
# Batch Send
# ==========================================================

    def send_batch(
        self,
        recipients: list[str],
        subject: str,
        template: str,
        **context,
    ) -> dict[str, int]:

        delivered = 0

        failed = 0

        for recipient in recipients:

            try:

                if self.send_email(

                    recipient=recipient,

                    subject=subject,

                    template=template,

                    **context,

                ):

                    delivered += 1

                else:

                    failed += 1

            except Exception:

                failed += 1

        return {

            "delivered": delivered,

            "failed": failed,

        }


# ==========================================================
# Delivery Statistics
# ==========================================================

    def delivery_statistics(
        self,
    ) -> dict[str, Any]:

        total = (

            len(self.delivery_log)

            +

            len(self.failed_log)

        )

        delivered = len(self.delivery_log)

        failed = len(self.failed_log)

        success_rate = (

            0

            if total == 0

            else round(

                delivered * 100 / total,

                2,

            )

        )

        return {

            "total": total,

            "delivered": delivered,

            "failed": failed,

            "success_rate": success_rate,

        }


# ==========================================================
# Bounce Handler
# ==========================================================

    def record_bounce(
        self,
        recipient: str,
        reason: str,
    ) -> None:

        self.failed_log.append(

            {

                "recipient": recipient,

                "reason": reason,

                "status": "bounce",

                "timestamp": self.now(),

            }

        )


# ==========================================================
# Complaint Handler
# ==========================================================

    def record_complaint(
        self,
        recipient: str,
        reason: str,
    ) -> None:

        self.failed_log.append(

            {

                "recipient": recipient,

                "reason": reason,

                "status": "complaint",

                "timestamp": self.now(),

            }

        )


# ==========================================================
# Rate Limit
# ==========================================================

    def rate_limit_ok(
        self,
        sent_last_hour: int,
        limit: int = 500,
    ) -> bool:

        return sent_last_hour < limit


# ==========================================================
# Email Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        stats = self.delivery_statistics()

        return {

            "service": "EmailService",

            "status": "healthy",

            "queue": self.queue_size(),

            "delivered": stats["delivered"],

            "failed": stats["failed"],

            "success_rate": stats["success_rate"],

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "health": self.health(),

            "statistics": self.delivery_statistics(),

            "queue_size": self.queue_size(),

            "failed_queue": len(self.failed_log),

        }
        
        # ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(
        self,
    ) -> bool:

        if not self.settings.smtp_host:

            raise ValueError(
                "SMTP host is required."
            )

        if self.settings.smtp_port <= 0:

            raise ValueError(
                "SMTP port must be greater than zero."
            )

        if not self.settings.sender_email:

            raise ValueError(
                "Sender email is required."
            )

        if not self.settings.sender_name:

            raise ValueError(
                "Sender name is required."
            )

        if self.settings.verify_expiry_minutes <= 0:

            raise ValueError(
                "Verification expiry must be greater than zero."
            )

        if self.settings.password_reset_expiry_minutes <= 0:

            raise ValueError(
                "Password reset expiry must be greater than zero."
            )

        if self.settings.magic_link_expiry_minutes <= 0:

            raise ValueError(
                "Magic link expiry must be greater than zero."
            )

        return True


# ==========================================================
# Singleton
# ==========================================================

_email_service: EmailService | None = None


def initialize_email_service(
    settings: EmailSettings | None = None,
) -> EmailService:

    global _email_service

    _email_service = EmailService(
        settings=settings,
    )

    _email_service.validate_configuration()

    return _email_service


# ==========================================================
# Get Service
# ==========================================================

def get_email_service() -> EmailService:

    if _email_service is None:

        raise RuntimeError(
            "EmailService has not been initialized."
        )

    return _email_service


# ==========================================================
# Convenience Functions
# ==========================================================

def send_email(**kwargs):

    return get_email_service().send_email(
        **kwargs
    )


def send_verification_email(**kwargs):

    return get_email_service().send_email_verification(
        **kwargs
    )


def send_password_reset_email(**kwargs):

    return get_email_service().send_password_reset(
        **kwargs
    )


def send_magic_link(**kwargs):

    return get_email_service().send_magic_link(
        **kwargs
    )


def send_security_event(**kwargs):

    return get_email_service().send_security_event(
        **kwargs
    )


def enqueue_email(message: EmailMessage):

    return get_email_service().enqueue(
        message
    )


def process_email_queue():

    return get_email_service().process_queue()


def email_health():

    return get_email_service().health()


def email_diagnostics():

    return get_email_service().diagnostics()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "EmailSettings",

    "EmailService",

    "initialize_email_service",

    "get_email_service",

    "send_email",

    "send_verification_email",

    "send_password_reset_email",

    "send_magic_link",

    "send_security_event",

    "enqueue_email",

    "process_email_queue",

    "email_health",

    "email_diagnostics",

]