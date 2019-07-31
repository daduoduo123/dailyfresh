from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import View
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import GoodsSKU


# Create your views here.

class CartAddView(View):
    """购物记录添加"""

    def post(self, request):

        # 判断用户是否登陆：
        if not request.user.is_authenticated:
            return JsonResponse({'res': 4, 'errmsg': '用户未登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        if not all([sku_id, count]):
            return JsonResponse({'res': 0, 'errmsg': '数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 1, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        sku = get_object_or_404(GoodsSKU, pk=sku_id)

        # 业务处理
        conn = get_redis_connection()
        cart_key = 'cart_%d' % request.user.id
        # 如果不存在，返回None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            count = int(cart_count) + count

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 2, 'errmsg': '商品库存不足'})
        # 重新设置购物车的值
        conn.hset(cart_key, sku_id, count)
        return JsonResponse({'res': 3, 'message': '添加成功'})


class CartInfoView(LoginRequiredMixin, View):
    """购物车页面"""

    def get(self, request):
        user = request.user
        cart_key = 'cart_%d' % user.id
        conn = get_redis_connection('default')
        # 获取商品信息，从redis中
        cart_dict = conn.hgetall(cart_key)
        sku_list = []
        total_count = 0
        total_price = 0
        for sku_id, count in cart_dict.items():
            sku = get_object_or_404(GoodsSKU, pk=sku_id)
            # 计算商品的小记
            amount = sku.price * int(count)
            # 动态增加一个小记属性
            sku.amount = amount
            # 对应商品的数量
            sku.count = int(count)
            sku_list.append(sku)
            total_count += int(sku.count)
            total_price += amount

        context = {
            'sku_list': sku_list,
            'total_count': total_count,
            'total_price': total_price,
        }

        return render(request, 'cart/cart.html', context)


class CartUpdateView(View):
    """购物车记录更新"""

    def post(self, request):
        """购物车更新记录"""
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        sku = get_object_or_404(GoodsSKU, pk=sku_id)

        # 业务处理
        conn = get_redis_connection()
        cart_key = 'cart_%d' % user.id
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 3, 'errmsg': '商品库存不足'})

        # 更新
        conn.hset(cart_key, sku_id, count)

        # 获取总件数
        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 4, 'message': '添加成功', 'total_count': total_count})


class CartDeleteView(View):
    """购物车删除"""
    def post(self, request):
        """购物车删除"""
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        sku_id = request.POST.get('sku_id')

        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})


        # 校验商品是否存在
        sku = get_object_or_404(GoodsSKU, pk=sku_id)

        # 业务处理
        conn = get_redis_connection()
        cart_key = 'cart_%d' % user.id

        # 删除
        conn.hdel(cart_key, sku_id)

        # 获取总件数
        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 2, ';message': '删除成功', 'total_count': total_count})