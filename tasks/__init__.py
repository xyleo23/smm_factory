"""Celery tasks for SMM Factory automation."""

from tasks.celery_app import celery_app
from tasks.parse_task import parse_and_generate
from tasks.publish_task import publish_post

__all__ = ["celery_app", "parse_and_generate", "publish_post"]
