"""
Email service for Paddio Backend
Handles SMTP configuration and email sending with HTML templates
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.from_addr = os.getenv("ERROR_FROM", "errors@paddio.local")
        self.to_addrs = [
            addr.strip()
            for addr in os.getenv("ERROR_TO", "").split(",")
            if addr.strip()
        ]

    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return bool(
            self.smtp_host and self.smtp_user and self.smtp_pass and self.to_addrs
        )

    def test_connection(self) -> dict:
        """Test SMTP connection and return detailed results"""
        result = {
            "config": {
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port,
                "smtp_user": self.smtp_user,
                "smtp_pass_length": len(self.smtp_pass) if self.smtp_pass else 0,
                "smtp_use_tls": self.smtp_use_tls,
                "to_addrs": self.to_addrs,
            },
            "tests": {},
        }

        try:
            # Test 1: Connect to SMTP server
            logger.info("Testing SMTP connection...")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            result["tests"]["connection"] = "✅ Connected successfully"

            # Test 2: Start TLS if needed
            if self.smtp_use_tls:
                logger.info("Starting TLS...")
                server.starttls()
                result["tests"]["tls"] = "✅ TLS started successfully"

            # Test 3: Login with credentials
            logger.info("Testing login...")
            server.login(self.smtp_user, self.smtp_pass)
            result["tests"]["login"] = "✅ Login successful"

            # Test 4: Close connection
            server.quit()
            result["tests"]["disconnect"] = "✅ Disconnected successfully"

            result["status"] = "✅ All tests passed! SMTP is correctly configured."

        except smtplib.SMTPAuthenticationError as e:
            result["tests"]["login"] = f"❌ Authentication failed: {str(e)}"
            result["status"] = "❌ SMTP authentication failed"
            logger.error(f"SMTP auth error: {e}")

        except smtplib.SMTPException as e:
            result["tests"]["smtp_error"] = f"❌ SMTP error: {str(e)}"
            result["status"] = "❌ SMTP configuration error"
            logger.error(f"SMTP error: {e}")

        except Exception as e:
            result["tests"]["general_error"] = f"❌ General error: {str(e)}"
            result["status"] = "❌ Unexpected error"
            logger.error(f"General error: {e}")

        return result

    def send_error_email(self, error_data: dict) -> bool:
        """
        Send error notification email

        Args:
            error_data: Dictionary containing error information
                - path: Request path
                - method: HTTP method
                - client: Client IP
                - user: User email (optional)
                - exception: Exception object
                - timestamp: Error timestamp
        """
        if not self.is_configured():
            logger.warning("Email service not configured, skipping error email")
            return False

        try:
            # Generate HTML content
            html_content = self._generate_error_html(error_data)

            # Create email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[Paddio Backend][{os.getenv('ENV', 'development')}] ERROR"
            )
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            # Add HTML content
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.smtp_use_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
            server.quit()

            logger.info(f"Error email sent successfully to {', '.join(self.to_addrs)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send error email: {e}")
            return False

    def _generate_error_html(self, error_data: dict) -> str:
        """Generate HTML content for error email"""
        import traceback

        path = error_data.get("path", "Unknown")
        method = error_data.get("method", "Unknown")
        client = error_data.get("client", "Unknown")
        user = error_data.get("user", "Anonymous")
        exception = error_data.get("exception")
        timestamp = error_data.get(
            "timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Generate traceback
        traceback_html = ""
        if exception:
            try:
                tb_lines = traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
                for line in tb_lines:
                    clean_line = line.strip()
                    if clean_line:
                        traceback_html += f'<div class="line">{clean_line}</div>'
            except:
                traceback_html = '<div class="line">Unable to generate traceback</div>'
        else:
            traceback_html = '<div class="line">No traceback available</div>'

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                .header .env {{ opacity: 0.9; font-size: 14px; margin-top: 5px; }}
                .content {{ padding: 20px; }}
                .error-info {{ background: #f8f9fa; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; border-radius: 4px; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 15px 0; }}
                .info-item {{ background: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #e9ecef; }}
                .info-label {{ font-weight: 600; color: #495057; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .info-value {{ color: #212529; font-size: 14px; margin-top: 4px; word-break: break-all; }}
                .traceback {{ background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 6px; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 12px; line-height: 1.4; overflow-x: auto; }}
                .traceback .line {{ margin: 2px 0; }}
                .footer {{ background: #f8f9fa; padding: 15px; text-align: center; color: #6c757d; font-size: 12px; border-top: 1px solid #e9ecef; }}
                .timestamp {{ color: #6c757d; font-size: 12px; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 Error Report</h1>
                    <div class="env">Paddio Backend • {os.getenv('ENV', 'development').upper()}</div>
                </div>
                
                <div class="content">
                    <div class="timestamp">
                        📅 {timestamp} UTC
                    </div>
                    
                    <div class="error-info">
                        <strong>❌ Unhandled Exception</strong><br>
                        <span style="color: #6c757d; font-size: 14px;">An unexpected error occurred in the application</span>
                    </div>
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">🌐 Endpoint</div>
                            <div class="info-value">{method} {path}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">👤 User</div>
                            <div class="info-value">{user}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">🌍 Client IP</div>
                            <div class="info-value">{client}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">⚡ Level</div>
                            <div class="info-value">ERROR</div>
                        </div>
                    </div>
                    
                    <h3 style="color: #dc3545; margin-top: 25px;">📋 Stack Trace</h3>
                    <div class="traceback">
                        {traceback_html}
                    </div>
                </div>
                
                <div class="footer">
                    <div>🔧 Paddio Backend Error Reporting System</div>
                    <div style="margin-top: 5px;">This email was automatically generated by the application error handler</div>
                </div>
            </div>
        </body>
        </html>
        """

        return html_content


# Global email service instance
email_service = EmailService()
