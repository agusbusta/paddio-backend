from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user import UserCreate, UserResponse, UserChangePassword
from app.schemas.auth_two_step import (
    UserBasicRegistration,
    EmailVerification,
    UserProfileCompletion,
    ResendCodeRequest,
    UserBasicResponse,
    EmailVerificationResponse,
    ProfileCompletionResponse,
    ResendCodeResponse,
    RefreshTokenRequest,
)
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_user_from_refresh_token,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user,
)
from app.models.user import User
from app.utils.auth_two_step import (
    create_user_basic,
    get_user_by_email,
    get_user_by_email_and_code,
    activate_user,
    update_verification_code,
    complete_user_profile,
    is_verification_code_expired,
)
from app.services.email_service import email_service

router = APIRouter()


@router.post("/register-basic", response_model=UserBasicResponse)
def register_basic(user_data: UserBasicRegistration, db: Session = Depends(get_db)):
    """
    Registro básico (Paso 1): Crea usuario pendiente de verificación
    """
    # Verificar si el email ya existe
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    # Crear usuario básico
    user = create_user_basic(
        db=db,
        name=user_data.name,
        last_name=user_data.last_name,
        email=user_data.email,
        password=user_data.password,
        gender=user_data.gender,
    )

    # Enviar email con código de verificación
    email_sent = email_service.send_verification_email(
        to_email=user.email, verification_code=user.verification_code
    )

    if not email_sent:
        # Si falla el envío de email, eliminar el usuario creado
        db.delete(user)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Error enviando email de verificación. Intenta nuevamente.",
        )

    return UserBasicResponse(
        success=True,
        temp_token=user.temp_token,
        message="Código de verificación enviado a tu email",
    )


@router.post("/verify-email", response_model=EmailVerificationResponse)
def verify_email(verification_data: EmailVerification, db: Session = Depends(get_db)):
    """
    Verificación de email (Paso 2): Verifica código y activa cuenta
    """
    # Buscar usuario por email y código
    user = get_user_by_email_and_code(
        db=db, email=verification_data.email, code=verification_data.code
    )

    if not user:
        raise HTTPException(status_code=400, detail="Código inválido")

    # Verificar token temporal
    if user.temp_token != verification_data.temp_token:
        raise HTTPException(status_code=400, detail="Token inválido")

    # Verificar si el código ha expirado
    if is_verification_code_expired(user):
        raise HTTPException(
            status_code=400, detail="Código expirado. Solicita uno nuevo."
        )

    # Activar usuario
    activation_success = activate_user(db, user.id)
    if not activation_success:
        raise HTTPException(status_code=500, detail="Error activando cuenta")

    # Generar token de acceso y refresh
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.email})

    return EmailVerificationResponse(
        success=True,
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "name": user.name,
            "last_name": user.last_name,
            "email": user.email,
            "is_profile_complete": user.is_profile_complete,
        },
        message="Cuenta verificada exitosamente",
    )


@router.post("/resend-code", response_model=ResendCodeResponse)
def resend_code(email_data: ResendCodeRequest, db: Session = Depends(get_db)):
    """
    Reenvía código de verificación
    """
    user = get_user_by_email(db, email_data.email)

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.is_active:
        raise HTTPException(status_code=400, detail="Usuario ya verificado")

    # Generar nuevo código
    new_code = update_verification_code(db, user.id)
    if not new_code:
        raise HTTPException(status_code=500, detail="Error generando nuevo código")

    # Reenviar email
    email_sent = email_service.send_verification_email(
        to_email=user.email, verification_code=new_code
    )

    if not email_sent:
        raise HTTPException(
            status_code=500, detail="Error enviando email. Intenta nuevamente."
        )

    return ResendCodeResponse(success=True, message="Código reenviado exitosamente")


