"""OIDC helper — exchanges authorization codes for ID tokens and extracts claims."""

import jwt
import requests
from django.conf import settings


def _get_oidc_config():
    """Return cached OIDC provider configuration from the discovery endpoint."""
    discovery_url = settings.OIDC_DISCOVERY_URL
    if not discovery_url:
        raise ValueError("OIDC_DISCOVERY_URL is not configured.")
    resp = requests.get(discovery_url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_jwks(jwks_uri):
    """Fetch the provider's JSON Web Key Set."""
    resp = requests.get(jwks_uri, timeout=10)
    resp.raise_for_status()
    return resp.json()


def exchange_code_for_claims(code, redirect_uri):
    """
    Exchange an authorization code for an ID token and return decoded claims.

    Returns a dict with at least 'sub' and optionally 'email', 'name', etc.
    """
    config = _get_oidc_config()
    token_endpoint = config["token_endpoint"]
    jwks_uri = config["jwks_uri"]
    issuer = config["issuer"]

    # Exchange code for tokens
    token_resp = requests.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.OIDC_CLIENT_ID,
            "client_secret": settings.OIDC_CLIENT_SECRET,
        },
        timeout=10,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    id_token = token_data.get("id_token")
    if not id_token:
        raise ValueError("No id_token in token response.")

    # Decode and verify the ID token
    jwks = _get_jwks(jwks_uri)
    public_keys = {}
    for key_data in jwks.get("keys", []):
        kid = key_data.get("kid")
        if kid:
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if kid not in public_keys:
        raise ValueError("Unable to find matching key for ID token.")

    claims = jwt.decode(
        id_token,
        key=public_keys[kid],
        algorithms=["RS256"],
        audience=settings.OIDC_CLIENT_ID,
        issuer=issuer,
    )
    return claims


def get_authorization_url(redirect_uri, state):
    """Build the OIDC provider authorization URL."""
    config = _get_oidc_config()
    params = (
        f"response_type=code"
        f"&client_id={settings.OIDC_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=openid email profile"
        f"&state={state}"
    )
    return f"{config['authorization_endpoint']}?{params}"
