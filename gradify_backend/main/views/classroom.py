import csv
from io import StringIO
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.contrib.auth import get_user_model

from main.models import ClassRoom, Assignment, Submission
from main.serizalizer import ClassRoomSerializer

u1 = get_user_model()
u11 = settings.AUTH_USER_MODEL

class ClassRoomViewSet(viewsets.ModelViewSet):
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer
    # permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'], url_path='download-results-csv')
    def download_results_csv(self, request, pk=None):
        try:
            classroom = ClassRoom.objects.get(id=pk)
        except ClassRoom.DoesNotExist:
            return Response({"error": "Classroom not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.user != classroom.created_by:
            return Response({"error": "Only the teacher can download results."}, status=status.HTTP_403_FORBIDDEN)

        students = classroom.students.all()
        assignments = Assignment.objects.filter(classroom=classroom).order_by('id')

        if not students.exists():
            return Response({"error": "No students enrolled in this classroom."}, status=status.HTTP_404_NOT_FOUND)
        if not assignments.exists():
            return Response({"error": "No assignments found in this classroom."}, status=status.HTTP_404_NOT_FOUND)

        output = StringIO()
        writer = csv.writer(output)
        headers = ['Student Name', 'Student Roll_number'] + [assignment.title for assignment in assignments]
        writer.writerow(headers)

        for student in students:
            row = [student.username, student.roll_number]
            for assignment in assignments:
                submission = Submission.objects.filter(student=student, assignment=assignment).order_by('-submitted_at').first()
                if submission:
                    marks = submission.marks if submission.marks is not None else 0
                    teacher_marks = submission.teacher_marks if submission.teacher_marks is not None else 0
                    avg_marks = round((marks + teacher_marks) / 2, 2) if marks > 0 and teacher_marks > 0 else marks or teacher_marks
                    row.append(avg_marks)
                else:
                    row.append(0)
            writer.writerow(row)

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="classroom_{classroom.code}_results.csv"'},
        )
        response.write(output.getvalue().encode('utf-8'))
        output.close()
        return response

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='join')
    def join_classroom(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Classroom code is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            classroom = ClassRoom.objects.get(code=code)
        except ClassRoom.DoesNotExist:
            return Response({'error': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        classroom.students.add(user)
        return Response({'message': f'Joined classroom "{classroom.name}" successfully.'})

    @action(detail=False, methods=['get'], url_path='my-classes')
    def my_classes(self, request):
        user = request.user
        created_classes = ClassRoom.objects.filter(created_by=user)
        joined_classes = ClassRoom.objects.filter(students=user).exclude(created_by=user)

        created_serializer = self.get_serializer(created_classes, many=True)
        joined_serializer = self.get_serializer(joined_classes, many=True)

        return Response({
            'created_classes': created_serializer.data,
            'joined_classes': joined_serializer.data
        })

    @action(detail=True, methods=['get', 'post', 'delete', 'put'], url_path='assignments')
    def assignments(self, request, pk=None):
        try:
            classroom = ClassRoom.objects.get(id=pk)
        except ClassRoom.DoesNotExist:
            return Response({"error": "Classroom not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            user = request.user
            if user != classroom.created_by and not classroom.students.filter(id=user.id).exists():
                return Response({"error": "You are not part of this classroom."}, status=status.HTTP_403_FORBIDDEN)
            assignments = Assignment.objects.filter(classroom=classroom)
            serializer = AssignmentSerializer(assignments, many=True)
            return Response({"assignments": serializer.data})

        if request.method == "POST":
            if request.user != classroom.created_by:
                return Response({"error": "Only teacher can add assignments."}, status=status.HTTP_403_FORBIDDEN)
            serializer = AssignmentSerializer(data=request.data)
            if serializer.is_valid():
                assignment = serializer.save(classroom=classroom)
                # Send push notification to all students
                from main.notification import send_assignment_notification
                send_assignment_notification(classroom, assignment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if request.method == "DELETE":
            if request.user != classroom.created_by:
                return Response({"error": "Only teacher can delete assignments."}, status=status.HTTP_403_FORBIDDEN)
            assignment_id = request.data.get('assignment_id')
            try:
                assignment = Assignment.objects.get(id=assignment_id, classroom=classroom)
                assignment.delete()
                return Response({"message": "Assignment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
            except Assignment.DoesNotExist:
                return Response({"error": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "PUT":
            if request.user != classroom.created_by:
                return Response({"error": "Only teacher can update assignments."}, status=status.HTTP_403_FORBIDDEN)
            assignment_id = request.data.get('assignment_id')
            try:
                assignment = Assignment.objects.get(id=assignment_id, classroom=classroom)
                serializer = AssignmentSerializer(assignment, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except Assignment.DoesNotExist:
                return Response({"error": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], url_path='generate-result-csv')
    def generate_result_csv(self, request, pk=None):
        try:
            classroom = ClassRoom.objects.get(id=pk)
        except ClassRoom.DoesNotExist:
            return Response({"error": "Classroom not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.user != classroom.created_by:
            return Response({"error": "Only the teacher can generate results."}, status=status.HTTP_403_FORBIDDEN)

        students = classroom.students.all()
        if not students.exists():
            return Response({"error": "No students found in this classroom."}, status=status.HTTP_404_NOT_FOUND)

        assignments = Assignment.objects.filter(classroom=classroom).order_by('id')
        output = StringIO()
        writer = csv.writer(output)
        headers = ['Student ID', 'Student Name'] + [f"{assignment.title} (Max: {assignment.max_marks})" for assignment in assignments] + ['Total Marks']
        writer.writerow(headers)

        for student in students:
            row = [student.roll_number if hasattr(student, 'roll_number') else student.id, student.username]
            student_total = 0
            for assignment in assignments:
                submission = Submission.objects.filter(student=student, assignment=assignment).order_by('-id').first()
                if submission:
                    marks = submission.marks if submission.marks is not None else 0
                    teacher_marks = submission.teacher_marks if submission.teacher_marks is not None else 0
                    
                    # Logic: Use teacher_marks if available, else use marks (AI/Auto), or average?
                    # Previous logic: avg_marks = round((marks + teacher_marks) / 2, 2) if marks > 0 and teacher_marks > 0 else marks or teacher_marks
                    # Sticking to previous logic for consistency for now
                    if marks > 0 and teacher_marks > 0:
                         avg_marks = round((marks + teacher_marks) / 2, 2)
                    else:
                         avg_marks = teacher_marks or marks # Prioritize teacher marks if marks is 0? No, if one is 0 and other present, take present.

                    row.append(avg_marks)
                    student_total += avg_marks
                else:
                    row.append(0)
            
            row.append(round(student_total, 2))
            writer.writerow(row)

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="classroom_{classroom.code}_results.csv"'},
        )
        response.write(output.getvalue())
        output.close()
        return response
