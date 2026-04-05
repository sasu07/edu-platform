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


def send_parent_invite(parent_email: str, parent_name: str,
                        student_name: str, temp_password: str) -> None:
    """Trimis când un elev adaugă un părinte care nu are cont — îi creăm contul și îi trimitem credențialele."""
    link = f"{APP_URL}/login"
    html = f"""
    <p>Bună, <strong>{parent_name}</strong>,</p>
    <p>
      <strong>{student_name}</strong> te-a adăugat ca părinte pe platforma <strong>EtoX</strong>.
      Poți urmări progresul elevului — exerciții rezolvate, variante generate, întrebări trimise.
    </p>
    <p>
      Contul tău a fost creat automat. Folosește aceste credențiale pentru a intra:
    </p>
    <ul>
      <li><strong>Email:</strong> {parent_email}</li>
      <li><strong>Parolă temporară:</strong> {temp_password}</li>
    </ul>
    <p>Te rugăm să îți schimbi parola după prima autentificare.</p>
    <p>
      <a href="{link}" style="
        display:inline-block;padding:10px 20px;background:#7c3aed;
        color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Intră în cont
      </a>
    </p>
    <p style="color:#6b7280;font-size:0.85em;">EtoX Platform</p>
    """
    _send(parent_email, f"Ai fost adăugat ca părinte al lui {student_name} — EtoX", html)


def send_parent_linked(parent_email: str, parent_name: str, student_name: str) -> None:
    """Trimis când un cont de părinte existent este legat de un elev."""
    link = f"{APP_URL}/login"
    html = f"""
    <p>Bună, <strong>{parent_name}</strong>,</p>
    <p>
      Contul tău a fost legat de profilul elevului <strong>{student_name}</strong> pe platforma EtoX.
      Acum poți urmări progresul său direct din dashboard-ul pentru părinți.
    </p>
    <p>
      <a href="{link}" style="
        display:inline-block;padding:10px 20px;background:#7c3aed;
        color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Vezi dashboard
      </a>
    </p>
    <p style="color:#6b7280;font-size:0.85em;">EtoX Platform</p>
    """
    _send(parent_email, f"Cont legat de {student_name} — EtoX", html)


def send_weekly_digest(parent_email: str, parent_name: str, student_name: str,
                        exercises_completed: int, variants_generated: int,
                        flags_sent: int, days_active: int) -> None:
    """Raport săptămânal trimis părintelui."""
    link = f"{APP_URL}/app/parent"
    html = f"""
    <p>Bună, <strong>{parent_name}</strong>,</p>
    <p>Iată activitatea lui <strong>{student_name}</strong> din săptămâna trecută:</p>
    <table style="border-collapse:collapse;width:100%;max-width:400px;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px 14px;font-weight:600;">Exerciții marcate rezolvate</td>
        <td style="padding:10px 14px;text-align:right;font-size:1.2em;font-weight:700;color:#16a34a;">{exercises_completed}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;font-weight:600;">Variante generate</td>
        <td style="padding:10px 14px;text-align:right;font-size:1.2em;font-weight:700;color:#2563eb;">{variants_generated}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px 14px;font-weight:600;">Întrebări trimise profesorilor</td>
        <td style="padding:10px 14px;text-align:right;font-size:1.2em;font-weight:700;color:#d97706;">{flags_sent}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;font-weight:600;">Zile active</td>
        <td style="padding:10px 14px;text-align:right;font-size:1.2em;font-weight:700;">{days_active}/7</td>
      </tr>
    </table>
    <br>
    <p>
      <a href="{link}" style="
        display:inline-block;padding:10px 20px;background:#7c3aed;
        color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Vezi detalii complete
      </a>
    </p>
    <p style="color:#6b7280;font-size:0.85em;">EtoX Platform — raport săptămânal</p>
    """
    _send(parent_email, f"Raport săptămânal {student_name} — EtoX", html)


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
