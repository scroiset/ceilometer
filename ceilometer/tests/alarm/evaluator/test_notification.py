# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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
"""Tests for ceilometer/alarm/threshold_evaluation.py
"""
import copy
import logging
import mock
import StringIO
import uuid

from ceilometer.alarm.evaluator import notification
from ceilometer.openstack.common import timeutils
from ceilometer.storage import models
from ceilometer.tests.alarm.evaluator import base
from ceilometerclient.v2 import alarms


class TestEvaluate(base.TestEvaluatorBase):
    EVALUATOR = notification.NotificationEvaluator

    message = {'event_type': 'autoscale.vm.addOne',
               '_context_project_id': 'test_project_id',
               'payload': {'command_id': 'b057c8ea',
                           'aaa': 10,
                           'bbb': {'cc': 30}}}

    def setUp(self):
        super(TestEvaluate, self).setUp()
        self.output = StringIO.StringIO()
        self.str_handler = logging.StreamHandler(self.output)
        notification.LOG.logger.addHandler(self.str_handler)

    def tearDown(self):
        super(TestEvaluate, self).tearDown()
        notification.LOG.logger.removeHandler(self.str_handler)
        self.output.close()

    def prepare_alarms(self):
        now = timeutils.utcnow()
        self.alarms = [models.Alarm(name='eq-notification-alarm',
                                    description='the notification alarm',
                                    type='notification',
                                    enabled=True,
                                    user_id='foobar',
                                    project_id='test_project_id',
                                    alarm_id=str(uuid.uuid4()),
                                    state='insufficient data',
                                    state_timestamp=now,
                                    timestamp=None,
                                    insufficient_data_actions=[],
                                    ok_actions=[],
                                    alarm_actions=[],
                                    repeat_actions=False,
                                    rule=dict(
                                        notification_type='autoscale.vm.add*',
                                        comparison_operator='eq',
                                        period=100,
                                        query=[{'field': 'aaa', 'type': '',
                                                'value': '10', 'op': 'eq'},
                                               {'field': 'bbb.cc',
                                                'type': 'integer',
                                                'value': '34',
                                                'op': 'le'},
                                               {'field': 'project_id',
                                                'op': 'eq', 'type': '',
                                                'value': 'test_project_id'}])
                                    ),
                       ]

    @staticmethod
    def _get_alarm(state):
        return alarms.Alarm(None, {'state': state})

    def _evaluate_alarm(self, alarm, notification):
        self.evaluator.evaluate(alarm, notification)

    def test_alarm_eq_with_match_notification(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the first alarm for the test
            alarm = self.alarms[0]
            reason = self.evaluator._reason(alarm, 'alarm')
            self._evaluate_alarm(alarm, self.message)

            expected = [mock.call(alarm.alarm_id, state='alarm')]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)

            expected = [mock.call(alarm, 'insufficient data', reason,
                                  self.message)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_alarm_eq_with_missing_attribute(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the first alarm for the test
            alarm = self.alarms[0]
            alarm.rule['query'].append({'field': 'ddd', 'type': '',
                                        'value': '20', 'op': 'eq'})
            self._evaluate_alarm(alarm, self.message)

            # the set_state should not have been called
            self.assertEqual(self.api_client.alarms.set_state.called, False)

    def test_alarm_eq_with_invalid_data_type(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the first alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['query'][0]['type'] = 'bad_type'
            self._evaluate_alarm(alarm, self.message)

            # the set_state should not have been called
            self.assertEqual(self.api_client.alarms.set_state.called, False)
            # the not supported data type should have been logged.
            self.assertTrue('The data type bad_type is not supported.' in
                            self.output.getvalue())

    def test_alarm_eq_with_mismatch_notification(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('insufficient data'),
            ]
            # use the first alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['query'] = [{'field': 'aaa', 'type': '',
                                    'value': '10', 'op': 'eq'},
                                   {'field': 'bbb.cc',
                                    'type': 'integer',
                                    'value': '20', 'op': 'le'},
                                   {'field': 'project_id',
                                    'op': 'eq', 'type': '',
                                    'value': 'test_project_id'}]

            self._evaluate_alarm(alarm, self.message)

            # the set_state should not have been called
            self.assertEqual(self.api_client.alarms.set_state.called, False)

    def test_alarm_eq_with_mismatch_notification_reset_state(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('insufficient data'),
                self._get_alarm('insufficient data'),
            ]
            # use the first alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['notification_type'] = 'autoscale.vm.del*'
            alarm.rule['comparison_operator'] = 'ne'
            alarm.rule['period'] = 0
            alarm.rule['query'] = [{'field': 'aaa', 'type': '',
                                    'value': '10', 'op': 'eq'},
                                   {'field': 'bbb.cc',
                                    'type': 'integer',
                                    'value': '20', 'op': 'le'},
                                   {'field': 'project_id',
                                    'op': 'eq', 'type': '',
                                    'value': 'test_project_id'}]
            reason = self.evaluator._reason(alarm, 'ok')

            self._evaluate_alarm(alarm, self.message)

            # the set_state should have been called
            self.assertEqual(self.api_client.alarms.set_state.called, True)

            expected = [mock.call(alarm, 'insufficient data',
                                  reason, self.message)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_alarm_ne_with_match_notification(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the second alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['notification_type'] = 'autoscale.vm.del*'
            alarm.rule['comparison_operator'] = 'ne'
            reason = self.evaluator._reason(alarm, 'alarm')
            self._evaluate_alarm(alarm, self.message)

            expected = [mock.call(alarm.alarm_id, state='alarm')]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)

            expected = [mock.call(alarm, 'insufficient data', reason,
                                  self.message)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_alarm_ne_with_mismatch_notification(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the second alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['notification_type'] = 'autoscale.vm.del*'
            alarm.rule['comparison_operator'] = 'ne'
            alarm.rule['query'] = [{'field': 'aaa', 'type': '',
                                    'value': '10', 'op': 'eq'},
                                   {'field': 'bbb.cc',
                                    'type': 'integer',
                                    'value': '20', 'op': 'le'},
                                   {'field': 'project_id',
                                    'op': 'eq', 'type': '',
                                    'value': 'test_project_id'}]
            self._evaluate_alarm(alarm, self.message)

            # the set_state should not have been called
            self.assertEqual(self.api_client.alarms.set_state.called, False)

    def test_alarm_ne_with_mismatch_project_id(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
            ]
            # use the second alarm for the test
            alarm = copy.deepcopy(self.alarms[0])
            alarm.rule['notification_type'] = 'autoscale.vm.del*'
            alarm.rule['comparison_operator'] = 'ne'
            alarm.rule['query'] = [{'field': 'aaa', 'type': '',
                                    'value': '10', 'op': 'eq'},
                                   {'field': 'bbb.cc',
                                    'type': 'integer',
                                    'value': '50', 'op': 'le'},
                                   {'field': 'project_id',
                                    'op': 'eq', 'type': '',
                                    'value': 'other_test_project_id'}]
            self._evaluate_alarm(alarm, self.message)

            # the set_state should not have been called
            self.assertEqual(self.api_client.alarms.set_state.called, False)
