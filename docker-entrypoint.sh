#!/bin/sh
# При старте контейнера применяем миграции и собираем статику.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
