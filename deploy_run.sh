git pull
. venv/bin/activate
rm -rf static/
./manage.py collectstatic
./manage.py migrate
