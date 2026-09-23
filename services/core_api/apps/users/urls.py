from apps.users.views import MeView, RegisterView
from django.urls import path

urlpatterns = [
    path("register/", RegisterView.as_view(), name="user-register"),
    path("me/", MeView.as_view(), name="user-me"),
]
