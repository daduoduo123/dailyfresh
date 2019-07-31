from django.shortcuts import render, redirect, reverse, get_object_or_404, get_list_or_404
from django.http import JsonResponse
from django.db import transaction
from django.views.generic import View
from goods.models import GoodsSKU
from user.models import Address
from .models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from datetime import datetime
import os
from alipay import AliPay
from django.conf import settings


# Create your views here.
class OrderPlaceView(LoginRequiredMixin, View):
    """提交订单"""

    def post(self, request):
        user = request.user
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')
        # 校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))

        conn = get_redis_connection()
        cart_key = 'cart_%d' % user.pk
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            sku = get_object_or_404(GoodsSKU, pk=sku_id)
            # 数量
            count = conn.hget(cart_key, sku.pk)
            count = int(count)
            # 小记
            amount = sku.price * count
            # 动态增加属性
            sku.amount = amount
            sku.count = count
            skus.append(sku)
            total_count += count
            total_price += amount

        # 运费，有单独models来控制，这里直接给个固定的值
        transit_price = 10
        # 实际付款
        total_pay = total_price + transit_price
        # 用户地址 必须要有默认地址
        addrs = get_list_or_404(Address, user=user)

        # 组织上下文
        sku_ids = ','.join(sku_ids)
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'transit_price': transit_price,
            'sku_ids': sku_ids,
        }

        return render(request, 'order/place_order.html', context)


# mysql事物，要么都成功，要么都是失败
# 高并发：秒杀
# 支付宝支付
# 悲观锁，冲突多用
class OrderCommitView1(View):
    """订单创建"""

    @transaction.atomic()
    def post(self, request):
        # 由于是ajax请求，同时需要判断用户登陆，所以不能集成mixinlei，需要单独判断
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受数据
        sku_ids = request.POST.get('sku_ids')
        pay_method = request.POST.get("pay_method")
        addr_id = request.POST.get('addr_id')

        # 校验数据：
        if not all([sku_ids, pay_method, addr_id]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})
        addr = get_object_or_404(Address, pk=addr_id)

        # 业务处理
        # 向order_info添加记录
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        transit_price = 10  # 固定运费
        total_price = 0
        total_count = 0

        # 设置事物保存点
        save_id = transaction.savepoint()
        try:
            # 添加订单信息
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
            )
            # 向order_goods添加记录
            sku_ids = sku_ids.split(',')

            for sku_id in sku_ids:
                try:
                    # select * from df_goods_sku where id = sku_id for update 加锁（悲观所）
                    sku = GoodsSKU.objects.select_for_update().get(pk=sku_id)
                except:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # 从redis中获取要购买的数量
                conn = get_redis_connection()
                cart_key = 'cart_%d' % user.id
                count = conn.hget(cart_key, sku_id)
                count = int(count)

                # 判断商品库存
                if count > sku.stock:
                    # 回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 5, 'errmsg': sku.name + '商品库存不足'})

                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=count,
                    price=sku.price,
                )
                # 跟新商品的库存和销量
                sku.stock -= count
                sku.sales += count
                sku.save()

                # 累加计算订单商品的总数目，和总价格
                amount = sku.price * count
                total_count += count
                total_price += amount

            # 更新order_info总数量和总价
            order.total_count = total_count
            order.total_price = transit_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 6, 'errmsg': '下单失败'})

        # 提交事物
        transaction.savepoint_commit(save_id)

        # 清除用户购物车中记录
        conn.hdel(cart_key, *sku_ids)  # 进行拆包

        # 返回应答
        return JsonResponse({'res': 3, 'message': '创建成功'})


