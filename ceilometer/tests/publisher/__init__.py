import datetime
import copy

from ceilometer import sample


COUNTER_SOURCE = 'testsource'

data_samples = [
    sample.Sample(
        name='test',
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish'},
        source=COUNTER_SOURCE,
    ),
    sample.Sample(
        name='test',
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish'},
        source=COUNTER_SOURCE,
    ),
    sample.Sample(
        name='test2',
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish'},
        source=COUNTER_SOURCE,
    ),
    sample.Sample(
        name='test2',
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish'},
        source=COUNTER_SOURCE,
    ),
    sample.Sample(
        name='test3',
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish'},
        source=COUNTER_SOURCE,
    ),
]


def get_samples(num=5):
    if len(data_samples) <= num and num > 0:
        data = data_samples[:num]
    else:
        data = data_samples
    return copy.copy(data)
#def get_samples(num=5):
#    if len(data_samples) <= num and num > 0:
#        return data_samples[:num]
#    else:
#        return copy.copy(data_samples)
