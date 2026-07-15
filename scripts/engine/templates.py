"""Shared module templates for ERPNext app generation (Phase 3).

Consolidated from planner.py and executor.py to eliminate duplication.
C2: Single source of truth for all module templates.
"""

MODULE_TEMPLATES: dict[str, dict] = {
    "field_service": {
        "doctypes": ["Site Visit", "Inspection Report", "Work Order", "Crew", "Equipment"],
        "child_tables": ["Site Visit Photo", "Inspection Checklist Item", "Crew Member"],
    },
    "contractor": {
        "doctypes": ["Contractor", "Contract", "Compliance Check", "Trade", "Site"],
        "child_tables": ["Contractor Document", "Compliance Item"],
    },
    "hr_extended": {
        "doctypes": ["Training Program", "Training Event", "Certification", "Skill Matrix"],
        "child_tables": ["Training Attendee", "Skill Assessment Item"],
    },
    "inventory_extended": {
        "doctypes": ["Stocktake", "Stock Reconciliation", "Quality Check", "Batch Trace"],
        "child_tables": ["Stocktake Item", "Quality Check Item"],
    },
    "project_extended": {
        "doctypes": ["Project Phase", "Resource Allocation", "Progress Report", "Variation Order"],
        "child_tables": ["Phase Task", "Resource Item", "Variation Item"],
    },
    "maintenance": {
        "doctypes": ["Asset Maintenance Log", "Preventive Schedule", "Breakdown Report", "Spare Part"],
        "child_tables": ["Maintenance Task", "Part Used"],
    },
}
