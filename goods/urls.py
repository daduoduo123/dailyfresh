from django.urls import path
from .views import IndexView, DetailView,ListView

app_name = 'goods'
urlpatterns = [
    path('index/', IndexView.as_view(), name='index'),
    path('detail/<int:goods_pk>/', DetailView.as_view(), name='detail'),
    path('list/<int:types_pk>/<int:page>/', ListView.as_view(), name='list'),
]
