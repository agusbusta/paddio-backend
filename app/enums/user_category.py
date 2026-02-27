from enum import Enum


class UserCategory(str, Enum):
    """Categorías de juego de padel"""

    NOVENA = "9na"
    OCTAVA = "8va"
    SEPTIMA = "7ma"
    SEXTA = "6ta"
    QUINTA = "5ta"
    CUARTA = "4ta"
    TERCERA = "3ra"
    SEGUNDA = "2da"
    PRIMERA = "1ra"
