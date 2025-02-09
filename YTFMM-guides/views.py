from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponse, JsonResponse
from django.conf import settings as s
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils import timezone
from .models import Setting, Order, Log, Guide
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
    return render(request, 'index.html', {'title': 'Гайды',
                                          'guides': Guide.objects.all()})


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


def show_guide(request):
    try:
        id = int(request.GET['id'])
        guide = Guide.objects.get(id=id)
    except Exception:
        return render(request, 'error.html', {'title': 'Ошибка 404',
                                              'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                              },
                      status=404)
    return render(request, 'guide.html', {'title': guide.name,
                                          'guide': guide,})


@csrf_exempt
def buy_guide(request):
    try:
        id = int(request.GET['id'])
        guide = Guide.objects.get(id=id)
    except Exception:
        return render(request, 'error.html', {'title': 'Ошибка 400',
                                              'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                              }, status=400)
    return render(request, 'buy_guide.html', {'title': 'Выбор метода оплаты',
                                              'guide': guide,
                                              'form': OrderForm})


def place_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                id = form.cleaned_data['guide_id']
                guide = Guide.objects.get(id=id)
            except Exception:
                return render(request, 'error.html', {'title': 'Ошибка 404',
                                                      'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',
                                                      }, status=404)
            order = Order(guide=guide,
                          value_to_pay=guide.price,
                          payment_type=form.cleaned_data['pay_type'])
            if order.payment_type == 'YA':
                comission_wallet = math.ceil((order.value_to_pay * 0.005 + order.value_to_pay)*100)/100
                comission_bank = math.ceil((order.value_to_pay / (1-0.02))*100)/100
                pay_to = get_setting('yandex_wallet')
                order.save()
                return render(request, 'pay_yandex.html', {'title':'Оплата Яндекс Деньгами',
                                                           'wallet': comission_wallet,
                                                           'bank': comission_bank,
                                                           'pay_to': pay_to,
                                                           'pay_desc': "Гайды от Крутого Папы: Покупка гайда {}, Заказ №{}".format(order.guide.name, order.id),
                                                           'order_id': order.id})
            if order.payment_type == 'QI':
                order.save()
                dat = {
                    "amount": {
                        "currency": "RUB",
                        "value": '{0:0.2f}'.format(math.ceil(order.value_to_pay*100)/100)
                    },
                    "comment": "Гайды от Крутого Папы: Покупка гайда {}, Заказ №{}".format(order.guide.name, order.id),
                    "expirationDateTime": (datetime.datetime.now().replace(microsecond=0)+datetime.timedelta(days=2)).isoformat()+'+03:00'
                }
                headers = {
                    'Authorization': 'Bearer {}'.format(get_setting('qiwi_seckey')),
                    'Content-Type': 'application/json',
                }
                response = requests.put('https://api.qiwi.com/partner/bill/v1/bills/{}'.format(order.id), data=json.dumps(dat), headers=headers)
                response = json.loads(str(response.content, encoding='UTF-8'))
                link = response['payUrl'] + '&successUrl=https://guides.robloxmafia.ru/success-payment?order=' + str(order.id)
                return redirect(link)
        else:
            return render(request, 'error.html', {'title': 'Ошибка 400',
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова'},
                          status=400)
    else:
        return redirect('index')


def success_payment(request):
    if request.method == 'GET' and 'order' in request.GET:
        try:
            order_id = request.GET['order']
            s = Order.objects.get(id=order_id)
        except Exception:
            return render(request, 'error.html', {'title': 'Ошибка 400',
                                                  'text': 'Попробуйте венуться на прошлую страницу и попробовать снова',},
                          status=400)
        if not s.paid:
            check_routine(s)
        if not s.been_success:
            s.been_success = True
            s.save()
        return render(request, 'success.html', {'title': 'Спасибо за покупку!','order':s})
    else:
        return render(request, 'error.html', {'title': 'Ошибка 404',
                                              'text': 'Проверьте правильность адреса и повторите попытку',}, status=404)


def check_status(request):
    resp = {
        "status": "Неверный запрос",
        "color": "red",
        "final": True
    }
    if request.method == 'GET' and 'order' in request.GET:
        try:
            order_id = request.GET['order']
            o = Order.objects.get(id=order_id)
        except Exception:
            return JsonResponse(resp)
        if o.paid:
            resp['status'] = 'Перевод выполен'
            resp['color'] = 'green'
            resp['guide'] = o.guide.paid
            return JsonResponse(resp)
        else:
            # Jobs to check payments goes here
            check_routine(o)
            # End of block
            resp['status'] = 'Ожидание потверждения от {}. Пожалуйста, не уходите со страницы.'.format(o.get_payment_type_display())
            resp['color'] = 'orange'
            resp['final'] = False
            return JsonResponse(resp)
    else:
        return JsonResponse(resp)


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
            #o.operation_id = 'Locked'
            #o.save()
            if o.value_to_pay <= float(response['amount']['value']) and not o.paid:
                # Log(message='Qiwi duplicate, order_id: {}'.format(o.id)).save()
                # This is a duplicate (qiwi sends it)
                o.paid = True
            else:
                if not o.paid:
                    Log(message='Value mismatch got: {} need: {} {}'.format(o.value_to_pay,
                                                                        response['amount']['value'], o.id)).save()
            o.operation_id = '{} {}'.format(response['billId'], response['siteId'])
            o.save()
    except Exception:
        pass


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
            or_id = label
            s = Order.objects.get(id=or_id)
            #if s.operation_id == 'Locked':
            #    return HttpResponse()
            #s.operation_id = 'Locked'
            #s.save()
            if s.value_to_pay <= float(amount) and not s.paid:
                s.paid = True
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
            #if s.operation_id == 'Locked':
            #    return HttpResponse('{"error":"0"}', content_type='application/json')
            #s.operation_id = 'Locked'
            #s.save()
            if s.value_to_pay <= float(string['amount']['value']) and not s.paid:
                s.paid = True
                #Log(message='Qiwi duplicate, order_id: {}'.format(s.id)).save()
                # This is a duplicate (qiwi sends it)
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
    pass
