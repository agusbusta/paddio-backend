from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import traceback
import json
import logging
from fastapi.responses import JSONResponse

from app.database import get_db
from app.crud import user as crud
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    UserCreate,
    AdminResponse,
    AdminsResponse,
    AdminCreate,
    AdminUpdate,
    AdminSchema,
)
from app.services.auth import get_current_user, get_password_hash
from app.models.user import User

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/admins")
def get_admins(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Lista todos los administradores.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Obtener administradores
    admins = (
        db.query(User).filter(User.is_admin == True, User.is_super_admin == False).all()
    )
    admin_list = []

    for admin in admins:
        # Formato exacto que espera el frontend
        admin_data = {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "phone": admin.phone if hasattr(admin, "phone") else None,
            "club_id": None,  # Ajustar si existe relación con clubes
            "club_name": None,  # Ajustar si existe relación con clubes
            "is_active": (
                True if hasattr(admin, "is_active") and admin.is_active else False
            ),
            "created_at": (
                admin.created_at.isoformat()
                if hasattr(admin, "created_at") and admin.created_at
                else datetime.utcnow().isoformat()
            ),
            "updated_at": None,  # Ajustar si existe campo updated_at
            "role": "admin",
        }
        admin_list.append(admin_data)

    # Devolver exactamente la estructura que espera el frontend
    return {"admins": admin_list}


@router.get("/admins/{admin_id}")
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un administrador específico por ID.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Formato exacto que espera el frontend
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone if hasattr(admin, "phone") else None,
        "club_id": None,  # Ajustar si existe relación con clubes
        "club_name": None,  # Ajustar si existe relación con clubes
        "is_active": True if hasattr(admin, "is_active") and admin.is_active else False,
        "created_at": (
            admin.created_at.isoformat()
            if hasattr(admin, "created_at") and admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,  # Ajustar si existe campo updated_at
        "role": "admin",
    }

    return {"admin": admin_data}


@router.post("/admins")
def create_admin(
    admin_data: dict,  # Usar dict en lugar de modelo Pydantic para más flexibilidad
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea un nuevo administrador.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Verificar datos requeridos
    if not all(key in admin_data for key in ["name", "email", "password"]):
        raise HTTPException(status_code=400, detail="Faltan campos requeridos")

    # Verificar si el email ya existe
    existing = db.query(User).filter(User.email == admin_data["email"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Crear el administrador
    hashed_password = get_password_hash(admin_data["password"])
    new_admin = User(
        name=admin_data["name"],
        email=admin_data["email"],
        phone=admin_data.get("phone"),
        hashed_password=hashed_password,
        is_admin=True,
        is_super_admin=False,
        is_active=True,
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    # Formato exacto que espera el frontend
    response_data = {
        "id": new_admin.id,
        "name": new_admin.name,
        "email": new_admin.email,
        "phone": new_admin.phone,
        "club_id": None,
        "club_name": None,
        "is_active": new_admin.is_active,
        "created_at": (
            new_admin.created_at.isoformat()
            if hasattr(new_admin, "created_at") and new_admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,
        "role": "admin",
    }

    return {"admin": response_data}


@router.put("/admins/{admin_id}")
def update_admin(
    admin_id: int,
    admin_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un administrador existente.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Actualizar campos
    if "name" in admin_data:
        admin.name = admin_data["name"]
    if "email" in admin_data:
        # Verificar si el nuevo email ya existe
        if admin_data["email"] != admin.email:
            existing = db.query(User).filter(User.email == admin_data["email"]).first()
            if existing:
                raise HTTPException(
                    status_code=400, detail="El email ya está registrado"
                )
        admin.email = admin_data["email"]
    if "phone" in admin_data:
        admin.phone = admin_data["phone"]
    if "is_active" in admin_data:
        admin.is_active = admin_data["is_active"]

    db.commit()
    db.refresh(admin)

    # Formato exacto que espera el frontend
    response_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,
        "club_name": None,
        "is_active": admin.is_active,
        "created_at": (
            admin.created_at.isoformat()
            if hasattr(admin, "created_at") and admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,
        "role": "admin",
    }

    return {"admin": response_data}


@router.get("/admins/{admin_id}", response_model=AdminResponse)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.post(
    "/admins", response_model=AdminResponse, status_code=status.HTTP_201_CREATED
)
def create_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Verificar si el email ya existe
    existing_admin = db.query(User).filter(User.email == admin_data.email).first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="El email ya está en uso")

    # Crear hash de la contraseña
    hashed_password = get_password_hash(admin_data.password)

    # Crear el administrador
    new_admin = User(
        name=admin_data.name,
        email=admin_data.email,
        phone=admin_data.phone,
        hashed_password=hashed_password,
        is_admin=True,
        is_super_admin=False,
        is_active=True,
        created_at=datetime.utcnow(),
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": new_admin.id,
        "name": new_admin.name,
        "email": new_admin.email,
        "phone": new_admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": new_admin.is_active,
        "created_at": new_admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.put("/admins/{admin_id}", response_model=AdminResponse)
def update_admin(
    admin_id: int,
    admin_data: AdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Verificar si el email ya existe y no es del mismo admin
    if admin_data.email != admin.email:
        existing_admin = db.query(User).filter(User.email == admin_data.email).first()
        if existing_admin:
            raise HTTPException(status_code=400, detail="El email ya está en uso")

    # Actualizar datos
    admin.name = admin_data.name
    admin.email = admin_data.email
    admin.phone = admin_data.phone
    admin.is_active = admin_data.is_active

    db.commit()
    db.refresh(admin)

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    db.delete(admin)
    db.commit()

    return None


@router.patch("/admins/{admin_id}/toggle-status", response_model=AdminResponse)
def toggle_admin_status(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Cambiar estado
    admin.is_active = not admin.is_active

    db.commit()
    db.refresh(admin)

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.get("/", response_model=List[UserResponse])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all users. Requires authentication.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific user by ID. Requires authentication.
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a user. Requires authentication and user can only update their own profile.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to update other users"
        )

    db_user = crud.update_user(db=db, user_id=user_id, user=user)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a user. Requires authentication and admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to delete users"
        )

    success = crud.delete_user(db=db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}
