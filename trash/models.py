from django.db import models


class TrashStatus(models.Model):
    device_name = models.CharField(max_length=100)
    distance = models.FloatField()  # cm 단위로 저장
    date_time = models.DateTimeField()

    def __str__(self):
        return f"{self.device_name} - {self.date_time}"


class Complaint(models.Model):
    building = models.CharField(max_length=100)
    floor = models.IntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.building} {self.floor}층 - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
class DeviceToken(models.Model):
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.token
    

# models.py
class Alert(models.Model):
    CATEGORY_CHOICES = [
        ('푸시', '푸시'),
        ('민원', '민원'),
    ]
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)
