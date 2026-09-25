from django.urls import path

from . import api, views

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
    path("manage/parts/<int:pk>/", views.manage_part_edit_view, name="manage_part_edit"),
    path("manage/users/", views.manage_users_view, name="manage_users_view"),
    path(
        "api/equipment/<int:pk>/reassign/",
        views.reassign_equipment_view,
        name="reassign_equipment_view",
    ),
    path("reports/", views.reports_view, name="reports_view"),
    path("api/ingest/", views.ingest_view, name="ingest_view"),
    # Android companion app
    path("api/login/", api.api_login_view, name="api_login"),
    path("api/me/", api.api_me_view, name="api_me"),
    path("api/checklist/", api.api_checklist_view, name="api_checklist"),
    path("api/equipment/", api.api_equipment_list_view, name="api_equipment_list"),
    path("api/equipment/<int:pk>/", api.api_equipment_detail_view, name="api_equipment_detail"),
    path(
        "api/equipment/<int:pk>/inspections/",
        api.api_create_inspection_view,
        name="api_create_inspection",
    ),
    path("api/equipment/<int:pk>/issues/", api.api_report_issue_view, name="api_report_issue"),
    path("api/work-orders/", api.api_work_orders_list_view, name="api_work_orders_list"),
    path("api/work-orders/<int:pk>/", api.api_work_order_detail_view, name="api_work_order_detail"),
    path(
        "api/work-orders/<int:pk>/status/",
        api.api_work_order_status_view,
        name="api_work_order_status",
    ),
    path("api/work-orders/<int:pk>/labor/", api.api_add_labor_line_view, name="api_add_labor_line"),
    path("api/work-orders/<int:pk>/parts/", api.api_add_part_line_view, name="api_add_part_line"),
    path(
        "api/work-orders/<int:pk>/comments/",
        api.api_add_work_order_comment_view,
        name="api_add_work_order_comment",
    ),
    path("api/parts/", api.api_parts_list_view, name="api_parts_list"),
]
