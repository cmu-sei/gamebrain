import logging
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader
from jose import jwt
from jose.exceptions import JWTError, JWTClaimsError, ExpiredSignatureError

from .config import get_settings, Global


def admin_api_key_dependency(x_api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    expected_api_key = get_settings().gamebrain_admin_api_key
    return check_api_key(x_api_key, expected_api_key)


def check_api_key(x_api_key: str, expected_x_api_key: str):
    if x_api_key != expected_x_api_key:
        logging.error(
            "Invalid X-API-Key header received.\n"
            f"Expected API key: {expected_x_api_key}"
            f"Request included: {x_api_key}\n"
        )
        raise HTTPException(
            status_code=401,
            detail=f"Invalid X-API-Key header received. You sent: \n{x_api_key}",
        )


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
                raise JWTClaimsError(
                    f"JWT Error. Required: {scope}. Provided: {token_scopes}."
                )
        return payload
    except (JWTError, JWTClaimsError, ExpiredSignatureError) as e:
        logging.error(str(e))
        raise HTTPException(status_code=401, detail="JWT Error")
