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

import eventlet
import socket
from lxml import etree

from oslo.config import cfg

from ceilometer import plugin
from ceilometer import sample
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import timeutils


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('default_resource_id',
               default='instance',
               help='Value to use for resource_id of all'
                    'published samples.'
                    'Not used if metric_to_resource_id is set'),
    cfg.StrOpt('metric_to_resource_id',
               default='',
               help='Use a metric value to set resource_id of '
                    'published samples.'),
    cfg.StrOpt('add_metrics_to_metadata',
               default='os_name,os_release,machine_type',
               help='Use metrics to populate all pusblished samples. '
               '(note: "ip" and "hostname" reported by Ganglia are added '
               'to metadata as well as "ganglia_source")'),
]

cfg.CONF.register_opts(OPTS, group='ganglia')


class UnableToFetchMetric(Exception):
    """Thrown when fetching metric failed."""
    pass


class Metric(object):
    def __init__(self, elt, cluster, host):
        self.element = elt
        self.cluster = cluster
        self.host = host
        self._extra = {}
        self.resource_id = None

    @staticmethod
    def get_type(_type):
        # not supported:  string, timestamp
        map_type = {'float': 'gauge',
                    'double': 'gauge',
                    'int8': 'cumulative',
                    'int16': 'cumulative',
                    'int32': 'cumulative',
                    'uint8': 'cumulative',
                    'uint16': 'cumulative',
                    'uint32': 'cumulative',
                    }
        try:
            return map_type[_type]
        except KeyError:
            return None

    def is_valid(self):
        if self.type is None:
            return False
        if self.resource_id is None:
            if not cfg.CONF.ganglia.default_resource_id:
                return False
            self.resource_id = cfg.CONF.ganglia.default_resource_id

        return True

    @property
    def value(self):
        value = self.element.get('VAL')
        if self.type:
            return float(value)
        else:
            return value

    @property
    def type(self):
        t = self.element.get('TYPE')
        return Metric.get_type(t)

    @property
    def name(self):
        return self.element.get('NAME')

    @property
    def unit(self):
        return self.element.get('UNITS')

    @property
    def timestamp(self):
        reported = self.host.get('REPORTED')
        timestamp = timeutils.iso8601_from_timestamp(float(reported))
        return timestamp

    @property
    def ip_source(self):
        return self.host.get('IP')

    @property
    def cluster_name(self):
        return self.cluster.get('NAME')

    @property
    def hostname(self):
        return self.host.get('NAME')

    @property
    def extra_data(self):
        if self._extra:
            return self._extra

        d = {}
        for e in self.element.findall('EXTRA_DATA/EXTRA_ELEMENT'):
            d[e.get('NAME')] = e.get('VAL')
        self._extra = d

        return self._extra

    def add_extradata(self, key, value):
        self._extra.update({key: value})

    def to_sample(self):
        extra = self.extra_data

        extra.update({'ip': self.ip_source,
                      'hostname': self.hostname
                      })

        return sample.Sample(
            name=self.name,
            type=self.type,
            unit=self.unit,
            volume=self.value,
            user_id=None,
            project_id=None,
            resource_id=self.resource_id,
            source=self.resource_id,
            timestamp=self.timestamp,
            resource_metadata=extra
        )

    def __str__(self):
        return self.name

    def __unicode__(self):
        tpl = u"""
        metric '%s = %s'
        resource_id = %s / type:%s / unit:%s
        extra: <%s>
        """
        return tpl % (self.name, str(self.value),
                      self.resource_id, self.type,
                      self.unit, self._extra)


class GangliaPollster(plugin.PollsterBase):

    def __init__(self, *args, **kargs):
        self.resources = []
        self.extra_metrics = cfg.CONF.ganglia.\
            add_metrics_to_metadata.split(',')
        super(GangliaPollster, self).__init__(*args, **kargs)

    @staticmethod
    def _resources(resources):
        return [network_utils.urlsplit(host) for host in resources]

    def get_samples(self, manager, cache, resources=[]):

        #import pdb
        #pdb.set_trace()
        pipelines = manager.pipeline_manager.pipelines
        wanted = set([m for p in pipelines for m in p.source.meters])
        LOG.debug('WANTED metrics : %s' % wanted)
        self.wanted_meter_names = wanted
        self.resources = self._resources(resources)
        LOG.debug(self.resources)
        self.verify_resources(self.resources)

        for resource in self.resources:
            LOG.debug('get_samples rsrc:%s' % (resource.netloc))
            try:
                metrics = self.fetch_metrics(resource)
            except UnableToFetchMetric:
                LOG.debug('No endpoint for Ganglia pollster')
            else:
                for metric in metrics:
                    if metric.is_valid():
                        #LOG.debug(metric)
                        yield metric.to_sample()

    @staticmethod
    def verify_resources(rsrcs):
        for r in rsrcs:
            if not r.port or not r.netloc:
                raise RuntimeError("bad resource")
            LOG.debug('Use resource as Ganglia url: %s://%s' %
                      (r.scheme, r.netloc))
        return True

    def fetch_metrics(self, resource):
        xml = self.fetch_xml(resource)
        metrics, rsrcid_metrics, extra_info_metrics = [], {}, []
        clusters = xml.findall("GRID/CLUSTER")
        if not clusters:
            # if metrics are fetched from gmond
            clusters = xml.findall("CLUSTER")

        totalmetrics = []
        for cluster in clusters:
            for host in cluster.findall("HOST"):
                for metric in host.findall('METRIC'):
                    m = Metric(metric, cluster, host)
                    if m.name == cfg.CONF.ganglia.metric_to_resource_id:
                        key = '%s%s' % (m.cluster_name, m.hostname)
                        rsrcid_metrics[key] = m
                    if m.name in self.extra_metrics:
                        extra_info_metrics.append(m)
                    if m.name in self.wanted_meter_names:
                        m.add_extradata('ganglia_source', resource.netloc)
                        metrics.append(m)
                    #XXX try regexp here
                    totalmetrics.append(m.name)

        if len(metrics) == 0:
            LOG.info('No metric fetched from Ganglia %s' % resource.netloc)
        else:
            LOG.info('%d metrics fetched from '
                     'Ganglia %s (total %d)' % (len(metrics),
                                                resource.netloc,
                                                len(totalmetrics)))
            allm = [m.name for m in metrics]
            LOG.debug('Metrics found:  %s' %
                      (" ".join(allm)))

            self._sweeten(metrics, extra_info_metrics, rsrcid_metrics)

        return metrics

    @staticmethod
    def fetch_xml(resource):
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        row_xml = ''
        try:
            with eventlet.Timeout(1, False):
                tcp.connect((resource.hostname, resource.port))
                while True:
                    buff = tcp.recv(128 * 1024)
                    if not buff:
                        break
                    row_xml += buff

                return etree.XML(row_xml)
        except Exception as e:
           # LOG.exception(e)
            raise UnableToFetchMetric(e)

        if not row_xml:
            raise UnableToFetchMetric('Empty')

    @staticmethod
    def _sweeten(metrics, extra_metrics, rsrcid_metrics):
        for extra in extra_metrics:
            for m in metrics:
                if not m.resource_id:
                    try:
                        k = '%s%s' % (m.cluster_name, m.hostname)
                        m.resource_id = str(rsrcid_metrics[k].value)
                    except KeyError:
                        pass

                if m.ip_source == extra.ip_source and \
                   m.hostname == extra.hostname and \
                   m.cluster_name == extra.cluster_name:
                    m.add_extradata(extra.name, extra.value)
