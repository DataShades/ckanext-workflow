# -*- coding: utf-8 -*-
from __future__ import annotations
from abc import ABC, abstractmethod


class IWorkflowAutomatedTaskRunner(ABC):
    """Interface class for external workflow engines running automated steps.
    
    This abstracts all communication between CKAN and the external task execution engines
    (such as n8n or testing mocks).
    """

    @abstractmethod
    def trigger_task(self, task_id: str, dataset_id: str, callback_url: str, config: dict) -> bool:
        """Triggers the execution of the automated task on the external engine.

        :param task_id: Unique task identifier in CKAN database.
        :param dataset_id: ID of the dataset package.
        :param callback_url: CKAN API endpoint the engine must call when finished.
        :param config: Dictionary with task configurations (e.g., webhook URL).
        :returns: True if task was successfully triggered, False otherwise.
        """
        pass

    @abstractmethod
    def cancel_task(self, task_id: str, config: dict) -> bool:
        """Cancels an active automated task.

        :param task_id: Unique task identifier.
        :param config: Dictionary with task configurations.
        :returns: True if task was cancelled successfully.
        """
        pass

    @abstractmethod
    def get_task_status(self, task_id: str, config: dict) -> str:
        """Retrieves the current execution status of the automated task from the engine.

        :param task_id: Unique task identifier.
        :param config: Dictionary with task configurations.
        :returns: Status string: 'pending', 'running', 'completed', 'failed', or 'unknown'.
        """
        pass
