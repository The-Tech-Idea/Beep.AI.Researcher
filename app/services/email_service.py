"""Email service — multi-backend outbound mail.

Supported authentication methods (set via Admin → Settings → Email):

  ``smtp``          Classic SMTP with optional STARTTLS.
  ``oauth2_ms365``  Microsoft 365 / Exchange Online via MSAL client-credentials.
                    Requires ``pip install msal``.
  ``oauth2_google`` Google Workspace via service-account or OAuth2 refresh token.
                    Requires ``pip install google-auth``.

The active backend is chosen from ``config_manager.get('mail_auth_method')``.
``is_configured()`` returns True as long as ``smtp_host`` *or* the needed
OAuth2 credentials are present — callers that relied on ``smtp_host`` alone
should migrate to ``is_configured()``.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

from app.config_manager import config_manager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Return True if any email backend has enough credentials to send mail."""
    method = _auth_method()
    if method == 'smtp':
        return bool(config_manager.get_setting('smtp_host', env_var='SMTP_HOST'))
    if method == 'oauth2_ms365':
        return bool(
            config_manager.get_setting('mail_oauth2_client_id')
            and config_manager.get_setting('mail_oauth2_client_secret')
            and config_manager.get_setting('mail_oauth2_tenant_id')
            and config_manager.get_setting('mail_from')
        )
    if method == 'oauth2_google':
        return bool(
            config_manager.get_setting('mail_oauth2_client_id')
            and config_manager.get_setting('mail_oauth2_refresh_token')
            and config_manager.get_setting('mail_from')
        )
    return False


