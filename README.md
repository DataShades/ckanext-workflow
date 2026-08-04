# ckanext-workflow

An advanced, flexible workflow engine extension for CKAN dataset lifecycle management.

It allows administrators to define structured publication steps, request manual approvals, make branching choices, execute automated actions, configure timeouts, and secure dataset visibility under incomplete workflows via CKAN's permission labels.

---

## Key Features

- **Intuitive Workflow Builder**: Add, remove, and reorder steps inside step cards, featuring live validation inputs for names, types, roles/users, automated tasks, custom transitions, timeouts, and branching routes.
- **Dynamic Decision Branching**: Model branching logic by defining decision steps with customized option buttons (e.g., Option A vs Option B labels and target step routes).
- **Flexible Transitions & Loops**: Design non-linear logic loops by returning a rejected/failed step to any previous step (which resets target tasks to `pending`) or rejecting the workflow entirely.
- **Role & Individual Assignees**: Assign steps to specific organization roles (member, editor, admin) or to a single individual user (prefixed with `user:`).
- **Automated Tasks**: Integrate with external engines/APIs using pluggable adapters (e.g., sending HTTP posts/webhooks) configured on automated steps.
- **Timeouts**: Define human-readable timeout durations (e.g., `1d 4h`, `2 days`, `1 minute`) that are automatically parsed, validated, and formatted.
- **Granular Security (IPermissionLabels)**: Restrict dataset access under active workflows to authorized assignees, organization editors, and dataset creators, keeping public users from seeing incomplete datasets.
- **Mermaid.js Visualizations**: Render clear workflow flowcharts with colored active steps, custom rejection loops, and diamond branching nodes inside dataset detail and admin dashboards.
- **Restricted Updates**: Prevent users from deleting, swapping, or changing the type of steps on workflows with active/overdue instances.

---

## User Interface Screenshots

### 1. Workflow Definition List
Admin view to manage all configured workflow definitions.
<!-- PLACEHOLDER: workflow_definition_list_screenshot.png -->

### 2. Workflow Builder
Form showing dynamic step cards, timeouts, assignee selector, and branching path configurations.
<!-- PLACEHOLDER: workflow_builder_screenshot.png -->

### 3. Dataset Workflow Visualizer
Interactive Mermaid.js chart rendering step structures, decision nodes, and current progress.
<!-- PLACEHOLDER: dataset_workflow_visualizer_screenshot.png -->

### 4. User Task Dashboard
My Tasks workspace displaying pending approvals, decisions, manual steps, and notifications.
<!-- PLACEHOLDER: user_task_dashboard_screenshot.png -->

---

## Installation

1. Activate your CKAN virtual environment:
   ```bash
   . /usr/lib/ckan/default/bin/activate
   ```
2. Install the extension package:
   ```bash
   pip install ckanext-workflow
   ```
3. Add `workflow` to the `ckan.plugins` list in your configuration file (e.g., `ckan.ini` or `production.ini`):
   ```ini
   ckan.plugins = ... workflow
   ```
4. Run the database migration:
   ```bash
   ckan db upgrade
   ```
5. Restart your CKAN instance.

---

## API Actions

This extension exposes several action APIs to manage definitions and tasks programmatically:

### Definitions
- `workflow_definition_create`: Creates a new workflow definition with steps and trigger configurations.
- `workflow_definition_update`: Modifies an existing workflow definition (restricts step sequence changes if active instances exist).
- `workflow_definition_show`: Shows details of a specific workflow definition.
- `workflow_definition_delete`: Deletes a workflow definition.

### Instances & Tasks
- `workflow_task_complete`: Submits an action (Approve, Reject, Complete, Option Choice) to advance the active step.
- `workflow_instance_show`: Retrieves progress details of an active/completed workflow instance.
- `workflow_instance_cancel`: Cancels an active/overdue workflow instance.
- `workflow_user_task_list`: Lists all workflow tasks assigned to the current user.

---

## Development & Testing

### Installation for Development
1. Clone the repository:
   ```bash
   git clone https://github.com/DataShades/ckanext-workflow.git
   cd ckanext-workflow
   ```
2. Install development requirements and package:
   ```bash
   pip install -e .
   pip install -r dev-requirements.txt
   ```

### Running Tests
To run the full unit and integration test suite:
```bash
pytest --ckan-ini=test.ini
```