@router.post("/complete-profile", response_model=ProfileCompletionResponse)
def complete_profile(
    profile_data: UserProfileCompletion,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Completar perfil (Paso 3): Completa información deportiva
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Usuario no verificado")

    if current_user.is_profile_complete:
        raise HTTPException(status_code=400, detail="Perfil ya completado")

    # Actualizar perfil
    updated_user = complete_user_profile(
        db=db,
        user_id=current_user.id,
        profile_data=profile_data.dict(exclude_unset=True),
    )

    if not updated_user:
        raise HTTPException(status_code=500, detail="Error completando perfil")

    # Enviar email de bienvenida
    email_service.send_welcome_email(
        to_email=updated_user.email, user_name=updated_user.name
    )

    return ProfileCompletionResponse(
        success=True,
        user={
            "id": updated_user.id,
            "name": updated_user.name,
            "last_name": updated_user.last_name,
            "email": updated_user.email,
            "category": updated_user.category,
            "gender": updated_user.gender,
            "height": updated_user.height,
            "dominant_hand": updated_user.dominant_hand,
            "preferred_side": updated_user.preferred_side,
            "preferred_court_type": updated_user.preferred_court_type,
            "city": updated_user.city,
            "province": updated_user.province,
            "is_profile_complete": updated_user.is_profile_complete,
        },
        message="Perfil completado exitosamente",
    )


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        name=user.name,
        email=user.email,
        phone=user.phone,
        hashed_password=hashed_password,
        category=user.category.value if user.category else None,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    print(f"🔍 DEBUG: Buscando usuario con email: {form_data.username}")

    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        print(f"❌ DEBUG: Usuario no autenticado para email: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(
        f"✅ DEBUG: Usuario autenticado - ID: {user.id}, Name: {user.name}, Email: {user.email}"
    )
    print(
        f"📊 DEBUG: is_profile_complete: {user.is_profile_complete}, category: {user.category}"
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.email})

    # Devolver perfil completo del usuario
    user_response = {
        "id": str(user.id),
        "name": user.name,
        "last_name": user.last_name,
        "email": user.email,
        "is_profile_complete": user.is_profile_complete,
        "category": user.category,
        "gender": user.gender,
        "height": user.height,
        "dominant_hand": user.dominant_hand,
        "preferred_side": user.preferred_side,
        "preferred_court_type": user.preferred_court_type,
        "city": user.city,
        "province": user.province,
        "photoUrl": user.profile_image_url,
        "phoneNumber": user.phone,
        "isActive": user.is_active,
        "is_admin": user.is_admin,
        "is_super_admin": user.is_super_admin,
        "club_id": user.club_id,  # Agregar club_id para admins
        "must_change_password": user.must_change_password,  # Flag para forzar cambio de contraseña
        "createdAt": user.created_at.isoformat() if user.created_at else None,
    }

    print(f"📤 DEBUG: Enviando respuesta con user: {user_response}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_response,
    }


@router.post("/refresh")
def refresh_access_token(
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Renueva access_token y refresh_token usando el refresh_token (sin Bearer)."""
    user = get_user_from_refresh_token(body.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    print(
        f"🔍 DEBUG GET /me: Usuario actual - ID: {current_user.id}, Name: {current_user.name}, Email: {current_user.email}"
    )
    print(
        f"📊 DEBUG GET /me: is_profile_complete: {current_user.is_profile_complete}, category: {current_user.category}"
    )

    # Devolver perfil completo del usuario
    user_response = {
        "id": str(current_user.id),
        "name": current_user.name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "is_profile_complete": current_user.is_profile_complete,
        "category": current_user.category,
        "gender": current_user.gender,
        "height": current_user.height,
        "dominant_hand": current_user.dominant_hand,
        "preferred_side": current_user.preferred_side,
        "preferred_court_type": current_user.preferred_court_type,
        "city": current_user.city,
        "province": current_user.province,
        "photoUrl": current_user.profile_image_url,
        "phoneNumber": current_user.phone,
        "isActive": current_user.is_active,
        "is_admin": current_user.is_admin,
        "is_super_admin": current_user.is_super_admin,
        "club_id": current_user.club_id,  # Agregar club_id para admins
        "must_change_password": current_user.must_change_password,  # Flag para forzar cambio de contraseña
        "createdAt": (
            current_user.created_at.isoformat() if current_user.created_at else None
        ),
    }

    print(f"📤 DEBUG GET /me: Enviando respuesta con user: {user_response}")

    return {
        "success": True,
        "user": user_response,
    }


@router.post("/refresh-token")
def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Refresh the access token for the current user.
    This endpoint allows users to get a new token without re-entering credentials.
    """
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.email}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # en segundos
        "message": "Token refreshed successfully",
    }


@router.post("/change-password", response_model=dict)
def change_password(
    password_data: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password. Requires authentication.
    The user must provide the current password for security verification.
    """
    # Verify current password
    user = authenticate_user(db, current_user.email, password_data.current_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update password
    hashed_password = get_password_hash(password_data.new_password)
    user.hashed_password = hashed_password
    # Marcar que ya no necesita cambiar la contraseña
    user.must_change_password = False
    db.commit()

    return {"message": "Password updated successfully"}
