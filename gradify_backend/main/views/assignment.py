from rest_framework import viewsets
from main.models import Assignment
from main.serizalizer import AssignmentSerializer
from main.notification import send_assignment_notification

class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer
    #permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        instance = serializer.save()
        send_assignment_notification(instance.classroom, instance)
