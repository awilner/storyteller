import logging
import secrets

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..models import OIDCIdentity
from ..oidc import exchange_code_for_claims, get_authorization_url
from ..serializers import UserSerializer

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def oidc_login_view(request):
    """Return the OIDC authorization URL. Frontend redirects the browser there."""
    redirect_uri = request.query_params.get("redirect_uri", "")
    if not redirect_uri:
        return Response(
            {"detail": _("redirect_uri query param is required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    state = secrets.token_urlsafe(32)
    request.session["oidc_state"] = state
    url = get_authorization_url(redirect_uri, state)
    return Response({"authorization_url": url})


@api_view(["POST"])
@permission_classes([AllowAny])
def oidc_callback_view(request):
    code = request.data.get("code", "")
    redirect_uri = request.data.get("redirect_uri", "")
    state = request.data.get("state", "")

    if not code or not redirect_uri:
        return Response(
            {"detail": _("code and redirect_uri are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expected_state = request.session.pop("oidc_state", None)
    if not expected_state or state != expected_state:
        return Response(
            {"detail": _("Invalid or missing state parameter.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        claims = exchange_code_for_claims(code, redirect_uri)
    except Exception:
        logger.error("OIDC token exchange failed", exc_info=True)
        return Response(
            {"detail": _("OIDC token exchange failed")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sub = claims.get("sub", "")
    email = claims.get("email", "")
    provider = claims.get("iss", "oidc")

    try:
        identity = OIDCIdentity.objects.select_related("user").get(
            provider=provider, sub=sub,
        )
        user = identity.user
    except OIDCIdentity.DoesNotExist:
        base_username = email.split("@")[0] if email else f"oidc_{sub[:8]}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create_user(username=username, email=email)
        OIDCIdentity.objects.create(
            user=user, provider=provider, sub=sub, email=email,
        )

    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def oidc_link_view(request):
    code = request.data.get("code", "")
    redirect_uri = request.data.get("redirect_uri", "")
    state = request.data.get("state", "")

    if not code or not redirect_uri:
        return Response(
            {"detail": _("code and redirect_uri are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expected_state = request.session.pop("oidc_state", None)
    if not expected_state or state != expected_state:
        return Response(
            {"detail": _("Invalid or missing state parameter.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        claims = exchange_code_for_claims(code, redirect_uri)
    except Exception:
        logger.error("OIDC token exchange failed", exc_info=True)
        return Response(
            {"detail": _("OIDC token exchange failed")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sub = claims.get("sub", "")
    email = claims.get("email", "")
    provider = claims.get("iss", "oidc")

    if OIDCIdentity.objects.filter(provider=provider, sub=sub).exists():
        return Response(
            {"detail": _("This OIDC identity is already linked to an account.")},
            status=status.HTTP_409_CONFLICT,
        )

    OIDCIdentity.objects.create(
        user=request.user, provider=provider, sub=sub, email=email,
    )
    return Response({"detail": _("OIDC identity linked.")}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def oidc_unlink_view(request, identity_id):
    """Unlink an OIDC identity from the current user."""
    deleted, _count = OIDCIdentity.objects.filter(
        id=identity_id, user=request.user,
    ).delete()
    if not deleted:
        return Response(
            {"detail": _("Identity not found.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({"detail": _("OIDC identity unlinked.")})
