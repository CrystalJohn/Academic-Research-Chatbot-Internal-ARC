"""
Authentication Service for Cognito JWT verification.

Verifies JWT tokens from AWS Cognito and extracts user info.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from functools import lru_cache
import time

import httpx
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# Configuration
COGNITO_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-southeast-1_8KB4JYvsX")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "457qqut8jm0b6a46dttdrn6rs4")

# Cognito JWKS URL
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

# Security scheme
security = HTTPBearer(auto_error=False)


class CognitoJWKS:
    """Cache and manage Cognito JWKS keys."""
    
    def __init__(self):
        self._keys: Dict[str, Any] = {}
        self._last_fetch: float = 0
        self._cache_ttl: int = 3600  # 1 hour
    
    def _should_refresh(self) -> bool:
        return time.time() - self._last_fetch > self._cache_ttl
    
    def get_keys(self) -> Dict[str, Any]:
        """Get JWKS keys, fetching if needed."""
        if not self._keys or self._should_refresh():
            self._fetch_keys()
        return self._keys
    
    def _fetch_keys(self):
        """Fetch JWKS from Cognito."""
        try:
            response = httpx.get(JWKS_URL, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
            
            # Index by kid for fast lookup
            self._keys = {key["kid"]: key for key in jwks.get("keys", [])}
            self._last_fetch = time.time()
            logger.info(f"Fetched {len(self._keys)} JWKS keys from Cognito")
            
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            if not self._keys:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable"
                )
    
    def get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get specific key by kid."""
        keys = self.get_keys()
        return keys.get(kid)


# Global JWKS cache
_jwks_cache = CognitoJWKS()


def verify_cognito_token(token: str) -> Dict[str, Any]:
    """
    Verify Cognito JWT token and return claims.
    
    Args:
        token: JWT token string
        
    Returns:
        Token claims dict
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Decode header to get kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing kid"
            )
        
        # Get public key
        key_data = _jwks_cache.get_key(kid)
        if not key_data:
            # Try refreshing keys
            _jwks_cache._fetch_keys()
            key_data = _jwks_cache.get_key(kid)
            
            if not key_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: unknown key"
                )
        
        # Construct public key
        public_key = jwk.construct(key_data)
        
        # Verify and decode token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )
        
        return claims
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )


class CurrentUser:
    """Represents authenticated user."""
    
    def __init__(self, claims: Dict[str, Any]):
        self.claims = claims
        self.user_id = claims.get("sub", "")
        self.email = claims.get("email", "")
        self.username = claims.get("cognito:username", claims.get("preferred_username", ""))
        self.groups: List[str] = claims.get("cognito:groups", [])
    
    @property
    def is_admin(self) -> bool:
        return "admin" in self.groups
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "groups": self.groups,
            "is_admin": self.is_admin,
        }


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> CurrentUser:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: CurrentUser = Depends(get_current_user)):
            return {"user": user.email}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    claims = verify_cognito_token(credentials.credentials)
    return CurrentUser(claims)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[CurrentUser]:
    """
    Optional authentication - returns None if not authenticated.
    
    Usage:
        @router.get("/public")
        async def public_route(user: Optional[CurrentUser] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello guest"}
    """
    if not credentials:
        return None
    
    try:
        claims = verify_cognito_token(credentials.credentials)
        return CurrentUser(claims)
    except HTTPException:
        return None


async def require_admin(
    user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Require admin role.
    
    Usage:
        @router.post("/admin-only")
        async def admin_route(admin: CurrentUser = Depends(require_admin)):
            return {"admin": admin.email}
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
