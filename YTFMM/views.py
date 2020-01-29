from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponse, JsonResponse
from django.conf import settings as s
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils import timezone
from .models import Setting, Order, Log, Balance
from .forms import OrderForm
import requests
import hashlib
import math
import datetime
import json
import hmac

# Create your views here.


@cache_page(60 * 15)
def index(request):
    return render(request, 'index.html', {'title': 'Купить Robux',
                                          'percent': get_setting('percent'),
                                          'balance': balance_all(),
                                          'groups': Balance.objects.all()})


def get_setting(name):
    try:
        se = Setting.objects.get(name=name)
    except (Setting.DoesNotExist, KeyError):
        if name in s.DEFAULT_SETTINGS:
            se = Setting(name=name, value=s.DEFAULT_SETTINGS[name])
            se.save()
        else:
            se = Setting(name=name, value='Change me pls')
            se.save()
            Log(message='Create default value for {}'.format(name)).save()
    return se.value


@csrf_exempt
def buy_robux(request):
    try:
        name = request.POST['name']
        value = request.POST['value']
        group = request.POST['group']
    except Exception:
        return render(request, 'error.html', {'title': 'Ошибка 400',
                                              'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                              'balance': balance_all()}, status=400)
    name_id, is_premium = get_id(name, group)
    if name_id < 0:
        return render(request, 'error.html', {'title': 'Ошибка поиска',
                                              'text': 'Никнейм указанный Вами не найден в нашей группе. \
                                                      Для покупки Robux вступите в нашу группу. Внимание: Вы можете вступить максимум в 5 групп.',
                                              'help_url': s.JOIN_URL.format(group),
                                              'balance': balance(group)})
    return render(request, 'buy_robux.html', {'title': 'Выбор метода оплаты',
                                              'username': name,
                                              'userid': name_id,
                                              'value': value,
                                              'group': group,
                                              'form': OrderForm,
                                              'balance': balance(group)})


def place_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data['group_id']
            order = Order(name_id=form.cleaned_data['name_id'],
                          sum_to_get=form.cleaned_data['sum_to_get'],
                          value_to_pay=float(form.cleaned_data['sum_to_get'])*float(get_setting('percent')),
                          payment_type=form.cleaned_data['pay_type'],
                          group_id=form.cleaned_data['group_id'])
            if balance_status(group) <= 10000:
                return render(request, 'error.html', {'title': 'Ошибка сервера',
                                                      'text': 'Извините, РОБУКСЫ закончились. Ожидайте пополнения.',
                                                      'balance': balance(group)})
            if order.payment_type == 'YA':
                comission_wallet = math.ceil((order.value_to_pay * 0.005 + order.value_to_pay)*100)/100
                comission_bank = math.ceil((order.value_to_pay / (1-0.02))*100)/100
                pay_to = get_setting('yandex_wallet')
                order.save()
                return render(request, 'pay_yandex.html', {'title':'Оплата Яндекс Деньгами',
                                                           'wallet': comission_wallet,
                                                           'bank': comission_bank,
                                                           'pay_to': pay_to,
                                                           'pay_desc': 'Roblox Mafia: Покупка {} Robux, Заказ №{}'.format(order.sum_to_get, order.id),
                                                           'order_id': order.id,
                                                           'balance': balance(group)})
            if order.payment_type == 'QI':
                order.save()
                dat = {
                    "amount": {
                        "currency": "RUB",
                        "value": '{0:0.2f}'.format(math.ceil(order.value_to_pay*100)/100)
                    },
                    "comment": "Roblox Mafia: Покупка {} Robux, Заказ №{}".format(order.sum_to_get, order.id),
                    "expirationDateTime": (datetime.datetime.now().replace(microsecond=0)+datetime.timedelta(days=2)).isoformat()+'+03:00'
                }
                headers = {
                    'Authorization': 'Bearer {}'.format(get_setting('qiwi_seckey')),
                    'Content-Type': 'application/json',
                }
                response = requests.put('https://api.qiwi.com/partner/bill/v1/bills/{}'.format(order.id), data=json.dumps(dat), headers=headers)
                response = json.loads(str(response.content, encoding='UTF-8'))
                link = response['payUrl'] + '&successUrl=http://localhost:8000/success-payment?order=' + str(order.id)
                return redirect(link)
        else:
            return render(request, 'error.html', {'title': 'Ошибка 400',
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                                  'balance': balance_all()},
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
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                                  'balance': balance_all()},
                          status=400)
        if not s.paid:
            check_routine(s)
        if not s.been_success:
            s.been_success = True
            s.save()
        return render(request, 'success.html', {'title': 'Спасибо за покупку!','balance': balance_all(),'order':s})
    else:
        return render(request, 'error.html', {'title': 'Ошибка 404',
                                              'text': 'Проверьте правильность адреса и повторите попытку',
                                              'balance': balance_all()}, status=404)


def check_status(request):
    resp = {
        "status": "Неверный запрос",
        "color": "red",
        "final": True
    }
    if request.method == 'GET' and 'order' in request.GET:
        try:
            order_id = int(request.GET['order'])
            o = Order.objects.get(id=order_id)
        except Exception:
            return HttpResponseBadRequest(json.dumps(resp))
        if o.paid:
            resp['status'] = 'Перевод выполен, robux отправленны'
            resp['color'] = 'green'
            return HttpResponse(json.dumps(resp))
        else:
            # Jobs to check payments goes here
            check_routine(o)
            # End of block
            resp['status'] = 'Ожидание потверждения от {}. Пожалуйста, не уходите со страницы.'.format(o.get_payment_type_display())
            resp['color'] = 'orange'
            resp['final'] = False
            return HttpResponse(json.dumps(resp))
    else:
        return HttpResponseBadRequest(json.dumps(resp))


# Try to update qiwi
def check_routine(o):
    try:
        headers = {
            'Authorization': 'Bearer {}'.format(get_setting('qiwi_seckey')),
            'Content-Type': 'application/json',
        }
        response = requests.get('https://api.qiwi.com/partner/bill/v1/bills/{}'.format(o.id), headers=headers)
        response = json.loads(str(response.content, encoding='UTF-8'))
        # Pay funds
        if response['status']['value'] == 'PAID' and o.operation_id != 'Locked':
            o.operation_id = 'Locked'
            o.save()
            if o.value_to_pay <= float(response['amount']['value']) and not o.paid:
                # Log(message='Qiwi duplicate, order_id: {}'.format(o.id)).save()
                # This is a duplicate (qiwi sends it)
                result = send(o.name_id, o.sum_to_get, o.group_id)
                if result:
                    o.paid = True
                    ba = Balance.objects.get(group_id=o.group_id)
                    ba.value -= o.sum_to_get
                    ba.save()
                else:
                    Log(message='Failed to send funds, order_id: {}'.format(o.id)).save()
            else:
                if not o.paid:
                    Log(message='Value mismatch got: {} need: {} {}'.format(o.value_to_pay,
                                                                        response['amount']['value'], o.id)).save()
            o.operation_id = '{} {}'.format(response['billId'], response['siteId'])
            o.save()
    except Exception:
        pass


@cache_page(60 * 15)
def get_avatar(request):
    resp = {
        "url": "",
        "success": False
    }
    if request.method == 'GET' and 'user_id' in request.GET:
        try:
            user_id = int(request.GET['user_id'])
            url = "https://www.roblox.com/avatar-thumbnails?params=%5B%7B%22imageSize%22%3A%22medium%22%2C%22noClick%22%3Afalse%2C%22noOverlays%22%3Afalse%2C%22userId%22%3A%22{}%22%2C%22userOutfitId%22%3A0%2C%22name%22%3A%22%22%7D%5D".format(
                user_id)
        except Exception:
            return HttpResponseBadRequest(json.dumps(resp))
        try:
            response = requests.get(url)
            response = str(response.content, encoding='UTF-8')
            response = response[1:len(response)-1]
            resp['url'] = json.loads(response)['thumbnailUrl']
            resp['success'] = True
            return JsonResponse(resp)
        except Exception:
            return JsonResponse(resp)
    else:
        return HttpResponseBadRequest(json.dumps(resp))


@cache_page(60 * 15)
def get_group_image(request):
    resp = {
        "response": "",
        "success": False
    }
    if request.method == 'GET' and 'group_ids' in request.GET:
        try:
            group_ids = request.GET['group_ids']
            url = "https://thumbnails.roblox.com/v1/groups/icons?format=png&groupIds={}&size=150x150".format(
                group_ids)
        except Exception:
            return HttpResponseBadRequest(json.dumps(resp))
        try:
            response = requests.get(url)
            response = str(response.content, encoding='UTF-8')
            resp['response'] = json.loads(response)
            resp['success'] = True
            return JsonResponse(resp)
        except Exception:
            return JsonResponse(resp)
    else:
        return HttpResponseBadRequest(json.dumps(resp))


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
            if s.operation_id == 'Locked':
                return HttpResponse()
            s.operation_id = 'Locked'
            s.save()
            if s.value_to_pay <= float(amount) and not s.paid:
                result = send(s.name_id, s.sum_to_get, s.group_id)
                if result:
                    s.paid = True
                    ba = Balance.objects.get(group_id=s.group_id)
                    ba.value -= s.sum_to_get
                    ba.save()
                else:
                    # Failed to verify, save log
                    Log(message='Failed to send funds, order_id: {}'.format(s.id)).save()
            else:
                if not s.paid:
                    Log(message='Value mismatch got: {} need: {} {}'.format(s.value_to_pay, float(amount), s.id)).save()
            s.operation_id = operation_id
            s.save()
            return HttpResponse()
        else:
            Log(message=('Hash mis: '+m.hexdigest() + ' ' + request.POST['sha1_hash'])).save()
            return HttpResponseForbidden()
    except Exception as e:
        Log(message='Bad try: {}'.format(str(e))).save()
        return HttpResponseBadRequest()


@csrf_exempt
def qiwi_callback(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()
    try:
        test_sum = request.META['HTTP_X_API_SIGNATURE_SHA256']  # X-Api-Signature-SHA256
        string = json.loads(str(request.body, encoding='UTF-8'))['bill']
    except Exception:
        Log(message='Bad qiwi parse: {} {}'.format(request.body, datetime.datetime.now())).save()
        return HttpResponseBadRequest()
    invoice_parameters = '{}|{}|{}|{}|{}'.format(string['amount']['currency'], string['amount']['value'], string['billId'], string['siteId'], string['status']['value'])
    has = hmac.new(get_setting('qiwi_seckey').encode(), invoice_parameters.encode(), 'SHA256').hexdigest()
    if hmac.compare_digest(has, test_sum):
        try:
            s = Order.objects.get(id=string['billId'])
            if s.operation_id == 'Locked':
                return HttpResponse('{"error":"0"}', content_type='application/json')
            s.operation_id = 'Locked'
            s.save()
            if s.value_to_pay <= float(string['amount']['value']) and not s.paid:
                #Log(message='Qiwi duplicate, order_id: {}'.format(s.id)).save()
                # This is a duplicate (qiwi sends it)
                result = send(s.name_id, s.sum_to_get, s.group_id)
                if result:
                    s.paid = True
                    ba = Balance.objects.get(group_id=s.group_id)
                    ba.value -= s.sum_to_get
                    ba.save()
                else:
                    Log(message='Failed to send funds, order_id: {}'.format(s.id)).save()
            else:
                Log(message='Value mismatch got: {} need: {} {}'.format(s.value_to_pay, string['amount']['value'], s.id)).save()
            s.operation_id = '{} {}'.format(string['billId'], string['siteId'])
            s.save()
            return HttpResponse('{"error":"0"}', content_type='application/json')
        except Exception:
            Log(message='Qiwi Bill error {}'.format(request.body)).save()
    else:
        Log(message='Hash qiwi: {}'.format(request.body)).save()
        return HttpResponseForbidden('{"error":"Hashes mismatch"}', content_type='application/json')


def send(id, num, group):
    url = s.SEND_URL.format(group)
    cookie = s.COOKIE
    cookie['.ROBLOSECURITY'] = get_setting('robsec-{}'.format(group))
    csrf = requests.get(s.CSRF_URL, cookies=cookie)
    csrf = csrf.content
    kek = csrf.find(b'Roblox.XsrfToken.setToken(')
    csrf = csrf[kek+27:]
    kek = csrf.find(b'\'')
    csrf = csrf[:kek]
    headers = {
        'X-CSRF-TOKEN': csrf.decode('ascii'),
    }
    response = requests.post(url, headers=headers, data={'percentages': '{"'+str(id)+'": "'+str(num)+'"}'}, cookies=cookie)
    if response.status_code == 200:
        return True
    else:
        return False


def get_id(name, group):
    url = s.GROUP_URL.format(group, name)
    cookie = s.COOKIE
    cookie['.ROBLOSECURITY'] = get_setting('robsec-{}'.format(group))
    response = requests.get(url, cookies=cookie)
    if response.status_code != 200:
        return -1, False
    response = response.json()
    if len(response) == 0:
        return -2, False
    userid = response[0]['UserId']
    is_premium = response[0]['RoleSet']['Rank'] in s.PREMIUM_ROLES
    return userid, is_premium


def balance_status(group):
    url = 'https://economy.roblox.com/v1/groups/{}/currency'.format(group)
    cookie = s.COOKIE
    cookie['.ROBLOSECURITY'] = get_setting('robsec-{}'.format(group))
    response = requests.get(url, cookies=cookie)
    response = int(response.json()['robux'])
    return response


def balance(group):
    try:
        balance_rbx = Balance.objects.get(group_id=group)
    except Exception:
        balance_rbx = Balance(name=group, group_id=group, updated=timezone.now(), value=balance_status(group))
        balance_rbx.save()
    if (balance_rbx.updated + datetime.timedelta(minutes=15)) < timezone.now():
        try:
            balance_rbx.value = balance_status(group)
            balance_rbx.updated = timezone.now()
            balance_rbx.save()
        except Exception:
            Log(message='Failed to update balance {} group {}'.format(datetime.datetime.now(), group)).save()
    return balance_rbx.value - 10000


def balance_all():
    try:
        balance_rbx = Balance.objects.last()
    except Exception:
        balance_rbx = Balance(name='NEW', group_id='0', updated=timezone.now(), value=balance_status(0))
        balance_rbx.save()
    if (balance_rbx.updated + datetime.timedelta(minutes=15)) < timezone.now():
        return sum([balance(x) for x in Balance.objects.values_list('group_id', flat=True)])
    return sum([x - 10000 for x in Balance.objects.values_list('value', flat=True)])
