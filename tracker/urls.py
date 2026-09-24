from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard_view"),
    path("equipment/", views.equipment_list, name="equipment_list"),
    path("equipment/<int:pk>/", views.equipment_detail, name="equipment_detail"),
    path("equipment/<int:pk>/inspect/", views.new_inspection_view, name="new_inspection"),
    path("schedule/", views.schedule_view, name="schedule_view"),
    path("work-orders/", views.work_orders_view, name="work_orders_view"),
    path("work-orders/<int:pk>/", views.work_order_detail_view, name="work_order_detail"),
    path("fleet-map/", views.fleet_map_view, name="fleet_map_view"),
    path("fleet-tree/", views.fleet_tree_view, name="fleet_tree_view"),
    path("manage/", views.manage_view, name="manage_view"),
    path("manage/equipment/<int:pk>/", views.manage_equipment_edit_view, name="manage_equipment_edit"),
    path("manage/sites/<int:pk>/", views.manage_site_edit_view, name="manage_site_edit"),
    path("manage/users/", views.manage_users_view, name="manage_users_view"),
    path(
        "api/equipment/<int:pk>/reassign/",
        views.reassign_equipment_view,
        name="reassign_equipment_view",
    ),
    path("reports/", views.reports_view, name="reports_view"),
    path("api/ingest/", views.ingest_view, name="ingest_view"),
]
