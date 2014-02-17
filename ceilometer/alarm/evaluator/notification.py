# -*- encoding: utf-8 -*-
#
# Copyright © 2014 IBM Corp.
#
# Author: Tong Li <litong01@us.ibm.com>
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

import ast
import fnmatch
import functools
import jsonpath_rw
import operator
import six

from ceilometer.alarm import evaluator
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import strutils
from ceilometer.openstack.common import timeutils


LOG = log.getLogger(__name__)

COMPARATORS = {
    'eq': operator.eq,
    'ne': operator.ne,
}


TYPE_CONVERTERS = {'integer': int,
                   'float': float,
                   'boolean': functools.partial(strutils.bool_from_string,
                                                strict=True),
                   'string': six.text_type,
                   'datetime': timeutils.parse_isotime}


class NotificationEvaluator(evaluator.Evaluator):

    _supported_types = ['integer', 'float', 'string', 'boolean']

    @staticmethod
    def _get_value_as_type(query, forced_type=None):
        """Convert query value to the specified data type.

        :returns: query value converted with the specified data type.
        """
        type = forced_type or query['type']
        find_error = False
        try:
            converted_value = query['value']
            if not type:
                try:
                    converted_value = ast.literal_eval(query['value'])
                except (ValueError, SyntaxError):
                    msg = _('Failed to convert the query value %s'
                            ' automatically') % (query['value'])
                    LOG.debug(msg)
            else:
                if type not in NotificationEvaluator._supported_types:
                    raise TypeError()
                converted_value = TYPE_CONVERTERS[type](query['value'])
        except ValueError:
            msg = _('Failed to convert the value %(value)s'
                    ' to the expected data type %(type)s.') % \
                {'value': query['value'], 'type': type}
            LOG.exception(msg)
            find_error = True
        except TypeError:
            msg = _('The data type %(type)s is not supported. The supported'
                    ' data type list is: %(supported)s') % \
                {'type': type,
                 'supported': NotificationEvaluator._supported_types}
            LOG.exception(msg)
            find_error = True
        except Exception:
            msg = _('Unexpected exception converting %(value)s to'
                    ' the expected data type %(type)s.') % \
                {'value': query['value'], 'type': type}
            LOG.exception(msg)
            find_error = True
        return (converted_value, find_error)

    def _get_alarm_state(self, alarm_id):
        try:
            alarm = self._client.alarms.get(alarm_id)
        except Exception:
            LOG.exception(_('alarm retrieval failed'))
            return None
        return alarm.state

    @staticmethod
    def _reason(alarm, state):
        """Fabricate reason string."""
        return (_('Transition to %(state)s from %(old_state)s due to '
                  'notification matching the defined condition for alarm '
                  ' %(alarm_name)s with type %(noti_type)s and period '
                  '%(period)s') %
                {'state': state, 'old_state': alarm.state,
                 'alarm_name': alarm.name,
                 'noti_type': alarm.rule['notification_type'],
                 'period': alarm.rule['period']})

    @staticmethod
    def _checkquery(query_conditions, notification):
        """get all query conditions and evaluate against each field and
           specified operator, value
        """
        if not query_conditions:
            # if no condition specified, consider the condition is satisfied
            return True
        for condition in query_conditions:
            op = evaluator.COMPARATORS[condition['op']]
            field_expr = jsonpath_rw.parse(condition['field'])
            matching_field = field_expr.find(notification['payload'])
            if matching_field and op:
                """ if one condition fails, entire query condition is
                    considered fail
                """
                value, has_error = \
                    NotificationEvaluator._get_value_as_type(condition)
                if has_error or not op(matching_field[0].value, value):
                    return False
            else:
                return False
        return True

    def _sufficient(self, alarm, notification):
        """This method will do two things:
           1. Check if the defined alarm condition is met. If yes and the
           current alarm state is not ALARM, then transit the alarm state
           to ALARM and set the alarm timestamp to current time. If the
           condition is not met, do nothing.
           2. Check if the elapsed time has passed the alarm defined state
           reset time, if yes and the current state is not OK, then transit
           the alarm state to OK. Otherwise, do nothing.

        """

        now = timeutils.utcnow()
        state = alarm.state
        transit = False
        if timeutils.is_older_than(alarm.state_timestamp,
                                   int(alarm.rule['period'])):
            # the reset_time has elapsed, so set the alarm start to OK.
            if state != evaluator.OK:
                transit = True
                state = evaluator.OK

        op = evaluator.COMPARATORS[alarm.rule['comparison_operator']]
        if op(fnmatch.fnmatch(notification['event_type'],
                              alarm.rule['notification_type']), True):
            #get the project id from the notification and add to the payload
            #for further evaluation, this is to make sure that notification
            #alarms are set per project
            notification['payload']['project_id'] = \
                notification.get('_context_project_id')

            if self._checkquery(alarm.rule['query'], notification):
                if state != evaluator.ALARM:
                    alarm.state_timestamp = now
                    return True, evaluator.ALARM

        return transit, state

    def _transition(self, alarm, state, notification):
        """Transition alarm state to specified state.
        """
        reason = self._reason(alarm, state)
        if alarm.state != state:
            self._refresh(alarm, state, reason, notification)
            alarm.state = state

    def evaluate(self, alarm, notification):
        transit, new_state = self._sufficient(alarm, notification)
        if transit:
            self._transition(alarm, new_state, notification)
