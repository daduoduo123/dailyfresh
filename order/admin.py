from django.contrib import admin
from .models import OrderInfo, OrderGoods


# Register your models here.
@admin.register(OrderGoods)
class OrderGoodsAdmin(admin.ModelAdmin):
    list_display = ['order', 'sku', 'count']


@admin.register(OrderInfo)
class OrderInfoAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'trade_no', 'addr', 'pay_method']
