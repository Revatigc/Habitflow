import jwt, httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from ..database import settings, db
from ..models.core import User
bearer=HTTPBearer()
async def current_user(token:HTTPAuthorizationCredentials=Depends(bearer), session:Session=Depends(db)):
    try:
        jwks=(await httpx.AsyncClient().get(f"https://{settings.auth_provider_domain}/.well-known/jwks.json")).json()
        key=jwt.PyJWKClient(f"https://{settings.auth_provider_domain}/.well-known/jwks.json").get_signing_key_from_jwt(token.credentials).key
        claims=jwt.decode(token.credentials,key,algorithms=["RS256"],audience=settings.auth_audience,issuer=f"https://{settings.auth_provider_domain}/")
    except Exception: raise HTTPException(401,"Invalid or expired session")
    user=session.get(User,claims["sub"])
    if not user:
        user=User(id=claims["sub"],email=claims.get("email",""),name=claims.get("name","Member")); session.add(user); session.commit()
    return user
