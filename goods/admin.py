from django.contrib import admin
from django.core.cache import cache
from .models import GoodsSKU, GoodsSPU, IndexGoodsBanner, IndexTypeGoodsBanner, GoodsType, IndexPromotionBanner
from celery_tasks.tasks import generate_static_index_html


# Register your models here.
class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """跟新表中的数据时调用"""
        super().save_model(request, obj, form, change)

        # 发出任务，重新生成首页静态页面
        generate_static_index_html.delay()
        # 清除缓存数据
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """删除表中数据时调用"""
        super().delete_model(request, obj)
        # 发出任务，重新生成首页静态页面
        generate_static_index_html.delay()
        # 清除缓存数据
        cache.delete('index_page_data')


@admin.register(GoodsType)
class GoodsTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'logo']


@admin.register(GoodsSPU)
class GoodsSPUAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


@admin.register(GoodsSKU)
class GoodsSKUAdmin(BaseModelAdmin):
    list_display = ['id', 'name', 'type', 'price', 'status','stock']


@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['id', 'sku']


@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['sku', 'display_type', 'type']


@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(BaseModelAdmin):
    list_display = ['id', 'name']
