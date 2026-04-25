"""SMS Service — provider abstraction for sending SMS messages.

Supports three providers configurable via admin Settings → MFA tab:

  mfa_sms_provider = 'twilio'   (default)   — Twilio REST API
  mfa_sms_provider = 'vonage'               — Vonage (formerly Nexmo) REST API
  mfa_sms_provider = 'aws_sns'              — AWS SNS (Publish)

Config keys read from config_manager:
  mfa_sms_provider        str   'twilio' | 'vonage' | 'aws_sns'
  mfa_sms_account_sid     str   Twilio Account SID  / Vonage API key  / AWS key ID
  mfa_sms_auth_token      str   Twilio Auth Token   / Vonage API secret / AWS secret
  mfa_sms_from_number     str   Twilio / Vonage from number; not used for SNS

All imports are deferred to avoid hard-dependency errors when the package is
not installed. A graceful OSError is raised if the provider library is missing.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config_manager import config_manager

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def send_sms(to_number: str, message: str) -> tuple[bool, str]:
    """Send *message* to *to_number* using the configured SMS provider.

    Returns ``(success, error_message)``. *error_message* is empty on success.

    *to_number* must be E.164 format: ``+15551234567``.
    """
    provider = (config_manager.get('mfa_sms_provider') or 'twilio').strip().lower()

    try:
        if provider == 'twilio':
            return _send_twilio(to_number, message)
        elif provider in ('vonage', 'nexmo'):
            return _send_vonage(to_number, message)
        elif provider == 'aws_sns':
            return _send_aws_sns(to_number, message)
        else:
            err = f'Unknown SMS provider: {provider!r}'
            logger.error(err)
            return False, err
    except Exception as exc:
        logger.exception('SMS send failed to %s', _mask_number(to_number))
        return False, str(exc)


def mask_number(number: str) -> str:
    """Return a partially masked phone number for display, e.g. ``+1 *** ***4321``."""
    return _mask_number(number)


# ── Provider implementations ──────────────────────────────────────────────────

def _cfg(key: str) -> str:
    return (config_manager.get(key) or '').strip()


def _send_twilio(to_number: str, message: str) -> tuple[bool, str]:
    account_sid = _cfg('mfa_sms_account_sid')
    auth_token = _cfg('mfa_sms_auth_token')
    from_number = _cfg('mfa_sms_from_number')

    if not account_sid or not auth_token or not from_number:
        return False, 'Twilio credentials not configured (account_sid, auth_token, from_number required).'

    try:
        from twilio.rest import Client  # type: ignore
    except ImportError:
        return False, 'twilio package is not installed. Run: pip install twilio'

    try:
        client = Client(account_sid, auth_token)
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        logger.info('Twilio SMS sent to %s — SID %s', _mask_number(to_number), msg.sid)
        return True, ''
    except Exception as exc:
        logger.error('Twilio SMS error: %s', exc)
        return False, str(exc)


def _send_vonage(to_number: str, message: str) -> tuple[bool, str]:
    api_key = _cfg('mfa_sms_account_sid')
    api_secret = _cfg('mfa_sms_auth_token')
    from_name = _cfg('mfa_sms_from_number') or 'BeepAI'

    if not api_key or not api_secret:
        return False, 'Vonage credentials not configured (account_sid=APIkey, auth_token=APIsecret required).'

    try:
        import vonage  # type: ignore
    except ImportError:
        # Fallback to requests-based Vonage REST call
        return _send_vonage_rest(to_number, message, api_key, api_secret, from_name)

    try:
        client = vonage.Client(key=api_key, secret=api_secret)
        sms = vonage.Sms(client)
        resp = sms.send_message({'from': from_name, 'to': to_number.replace('+', ''), 'text': message})
        msgs = resp.get('messages', [])
        if msgs and msgs[0].get('status') == '0':
            logger.info('Vonage SMS sent to %s', _mask_number(to_number))
            return True, ''
        err = msgs[0].get('error-text', 'Unknown Vonage error') if msgs else 'Empty Vonage response'
        return False, err
    except Exception as exc:
        logger.error('Vonage SDK error: %s', exc)
        return False, str(exc)


def _send_vonage_rest(to: str, message: str, api_key: str, api_secret: str, from_name: str) -> tuple[bool, str]:
    """Vonage REST fallback (no vonage SDK)."""
    try:
        import requests  # type: ignore
    except ImportError:
        return False, 'requests package is not installed.'

    url = 'https://rest.nexmo.com/sms/json'
    payload = {
        'api_key': api_key,
        'api_secret': api_secret,
        'from': from_name,
        'to': to.replace('+', ''),
        'text': message,
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        msgs = data.get('messages', [])
        if msgs and msgs[0].get('status') == '0':
            logger.info('Vonage REST SMS sent to %s', _mask_number(to))
            return True, ''
        err = msgs[0].get('error-text', 'Unknown Vonage error') if msgs else 'Empty response'
        return False, err
    except Exception as exc:
        return False, str(exc)


def _send_aws_sns(to_number: str, message: str) -> tuple[bool, str]:
    aws_key = _cfg('mfa_sms_account_sid')
    aws_secret = _cfg('mfa_sms_auth_token')

    if not aws_key or not aws_secret:
        return False, 'AWS SNS credentials not configured (account_sid=access_key_id, auth_token=secret_access_key required).'

    try:
        import boto3  # type: ignore
    except ImportError:
        return False, 'boto3 package is not installed. Run: pip install boto3'

    try:
        sns = boto3.client(
            'sns',
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name='us-east-1',
        )
        response = sns.publish(
            PhoneNumber=to_number,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional',
                },
            },
        )
        logger.info('AWS SNS SMS sent to %s — MessageId %s',
                    _mask_number(to_number), response.get('MessageId', '?'))
        return True, ''
    except Exception as exc:
        logger.error('AWS SNS SMS error: %s', exc)
        return False, str(exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_number(number: str) -> str:
    """Mask middle digits, e.g. +15551234567 → +1*****4567."""
    n = (number or '').strip()
    if len(n) <= 4:
        return '****'
    return n[:2] + '*' * (len(n) - 5) + n[-4:]
