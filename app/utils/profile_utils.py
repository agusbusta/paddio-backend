"""
Utilidades para el cálculo de completitud del perfil.
UNA SOLA FUENTE DE VERDAD para determinar si un perfil está completo.
"""

from app.models.user import User


def calculate_profile_completeness(user: User) -> bool:
    """
    Calcula si el perfil del usuario está completo basado en los campos requeridos.

    Esta es la ÚNICA función que determina si un perfil está completo.
    Todos los lugares que necesiten verificar completitud deben usar esta función.

    Campos requeridos:
    - name: Nombre del usuario
    - last_name: Apellido del usuario
    - gender: Género
    - height: Altura
    - dominant_hand: Mano dominante
    - preferred_side: Lado preferido (Revés/Drive)
    - preferred_court_type: Tipo de cancha preferido
    - city: Ciudad
    - category: Categoría deportiva

    Nota: province es opcional ya que no todos los países/regiones tienen provincias.

    Args:
        user: Instancia del modelo User

    Returns:
        bool: True si el perfil está completo, False en caso contrario
    """
    required_fields = [
        user.name,
        user.last_name,
        user.gender,
        user.height,
        user.dominant_hand,
        user.preferred_side,
        user.preferred_court_type,
        user.city,
        user.category,
    ]

    # Verificar que todos los campos requeridos estén completos
    # Un campo está completo si no es None y no es una cadena vacía
    is_complete = all(field is not None and field != "" for field in required_fields)

    # Log detallado para depuración
    print(f"🔍 [PROFILE_UTILS] calculate_profile_completeness para usuario {user.id} ({user.email}):")
    print(f"   - name: {user.name} (completo: {user.name is not None and user.name != ''})")
    print(f"   - last_name: {user.last_name} (completo: {user.last_name is not None and user.last_name != ''})")
    print(f"   - gender: {user.gender} (completo: {user.gender is not None and user.gender != ''})")
    print(f"   - height: {user.height} (completo: {user.height is not None})")
    print(f"   - dominant_hand: {user.dominant_hand} (completo: {user.dominant_hand is not None and user.dominant_hand != ''})")
    print(f"   - preferred_side: {user.preferred_side} (completo: {user.preferred_side is not None and user.preferred_side != ''})")
    print(f"   - preferred_court_type: {user.preferred_court_type} (completo: {user.preferred_court_type is not None and user.preferred_court_type != ''})")
    print(f"   - city: {user.city} (completo: {user.city is not None and user.city != ''})")
    print(f"   - category: {user.category} (completo: {user.category is not None and user.category != ''})")
    print(f"   - province (opcional): {user.province}")
    print(f"   - is_complete: {is_complete}")
    
    # Identificar campos faltantes para debugging
    missing_fields = []
    field_names = ['name', 'last_name', 'gender', 'height', 'dominant_hand', 'preferred_side', 'preferred_court_type', 'city', 'category']
    for i, field in enumerate(required_fields):
        if field is None or field == "":
            missing_fields.append(field_names[i])
    
    if missing_fields:
        print(f"   ⚠️ Campos faltantes: {', '.join(missing_fields)}")

    return is_complete
