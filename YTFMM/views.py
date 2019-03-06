from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.conf import settings as s
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from .models import Setting, Order, Log
from .forms import OrderForm
import requests
import hashlib

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
                                              'text': 'Никнейм указанный Вами не найден в нашей группе. \
                                                      Для покупки Robux вступите в нашу группу. Внимание: Вы можете вступить максимум в 5 групп.',
                                              'help_url': s.JOIN_URL})
    return render(request, 'buy_robux.html', {'title': 'Выбор метода оплаты', 'userid': name_id, 'value': value, 'form': OrderForm})


def place_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = Order(name_id=form.cleaned_data['name_id'], sum_to_get=form.cleaned_data['sum_to_get'], value_to_pay=float(form.cleaned_data['sum_to_get'])*float(get_setting('percent')), payment_type=form.cleaned_data['pay_type'])
            if balance_status() <= 10000:
                return render(request, 'error.html', {'title': 'Ошибка сервера',
                                                      'text': 'Деньги кончились :). Пожалуйста сообщите нам об этом и мы восполним запас.'})
            if order.payment_type == 'YA':
                comission_wallet = order.value_to_pay * 0.005 + order.value_to_pay
                comission_bank = order.value_to_pay * 0.02 + order.value_to_pay
                pay_to = get_setting('yandex_wallet')
                order.save()
                return render(request, 'pay_yandex.html', {'title':'Оплата Яндекс Деньгами',
                                                           'wallet': comission_wallet,
                                                           'bank': comission_bank,
                                                           'pay_to': pay_to,
                                                           'pay_desc': 'Roblox Mafia: Покупка {} Robux, Заказ №{}'.format(order.sum_to_get, order.id),
                                                           'order_id': order.id})
        else:
            return render(request, 'error.html', {'title': 'Ошибка 400',
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова'},
                          status=400)
    else:
        return redirect('index')


def success_payment(request):
    if request.method == 'GET' and 'order' in request.GET:
        try:
            order_id = int(request.GET['order'])
            s = Order.objects.get(id=order_id)
        except Exception:
            return render(request, 'error.html', {'title': 'Ошибка 400',
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова'},
                          status=400)
        s.been_success = True
        s.save()
        return render(request, 'success.html', {'title': 'Спасибо за покупку!'})
    else:
        return render(request, 'error.html', {'title': 'Ошибка 404',
                                              'text': 'Проверьте правильность адреса и повторите попытку'}, status=404)


@csrf_exempt
def yandex_callback(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()
    try:
        notification_type = request.POST['notification_type']
        operation_id = request.POST['operation_id']
        amount = request.POST['amount']
        currency = request.POST['currency']
        datetime = request.POST['datetime']
        sender = request.POST['sender']
        codepro = request.POST['codepro']
        notification_secret = get_setting('yandex_secret')
        label = request.POST['label']
    except Exception:
        Log(message='Bad parse: {}'.format(request.POST)).save()
        return HttpResponseBadRequest()
    try:
        # notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label
        m = hashlib.sha1('{}&{}&{}&{}&{}&{}&{}&{}&{}'.format(notification_type, operation_id, amount, currency, datetime,
                                                             sender, codepro, notification_secret, label).encode('UTF-8'))
        if m.hexdigest() == request.POST['sha1_hash']:
            if operation_id == 'test-notification':
                Log(message='Yandex Money: Test ok').save()
                return HttpResponse()
            or_id = int(label[2:])
            s = Order.objects.get(id=or_id)
            if s.value_to_pay == float(amount):
                result = send(s.name_id, s.sum_to_get)
                if result:
                    s.paid = True
                else:
                    # Failed to verify, save log
                    Log(message='Failed to send funds, order_id: {}'.format(s.id))
            else:
                Log(message='Value mismatch got: {} need: {}'.format(s.value_to_pay, float(amount)))
            s.operation_id = operation_id
            s.save()
            return HttpResponse()
        else:
            Log(message=('Hash mis: '+m.hexdigest() + ' ' + request.POST['sha1_hash'])).save()
            return HttpResponseForbidden()
    except Exception as e:
        Log(message='Bad try: {}'.format(str(e))).save()
        return HttpResponseBadRequest()


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
    cookie = s.COOKIE
    cookie['.ROBLOSECURITY'] = get_setting('robsec')
    response = requests.post(url, headers=headers, data={'percentages': '{"'+str(id)+'": "'+str(num)+'"}'}, cookies=s.COOKIE)
    if response.content == '':
        return True
    else:
        return False


def get_id(name):
    url = s.GROUP_URL.format(name)
    cookie = s.COOKIE
    cookie['.ROBLOSECURITY'] = get_setting('robsec')
    response = requests.get(url, cookies=cookie)
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
    response = int(response)
    return response
