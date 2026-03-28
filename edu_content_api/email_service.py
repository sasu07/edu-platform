import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
APP_URL   = os.getenv("APP_URL", "http://localhost:3000")


def _send(to: str, subject: str, html: str) -> None:
    if not SMTP_HOST or not SMTP_USER:
        log.info("Email disabled (SMTP_HOST/SMTP_USER not set). Would send to %s: %s", to, subject)
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"EtoX Platform <{SMTP_FROM}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, [to], msg.as_string())
    except Exception:
        log.exception("Failed to send email to %s", to)


def send_new_request_to_teacher(teacher_email: str, teacher_name: str,
                                 student_name: str, flag_type: str, request_id: str) -> None:
    labels = {"WRITTEN": "rezolvare scrisă ✍️", "VIDEO": "clip video 🎥", "LIVE": "sesiune live 🎙️"}
    label = labels.get(flag_type, flag_type)
    link  = f"{APP_URL}/app/teacher/requests"

    html = f"""
    <p>Bună, <strong>{teacher_name}</strong>,</p>
    <p>
      <strong>{student_name}</strong> a solicitat ajutor pentru un exercițiu
      prin <strong>{label}</strong>.
    </p>
    <p>
      <a href="{link}" style="
        display:inline-block;padding:10px 20px;background:#2563eb;
        color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Vezi cererea
      </a>
    </p>
    <p style="color:#6b7280;font-size:0.85em;">EtoX Platform</p>
    """
    _send(teacher_email, f"Cerere nouă de ajutor — {student_name}", html)


def send_response_to_student(student_email: str, student_name: str,
                              teacher_name: str, flag_type: str) -> None:
    labels = {"WRITTEN": "rezolvare scrisă ✍️", "VIDEO": "clip video 🎥", "LIVE": "sesiune live 🎙️"}
    label = labels.get(flag_type, flag_type)
    link  = f"{APP_URL}/app/my-requests"

    html = f"""
    <p>Bună, <strong>{student_name}</strong>,</p>
    <p>
      Profesorul <strong>{teacher_name}</strong> a răspuns la cererea ta
      de <strong>{label}</strong>.
    </p>
    <p>
      <a href="{link}" style="
        display:inline-block;padding:10px 20px;background:#16a34a;
        color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Vezi răspunsul
      </a>
    </p>
    <p style="color:#6b7280;font-size:0.85em;">EtoX Platform</p>
    """
    _send(student_email, f"Ai primit un răspuns de la {teacher_name}", html)
