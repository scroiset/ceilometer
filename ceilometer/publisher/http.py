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

from ceilometer import publisher
from ceilometer.openstack.common import log
from ceilometer.openstack.common.gettextutils import _  # noqa

from ceilometerclient import client as ceiloclient
from oslo.config import cfg


LOG = log.getLogger(__name__)


class RestPublisher(publisher.PublisherBase):
    """HTTP Rest publisher (to Ceilometer API)."""

    def __init__(self, parsed_url):
        super(RestPublisher, self).__init__(parsed_url)

        self._cli = None
        self.parsed_url = parsed_url

    @property
    def _client(self):

        if self._cli is None:
            auth_config = cfg.CONF.service_credentials
            creds = dict(
                os_auth_url=auth_config.os_auth_url,
                os_region_name=auth_config.os_region_name,
                os_tenant_name=auth_config.os_tenant_name,
                os_password=auth_config.os_password,
                os_username=auth_config.os_username,
                cacert=auth_config.os_cacert,
                endpoint_type=auth_config.os_endpoint_type,
            )
            if self.parsed_url.netloc:
                creds['ceilometer_url'] = "%s://%s" % (self.parsed_url.scheme,
                                                       self.parsed_url.netloc)

            self._cli = ceiloclient.get_client(2, **creds)

        return self._cli

    def publish_samples(self, context, samples):
        """POST samples to Ceilometer API."""
        try:
            #TODO(scroiset): post samples in batch mode,
            # need to group by name due to the API semantic
            for s in samples:
                sample = s.as_dict_api()
                self._client.samples.create(**sample)
        except Exception:
            LOG.exception(_("Unable to send sample over HTTP"))
