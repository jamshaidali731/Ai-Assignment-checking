import fitz
from django.core.files.base import ContentFile
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from main.models import Submission
from main.serizalizer import SubmissionSerializer

class Update(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        try:
            submission = self.get_object()
            assignment = submission.assignment
            if request.user != assignment.classroom.created_by:
                return Response({"error": "Only the teacher can update submissions."}, status=status.HTTP_403_FORBIDDEN)

            # Update fields from request data
            if 'marks' in request.data:
                submission.marks = float(request.data['marks']) if request.data['marks'] else None
            if 'feedback' in request.data:
                submission.feedback = request.data['feedback']
            if 'teacher_marks' in request.data:
                teacher_marks = request.data['teacher_marks']
                submission.teacher_marks = float(teacher_marks) if teacher_marks else None

            # Handle XFDF annotations and update PDF
            if 'annotations' in request.FILES:
                xfdf_file = request.FILES['annotations']
                pdf_path = submission.submitted_file.path
                pdf = fitz.open(pdf_path)
                pdf.import_xfdf(xfdf_file.temporary_file_path())
                output = ContentFile(pdf.write())
                submission.submitted_file.save(f"annotated_{submission.submitted_file.name}", output)
                pdf.close()
            elif 'submitted_file' in request.FILES:
                submission.submitted_file = request.FILES['submitted_file']

            submission.save()
            serializer = self.get_serializer(submission)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": f"Invalid data format: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Error updating submission: {e}"}, status=status.HTTP_400_BAD_REQUEST)
