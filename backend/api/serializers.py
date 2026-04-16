from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import CompileLayout, DailyWordCount, FileVersion, Folder, Label, ManuscriptWordCount, Project, ProjectFile, SessionWordCount, Status


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


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["id", "name", "colour", "order"]
        read_only_fields = ["id"]


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ["id", "name", "colour", "order"]
        read_only_fields = ["id"]


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
    pov_character = serializers.PrimaryKeyRelatedField(
        queryset=ProjectFile.objects.all(), required=False, allow_null=True,
    )
    label = serializers.PrimaryKeyRelatedField(
        queryset=Label.objects.all(), required=False, allow_null=True,
    )
    status = serializers.PrimaryKeyRelatedField(
        queryset=Status.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Folder
        fields = ["title", "description", "notes", "tags", "target_word_count", "icon", "order", "parent", "include_in_compile", "pov_character", "label", "status"]
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
    pov_character = serializers.PrimaryKeyRelatedField(
        queryset=ProjectFile.objects.all(), required=False, allow_null=True,
    )
    label = serializers.PrimaryKeyRelatedField(
        queryset=Label.objects.all(), required=False, allow_null=True,
    )
    status = serializers.PrimaryKeyRelatedField(
        queryset=Status.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = ProjectFile
        fields = ["title", "description", "notes", "tags", "target_word_count", "icon", "order", "folder", "include_in_compile", "pov_character", "label", "status", "colour"]
        extra_kwargs = {f: {"required": False} for f in fields}


class ProjectFileNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ["id", "title", "order", "file_type", "icon", "description", "notes", "tags", "target_word_count", "include_in_compile", "pov_character", "label", "status", "colour"]


class FolderTreeSerializer(serializers.ModelSerializer):
    items = ProjectFileNodeSerializer(source="texts", many=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ["id", "title", "order", "icon", "description", "notes", "tags", "target_word_count", "is_trash", "include_in_compile", "items", "children", "pov_character", "label", "status"]

    def get_children(self, obj):
        children = obj.children.all().order_by("order")
        return FolderTreeSerializer(children, many=True).data


class ProjectTreeSerializer(serializers.ModelSerializer):
    folders = serializers.SerializerMethodField()
    labels = serializers.SerializerMethodField()
    statuses = serializers.SerializerMethodField()
    characters = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "title", "settings", "folders", "labels", "statuses", "characters"]

    def get_folders(self, obj):
        root_folders = obj.folders.filter(parent__isnull=True).order_by("order")
        non_trash = [f for f in root_folders if not f.is_trash]
        trash = [f for f in root_folders if f.is_trash]
        ordered = non_trash + trash
        return FolderTreeSerializer(ordered, many=True).data

    def get_labels(self, obj):
        return LabelSerializer(Label.objects.filter(project=obj).order_by("order"), many=True).data

    def get_statuses(self, obj):
        return StatusSerializer(Status.objects.filter(project=obj).order_by("order"), many=True).data

    def get_characters(self, obj):
        return list(ProjectFile.objects.filter(project=obj, file_type="character").values("id", "title", "colour"))


class FileVersionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileVersion
        fields = ["id", "created_at", "content_length"]


class FileVersionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileVersion
        fields = ["id", "created_at", "content_length", "content"]


class CompileLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompileLayout
        fields = ["id", "name", "settings", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ManuscriptWordCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManuscriptWordCount
        fields = ["date", "word_count"]


class DailyWordCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyWordCount
        fields = ["date", "word_count"]


class SessionWordCountSerializer(serializers.ModelSerializer):
    started_at = serializers.SerializerMethodField()
    ended_at = serializers.SerializerMethodField()

    class Meta:
        model = SessionWordCount
        fields = ["id", "started_at", "ended_at", "word_count"]

    @staticmethod
    def _to_utc_iso(dt):
        """Format a datetime as UTC ISO 8601 with Z suffix."""
        if dt is None:
            return None
        # Strip any existing tzinfo to avoid double-suffix (+00:00Z)
        naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        return naive.isoformat() + "Z"

    def get_started_at(self, obj):
        return self._to_utc_iso(obj.started_at)

    def get_ended_at(self, obj):
        return self._to_utc_iso(obj.ended_at)


class CompileRequestSerializer(serializers.Serializer):
    format = serializers.ChoiceField(
        choices=["docx", "rtf", "markdown", "pdf", "latex", "epub", "mobi"],
    )
    layout_id = serializers.IntegerField(required=False, allow_null=True)
    root_folder_id = serializers.IntegerField()
    front_matter_folder_id = serializers.IntegerField(required=False, allow_null=True)
    back_matter_folder_id = serializers.IntegerField(required=False, allow_null=True)
