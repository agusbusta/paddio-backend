import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio para envío de emails"""

    def __init__(self):
        self.smtp_server = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASS")
        self.from_email = os.getenv("SMTP_USER")
        self.from_name = os.getenv("ERROR_FROM", "Paddio Team")

    def send_verification_email(self, to_email: str, verification_code: str) -> bool:
        """
        Envía email con código de verificación

        Args:
            to_email: Email del destinatario
            verification_code: Código de 5 dígitos

        Returns:
            bool: True si se envió exitosamente, False en caso contrario
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = "Verifica tu cuenta en Paddio"

            # Cuerpo del email
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">¡Bienvenido a Paddio!</h2>
                    
                    <p>Hola,</p>
                    
                    <p>Gracias por registrarte en Paddio. Para activar tu cuenta, ingresa el siguiente código de verificación:</p>
                    
                    <div style="background-color: #f8f9fa; border: 2px solid #e9ecef; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                        <h1 style="color: #007bff; font-size: 32px; margin: 0; letter-spacing: 5px;">{verification_code}</h1>
                    </div>
                    
                    <p>Ingresa este código en la aplicación para continuar con tu registro.</p>
                    
                    <p><strong>Importante:</strong></p>
                    <ul>
                        <li>Este código expira en 15 minutos</li>
                        <li>No compartas este código con nadie</li>
                        <li>Si no solicitaste este registro, ignora este email</li>
                    </ul>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px;">
                        Saludos,<br>
                        <strong>Equipo Paddio</strong>
                    </p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, "html"))

            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()

            logger.info(f"Email de verificación enviado exitosamente a {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email de verificación a {to_email}: {e}")
            return False

    def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """
        Envía email de bienvenida después de completar el perfil

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario

        Returns:
            bool: True si se envió exitosamente, False en caso contrario
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = "¡Bienvenido a Paddio! Tu cuenta está lista"

            # Cuerpo del email
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">¡Hola {user_name}!</h2>
                    
                    <p>¡Excelente! Tu cuenta en Paddio está completamente configurada y lista para usar.</p>
                    
                    <div style="background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <h3 style="color: #155724; margin-top: 0;">¿Qué puedes hacer ahora?</h3>
                        <ul style="color: #155724;">
                            <li>Buscar y reservar turnos de pádel</li>
                            <li>Crear tus propios turnos</li>
                            <li>Invitar amigos a jugar</li>
                            <li>Explorar clubs cercanos</li>
                            <li>Gestionar tus reservas</li>
                        </ul>
                    </div>
                    
                    <p>¡Es hora de empezar a jugar pádel!</p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px;">
                        Saludos,<br>
                        <strong>Equipo Paddio</strong>
                    </p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, "html"))

            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()

            logger.info(f"Email de bienvenida enviado exitosamente a {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email de bienvenida a {to_email}: {e}")
            return False

    def send_admin_welcome_email(
        self, 
        to_email: str, 
        admin_name: str, 
        club_name: str, 
        default_password: str,
        dashboard_url: Optional[str] = None
    ) -> bool:
        """
        Envía email de bienvenida a administrador de club con credenciales

        Args:
            to_email: Email del administrador
            admin_name: Nombre del administrador
            club_name: Nombre del club asignado
            default_password: Contraseña por defecto
            dashboard_url: URL del dashboard de club (opcional)

        Returns:
            bool: True si se envió exitosamente, False en caso contrario
        """
        try:
            # URL del dashboard de club (usar variable de entorno o valor por defecto)
            if not dashboard_url:
                dashboard_url = os.getenv("CLUB_DASHBOARD_URL", "https://club.paddio.com/login")
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = f"¡Bienvenido a Paddio! Tu club {club_name} ha sido creado"

            # Cuerpo del email
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">¡Bienvenido a la familia Paddio, {admin_name}!</h2>
                    
                    <p>Nos complace informarte que tu club <strong>{club_name}</strong> ha sido creado satisfactoriamente.</p>
                    
                    <div style="background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <h3 style="color: #155724; margin-top: 0;">Tus credenciales de acceso</h3>
                        <p style="color: #155724; margin-bottom: 10px;">
                            <strong>Email:</strong> {to_email}
                        </p>
                        <p style="color: #155724; margin-bottom: 10px;">
                            <strong>Contraseña por defecto:</strong> 
                            <span style="background-color: #fff; padding: 5px 10px; border-radius: 4px; font-family: monospace; font-weight: bold; color: #155724;">
                                {default_password}
                            </span>
                        </p>
                    </div>
                    
                    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <h3 style="color: #856404; margin-top: 0;">⚠️ Importante: Cambiar contraseña</h3>
                        <p style="color: #856404;">
                            Por seguridad, te recomendamos cambiar tu contraseña después del primer inicio de sesión.
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{dashboard_url}" 
                           style="background-color: #5BE12C; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                            Iniciar Sesión en el Dashboard
                        </a>
                    </div>
                    
                    <div style="background-color: #e7f3ff; border: 1px solid #b3d9ff; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <h3 style="color: #004085; margin-top: 0;">¿Qué puedes hacer en tu dashboard?</h3>
                        <ul style="color: #004085;">
                            <li>Gestionar las canchas de tu club</li>
                            <li>Ver y administrar turnos y reservas</li>
                            <li>Configurar horarios y precios</li>
                            <li>Ver estadísticas de tu club</li>
                            <li>Gestionar información del club</li>
                        </ul>
                    </div>
                    
                    <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.</p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px;">
                        Saludos,<br>
                        <strong>Equipo Paddio</strong>
                    </p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, "html"))

            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()

            logger.info(f"Email de bienvenida a administrador enviado exitosamente a {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email de bienvenida a administrador a {to_email}: {e}")
            return False


# Instancia global del servicio
email_service = EmailService()
