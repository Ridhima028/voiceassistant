"""
Celery application shared by the API (producer) and the worker (consumer).

The API only uses this to *send* messages (send_task by name), so importing
it never pulls in Whisper. The worker imports the modules listed in
`include`, which is where the heavy transcription code lives.

There is deliberately no result backend: Postgres `lectures.status` is the
single source of truth for job state.
"""

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "voicepilot",
    broker=REDIS_URL,
    include=["tasks"],
)

celery_app.conf.update(
    # Ack the message only AFTER the task finishes, so a worker crash
    # mid-transcription leaves the message in Redis to be redelivered.
    task_acks_late=True,
    # If the worker process is killed (OOM, SIGKILL), requeue the message
    # instead of acking it as failed.
    task_reject_on_worker_lost=True,
    # Reserve one message at a time. Transcriptions are long, so prefetching
    # extra jobs would just park them behind a busy worker.
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    broker_transport_options={
        # How long Redis waits for an ack before handing an unacked message
        # to another worker. Must be longer than the longest transcription,
        # or a healthy job gets redelivered and runs twice.
        "visibility_timeout": 3 * 60 * 60,  # 3 hours
    },
)
