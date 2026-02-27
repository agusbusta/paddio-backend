#!/bin/bash
# Script para ejecutar tests del backend

echo "🔧 Activando entorno virtual..."
source venv/bin/activate

echo "🧪 Ejecutando tests..."
pytest tests/ -v

echo "✅ Tests completados"
