from django.conf import settings
from django.contrib import admin
from django.urls import path
from strawberry.django.views import GraphQLView

from meetings.schema import schema

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "graphql/",
        GraphQLView.as_view(schema=schema, graphql_ide="graphiql" if settings.DEBUG else None),
    ),
]
