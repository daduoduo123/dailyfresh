from django.core.mail import send_mail
from django.conf import settings
from celery import Celery
import os
import django
from django.template import loader, RequestContext

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()

# 创建一个对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    subject = '电商网站欢迎你'
    message = ''
    sender = settings.EMAIL_HOST_USER
    receiver = [to_email]
    html_message = '%s进行用户激活<a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
        username, token, token)

    send_mail(subject, message, sender, receiver, html_message=html_message)


from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
@app.task
def generate_static_index_html():
    """产生首页静态页面"""
    """显示首页"""
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
    # 使用模版
    # 加载模版文件
    template = loader.get_template('static_index.html')
    # # 定义上下文
    # context = RequestContext(request, context)
    # 模版渲染
    static_index_html = template.render(context)

    # 生成首页静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w') as f:
        f.write(static_index_html)
