# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Bull
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
"""Tests for ceilometer/publisher/http.py
"""

import mock

from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import test
from ceilometer.publisher import http

from ceilometer.tests import publisher as test_publisher

from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class TestHttpPublisher(test.BaseTestCase):

    test_data = test_publisher.get_samples()

    def setUp(self):
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.publisher.metering_secret = 'not-so-secret'
        self.client = mock.MagicMock()
        self.publisher = http.RestPublisher(
            network_utils.urlsplit('http://'))
        super(TestHttpPublisher, self).setUp()

    def test_http_publisher(self):
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.client):
            self.publisher.publish_samples(None, self.test_data)

            self.assertEqual(self.client.samples.create.call_args_list,
                             [(s.as_dict_api(),)
                              for s in self.test_data])

    def test_http_publisher_failure(self):
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.client):
            with mock.patch.object(http.LOG, 'exception') as logger:
                self.client.samples.create.side_effect = Exception
                self.publisher.publish_samples(None, self.test_data)
                self.assertTrue(logger.called)
