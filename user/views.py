import re
from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django_redis import get_redis_connection
from order.models import OrderGoods, OrderInfo
from django.core.paginator import Paginator

from itsdangerous import TimedJSONWebSignatureSerializer as Serialiezer
from itsdangerous import SignatureExpired
from .models import User, Address
from goods.models import GoodsSKU
from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequiredMixin


class RegisterView(View):

    def get(self, request):
        """显示注册页面"""
        return render(request, 'user/register.html')

    def post(self, request):
        """进行注册处理"""
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        password2 = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 数据校验
        if not all([username, password, password2, email]):
            # 数据不完整
            return render(request, 'user/register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'user/register.html', {'errmsg': '邮箱格式不正确'})

        # 密码一致
        if password != password2:
            return render(request, 'user/register.html', {'errmsg': '两次密码输入不一致'})

        # 是否统一协议
        if allow != 'on':
            return render(request, 'user/register.html', {'errmsg': '请同意协议'})

        # 用户名,邮箱不能重复
        try:
            user = User.objects.get(username=username)

        except User.DoesNotExist:
            user = None

        if user:
            return render(request, 'user/register.html', {'errmsg': '改用户名已被注册'})

        # 为了测试先把邮箱唯一注释
        # try:
        #     email = User.objects.get(email=email)
        # except User.DoesNotExist:
        #     email = None
        #
        # if email:
        #     return render(request, 'user/register.html', {'errmsg': '该邮箱已被注册'})

        # 业务处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接
        # 创建激活链接
        serializer = Serialiezer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()

        # 发送邮件，用celery异步发送
        # subject = '电商网站欢迎你'
        # message = ''
        # sender = settings.EMAIL_HOST_USER
        # html_message = '%s进行用户激活<a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
        #     user.username, token, token)
        #
        # send_mail(subject, message, sender, [email], html_message=html_message)

        # 异步任务delay方法
        send_register_active_email.delay(email, user.username, token)

        # 返回数据
        return redirect(reverse('goods:index'))


class ActiveView(View):
    def get(self, request, token):
        """进行用户激活"""
        # 解密
        serializer = Serialiezer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取带激活id
            user_id = info['confirm']

            # 根据id获取用户信息
            user = User.objects.get(pk=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登陆页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            raise HttpResponse("激活链接已过期")


class LoginView(View):
    def get(self, request):
        # 判断是否记住了用户名
        if 'username' not in request.COOKIES:
            """返回登陆页面"""
            username = ''
            checked = ''
        else:
            username = request.COOKIES['username']
            checked = 'checked'
        return render(request, 'user/login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登陆校验"""
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')

        # 数据校验
        if not all([username, password]):
            return render(request, 'user/login.html', {"errmsg": "数据不完整"})

        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户密码正确
            if user.is_active:
                # 已经激活
                login(request, user)
                # 获取登陆后所要跳转到的地址，默认首页
                next_url = request.GET.get("next", reverse('goods:index'))
                # 跳转到首页
                response = redirect(next_url)
                # 记住用户名，设置cookie
                if remember == 'on':
                    response.set_cookie('username', username, max_age=2 * 24 * 3600)
                else:
                    response.delete_cookie('username')
                # 返回应答
                return response
            else:
                return render(request, 'user/login.html', {"errmsg": "请激活你的账号"})
        else:
            return render(request, 'user/login.html', {"errmsg": "用户名或密码不正确"})


class UserInfoView(LoginRequiredMixin, View):
    """用户中心-信息页"""

    def get(self, request):
        # 获取用户跟人信息
        addr = Address.objects.get_default_address(request.user)

        # 获取用户历史浏览记录
        con = get_redis_connection('default')
        history_key = 'history_%d' % request.user.id
        # 获取用户最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)

        # 从数据库中查询用户浏览的商品的具体信息
        # 把数据按用户的浏览顺序进行排序
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(pk=id)
            goods_li.append(goods)

        context = {
            'goods_li': goods_li,
            'addr': addr,
            'username': request.user.username,
            'page': 'info',
        }

        return render(request, 'user/user_center_info.html', context)


class UserOrderView(LoginRequiredMixin, View):
    """用户中心-订单页"""

    def get(self, request, page):
        # 获取订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            for order_sku in order_skus:
                # 计算小记
                amount = order_sku.count * order_sku.price
                order_sku.amount = amount

            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            order.order_skus = order_skus
        # 分页
        paginator = Paginator(orders, 3)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        # 大于最大页数
        if page > paginator.num_pages:
            page = 1

        # page页的内容
        order_page = paginator.page(page)

        # 总页数小于五页，页面上显示所有页码
        # 前3显1-5，后3显后五，其他显左右各2
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif page >= num_pages - 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = [page - 2, page - 1, page, page + 1, page + 2]

        context = {
            'order_page': order_page,
            'page': 'order',
            'pages': pages,
        }

        return render(request, 'user/user_center_order.html', context)


class UserSiteView(LoginRequiredMixin, View):
    """用户中心-地址页"""

    def get(self, request):
        # 获取用户的默认收货地址
        addr = Address.objects.get_default_address(request.user)
        if addr:

            # 组织上下文
            context = {
                'receiver': addr.receiver,
                'address': addr.addr,
                'zip_code': addr.zip_code,
                'phone': addr.phone,
                'page': 'site'
            }
        else:
            context = {
                'page': 'site'
            }

        return render(request, 'user/user_center_site.html', context)

    def post(self, request):
        # 接受数据
        receiver = request.POST.get('receiver')
        address = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        print(receiver, address, zip_code, phone)

        # 校验
        if not all([receiver, address, phone]):
            return render(request, 'user/user_center_site.html', {"errmsg": "数据不完整"})

        if not re.match(r'^1[1|3|5|7|8][0-9]{9}', phone):
            return render(request, 'user/user_center_site.html', {"errmsg": "手机格式不正确"})
        # 业务处理
        addr = Address.objects.get_default_address(request.user)
        if addr:
            is_default = False
        else:
            is_default = True
        addr = Address()
        addr.receiver = receiver
        addr.addr = address
        addr.zip_code = zip_code
        addr.phone = phone
        addr.is_default = is_default
        addr.user = request.user
        addr.save()
        # 返回应答
        return redirect(reverse('user:site'))


class LogoutView(LoginRequiredMixin, View):
    """用户退出"""

    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))
