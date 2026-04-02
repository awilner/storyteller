from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import FileVersion, Folder, Project, ProjectFile


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("Username already taken."))
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    oidc_identities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "is_staff", "oidc_identities"]

    def get_oidc_identities(self, obj):
        return list(
            obj.oidc_identities.values("id", "provider", "email", "created_at")
        )


class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "title", "description", "settings"]


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "title", "description"]
        read_only_fields = ["id"]


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["title", "description", "settings"]
        extra_kwargs = {f: {"required": False} for f in fields}


class FolderCreateSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Folder
        fields = ["id", "title", "order", "parent"]
        read_only_fields = ["id"]


class FolderUpdateSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Folder
        fields = ["title", "description", "notes", "tags", "target_word_count", "icon", "order", "parent"]
        extra_kwargs = {f: {"required": False} for f in fields}


class TextCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ["id", "title", "order"]
        read_only_fields = ["id"]


class TextUpdateSerializer(serializers.ModelSerializer):
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = ProjectFile
        fields = ["title", "description", "notes", "tags", "target_word_count", "icon", "order", "folder"]
        extra_kwargs = {f: {"required": False} for f in fields}


class ProjectFileNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ["id", "title", "order", "file_type", "icon", "description", "notes", "tags", "target_word_count"]


class FolderTreeSerializer(serializers.ModelSerializer):
    items = ProjectFileNodeSerializer(source="texts", many=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ["id", "title", "order", "icon", "description", "notes", "tags", "target_word_count", "is_trash", "items", "children"]

    def get_children(self, obj):
        children = obj.children.all().order_by("order")
        return FolderTreeSerializer(children, many=True).data


class ProjectTreeSerializer(serializers.ModelSerializer):
    folders = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "title", "settings", "folders"]

    def get_folders(self, obj):
        root_folders = obj.folders.filter(parent__isnull=True).order_by("order")
        non_trash = [f for f in root_folders if not f.is_trash]
        trash = [f for f in root_folders if f.is_trash]
        ordered = non_trash + trash
        return FolderTreeSerializer(ordered, many=True).data


class FileVersionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileVersion
        fields = ["id", "created_at", "content_length"]


class FileVersionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileVersion
        fields = ["id", "created_at", "content_length", "content"]
