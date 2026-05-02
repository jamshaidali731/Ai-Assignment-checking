# notifications.py
import smtplib
from email.mime.text import MIMEText
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from onesignal_sdk.client import Client
from onesignal_sdk.error import OneSignalHTTPError
from .models import Notification

# Initialize OneSignal client
onesignal_client = Client(
    app_id="63d0bf46-da85-4900-9f15-e024d9a47458",
    rest_api_key="os_v2_app_mpil6rw2qveqbhyv4asntjdulajb7ctihzwectvynhv43tdrv5jtrdye6rnsc6joo7insdn5ydnagisuqicdybgd3clexyzxsevjiby"
)

def send_assignment_notification(classroom, assignment):
    """
    Send push and email notifications (via smtplib/MIMEText) to all students in the classroom.
    """
    try:
        students = classroom.students.all()
        if not students.exists():
            print(f"[Notifications] No students found in classroom {classroom.name}")
            return

        # Prepare Email Details
        teacher_name = classroom.created_by.name or classroom.created_by.username
        deadline_str = assignment.dead_line.strftime('%Y-%m-%d %H:%M') if assignment.dead_line else "No deadline"
        
        subject = f"New Assignment: {assignment.title} in {classroom.name}"
        message_body = (
            f"Hello Student,\n\n"
            f"A new assignment has been posted in your class '{classroom.name}'.\n\n"
            f"Assignment: {assignment.title}\n"
            f"Teacher: {teacher_name}\n"
            f"Deadline: {deadline_str}\n\n"
            f"Please log in to GradifyAi to complete your task.\n\n"
            f"Regards,\nGradifyAi Team"
        )
        
        recipient_list = [student.email for student in students if student.email]
        
        # 1. Send Email manually using smtplib (as requested)
        if recipient_list:
            try:
                # Use settings to keep credentials central
                smtp_server = "smtp.gmail.com"
                smtp_port = 587
                email_address = settings.EMAIL_HOST_USER
                email_password = settings.EMAIL_HOST_PASSWORD

                for recipient in recipient_list:
                    msg = MIMEText(message_body)
                    msg["Subject"] = subject
                    msg["From"] = f"GradifyAi <{email_address}>"
                    msg["To"] = recipient

                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.starttls()
                    server.login(email_address, email_password)
                    server.sendmail(email_address, recipient, msg.as_string())
                    server.quit()
                
                print(f"[Email] Notification sent to {len(recipient_list)} students via smtplib")
            except Exception as e:
                print(f"[Email] Failed to send email via smtplib: {e}")

        # 2. Database and OneSignal notifications
        player_ids = []
        for student in students:
            # Database Notification
            Notification.objects.create(
                user=student,
                title="New Assignment Notification",
                body=f"New assignment '{assignment.title}' added in {classroom.name}",
                classroom_id=str(classroom.id),
                assignment_id=str(assignment.id),
                type="new_assignment",
                sent_time=timezone.now()
            )

            # Collect OneSignal Player IDs
            if hasattr(student, 'onesignal_player_id') and student.onesignal_player_id:
                player_ids.append(student.onesignal_player_id)

        # OneSignal Push
        if player_ids:
            notification = {
                "app_id": "63d0bf46-da85-4900-9f15-e024d9a47458",
                "include_player_ids": player_ids,
                "headings": {"en": "New Assignment Notification"},
                "contents": {"en": f"New assignment '{assignment.title}' added in {classroom.name}"},
                "data": {
                    "classroom_id": str(classroom.id),
                    "assignment_id": str(assignment.id),
                    "type": "new_assignment"
                },
                "ios_badge_type": "Increase",
                "ios_badge_count": 1
            }
            try:
                response = onesignal_client.send_notification(notification)
                print(f"[OneSignal] Notification sent: {response}")
            except OneSignalHTTPError as e:
                print(f"[OneSignal] HTTP Error: {e}")

    except Exception as e:
        print(f"[Notifications] Error in notification flow: {e}")
