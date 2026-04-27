"""Add summary/description to semantic_spaces.py route decorators."""

import re

FILE = "ontology_engine/api/routes/semantic_spaces.py"

# Map: line_number -> (summary, description)
# Line numbers are 1-based
summaries = {
    173: ("List semantic spaces", "List all semantic spaces with their IDs, names, statuses, and entity counts."),
    189: ("Get semantic space", "Get detailed information about a specific semantic space."),
    201: ("Update space metadata", "Update space name, description, domain, or status."),
    224: ("Delete semantic space", "Delete a semantic space and all its associated data. Supports ?dry_run=true to preview impact."),
    240: ("List rule definitions", "List all rule definitions (L4) in the space."),
    252: ("Create rule definition", "Add a new rule definition to the space schema L4 layer."),
    291: ("Get rule definition", "Get a specific rule definition by ID."),
    311: ("Update rule definition", "Update an existing rule definition. Supports ?dry_run=true to preview impact."),
    352: ("Delete rule definition", "Delete a rule definition. Supports ?dry_run=true to preview impact."),
    378: ("List rule logics", "List all rule logics (L4) in the space."),
    390: ("Create rule logic", "Add a new rule logic to the space schema L4 layer."),
    427: ("Get rule logic", "Get a specific rule logic by ID."),
    447: ("Update rule logic", "Update an existing rule logic."),
    482: ("Delete rule logic", "Delete a rule logic."),
    508: ("List versions", "List all version snapshots for the space."),
    533: ("Create version snapshot", "Create a new version snapshot of the space."),
    561: ("Rollback to version", "Rollback the space to a specific version. Supports ?dry_run=true to preview changes."),
    581: ("List entities", "List all entities in the space."),
    600: ("Create entity", "Add a new entity to the space."),
    619: ("List relations", "List all relations in the space."),
    631: ("Create relation", "Add a new relation to the space."),
    673: ("Get schema graph", "Get the schema dependency graph for the space."),
    822: ("Get rule chain", "Get the rule execution chain for a specific analysis dimension."),
    915: ("Execute analysis", "Execute rule analysis on an entity. Runs L2 categorization, L3 metric computation, and L4 rule execution."),
    1054: ("Simulate analysis", "Simulate rule execution with hypothetical data overrides. Returns baseline vs simulated comparison."),
}

with open(FILE, "r") as f:
    lines = f.readlines()

for line_num, (summary, description) in summaries.items():
    line_idx = line_num - 1
    if line_idx < len(lines):
        line = lines[line_idx]
        if "summary=" not in line:
            new_line = line.replace(
                "response_model=dict)",
                f'response_model=dict, summary="{summary}", description="{description}")'
            )
            lines[line_idx] = new_line

with open(FILE, "w") as f:
    f.writelines(lines)

print(f"Updated {len(summaries)} route decorators in {FILE}")
