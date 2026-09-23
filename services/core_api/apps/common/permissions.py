from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrReadOnly(BasePermission):
    """Object-level permission: only the owner may edit/delete."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "customer", None) or getattr(obj, "user", None)
        return owner == request.user


class IsStaffOrReadOnly(BasePermission):
    """Anyone authenticated can read; only staff can write. Used for
    catalog/inventory endpoints where product data is managed by ops
    but browsable by any authenticated customer or service.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)
