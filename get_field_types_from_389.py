#!/usr/bin/env python3
"""Helper script to get field datatypes from project 389 for CustomEntity02."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from ff_bidding_app.shotgrid import ShotgridClient

# Fields to check
fields = [
    "sg_vfx_breakdown_scene",
    "sg_interior_exterior",
    "sg_set",
    "sg_time_of_day",
    "code",
    "sg_previs",
    "sg_sim",
    "sg_script_excerpt",
    "sg_vfx_type",
    "sg_number_of_shots",
    "sg_complexity",
    "sg_vfx_assumptions",
    "sg_vfx_questions",
    "sg_team_notes",
    "sg_vfx_supervisor_notes",
    "sg_on_set_vfx_needs",
    "sg_page_eights",
    "sg_unit",
    "sg_sorting_priority",
]

with ShotgridClient() as client:
    schema = client.get_entity_schema("CustomEntity02")

    print("# Field datatypes from CustomEntity02 (for project 389 template)")
    print("BREAKDOWN_ITEM_REQUIRED_FIELDS = {")

    for field_name in fields:
        if field_name in schema:
            field_info = schema[field_name]
            datatype = field_info.get("data_type", {})

            # Handle case where data_type might be a dict with 'value' key or just a string
            if isinstance(datatype, dict):
                datatype = datatype.get("value", str(datatype))

            field_label = field_info.get("name", {})
            if isinstance(field_label, dict):
                field_label = field_label.get("value", field_name)

            print(f'    "{field_name}": "{datatype}",  # {field_label}')
        else:
            print(f'    "{field_name}": "MISSING",  # NOT FOUND IN SCHEMA')

    print("}")
