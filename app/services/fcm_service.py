import os
import json
import logging
from typing import List, Dict, Optional
from firebase_admin import credentials, messaging, initialize_app
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)


class FCMService:
    def __init__(self):
        self.app = None
        self._initialize_firebase()

    def _initialize_firebase(self):
        """Inicializa Firebase Admin SDK"""
        try:
            # Verificar si ya está inicializado
            if self.app is not None:
                return

            # Opción 1: Intentar leer desde variable de entorno (JSON string)
            firebase_config = os.getenv("FIREBASE_CONFIG")

            # Opción 2: Intentar leer desde archivo si no está en env
            if not firebase_config:
                firebase_config_path = os.getenv(
                    "FIREBASE_CONFIG_PATH", "firebase-service-account.json"
                )
                if os.path.exists(firebase_config_path):
                    logger.info(
                        f"Loading Firebase config from file: {firebase_config_path}"
                    )
                    with open(firebase_config_path, "r") as f:
                        config_dict = json.load(f)
                else:
                    logger.warning(
                        f"FIREBASE_CONFIG not found in environment variables "
                        f"and config file {firebase_config_path} not found"
                    )
                    return
            else:
                # Parsear configuración JSON desde string
                config_dict = json.loads(firebase_config)

            # Crear credenciales
            cred = credentials.Certificate(config_dict)

            # Inicializar Firebase Admin
            self.app = initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            self.app = None

    def is_configured(self) -> bool:
        """Verifica si FCM está configurado correctamente"""
        return self.app is not None

    def send_notification_to_token(
        self, token: str, title: str, body: str, data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Envía una notificación push a un token específico

        Args:
            token: Token FCM del dispositivo
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        if not self.is_configured():
            logger.error("FCM not configured")
            return False

        try:
            # Crear mensaje con configuración APNs para iOS
            # Firebase Admin SDK detecta automáticamente si es iOS por el token
            # Configuramos APNs para asegurar que las notificaciones lleguen correctamente
            apns_config = messaging.APNSConfig(
                headers={
                    "apns-priority": "10",  # Alta prioridad para notificaciones inmediatas
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        content_available=True,  # Permite notificaciones en background
                    ),
                ),
            )

            # Crear mensaje
            # Firebase convierte automáticamente notification a APNs para iOS
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=token,
                apns=apns_config,  # Configuración APNs adicional para iOS
            )

            # Enviar mensaje
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return True

        except FirebaseError as e:
            logger.error(f"Firebase error sending notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False

    def send_notification_to_multiple_tokens(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, int]:
        """
        Envía una notificación push a múltiples tokens

        Args:
            tokens: Lista de tokens FCM
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)

        Returns:
            Diccionario con estadísticas de envío
        """
        if not self.is_configured():
            logger.error("FCM not configured")
            return {"success": 0, "failure": len(tokens)}

        if not tokens:
            return {"success": 0, "failure": 0}

        try:
            # Configurar APNs para iOS (Firebase detecta automáticamente por token)
            apns_config = messaging.APNSConfig(
                headers={
                    "apns-priority": "10",  # Alta prioridad para notificaciones inmediatas
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        content_available=True,  # Permite notificaciones en background
                    ),
                ),
            )

            # Crear mensaje multicast
            # Firebase convierte automáticamente notification a APNs para iOS
            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=tokens,
                apns=apns_config,  # Configuración APNs adicional para iOS
            )

            # Enviar mensaje usando send_each_for_multicast
            response = messaging.send_each_for_multicast(message)

            # Log detallado de respuestas
            logger.info(
                f"Successfully sent {response.success_count} messages, "
                f"{response.failure_count} failed"
            )

            # Detectar tokens inválidos y prepararlos para eliminación
            invalid_tokens = []

            # Log de errores específicos si los hay
            if response.failure_count > 0:
                for i, resp in enumerate(response.responses):
                    if not resp.success:
                        error_str = str(resp.exception) if resp.exception else ""
                        logger.error(
                            f"Failed to send to token {tokens[i][:20]}...: {error_str}"
                        )

                        # Detectar errores que indican token inválido
                        # Estos errores significan que el token debe ser eliminado
                        if resp.exception:
                            error_code = getattr(resp.exception, "code", None)
                            error_message = str(resp.exception).lower()

                            # Errores que indican token inválido:
                            # - NOT_FOUND / "Requested entity was not found"
                            # - INVALID_ARGUMENT / "Invalid argument"
                            # - UNREGISTERED / "Unregistered"
                            if (
                                error_code == "NOT_FOUND"
                                or "not found" in error_message
                                or error_code == "INVALID_ARGUMENT"
                                or "invalid" in error_message
                                or error_code == "UNREGISTERED"
                                or "unregistered" in error_message
                            ):
                                invalid_tokens.append(tokens[i])
                                logger.warning(
                                    f"Token inválido detectado: {tokens[i][:20]}... (será eliminado)"
                                )

            return {
                "success": response.success_count,
                "failure": response.failure_count,
                "invalid_tokens": invalid_tokens,  # Lista de tokens que deben eliminarse
            }

        except FirebaseError as e:
            logger.error(f"Firebase error sending multicast notification: {e}")
            return {"success": 0, "failure": len(tokens)}
        except Exception as e:
            logger.error(f"Unexpected error sending multicast notification: {e}")
            return {"success": 0, "failure": len(tokens)}

    def send_notification_to_topic(
        self, topic: str, title: str, body: str, data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Envía una notificación push a un topic específico

        Args:
            topic: Nombre del topic
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        if not self.is_configured():
            logger.error("FCM not configured")
            return False

        try:
            # Crear mensaje
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                topic=topic,
            )

            # Enviar mensaje
            response = messaging.send(message)
            logger.info(f"Successfully sent message to topic {topic}: {response}")
            return True

        except FirebaseError as e:
            logger.error(f"Firebase error sending notification to topic: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification to topic: {e}")
            return False

    def test_connection(self) -> Dict[str, str]:
        """Prueba la conexión con Firebase"""
        if not self.is_configured():
            return {
                "status": "error",
                "message": "FCM not configured - FIREBASE_CONFIG environment variable not set",
            }

        return {
            "status": "success",
            "message": "FCM configured and ready to send notifications",
        }


# Instancia global del servicio
fcm_service = FCMService()
