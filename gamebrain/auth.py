import logging
from typing import Optional

from fastapi import HTTPException
from jose import jwt
from jose.exceptions import JWTError, JWTClaimsError, ExpiredSignatureError

from .config import get_settings, Global


def check_jwt(token: str, scope: Optional[str] = None, require_sub: bool = False):
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            Global.get_jwks(),
            issuer=settings.identity.jwt_issuer,
            options={
                "verify_aud": False,
                "require_iss": True,
                "require_sub": require_sub,
            },
        )
        if scope:
            token_scopes = payload.get("scope")
            if not token_scopes:
                raise JWTClaimsError(f"JWT Error. Required: {scope}. Provided: None. ")
            if scope not in token_scopes:
                raise JWTClaimsError(f"JWT Error. Required: {scope}. Provided: {token_scopes}.")
        return payload
    except (JWTError, JWTClaimsError, ExpiredSignatureError) as e:
        logging.error(str(e))
        raise HTTPException(status_code=401, detail="JWT Error")
