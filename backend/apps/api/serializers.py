from rest_framework import serializers
from apps.core.models import Project, Action

class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id","name","industry","industry_version","describe"]

# class ActionCreateSerializer(serializers.Serializer):
#     project_id = serializers.UUIDField()
#     action_id = serializers.CharField(max_length=120)
#     industry  = serializers.CharField(max_length=64)
#     node      = serializers.CharField(max_length=120)
#     parameter = serializers.JSONField()

class TargetItemSerializer(serializers.Serializer):
    node_id = serializers.CharField(max_length=120)
    node_name = serializers.CharField(max_length=120)
    industry = serializers.CharField(max_length=64)
    parameter = serializers.CharField(max_length=120)

class ActionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    target = TargetItemSerializer(many=True)
    project_id = serializers.UUIDField()
    # action_id = serializers.CharField(max_length=120)