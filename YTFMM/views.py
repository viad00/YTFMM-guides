from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings as s
from django.views.decorators.csrf import csrf_protect
from .models import Setting
from .forms import OrderForm
import requests
import json

# Create your views here.


def index(request):
    return render(request, 'index.html', {'title': 'Купить Robux', 'percent': get_setting('percent')})


def get_setting(name):
    try:
        se = Setting.objects.get(name=name)
    except Setting.DoesNotExist:
        se = Setting(name=name, value=s.DEFAULT_SETTINGS[name])
        se.save()
    return se.value


@csrf_protect
def buy_robux(request):
    try:
        name = request.POST['name']
        value = request.POST['value']
    except Exception:
        return render(request, 'error.html', {'title': 'Ошибка 400',
                                              'text': 'Попробуйте венуться на прошлую страницу и попробовать снова'}, status=400)
    name_id, is_premium = get_id(name)
    if name_id < 0:
        return render(request, 'error.html', {'title': 'Ошибка поиска',
                                              'text': 'Имя указанное вами не найденно в группе. Для перевода robux \
                                                       вступите в нашу группу.',
                                              'help_url': s.JOIN_URL})
    return render(request, 'buy_robux.html', {'title': 'Выбор метода оплаты', 'userid': name_id, 'value': value, 'form': OrderForm})


def send_to(request):
    id = int(request.GET['id'])
    num = int(request.GET['number'])
    username = request.GET['name'].lower()
    return HttpResponse(balance_status())


def send(id, num):
    url = s.SEND_URL
    csrf = requests.get(s.CSRF_URL, cookies=s.COOKIE)
    csrf = csrf.content
    kek = csrf.find(b'Roblox.XsrfToken.setToken(')
    csrf = csrf[kek+27:]
    kek = csrf.find(b'\'')
    csrf = csrf[:kek]
    headers = {
        'X-CSRF-TOKEN': csrf.decode('ascii'),
    }
    response = requests.post(url, headers=headers, data={'percentages': '{"'+str(id)+'": "'+str(num)+'"}'}, cookies=s.COOKIE)
    if response.content == '':
        return True
    else:
        return False


def get_id(name):
    url = s.GROUP_URL.format(name)
    response = requests.get(url, cookies = s.COOKIE)
    if response.status_code != 200:
        return -1, False
    response = response.json()
    if len(response) == 0:
        return -2, False
    userid = response[0]['UserId']
    is_premium = response[0]['RoleSet']['Rank'] in s.PREMIUM_ROLES
    return userid, is_premium


def balance_status():
    url = s.CSRF_URL
    response = requests.get(url, cookies=s.COOKIE)
    stri = b'Group Funds:'
    ptr = response.content.find(stri)
    response = response.content[ptr:]
    ptr = response.find(b'robux') + 7
    response = response[ptr:]
    ptr = response.find(b'<')
    response = response[:ptr]
    int(response)
    return response
