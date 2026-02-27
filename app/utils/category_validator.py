from app.enums.category_restriction import CategoryRestrictionType


class CategoryRestrictionValidator:
    """
    Validador para restricciones de categoría en turnos de padel.

    Maneja la lógica de validación para determinar si un jugador puede unirse
    a un turno basándose en las restricciones de categoría establecidas.
    """

    CATEGORY_NUMBERS = {
        "9na": 9,
        "8va": 8,
        "7ma": 7,
        "6ta": 6,
        "5ta": 5,
        "4ta": 4,
        "3ra": 3,
        "2da": 2,
        "1ra": 1,
    }

    @classmethod
    def can_join_turn(
        cls, player_category: str, organizer_category: str, restriction_type: str
    ) -> bool:
        """
        Determina si un jugador puede unirse a un turno basándose en las restricciones.

        Args:
            player_category: Categoría del jugador que quiere unirse
            organizer_category: Categoría del organizador del turno
            restriction_type: Tipo de restricción ('NONE', 'SAME_CATEGORY', 'NEARBY_CATEGORIES')

        Returns:
            bool: True si el jugador puede unirse, False en caso contrario
        """
        if restriction_type == CategoryRestrictionType.NONE:
            return True
        elif restriction_type == CategoryRestrictionType.SAME_CATEGORY:
            return player_category == organizer_category
        elif restriction_type == CategoryRestrictionType.NEARBY_CATEGORIES:
            player_num = cls.CATEGORY_NUMBERS.get(player_category)
            organizer_num = cls.CATEGORY_NUMBERS.get(organizer_category)
            if not player_num or not organizer_num:
                return False
            return abs(player_num - organizer_num) <= 2
        return False

    @classmethod
    def get_valid_categories(
        cls, organizer_category: str, restriction_type: str
    ) -> list:
        """
        Obtiene la lista de categorías válidas para un tipo de restricción.

        Args:
            organizer_category: Categoría del organizador
            restriction_type: Tipo de restricción

        Returns:
            list: Lista de categorías válidas
        """
        if restriction_type == CategoryRestrictionType.NONE:
            return list(cls.CATEGORY_NUMBERS.keys())
        elif restriction_type == CategoryRestrictionType.SAME_CATEGORY:
            return [organizer_category] if organizer_category else []
        elif restriction_type == CategoryRestrictionType.NEARBY_CATEGORIES:
            organizer_num = cls.CATEGORY_NUMBERS.get(organizer_category)
            if not organizer_num:
                return []

            valid_categories = []
            for category, num in cls.CATEGORY_NUMBERS.items():
                if abs(num - organizer_num) <= 2:
                    valid_categories.append(category)
            return valid_categories

        return []

    @classmethod
    def validate_restriction_type(cls, restriction_type: str) -> bool:
        """
        Valida que el tipo de restricción sea válido.

        Args:
            restriction_type: Tipo de restricción a validar

        Returns:
            bool: True si es válido, False en caso contrario
        """
        return restriction_type in [e.value for e in CategoryRestrictionType]

    @classmethod
    def get_category_difference(cls, category1: str, category2: str) -> int:
        """
        Obtiene la diferencia numérica entre dos categorías.

        Args:
            category1: Primera categoría
            category2: Segunda categoría

        Returns:
            int: Diferencia absoluta entre las categorías, -1 si alguna es inválida
        """
        num1 = cls.CATEGORY_NUMBERS.get(category1)
        num2 = cls.CATEGORY_NUMBERS.get(category2)

        if num1 is None or num2 is None:
            return -1

        return abs(num1 - num2)
