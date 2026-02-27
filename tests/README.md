# Tests del Backend

## Ejecutar Tests

### Instalar dependencias de test (si no están instaladas)
```bash
cd paddio-backend
pip install -r requirements.txt
```

### Ejecutar todos los tests
```bash
pytest
```

### Ejecutar tests específicos
```bash
# Tests de bloqueo de parámetros
pytest tests/test_turn_parameters_blocking.py -v

# Tests de turnos cancelados
pytest tests/test_cancelled_turn_blocking.py -v

# Tests de validación de géneros
pytest tests/test_gender_validation.py -v
```

### Ejecutar con más detalle
```bash
pytest -v -s
```

## Estructura de Tests

- `conftest.py`: Configuración compartida (fixtures, base de datos de test)
- `test_turn_parameters_blocking.py`: Tests para bloqueo de parámetros del partido
- `test_cancelled_turn_blocking.py`: Tests para bloqueo de turnos cancelados
- `test_gender_validation.py`: Tests para validación de géneros en turnos mixtos

## Notas

- Los tests usan SQLite en memoria para velocidad
- Cada test tiene su propia base de datos limpia
- Los fixtures crean datos de prueba reutilizables
