# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/publisher/udp.py
"""

import mock
import msgpack

from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import test
from ceilometer.publisher import udp
from ceilometer.publisher import utils

from ceilometer.tests import publisher as test_publisher

from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class TestUDPPublisher(test.BaseTestCase):
    test_data = test_publisher.get_samples()

    def _make_fake_socket(self, published):
        def _fake_socket_socket(family, type):
            def record_data(msg, dest):
                published.append((msg, dest))

            udp_socket = mock.Mock()
            udp_socket.sendto = record_data
            return udp_socket

        return _fake_socket_socket

    def setUp(self):
        super(TestUDPPublisher, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.publisher.metering_secret = 'not-so-secret'

    def test_published(self):
        self.data_sent = []
        with mock.patch('socket.socket',
                        self._make_fake_socket(self.data_sent)):
            publisher = udp.UDPPublisher(
                network_utils.urlsplit('udp://somehost'))
        publisher.publish_samples(None,
                                  self.test_data)

        self.assertEqual(5, len(self.data_sent))

        sent_counters = []

        for data, dest in self.data_sent:
            counter = msgpack.loads(data)
            sent_counters.append(counter)

            # Check destination
            self.assertEqual(('somehost',
                              self.CONF.collector.udp_port), dest)

        # Check that counters are equal
        self.assertEqual(sorted(
            [utils.meter_message_from_counter(d, "not-so-secret")
             for d in self.test_data]), sorted(sent_counters))

    @staticmethod
    def _raise_ioerror(*args):
        raise IOError

    def _make_broken_socket(self, family, type):
        udp_socket = mock.Mock()
        udp_socket.sendto = self._raise_ioerror
        return udp_socket

    def test_publish_error(self):
        with mock.patch('socket.socket',
                        self._make_broken_socket):
            publisher = udp.UDPPublisher(
                network_utils.urlsplit('udp://localhost'))
        publisher.publish_samples(None,
                                  self.test_data)
