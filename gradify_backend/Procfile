web: gunicorn backend.wsgi --workers 1 --threads 3 --timeout 120
release: python manage.py makemigrations && python manage.py migrate
