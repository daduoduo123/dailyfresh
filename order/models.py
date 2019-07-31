from django.db import models
from utils.db.base_model import BaseModel
from user.models import User, Address
from goods.models import GoodsSKU


# Create your models here.
class OrderInfo(BaseModel):
    """订单模型类"""
    PAY_METHODS = {
        '1': '货到付款',
        '2': '微信支付',
        '3': '支付宝',
        '4': '银联支付',
    }
    ORDER_STATUS = {
        1: '待支付',
        2: '待发货',
        3: '待收货',
        4: '待评价',
        5: '已完成',
    }
    PAY_METHOD_CHOICE = (
        (1, '货到付款'),
        (2, '微信支付'),
        (3, '支付宝'),
        (4, '银联支付'),
    )

    ORDER_STATUS_CHOICE = (
        (1, '待支付'),
        (2, '待发货'),
        (3, '待收货'),
        (4, '待评价'),
        (5, '已完成'),
    )

    order_id = models.CharField(max_length=128, primary_key=True, verbose_name='订单编号')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    addr = models.ForeignKey(Address, on_delete=models.CASCADE, verbose_name='地址')
    pay_method = models.SmallIntegerField(default=3, choices=PAY_METHOD_CHOICE, verbose_name='支付方式')
    order_status = models.SmallIntegerField(default=1, choices=ORDER_STATUS_CHOICE, verbose_name='订单状态')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='商品总价')
    total_count = models.IntegerField(default=1, verbose_name='商品数量')
    transit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='订单运费',default='5.0')
    trade_no = models.CharField(max_length=128, default='', verbose_name='支付编号')

    class Meta:
        db_table = 'df_order_info'

    def __str__(self):
        return self.user.username + ":" + str(self.order_id)


class OrderGoods(BaseModel):
    """订单商品模型累"""
    order = models.ForeignKey(OrderInfo, on_delete=models.CASCADE, verbose_name='订单')
    sku = models.ForeignKey(GoodsSKU, on_delete=models.CASCADE, verbose_name='商品SKU')
    count = models.IntegerField(default=1, verbose_name='商品数目')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='商品价格')
    comment = models.CharField(max_length=256, default='', verbose_name='评论')

    class Meta:
        db_table = 'df_order_goods'

    def __str__(self):
        return self.order
