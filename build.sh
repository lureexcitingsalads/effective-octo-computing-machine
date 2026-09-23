#!/usr/bin/env bash
# Render build step: install deps, gather static files, apply migrations.
# No Shell access on the free plan, so bootstrap the superuser and demo data here too --
# both are safe to re-run on every deploy (createsuperuser no-ops if the user already
# exists; seed_demo_data wipes/rebuilds only its own 4 demo units, nothing else).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --noinput || true
fi

python manage.py seed_demo_data
