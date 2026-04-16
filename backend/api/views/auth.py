from django.contrib.auth import authenticate, login, logout
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..serializers import RegisterSerializer, UserSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": _("Invalid credentials.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"detail": _("Logged out.")})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change the authenticated user's password."""
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")
    if not current_password or not new_password:
        return Response(
            {"detail": _("Both current and new password are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not request.user.check_password(current_password):
        return Response(
            {"detail": _("Current password is incorrect.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(new_password) < 8:
        return Response(
            {"detail": _("New password must be at least 8 characters.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    request.user.set_password(new_password)
    request.user.save()
    login(request, request.user)
    return Response({"detail": _("Password changed.")})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def user_settings_view(request):
    """Get or update the authenticated user's preferences."""
    from ..models import UserSettings
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return Response(settings_obj.preferences)
    if not isinstance(request.data, dict):
        return Response(
            {"detail": _("Expected a JSON object.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    settings_obj.preferences.update(request.data)
    settings_obj.save()
    return Response(settings_obj.preferences)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Return the currently authenticated user."""
    return Response(UserSerializer(request.user).data)