# 乐观锁，冲突少时，使用乐观锁
class OrderCommitView(View):
    """订单创建"""

    @transaction.atomic()
    def post(self, request):
        # 由于是ajax请求，同时需要判断用户登陆，所以不能集成mixinlei，需要单独判断
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受数据
        sku_ids = request.POST.get('sku_ids')
        pay_method = request.POST.get("pay_method")
        addr_id = request.POST.get('addr_id')

        # 校验数据：
        if not all([sku_ids, pay_method, addr_id]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})
        addr = get_object_or_404(Address, pk=addr_id)

        # 业务处理
        # 向order_info添加记录
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        transit_price = 10  # 固定运费
        total_price = 0
        total_count = 0

        # 设置事物保存点
        save_id = transaction.savepoint()
        try:
            # 添加订单信息
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
            )
            # 向order_goods添加记录
            sku_ids = sku_ids.split(',')

            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(pk=sku_id)
                    except:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                    # 从redis中获取要购买的数量
                    conn = get_redis_connection()
                    cart_key = 'cart_%d' % user.id
                    count = conn.hget(cart_key, sku_id)
                    count = int(count)

                    # 判断商品库存
                    if count > sku.stock:
                        # 回滚
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 5, 'errmsg': sku.name + '商品库存不足'})
                    # 跟新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - count
                    new_sales = sku.sales + count
                    # update df_goods_sku set stock = new_stock, sales = new_sales where id=sku_id stock=orgin_stock
                    # 返回受影响的行数，(搜到的结果)return raws
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 三次多没有成功
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 6, 'errmsg': '下单失败2'})
                        continue
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price,
                    )

                    # 累加计算订单商品的总数目，和总价格
                    amount = sku.price * count
                    total_count += count
                    total_price += amount

                    # 跳出循环
                    break

            # 更新order_info总数量和总价
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 6, 'errmsg': '下单失败1'})

        # 提交事物
        transaction.savepoint_commit(save_id)

        # 清除用户购物车中记录
        conn.hdel(cart_key, *sku_ids)  # 进行拆包

        # 返回应答
        return JsonResponse({'res': 3, 'message': '创建成功'})


class OrderPayView(View):
    """订单支付"""

    def post(self, request):
        # 用户是否登陆
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单号码'})
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '无效订单'})

        # 业务处理：调用支付借口
        """
            设置配置，包括支付宝网关地址、app_id、应用私钥、支付宝公钥等，。
            """
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid="2016092900624520",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string   沙箱环境
        order_id = order.order_id
        subject = "女帝电商"
        total_pay = order.transit_price + order.total_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=total_pay,
            subject=subject,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


class CheckPayView(View):
    """查询支付结果"""

    def post(self, request):
        # 用户是否登陆
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单号码'})
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '无效订单'})

        # 业务处理：调用支付借口
        """
            设置配置，包括支付宝网关地址、app_id、应用私钥、支付宝公钥等，。
            """
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid="2016092900624520",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        while True:
            # 调用支付宝查询接口
            response = alipay.api_alipay_trade_query(order_id)
            """
                   response = {
                     "alipay_trade_query_response": {
                       "trade_no": "2017032121001004070200176844",
                       "code": "10000",
                       "invoice_amount": "20.00",
                       "open_id": "20880072506750308812798160715407",
                       "fund_bill_list": [
                         {
                           "amount": "20.00",
                           "fund_channel": "ALIPAYACCOUNT"
                         }
                       ],
                       "buyer_logon_id": "csq***@sandbox.com",
                       "send_pay_date": "2017-03-21 13:29:17",
                       "receipt_amount": "20.00",
                       "out_trade_no": "out_trade_no15",
                       "buyer_pay_amount": "20.00",
                       "buyer_user_id": "2088102169481075",
                       "msg": "Success",
                       "point_amount": "0.00",
                       "trade_status": "TRADE_SUCCESS",
                       "total_amount": "20.00"
                     },
                   }
                   """
            code = response['code']
            trade_status = response['trade_status']
            if code == '10000' and trade_status == "TRADE_SUCCESS":
                # 支付成功
                # 获取支付宝交易号，更新订单的状态
                trade_no = response['trade_no']
                order.trade_no = trade_no
                order.order_status = 4
                order.save()
                # 返回结果
                return JsonResponse({'res': 3, "message": '支付成功'})
            elif code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能等一会儿就好了
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res': 4, "errmsg": '支付失败'})


class CommentView(LoginRequiredMixin, View):
    """订单评论"""

    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品的小记
            amount = order_sku.count * order_sku.price
            order_sku.amount = amount
        # 动态给order增加属性order_skus,保存订单商品信息
        order.order_skus = order_skus

        # 使用模版
        return render(request, 'order/order_comment.html', {'order': order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)
        for i in range(1, total_count + 1):
            sku_id = request.POST.get('sku_%d' % i)
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue
            order_goods.comment = content
            order_goods.save()

        # 已完成
        order.order_status = 5
        order.save()
        return redirect(reverse('user:order', kwargs={'page': 1}))
