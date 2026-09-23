import factory
from apps.catalog.models import Category, Product
from apps.inventory.models import StockItem
from apps.users.models import User
from factory.django import DjangoModelFactory


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = "User"

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "StrongPassw0rd!")
        if create:
            self.save()


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product
        skip_postgeneration_save = True

    category = factory.SubFactory(CategoryFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    name = factory.Sequence(lambda n: f"Product {n}")
    price = "19.99"
    is_active = True

    @factory.post_generation
    def stock(self, create, extracted, **kwargs):
        if create:
            StockItem.objects.create(
                product=self, quantity=extracted if extracted is not None else 10
            )
