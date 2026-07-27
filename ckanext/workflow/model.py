from __future__ import annotations

import datetime
from typing import Any, ClassVar

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship

import ckan.plugins.toolkit as tk
from ckan.lib.dictization import table_dictize
from ckan.model.types import make_uuid


class WorkflowDefinition(tk.BaseModel):
    __table__: ClassVar[sa.Table] = sa.Table(
        "workflow_definition",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("trigger_type", sa.Text, default="dataset_create", nullable=False),
        sa.Column("dataset_type", sa.Text, default="all", nullable=False),
        sa.Column("metadata_template", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
    )

    id: Mapped[int]
    name: Mapped[str]
    description: Mapped[str | None]
    enabled: Mapped[bool]
    trigger_type: Mapped[str]
    dataset_type: Mapped[str]
    metadata_template: Mapped[str | None]
    created_at: Mapped[datetime.datetime]

    # Relationships
    steps: Mapped[list[WorkflowStep]] = relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowStep.sequence"
    )
    instances: Mapped[list[WorkflowInstance]] = relationship(
        "WorkflowInstance", back_populates="workflow", cascade="all, delete-orphan"
    )

    def dictize(self) -> dict[str, Any]:
        data = table_dictize(self, {})
        data["steps"] = [step.dictize() for step in self.steps]
        return data


class WorkflowStep(tk.BaseModel):
    __table__: ClassVar[sa.Table] = sa.Table(
        "workflow_step",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.Integer, sa.ForeignKey("workflow_definition.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("assigned_role", sa.Text, nullable=False),
        sa.Column("step_type", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("timeout_duration", sa.Integer, nullable=False, server_default="0"),
        sa.Column("post_actions", JSONB, server_default="{}", nullable=False),
    )

    id: Mapped[str]
    workflow_id: Mapped[int]
    sequence: Mapped[int]
    name: Mapped[str]
    assigned_role: Mapped[str]
    step_type: Mapped[str]
    instructions: Mapped[str | None]
    timeout_duration: Mapped[int]
    post_actions: Mapped[dict[str, Any]]

    workflow: Mapped[WorkflowDefinition] = relationship("WorkflowDefinition", back_populates="steps")

    def dictize(self) -> dict[str, Any]:
        return table_dictize(self, {})


class WorkflowInstance(tk.BaseModel):
    __table__: ClassVar[sa.Table] = sa.Table(
        "workflow_instance",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Text, primary_key=True, default=make_uuid),  # UUID
        sa.Column("package_id", sa.Text, nullable=False, index=True),
        sa.Column("workflow_id", sa.Integer, sa.ForeignKey("workflow_definition.id"), nullable=False),
        sa.Column("current_step_index", sa.Integer, default=0, nullable=False),
        sa.Column(
            "status", sa.Text, default="active", nullable=False
        ),  # 'active', 'completed', 'rejected', 'cancelled', 'overdue'
        sa.Column("started_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
    )

    id: Mapped[str]
    package_id: Mapped[str]
    workflow_id: Mapped[int]
    current_step_index: Mapped[int]
    status: Mapped[str]
    started_at: Mapped[datetime.datetime]
    updated_at: Mapped[datetime.datetime]

    tasks: Mapped[list[WorkflowTask]] = relationship(
        "WorkflowTask", back_populates="instance", cascade="all, delete-orphan", order_by="WorkflowTask.sequence"
    )

    workflow: Mapped[WorkflowDefinition] = relationship("WorkflowDefinition", back_populates="instances")

    def dictize(self) -> dict[str, Any]:
        data = table_dictize(self, {})
        data["tasks"] = [task.dictize() for task in self.tasks]
        data["workflow"] = self.workflow.dictize()
        return data


class WorkflowTask(tk.BaseModel):
    __table__: ClassVar[sa.Table] = sa.Table(
        "workflow_task",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.Text, sa.ForeignKey("workflow_instance.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("assigned_role", sa.Text, nullable=False),
        sa.Column("step_type", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("status", sa.Text, default="pending", nullable=False),  # 'pending', 'completed', 'rejected'
        sa.Column("completed_by", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(True), nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("post_actions", sa.Text, nullable=True),  # JSON config
    )

    id: Mapped[int]
    instance_id: Mapped[str]
    sequence: Mapped[int]
    name: Mapped[str]
    assigned_role: Mapped[str]
    step_type: Mapped[str]
    instructions: Mapped[str | None]
    status: Mapped[str]
    completed_by: Mapped[str | None]
    completed_at: Mapped[datetime.datetime | None]
    comments: Mapped[str | None]
    post_actions: Mapped[str | None]

    instance: Mapped[WorkflowInstance] = relationship("WorkflowInstance", back_populates="tasks")

    def dictize(self) -> dict[str, Any]:
        return table_dictize(self, {})


class WorkflowNotification(tk.BaseModel):
    __table__: ClassVar[sa.Table] = sa.Table(
        "workflow_notification",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_name", sa.String(100), nullable=False, index=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("read", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
    )

    id: Mapped[int]
    user_name: Mapped[str]
    message: Mapped[str]
    read: Mapped[bool]
    created_at: Mapped[datetime.datetime]

    def dictize(self) -> dict[str, Any]:
        return table_dictize(self, {})
