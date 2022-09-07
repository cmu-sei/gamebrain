from typing import Optional

from fastapi import HTTPException
from jose import jwt
from jose.exceptions import JWTError, JWTClaimsError, ExpiredSignatureError

from .config import get_settings, Global


def check_jwt(token: str, audience: Optional[str] = None, require_sub: bool = False):
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            Global.get_jwks(),
            audience=audience,
            issuer=settings.identity.jwt_issuer,
            options={
                "require_aud": True,
                "require_iss": True,
                "require_sub": require_sub,
            },
        )
    except (JWTError, JWTClaimsError, ExpiredSignatureError):
        raise HTTPException(status_code=401, detail="JWT Error")
