from rest_framework import serializers
from .models import *
from datetime import datetime

class TrashStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrashStatus
        fields = '__all__'

    # 문자열 시간도 처리할 수 있도록 커스텀
    def to_internal_value(self, data):
        data = data.copy()
        try:
            if isinstance(data.get("date_time"), str):
                data["date_time"] = datetime.fromisoformat(data["date_time"])
        except Exception:
            raise serializers.ValidationError("Invalid datetime format")
        return super().to_internal_value(data)


class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = '__all__'

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['token']