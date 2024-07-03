from django.urls import path,include
from apps.login import views
urlpatterns = [
    path("login/",views.index),
]