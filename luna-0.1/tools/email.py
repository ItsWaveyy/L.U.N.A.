import os
import smtplib
import ssl

from email.message import EmailMessage

from livekit.agents import function_tool, RunContext


@function_tool()
async def send_email(
    context: RunContext,
    recipient: str,
    subject: str,
    body: str,
) -> str:
    """
    Send an email.

    Use this tool only when the user explicitly asks Luna
    to send an email.
    """

    sender = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")  # Use App Password, not regular password

    if not sender or not password:
        return "Email is not configured yet."

    try:
        message = EmailMessage()

        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject

        message.set_content(body)

        context_ssl = ssl.create_default_context()

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            context=context_ssl,
        ) as server:

            server.login(sender, password)

            server.send_message(message)

        return f"Email sent successfully to {recipient}."

    except Exception as e:
        return f"I couldn't send the email: {e}"