def send_email(subject: str, body: str, recipients: List[str],
               html_body: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Send an email using the configured backend.

    Args:
        subject: Email subject line.
        body: Plain-text body.
        recipients: List of recipient email addresses.
        html_body: Optional HTML alternative body.

    Returns:
        (success: bool, error_message: str | None)
    """
    if not recipients:
        return False, 'No recipients provided'

    method = _auth_method()
    try:
        if method == 'smtp':
            return _send_smtp(subject, body, html_body, recipients)
        if method == 'oauth2_ms365':
            return _send_ms365_graph(subject, body, html_body, recipients)
        if method == 'oauth2_google':
            return _send_google_oauth2(subject, body, html_body, recipients)
        return False, f'Unknown mail_auth_method: {method!r}'
    except Exception as exc:
        logger.exception('email send failed')
        return False, str(exc)


# ── Convenience functions ─────────────────────────────────────────────────────

def send_verification_email(user, verify_url: str) -> Tuple[bool, Optional[str]]:
    """Send email-verification link to a new user."""
    instance = config_manager.get('instance_name', 'Beep.AI Researcher')
    subject = f'Verify your {instance} account'
    plain = (
        f'Hello {user.username},\n\n'
        f'Please verify your email by clicking the link below:\n\n'
        f'{verify_url}\n\n'
        f'This link expires in 24 hours.\n\n'
        f'If you did not create an account, ignore this email.\n\n'
        f'— {instance}'
    )
    html = (
        f'<p>Hello <strong>{user.username}</strong>,</p>'
        f'<p>Please verify your email address:</p>'
        f'<p><a href="{verify_url}">{verify_url}</a></p>'
        f'<p>This link expires in 24 hours.</p>'
        f'<p>If you did not create an account, ignore this email.</p>'
        f'<p>— {instance}</p>'
    )
    to = [user.email] if user.email else []
    return send_email(subject, plain, to, html_body=html)


def send_password_reset_email(user, reset_url: str) -> Tuple[bool, Optional[str]]:
    """Send a password-reset link."""
    instance = config_manager.get('instance_name', 'Beep.AI Researcher')
    subject = f'Reset your {instance} password'
    plain = (
        f'Hello {user.username},\n\n'
        f'Click the link below to reset your password:\n\n'
        f'{reset_url}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not request a reset, ignore this email.\n\n'
        f'— {instance}'
    )
    html = (
        f'<p>Hello <strong>{user.username}</strong>,</p>'
        f'<p>Click below to reset your password:</p>'
        f'<p><a href="{reset_url}">{reset_url}</a></p>'
        f'<p>This link expires in 1 hour.</p>'
        f'<p>If you did not request a reset, ignore this email.</p>'
        f'<p>— {instance}</p>'
    )
    to = [user.email] if user.email else []
    return send_email(subject, plain, to, html_body=html)


def send_mfa_otp_email(user, otp_code: str) -> Tuple[bool, Optional[str]]:
    """Send a one-time MFA code via email."""
    instance = config_manager.get('instance_name', 'Beep.AI Researcher')
    subject = f'Your {instance} login code'
    plain = (
        f'Hello {user.username},\n\n'
        f'Your one-time login code is:\n\n'
        f'  {otp_code}\n\n'
        f'This code expires in 10 minutes.\n\n'
        f'— {instance}'
    )
    html = (
        f'<p>Hello <strong>{user.username}</strong>,</p>'
        f'<p>Your one-time login code is:</p>'
        f'<p style="font-size:2em;letter-spacing:0.15em;font-weight:bold;">'
        f'{otp_code}</p>'
        f'<p>This code expires in 10 minutes.</p>'
        f'<p>— {instance}</p>'
    )
    to = [user.email] if user.email else []
    return send_email(subject, plain, to, html_body=html)


def send_invite_email(invite, invite_url: str) -> Tuple[bool, Optional[str]]:
    """Send an account-invitation email."""
    instance = config_manager.get('instance_name', 'Beep.AI Researcher')
    subject = f"You've been invited to {instance}"
    plain = (
        f'Hello,\n\n'
        f'You have been invited to join {instance}.\n\n'
        f'Click the link below to create your account:\n\n'
        f'{invite_url}\n\n'
        f'This invitation expires in 7 days.\n\n'
        f'— {instance}'
    )
    html = (
        f'<p>Hello,</p>'
        f'<p>You have been invited to join <strong>{instance}</strong>.</p>'
        f'<p><a href="{invite_url}">Accept invitation</a></p>'
        f'<p>This invitation expires in 7 days.</p>'
        f'<p>— {instance}</p>'
    )
    to = [invite.email] if invite.email else []
    return send_email(subject, plain, to, html_body=html)


# ─────────────────────────────────────────────────────────────────────────────
# Backend implementations
# ─────────────────────────────────────────────────────────────────────────────

def _auth_method() -> str:
    return config_manager.get('mail_auth_method', 'smtp') or 'smtp'


def _mail_from() -> str:
    return (
        config_manager.get_setting('mail_from', env_var='MAIL_FROM')
        or config_manager.get_setting('smtp_user', env_var='SMTP_USER')
        or 'noreply@localhost'
    )


def _build_mime(subject: str, body: str, html_body: Optional[str],
                recipients: List[str]) -> MIMEMultipart:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = _mail_from()
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    return msg


# ── SMTP ──────────────────────────────────────────────────────────────────────

def _send_smtp(subject: str, body: str, html_body: Optional[str],
               recipients: List[str]) -> Tuple[bool, Optional[str]]:
    host = config_manager.get_setting('smtp_host', env_var='SMTP_HOST') or ''
    if not host:
        return False, 'smtp_host is not configured'
    port = int(
        config_manager.get_setting('smtp_port', default=587, env_var='SMTP_PORT')
        or 587
    )
    user = config_manager.get_setting('smtp_user', env_var='SMTP_USER') or ''
    password = config_manager.get_setting('smtp_password', env_var='SMTP_PASSWORD') or ''
    use_tls = config_manager.get_setting('smtp_use_tls', default=True,
                                          env_var='SMTP_USE_TLS')
    if isinstance(use_tls, str):
        use_tls = use_tls.lower() in ('1', 'true', 'yes')
    mail_from = _mail_from()

    msg = _build_mime(subject, body, html_body, recipients)
    msg['From'] = mail_from

    with smtplib.SMTP(host, port, timeout=15) as server:
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(mail_from, recipients, msg.as_string())
    return True, None


# ── MS365 via Microsoft Graph ─────────────────────────────────────────────────

def _send_ms365_graph(subject: str, body: str, html_body: Optional[str],
                       recipients: List[str]) -> Tuple[bool, Optional[str]]:
    """Send via Microsoft Graph API using client-credentials OAuth2 flow.

    Requires: pip install msal requests
    """
    try:
        import msal
        import requests as req
    except ImportError:
        return False, "oauth2_ms365 requires 'msal' and 'requests': pip install msal requests"

    client_id     = config_manager.get('mail_oauth2_client_id', '')
    client_secret = config_manager.get('mail_oauth2_client_secret', '')
    tenant_id     = config_manager.get('mail_oauth2_tenant_id', '')
    sender        = _mail_from()

    if not all([client_id, client_secret, tenant_id, sender]):
        return False, 'MS365 OAuth2 credentials incomplete in admin settings'

    authority = f'https://login.microsoftonline.com/{tenant_id}'
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )
    token_result = app.acquire_token_for_client(
        scopes=['https://graph.microsoft.com/.default']
    )
    if 'access_token' not in token_result:
        err = token_result.get('error_description', str(token_result))
        return False, f'MS365 token acquisition failed: {err}'

    token = token_result['access_token']
    to_addrs = [{'emailAddress': {'address': r}} for r in recipients]
    payload: dict = {
        'message': {
            'subject': subject,
            'body': {
                'contentType': 'HTML' if html_body else 'Text',
                'content': html_body or body,
            },
            'toRecipients': to_addrs,
        },
        'saveToSentItems': 'false',
    }
    url = f'https://graph.microsoft.com/v1.0/users/{sender}/sendMail'
    resp = req.post(
        url,
        json=payload,
        headers={'Authorization': f'Bearer {token}',
                 'Content-Type': 'application/json'},
        timeout=15,
    )
    if resp.status_code == 202:
        return True, None
    return False, f'Graph API error {resp.status_code}: {resp.text}'


# ── Google Workspace OAuth2 ───────────────────────────────────────────────────

def _send_google_oauth2(subject: str, body: str, html_body: Optional[str],
                         recipients: List[str]) -> Tuple[bool, Optional[str]]:
    """Send via Gmail API using OAuth2 refresh-token flow.

    Requires: pip install google-auth google-auth-oauthlib google-api-python-client
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import base64
    except ImportError:
        return False, (
            "oauth2_google requires Google client libraries: "
            "pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    client_id     = config_manager.get('mail_oauth2_client_id', '')
    client_secret = config_manager.get('mail_oauth2_client_secret', '')
    refresh_token = config_manager.get('mail_oauth2_refresh_token', '')
    sender        = _mail_from()

    if not all([client_id, client_secret, refresh_token, sender]):
        return False, 'Google OAuth2 credentials incomplete in admin settings'

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
    )
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    msg = _build_mime(subject, body, html_body, recipients)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(
        userId='me', body={'raw': raw}
    ).execute()
    return True, None

