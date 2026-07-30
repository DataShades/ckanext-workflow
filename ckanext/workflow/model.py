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
        sa.Column("object_id", sa.Text, nullable=False, index=True),
        sa.Column("workflow_id", sa.Integer, sa.ForeignKey("workflow_definition.id"), nullable=False),
        sa.Column("current_step_index", sa.Integer, default=0, nullable=False),
        sa.Column(
            "status", sa.Text, default="active", nullable=False
        ),  # 'active', 'completed', 'rejected', 'cancelled', 'overdue'
        sa.Column("started_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(True), server_default=sa.func.now(), nullable=False),
    )

    id: Mapped[str]
    object_id: Mapped[str]
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
        sa.Column("name", sa.Text, key="_name", nullable=False),
        sa.Column("assigned_role", sa.Text, key="_assigned_role", nullable=False),
        sa.Column("step_type", sa.Text, key="_step_type", nullable=False),
        sa.Column("instructions", sa.Text, key="_instructions", nullable=True),
        sa.Column("status", sa.Text, default="pending", nullable=False),  # 'pending', 'completed', 'rejected'
        sa.Column("completed_by", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(True), nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("post_actions", JSONB, key="_post_actions", server_default="{}", nullable=False),
    )

    id: Mapped[int]
    instance_id: Mapped[str]
    sequence: Mapped[int]
    _name: Mapped[str]
    _assigned_role: Mapped[str]
    _step_type: Mapped[str]
    _instructions: Mapped[str | None]
    status: Mapped[str]
    completed_by: Mapped[str | None]
    completed_at: Mapped[datetime.datetime | None]
    comments: Mapped[str | None]
    _post_actions: Mapped[dict[str, Any]]

    instance: Mapped[WorkflowInstance] = relationship("WorkflowInstance", back_populates="tasks")

    @property
    def step(self) -> WorkflowStep | None:
        if self.instance and self.instance.workflow:
            for s in self.instance.workflow.steps:
                if s.sequence == self.sequence:
                    return s
        return None

    @property
    def name(self) -> str:
        s = self.step
        return s.name if s else (self._name or "")

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def assigned_role(self) -> str:
        s = self.step
        return s.assigned_role if s else (self._assigned_role or "")

    @assigned_role.setter
    def assigned_role(self, value: str):
        self._assigned_role = value

    @property
    def step_type(self) -> str:
        s = self.step
        return s.step_type if s else (self._step_type or "")

    @step_type.setter
    def step_type(self, value: str):
        self._step_type = value

    @property
    def instructions(self) -> str | None:
        s = self.step
        return s.instructions if s else self._instructions

    @instructions.setter
    def instructions(self, value: str | None):
        self._instructions = value

    @property
    def post_actions(self) -> dict[str, Any]:
        s = self.step
        return s.post_actions if s else (self._post_actions or {})

    @post_actions.setter
    def post_actions(self, value: dict[str, Any]):
        self._post_actions = value

    def dictize(self) -> dict[str, Any]:
        data = table_dictize(self, {})
        for k in ["_name", "_assigned_role", "_step_type", "_instructions", "_post_actions"]:
            data.pop(k, None)
        data["name"] = self.name
        data["assigned_role"] = self.assigned_role
        data["step_type"] = self.step_type
        data["instructions"] = self.instructions
        data["post_actions"] = self.post_actions
        return data


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
