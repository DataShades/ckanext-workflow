# ckanext-workflow

An advanced, flexible workflow engine extension for CKAN dataset lifecycle
management.

It allows administrators to define structured publication steps, request manual
approvals, make branching choices, execute automated actions, configure
timeouts, and secure dataset visibility under incomplete workflows via CKAN's
permission labels.

---

## User Interface Screenshots

### 1. Workflow Definition List

Admin view to manage all configured workflow definitions.

[![Definition list](./screenshots/definition_list.html)]

### 2. Workflow Builder
Form showing dynamic step cards, timeouts, assignee selector, and branching path configurations.

[![Definition list](./screenshots/builder.html)]

### 3. Dataset Workflow Visualizer
Interactive Mermaid.js chart rendering step structures, decision nodes, and current progress.

[![Definition list](./screenshots/vizualizer.html)]

### 4. User Task Dashboard
My Tasks workspace displaying pending approvals, decisions, manual steps, and notifications.

[![Definition list](./screenshots/user_dashboard.html)]

---

## Installation

Install the extension package:

```bash
pip install ckanext-workflow
```

Add `workflow` to the `ckan.plugins` list in your configuration file (e.g., `ckan.ini` or `production.ini`):

```ini
ckan.plugins = ... workflow
```

Run the database migration:
```bash
ckan db upgrade
```

---

## Core Concepts

Understanding the core abstractions is key to working with the workflow APIs
and database models:

* **Workflow Definition vs. Workflow Instance**:
  * **Workflow Definition**: A blueprint or schema template. It defines general
    settings (name, triggers, dataset types) and a static sequence of steps
    that a dataset must proceed through.
  * **Workflow Instance**: The active execution lifecycle of a workflow
    blueprint bound to a specific dataset. An instance is spawned when a
    dataset triggers a definition, and tracks its runtime progress.
* **Workflow Step vs. Workflow Task**:
  * **Workflow Step**: A configuration block inside a *Workflow Definition*
    detailing step rules (type, assignee role or username, instructions,
    timeout duration, and branching/rejection routes).
  * **Workflow Task**: A runtime record within a *Workflow Instance*. When an
    instance starts, the definition steps are copied into a sequence of task
    rows. Tasks track execution details (e.g., status, comments, assignee
    actions, completion timestamps) and transition through `pending`,
    `completed`, `rejected`, or `skipped` states.

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
