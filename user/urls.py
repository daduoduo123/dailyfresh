from django.urls import path, re_path
from django.contrib.auth.decorators import login_required
from .views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, UserSiteView, LogoutView

app_name = 'user'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    re_path(r'^active/(?P<token>.*)/$', ActiveView.as_view(), name='active'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),

    path('info/', UserInfoView.as_view(), name='info'),
    path('order/<int:page>', UserOrderView.as_view(), name='order'),
    path('site/', UserSiteView.as_view(), name='site'),

]
