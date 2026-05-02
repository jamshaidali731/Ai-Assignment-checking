import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.forms import ValidationError
from django.conf import settings

from main.models import Submission, Assignment
from main.serizalizer import SubmissionSerializer

from main.helper.openai_checker import openai_checker
from main.helper.extract_text import extract_text
from main.helper.check_plagriarism import check_plagiarism
from main.helper.evaluate_submission import evaluate_submission

from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-MiniLM-L3-v2',device='cpu')

class SubmissionViewSet(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    
    
    def perform_create(self, serializer):
        # Fetch the assignment before saving to validate deadline
        assignment_id = self.request.data.get('assignment_id')
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            # Check if the assignment's deadline has passed
            if assignment.dead_line > assignment.dead_line:
                raise ValidationError({"detail": "You are late. The deadline for this assignment has passed."})
        except Assignment.DoesNotExist:
            raise ValidationError({"detail": "Assignment does not exist."})
        # Automatically set the student to the authenticated user
        submission = serializer.save(student=self.request.user)
        
        try:
            # Fetch the assignment
            assignment = submission.assignment
            print(assignment)
            max_marks = assignment.max_marks 
            min_words = assignment.min_words 
            required_keywords = assignment.required_keywords or ["AI", "making decisions", "recognizing patterns"]

            # Get the teacher's assignment file path
            correct_file_path = os.path.join(settings.MEDIA_ROOT, assignment.file.name)
            if not os.path.exists(correct_file_path):
                print(f"Error: Teacher file {correct_file_path} not found")
                return

            # Extract text and compute embedding for the teacher's file
            correct_text = extract_text(correct_file_path)
            #teacher
            if not correct_text:
                print(f"Error: Could not extract text from teacher file {correct_file_path}")
                return
            correct_embedding = model.encode(correct_text, convert_to_tensor=True)

            # Get the student's submitted file path
            if not submission.submitted_file:
                print(f"Warning: No file for submission {submission.id}")
                return
            student_file_path = os.path.join(settings.MEDIA_ROOT, submission.submitted_file.name)
            if not os.path.exists(student_file_path):
                print(f"Warning: Submission file {student_file_path} not found")
                return

            # Extract text from student's submission
            #student
            student_text = extract_text(student_file_path)

            if correct_text and student_text:
                   teacher = correct_text
                   student = student_text
                   openai_score = openai_checker(teacher, student)

            if not student_text:
                print(f"Warning: Could not extract text from {student_file_path}")
                return

            # Evaluate the submission    
            marks, feedback = evaluate_submission(student_text, correct_embedding, min_words, required_keywords, max_marks)

            # Check for plagiarism with other submissions for this assignment
            student_embeddings = {submission.id: model.encode(student_text, convert_to_tensor=True)}
            submission_id_to_student = {submission.id: submission.student.name}
            other_submissions = Submission.objects.filter(assignment=assignment).exclude(id=submission.id)
            for other in other_submissions:
                if other.submitted_file:
                    other_file_path = os.path.join(settings.MEDIA_ROOT, other.submitted_file.name)
                    if os.path.exists(other_file_path):
                        other_text = extract_text(other_file_path)
                        if other_text:
                            student_embeddings[other.id] = model.encode(other_text, convert_to_tensor=True)
                            submission_id_to_student[other.id] = other.student.name

            plagiarism_results = check_plagiarism(student_embeddings, submission_id_to_student)
            if plagiarism_results:
                print("\n🔍 Plagiarism Check Between Students (Similarity > 80%):\n" + "-" * 50)
                plagiarism_feedback = []
                for student1, student2, sim in plagiarism_results:
                    print(f"{student1} <-> {student2}: {sim}% similar")
                    if submission.student.name in (student1, student2):
                        other_student = student2 if student1 == submission.student.name else student1
                        plagiarism_feedback.append(f"{other_student} same {sim}%")
                if plagiarism_feedback:
                    feedback += " | Plagiarism: " + ", ".join(plagiarism_feedback)

            # Update the submission with marks and feedback
            submission.marks = marks
            submission.feedback = feedback
            submission.openai_score = openai_score
            submission.save()
            print(f"Updated submission {submission.id} - Marks: {marks}, Feedback: {feedback}, OpenAI Score: {openai_score}")

        except Assignment.DoesNotExist:
            print(f"Error: Assignment with ID {submission.assignment_id} not found")
        except Exception as e:
            print(f"Error processing submission {submission.id}: {e}")

    def get_queryset(self):
        user = self.request.user
        pk = self.kwargs.get('pk')
        
        # 1. If requesting a specific submission (Detail View - PATCH, GET, etc.)
        if pk:
            queryset = Submission.objects.filter(id=pk)
            # Ensure the user is either the teacher or the student who submitted
            submission = queryset.first()
            if submission:
                if user == submission.assignment.classroom.created_by or user == submission.student:
                    return queryset
            return Submission.objects.none()

        # 2. If listing submissions (List View)
        assignment_id = self.request.query_params.get('assignment_id')
        if not assignment_id:
            return Submission.objects.none()

        try:
            assignment = Assignment.objects.get(id=assignment_id)
            classroom = assignment.classroom

            if user == classroom.created_by:
                return Submission.objects.filter(assignment_id=assignment_id)
            elif classroom.students.filter(id=user.id).exists():
                return Submission.objects.filter(assignment_id=assignment_id, student=user)
            else:
                return Submission.objects.none()
        except Assignment.DoesNotExist:
            return Submission.objects.none()

    @action(detail=True, methods=['patch'], url_path='grade')
    def grade_submission(self, request, pk=None):
        try:
            submission = self.get_object()
            assignment = submission.assignment
            if request.user != assignment.classroom.created_by:
                return Response({"error": "Only the teacher can grade submissions."}, status=status.HTTP_403_FORBIDDEN)
            
            marks = request.data.get('marks')
            feedback = request.data.get('feedback')
            
            if marks is not None:
                submission.marks = float(marks)
            if feedback is not None:
                submission.feedback = feedback
            submission.save()
            
            serializer = self.get_serializer(submission)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error grading submission: {e}"}, status=status.HTTP_400_BAD_REQUEST)
