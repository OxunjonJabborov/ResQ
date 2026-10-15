"""Helpers for Celery tasks."""

import functools
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def single_instance(timeout: int = 600):
    """Skip a run while another run of the same task holds the lock.

    Tasks are idempotent anyway; the lock only prevents wasted overlapping work when
    a run takes longer than the beat interval.
    """

    def decorator(fn):
        key = f"resq:task-lock:{fn.__module__}.{fn.__name__}"

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not cache.add(key, "1", timeout):
                logger.info("Skipping %s: previous run still in progress", fn.__name__)
                return None
            try:
                return fn(*args, **kwargs)
            finally:
                cache.delete(key)

        return wrapper

    return decorator
