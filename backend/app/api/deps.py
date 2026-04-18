from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.notification_service import (
    NotificationService,
    build_notification_service,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_notification_service_instance: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Lazy-init singleton notification service based on current settings."""
    global _notification_service_instance
    if _notification_service_instance is None:
        _notification_service_instance = build_notification_service(settings)
    return _notification_service_instance


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user
