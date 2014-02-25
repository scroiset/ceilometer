# Copyright (c) 2013 Bull
#
# Author: Swann Croiset <swann.croiset@bull.net>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import itertools

from ceilometer import agent
from ceilometer import service
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service

LOG = log.getLogger(__name__)


class AgentManager(agent.AgentManager):
    def __init__(self):
        super(AgentManager, self).__init__('satellite')

    def setup_polling_tasks(self):
        polling_tasks = {}
        for pipeline, pollster in itertools.product(
                self.pipeline_manager.pipelines,
                self.pollster_manager.extensions):
            polling_task = polling_tasks.get(pipeline.get_interval())
            if not polling_task:
                polling_task = self.create_polling_task()
                polling_tasks[pipeline.get_interval()] = polling_task
            polling_task.add(pollster, [pipeline])

        return polling_tasks
