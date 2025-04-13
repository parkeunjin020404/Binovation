from django.db import models

class TrashStatus(models.Model):
    device_name = models.CharField(max_length=100)
    distance = models.FloatField()  # cm 단위로 저장
    date_time = models.DateTimeField()

    def __str__(self):
        return f"{self.device_name} - {self.date_time}"


