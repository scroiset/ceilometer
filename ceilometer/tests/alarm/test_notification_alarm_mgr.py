# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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
"""Tests for ceilometer.alarm.service.SingletonAlarmService.
"""
import mock

from stevedore import extension

from ceilometer.alarm import service
from ceilometer.openstack.common import test


class TestNotificationAlarmManager(test.BaseTestCase):
    def setUp(self):
        super(TestNotificationAlarmManager, self).setUp()
        self.eval = mock.Mock()
        self.evaluators = extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'notification',
                    None,
                    None,
                    self.eval),
            ]
        )
        self.api_client = mock.MagicMock()
        self.srv = service.NotificationAlarmManager()
        self.srv.evaluators = self.evaluators
        self.message = {'event_type': 'autoscale.vm.addOne',
                        'payload': {'command_id': 'b057c8ea',
                                    'aaa': 10,
                                    'bbb': {'cc': 30}}}

    def test_evaluate_assigned_alarms(self):
        alarm = mock.Mock(type='notification')
        self.api_client.alarms.list.return_value = [alarm]
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.srv._evaluate_assigned_alarms(self.message)
            self.eval.evaluate.assert_called_once_with(alarm, self.message)

    def test_assigned_alarms(self):
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold'),
            mock.Mock(type='notification')
        ]

        self.api_client.alarms.list.return_value = alarms
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = alarms
            actual = self.srv._assigned_alarms()
            expected = [alarms[2]]
            self.assertEqual(actual, expected)
