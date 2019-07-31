from django.shortcuts import render, get_object_or_404
from django.views.generic import View
from django.core.cache import cache
from django.core.paginator import Paginator
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods
from django_redis import get_redis_connection


# Create your views here.
class IndexView(View):
    def get(self, request):
        """显示首页"""
        # 从缓存中获取数据
        if cache.get('index_page_data') is None:

            # 种类列表
            types = GoodsType.objects.all()[:5]

            # 首页轮播列表
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')
            # 促销商品列表
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
            # 展示分类商品展示列表
            for type in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                # 动态给商品种类增加属性
                type.image_banners = image_banners
                type.title_banners = title_banners

            context = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners,
            }
            # 设置缓存       key           value     timeout
            cache.set('index_page_data', context, 3600)
        else:
            context = cache.get('index_page_data')

        # 获取用户购物车商品数目
        if request.user.is_authenticated:
            # 登陆之后获取的商品数量
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % request.user.pk
            cart_count = conn.hlen(cart_key)

        else:
            # 未登陆
            cart_count = 0

        context['cart_count'] = cart_count

        return render(request, 'index.html', context)


class DetailView(View):
    """详情页"""

    def get(self, request, goods_pk):
        # 商品分类信息
        types = GoodsType.objects.all()[:6]
        # 当前商品信息
        sku = get_object_or_404(GoodsSKU, pk=goods_pk)
        # 商品评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 新品推荐信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同一个spu的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods_spu=sku.goods_spu).exclude(id=goods_pk)[:5]

        # 总价格
        total_acount = 0

        # 获取用户购物车商品数目
        if request.user.is_authenticated:
            # 登陆之后获取的商品数量
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % request.user.pk
            cart_count = conn.hlen(cart_key)
            # 添加用户的历史记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % request.user.id
            conn.lrem(history_key, 0, goods_pk)
            # 插入到最前方
            conn.lpush(history_key, goods_pk)
            # 只保存用户最新的五条信息
            conn.ltrim(history_key, 0, 4)
        else:
            # 未登陆
            cart_count = 0

        context = {
            'types': types,
            'sku': sku,
            'sku_orders': sku_orders,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'total_acount': total_acount,
            'same_spu_skus': same_spu_skus,
        }

        return render(request, 'goods/detail.html', context)


class ListView(View):
    """列表显示页面"""

    def get(self, request, types_pk, page):
        goods_type = get_object_or_404(GoodsType, pk=types_pk)
        # 全部商品分类
        types = GoodsType.objects.all()[:6]

        # 获取排序的方式
        sort = request.GET.get('sort')
        if sort == 'sales':
            # 人气排序
            skus = GoodsSKU.objects.filter(type=goods_type).order_by('-sales')
        elif sort == 'price':
            # 价格排序
            skus = GoodsSKU.objects.filter(type=goods_type).order_by('price')
        else:
            # 默认排序
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=goods_type).order_by()
        print(sort)
        # 新品推荐
        new_skus = GoodsSKU.objects.filter(type=goods_type).order_by('-create_time')[:4]

        # 获取用户购物车商品数目
        if request.user.is_authenticated:
            # 登陆之后获取的商品数量
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % request.user.pk
            cart_count = conn.hlen(cart_key)

        else:
            # 未登陆
            cart_count = 0

        # 分页
        paginator = Paginator(skus, 1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        # 大于最大页数
        if page > paginator.num_pages:
            page = 1

        # page页的内容
        skus_page = paginator.page(page)

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
            'type': goods_type,
            'skus_page': skus_page,
            'new_skus': new_skus,
            'types': types,
            'cart_count': cart_count,
            'sort': sort,
            'pages': pages,
            'num_pages':num_pages,
        }
        return render(request, 'goods/list.html', context)
