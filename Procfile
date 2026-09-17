web: python manage.py migrate && python manage.py collectstatic --noinput && python -m gunicorn config.wsgi --bind 0.0.0.0:$PORT --timeout 60
