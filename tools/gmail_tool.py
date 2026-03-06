# ================================================================
#  tools/gmail_tool.py
#  Gmail via IMAP (read) + SMTP (send) — NO Google Cloud needed!
#  Just uses your Gmail App Password (2-min setup)
# ================================================================

import imaplib
import smtplib
import email
import logging
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from config.settings import settings

log = logging.getLogger("GmailTool")


class GmailTool:

    # ── READ EMAILS via IMAP ──────────────────────────────────

    def get_unread_emails(self, max_results: int = None) -> List[Dict]:
        """Fetch unread emails from Gmail inbox using IMAP."""
        limit = max_results or settings.email_scan_limit
        emails = []
        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL(settings.gmail_imap_host, settings.gmail_imap_port)
            mail.login(settings.gmail_address, settings.gmail_app_password)
            mail.select("INBOX")

            # Search for unread emails
            status, message_ids = mail.search(None, "UNSEEN")
            if status != "OK":
                return []

            ids = message_ids[0].split()
            # Take latest N emails
            ids = ids[-limit:] if len(ids) > limit else ids
            ids = list(reversed(ids))  # Newest first

            for msg_id in ids:
                parsed = self._fetch_and_parse(mail, msg_id)
                if parsed:
                    emails.append(parsed)

            mail.logout()
        except Exception as e:
            log.error(f"IMAP fetch error: {e}")
        return emails

    def _fetch_and_parse(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[Dict]:
        """Fetch and parse a single email."""
        try:
            status, data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                return None

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = self._decode_header(msg.get("Subject", "(no subject)"))
            sender = self._decode_header(msg.get("From", "unknown"))
            date = msg.get("Date", "")
            msg_id_header = msg.get("Message-ID", str(msg_id))
            reply_to = msg.get("Reply-To", sender)

            body = self._extract_body(msg)

            return {
                "id": msg_id_header.strip(),
                "imap_id": msg_id.decode(),
                "subject": subject,
                "sender": sender,
                "reply_to": reply_to,
                "date": date,
                "body": body[:3000],
                "snippet": body[:200].replace("\n", " "),
            }
        except Exception as e:
            log.error(f"Email parse error: {e}")
            return None

    def _decode_header(self, value: str) -> str:
        """Decode email header (handles UTF-8, base64 encoded headers)."""
        if not value:
            return ""
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="ignore"))
            else:
                decoded.append(str(part))
        return " ".join(decoded)

    def _extract_body(self, msg) -> str:
        """Extract plain text body from email."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = part.get_payload(decode=True).decode(charset, errors="ignore")
                        break
                    except Exception:
                        continue
        else:
            if msg.get_content_type() == "text/plain":
                charset = msg.get_content_charset() or "utf-8"
                try:
                    body = msg.get_payload(decode=True).decode(charset, errors="ignore")
                except Exception:
                    body = str(msg.get_payload())
        return body.strip()

    def mark_as_read(self, imap_id: str):
        """Mark an email as read using its IMAP sequence number."""
        try:
            mail = imaplib.IMAP4_SSL(settings.gmail_imap_host, settings.gmail_imap_port)
            mail.login(settings.gmail_address, settings.gmail_app_password)
            mail.select("INBOX")
            mail.store(imap_id, "+FLAGS", "\\Seen")
            mail.logout()
        except Exception as e:
            log.error(f"Mark read error: {e}")

    # ── SEND EMAIL via SMTP ───────────────────────────────────

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via Gmail SMTP. No Google Cloud needed."""
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.gmail_address
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.gmail_smtp_host, settings.gmail_smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.gmail_address, settings.gmail_app_password)
                server.sendmail(settings.gmail_address, to, msg.as_string())

            log.info(f"Email sent → {to}: {subject}")
            return True
        except Exception as e:
            log.error(f"SMTP send error: {e}")
            return False

    def get_sender_email(self, sender_field: str) -> str:
        """Extract clean email from 'Name <email@example.com>'."""
        if "<" in sender_field:
            return sender_field.split("<")[1].rstrip(">").strip()
        return sender_field.strip()

    def search_emails(self, imap_query: str, max_results: int = 10) -> List[Dict]:
        """Search emails with IMAP query string."""
        emails = []
        try:
            mail = imaplib.IMAP4_SSL(settings.gmail_imap_host, settings.gmail_imap_port)
            mail.login(settings.gmail_address, settings.gmail_app_password)
            mail.select("INBOX")
            status, ids = mail.search(None, imap_query)
            if status == "OK":
                msg_ids = ids[0].split()[-max_results:]
                for mid in reversed(msg_ids):
                    parsed = self._fetch_and_parse(mail, mid)
                    if parsed:
                        emails.append(parsed)
            mail.logout()
        except Exception as e:
            log.error(f"Search error: {e}")
        return emails
