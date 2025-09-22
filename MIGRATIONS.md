# 🔄 Migraciones con Alembic - Paddio Backend

## 📋 Flujo de Trabajo Simple

### **1. Hacer cambios en los modelos**
Modifica cualquier archivo en `app/models/`:

```python
# Ejemplo: Agregar campo a User
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    # NUEVO CAMPO
    phone = Column(String, nullable=True)  # ← Cambio aquí
```

### **2. Commit normal**
```bash
git add .
git commit -m "Add phone field to users"
```

### **3. Generar migración automática**
```bash
alembic revision --autogenerate -m "Add phone field to users"
```

### **4. Aplicar migración**
```bash
alembic upgrade head
```

## 🚀 Comandos Principales

```bash
# Generar migración automática
alembic revision --autogenerate -m "Descripción del cambio"

# Aplicar migraciones pendientes
alembic upgrade head

# Ver estado actual
alembic current

# Ver historial de migraciones
alembic history

# Revertir última migración
alembic downgrade -1
```

## ⚠️ Casos Especiales

### **Migración manual**
Si necesitas hacer cambios que Alembic no puede detectar automáticamente:

```bash
alembic revision -m "Custom migration"
# Editar el archivo generado manualmente
alembic upgrade head
```

### **Resetear base de datos (CUIDADO)**
```bash
psql paddio_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head
```

## 📝 Mejores Prácticas

1. **Siempre revisa** la migración generada antes de aplicar
2. **Usa mensajes descriptivos** para las migraciones
3. **Haz backup** antes de migraciones importantes
4. **Un cambio = una migración** (no acumules cambios)

## 🆘 Solución de Problemas

### **Error: "Can't locate revision"**
```bash
# Limpiar y reinicializar
rm -rf alembic/versions/*
alembic init alembic
# Reconfigurar env.py
# Crear nueva migración inicial
```

### **Error: "Table already exists"**
```bash
# Verificar estado
alembic current
# Aplicar migraciones pendientes
alembic upgrade head
```
