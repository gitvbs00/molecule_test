from __future__ import absolute_import, unicode_literals
from celery import Celery
from kombu import Queue

app = Celery('script_task',
             broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0',
             include=['script'])

app.conf.update(
    task_routes={
        'script.run_script': {'queue': 'script'},
    },
    task_queues=(
        Queue('script', routing_key='script.#'),
    ),
    task_default_queue='script',
    task_default_routing_key='script.default'
)