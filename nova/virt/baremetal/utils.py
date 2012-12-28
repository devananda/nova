# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 NTT DOCOMO, INC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os

from nova.openstack.common import log as logging
from nova.virt.disk import api as disk_api
from nova.virt.libvirt import utils as libvirt_utils

LOG = logging.getLogger(__name__)


def cache_image(context, target, image_id, user_id, project_id):
    if not os.path.exists(target):
        libvirt_utils.fetch_image(context, target, image_id,
                                  user_id, project_id)


def inject_into_image(image, key, net, metadata, admin_password,
        files, partition, use_cow=False):
    try:
        disk_api.inject_data(locals())
    except Exception as e:
        LOG.warn(_("Failed to inject data into image %(image)s. "
                   "Error: %(e)s") % locals())


def unlink_without_raise(path):
    try:
        os.unlink(path)
    except OSError:
        LOG.exception(_("Failed to unlink %s") % path)


def write_to_file(path, contents):
    with open(path, 'w') as f:
        f.write(contents)


def create_link_without_raise(source, link):
    try:
        os.link(source, link)
    except OSError:
        LOG.exception(_("Failed to create symlink from %(source)s to %(link)s")
                % locals())
