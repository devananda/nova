# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding=utf-8
#
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

""" start add by NTT DOCOMO """

from nova import exception
from nova.openstack.common import log as logging
from nova.openstack.common import importutils
from nova.openstack.common import cfg
from nova import utils
from nova import flags
from nova import context as nova_context
from nova import db
from nova.virt.baremetal import bmdb
from nova.compute import power_state
from nova.virt import driver
from nova.virt.libvirt import imagecache
from nova.virt.phy import baremetal_states
from nova.virt.baremetal import nodes

#TODO: rename to baremetal_xxx
opts = [
    cfg.BoolOpt('baremetal_inject_password',
                default=True,
                help='Whether baremetal compute injects password or not'),
    cfg.StrOpt('baremetal_vif_driver',
               default='nova.virt.phy.vif_driver.BaremetalVIFDriver',
               help='Baremetal VIF driver.'),
    cfg.StrOpt('baremetal_firewall_driver',
                default='nova.virt.firewall.NoopFirewallDriver',
                help='Baremetal firewall driver.'),
    cfg.StrOpt('baremetal_volume_driver',
                default='nova.virt.phy.volume_driver.LibvirtVolumeDriver',
                help='Baremetal volume driver.'),
    cfg.StrOpt('baremetal_cpu_arch',
               default='x86_64',
               help='Baremetal cpu_arch in capability.')
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(opts)

LOG = logging.getLogger(__name__)


def get_connection(_):
    return BareMetalDriver.instance()


class NoSuitableBareMetalNode(exception.NovaException):
    message = _("Failed to find suitable BareMetalNode")


def _get_baremetal_nodes(context):
    nodes = bmdb.bm_node_get_all_by_service_host(context, FLAGS.host)
    return nodes


def _get_baremetal_node_by_instance_id(instance_id):
    ctx = nova_context.get_admin_context()
    for host in _get_baremetal_nodes(ctx):
        if host['instance_id'] == instance_id:
            return host
    return None

    
def _get_baremetal_node_by_instance_name(instance_name):
    context = nova_context.get_admin_context()
    for node in _get_baremetal_nodes(context):
        if not node['instance_id']:
            continue
        try:
            inst = db.instance_get(context, node['instance_id'])
            if inst['name'] == instance_name:
                return node
        except exception.InstanceNotFound:
            continue
    return None

    
def _find_suitable_baremetal_node(context, instance):
    result = None
    for node in _get_baremetal_nodes(context):
        if node['instance_id']:
            continue
        if node['registration_status'] != 'done':
            continue
        if node['cpus'] < instance['vcpus']:
            continue
        if node['memory_mb'] < instance['memory_mb']:
            continue
        if result == None:
            result = node
        else:
            if node['cpus'] < result['cpus']:
                result = node
            elif node['cpus'] == result['cpus'] and node['memory_mb'] < result['memory_mb']:
                result = node
    return result


def _update_baremetal_state(context, node, instance, state):
    instance_id = None
    if instance:
        instance_id = instance['id']
    bmdb.bm_node_update(context, node['id'],
        {'instance_id': instance_id,
        'task_state' : state,
        })


class BareMetalDriver(driver.ComputeDriver):
    """BareMetal hypervisor driver"""

    def __init__(self):
        LOG.info(_("BareMetal driver __init__"))

        super(BareMetalDriver, self).__init__()
        self.baremetal_nodes = nodes.get_baremetal_nodes()
        
        self._vif_driver = importutils.import_object(FLAGS.baremetal_vif_driver)
        self._firewall_driver = importutils.import_object(FLAGS.baremetal_firewall_driver)
        self._volume_driver = importutils.import_object(FLAGS.baremetal_volume_driver)
        self._image_cache_manager = imagecache.ImageCacheManager()

    @classmethod
    def instance(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def init_host(self, host):
        return

    def get_hypervisor_type(self):
        return 'baremetal'

    def get_hypervisor_version(self):
        return 1

    def list_instances(self):
        l = []
        ctx = nova_context.get_admin_context()
        for node in _get_baremetal_nodes(ctx):
            if node['instance_id']:
                inst = db.instance_get(ctx, node['instance_id'])
                if inst:
                    l.append(inst['name'])
        return l

    def list_instances_detail(self):
        l = []
        ctx = nova_context.get_admin_context()
        for node in _get_baremetal_nodes(ctx):
            if node['instance_id']:
                pm = nodes.get_power_manager(node)
                ps = power_state.SHUTDOWN
                if pm.is_power_on():
                    ps = power_state.RUNNING
                inst = db.instance_get(ctx, node['instance_id'])
                if inst:
                    ii = driver.InstanceInfo(inst['name'], ps)
                    l.append(ii)
        return l
 
    def spawn(self, context, instance, image_meta,
              network_info=None, block_device_info=None):
        LOG.debug("spawn:")
        LOG.debug("instance=%s", instance.__dict__)
        LOG.debug("image_meta=%s", image_meta)
        LOG.debug("network_info=%s", network_info)
        LOG.debug("block_device_info=%s", block_device_info)
       
        node = _find_suitable_baremetal_node(context, instance)

        if not node:
            LOG.info("no suitable baremetal node found")
            raise NoSuitableBareMetalNode()
        
        _update_baremetal_state(context, node, instance, baremetal_states.BUILDING)
                
        var = self.baremetal_nodes.define_vars(instance, network_info, block_device_info)

        # clear previous vif info
        pifs = bmdb.bm_interface_get_all_by_bm_node_id(context, node['id'])
        for pif in pifs:
            if pif['vif_uuid']:
                bmdb.bm_interface_set_vif_uuid(context, pif['id'], None)

        self.plug_vifs(instance, network_info)

        self._firewall_driver.setup_basic_filtering(instance, network_info)
        self._firewall_driver.prepare_instance_filter(instance, network_info)

        self.baremetal_nodes.create_image(var, context, image_meta, node, instance)
        self.baremetal_nodes.activate_bootloader(var, context, node, instance)
        #TODO attach volumes
        pm = nodes.get_power_manager(node)
        state = pm.activate_node()

        _update_baremetal_state(context, node, instance, state)
        
        self.baremetal_nodes.activate_node(var, context, node, instance)
        self._firewall_driver.apply_instance_filter(instance, network_info)
        pm.start_console(node['terminal_port'], node['id'])

    def reboot(self, instance, network_info):
        node = _get_baremetal_node_by_instance_id(instance['id'])
        
        if not node:
            raise exception.InstanceNotFound(instance_id=instance['id'])

        ctx = nova_context.get_admin_context()
        pm = nodes.get_power_manager(node)
        state = pm.reboot_node()
        _update_baremetal_state(ctx, node, instance, state)

    def destroy(self, instance, network_info, block_device_info=None):
        LOG.debug("destroy: instance=%s", instance.__dict__)
        LOG.debug("destroy: network_info=%s", network_info)
        LOG.debug("destroy: block_device_info=%s", block_device_info)
        ctx = nova_context.get_admin_context()

        node = _get_baremetal_node_by_instance_id(instance['id'])
        if not node:
            LOG.warning("Instance:id='%s' not found" % instance['id'])
            return
 
        var = self.baremetal_nodes.define_vars(instance, network_info, block_device_info)

        self.baremetal_nodes.activate_node(var, ctx, node, instance)

        pm = nodes.get_power_manager(node)

        ## stop console
        pm.stop_console(node['id'])
        
        ## power off the node
        state = pm.deactivate_node()

        ## cleanup volumes
        # NOTE(vish): we disconnect from volumes regardless
        block_device_mapping = driver.block_device_info_get_mapping(
            block_device_info)
        for vol in block_device_mapping:
            connection_info = vol['connection_info']
            mountpoint = vol['mount_device']
            self.detach_volume(connection_info, instance['name'], mountpoint)

        self.baremetal_nodes.deactivate_bootloader(var, ctx, node, instance)

        self.baremetal_nodes.destroy_images(var, ctx, node, instance)

        # stop firewall
        self._firewall_driver.unfilter_instance(instance,
                                                network_info=network_info)

        self._unplug_vifs(instance, network_info)
 
        _update_baremetal_state(ctx, node, None, state)

    def get_volume_connector(self, instance):
        return self._volume_driver.get_volume_connector(instance)

    def attach_volume(self, connection_info, instance_name, mountpoint):
        return self._volume_driver.attach_volume(connection_info, instance_name, mountpoint)

    @exception.wrap_exception()
    def detach_volume(self, connection_info, instance_name, mountpoint):
        return self._volume_driver.detach_volume(connection_info, instance_name, mountpoint)
    
    def get_info(self, instance):
        node = _get_baremetal_node_by_instance_id(instance['id'])
        if not node:
            raise exception.InstanceNotFound(instance_id=instance['id'])
        pm = nodes.get_power_manager(node)
        ps = power_state.SHUTDOWN
        if pm.is_power_on():
            ps = power_state.RUNNING
        LOG.debug("power_state=%s", ps)
        return {'state': ps,
                'max_mem': node['memory_mb'],
                'mem': node['memory_mb'],
                'num_cpu': node['cpus'],
                'cpu_time': 0}

    def refresh_security_group_rules(self, security_group_id):
        self._firewall_driver.refresh_security_group_rules(security_group_id)
        return True

    def refresh_security_group_members(self, security_group_id):
        self._firewall_driver.refresh_security_group_members(security_group_id)
        return True

    def refresh_provider_fw_rules(self):
        self._firewall_driver.refresh_provider_fw_rules()
    
    def _sum_baremetal_resources(self, ctxt):
        vcpus = 0
        vcpus_used = 0
        memory_mb = 0
        memory_mb_used = 0
        local_gb = 0
        local_gb_used = 0        
        for node in _get_baremetal_nodes(ctxt):
            if node['registration_status'] != 'done':
                continue
            vcpus += node['cpus']
            memory_mb += node['memory_mb']
            local_gb += node['local_gb']

        dic = {'vcpus': vcpus,
               'memory_mb': memory_mb,
               'local_gb': local_gb,
               'vcpus_used': vcpus_used,
               'memory_mb_used': memory_mb_used,
               'local_gb_used': local_gb_used,
               }
        return dic

    def _max_baremetal_resouces(self, ctxt):
        max_cpus = 0
        max_memory_mb = 0
        max_local_gb = 0
        
        for node in _get_baremetal_nodes(ctxt):
            if node['registration_status'] != 'done':
                continue
            if node['instance_id']:
                continue
            
            #put prioirty to memory size. You can use CPU and HDD, if you change the following line.
            if max_memory_mb > node['memory_mb']:
                max_memory_mb = node['momory_mb']
                max_cpus = node['cpus']
                max_local_gb = node['max_local_gb']

        dic = {'vcpus': max_cpus,
               'memory_mb': max_memory_mb,
               'local_gb': max_local_gb,
               'vcpus_used': 0,
               'memory_mb_used': 0,
               'local_gb_used': 0,
               }
        return dic

    def update_available_resource(self, ctxt, host):
        """Updates compute manager resource info on ComputeNode table.

        This method is called when nova-coompute launches, and
        whenever admin executes "nova-manage service update_resource".

        :param ctxt: security context
        :param host: hostname that compute manager is currently running

        """

        dic = self._max_baremetal_resouces(ctxt)
        #dic = self._sum_baremetal_resources(ctxt)
        dic['hypervisor_type'] = self.get_hypervisor_type()
        dic['hypervisor_version'] = self.get_hypervisor_version()
        dic['cpu_info'] = 'baremetal cpu'
        
        try:
            service_ref = db.service_get_all_compute_by_host(ctxt, host)[0]
        except exception.NotFound:
            raise exception.ComputeServiceUnavailable(host=host)

        dic['service_id'] = service_ref['id']

        compute_node_ref = service_ref['compute_node']
        if not compute_node_ref:
            LOG.info(_('Compute_service record created for %s ') % host)
            db.compute_node_create(ctxt, dic)
        else:
            LOG.info(_('Compute_service record updated for %s ') % host)
            db.compute_node_update(ctxt, compute_node_ref[0]['id'], dic)

    def ensure_filtering_rules_for_instance(self, instance_ref, network_info):
        self._firewall_driver.setup_basic_filtering(instance_ref, network_info)
        self._firewall_driver.prepare_instance_filter(instance_ref, network_info)

    def unfilter_instance(self, instance_ref, network_info):
        self._firewall_driver.unfilter_instance(instance_ref,
                                                network_info=network_info)

    def test_remove_vm(self, instance_name):
        """ Removes the named VM, as if it crashed. For testing"""
        LOG.info(_("test_remove_vm: instance_name=%s") % (instance_name))
        raise exception.InstanceNotFound(instance_id=instance_name)

    def _get_host_stats(self):
        dic = self._max_baremetal_resouces(nova_context.get_admin_context())
        memory_total = dic['memory_mb'] * 1024 * 1024
        memory_free = (dic['memory_mb'] - dic['memory_mb_used']) * 1024 * 1024
        disk_total = dic['local_gb'] * 1024 * 1024 * 1024
        disk_used = dic['local_gb_used'] * 1024 * 1024 * 1024

        # borrow ISI's instance_type_extra_specs code
        extra_specs = {}
        extra_specs["hypervisor_type"] = self.get_hypervisor_type()
        extra_specs["baremetal_driver"] = FLAGS.baremetal_driver
        for pair in FLAGS.instance_type_extra_specs:
            keyval = pair.split(':', 1)
            keyval[0] = keyval[0].strip()
            keyval[1] = keyval[1].strip()
            extra_specs[keyval[0]] = keyval[1]

        return {
          'host_name-description': 'baremetal ' + FLAGS.host,
          'host_hostname': FLAGS.host,
          'host_memory_total': memory_total,
          'host_memory_overhead': 0,
          'host_memory_free': memory_free,
          'host_memory_free_computed': memory_free,
          'host_other_config': {},
#          'host_ip_address': '192.168.1.109',
#          'host_cpu_info': {},
          'disk_available': disk_total - disk_used,
          'disk_total': disk_total,
          'disk_used': disk_used,
#          'host_uuid': 'cedb9b39-9388-41df-8891-c5c9a0c0fe5f',
          'host_name_label': FLAGS.host,
          'type': 'baremetal',
          'instance_type_extra_specs': extra_specs,
          }

    def update_host_status(self):
        LOG.info(_("update_host_status:"))
        return self._get_host_stats()

    def get_host_stats(self, refresh=False):
        LOG.info(_("get_host_stats: refresh=%s") % (refresh))
        return self._get_host_stats()

    def plug_vifs(self, instance, network_info):
        """Plugin VIFs into networks."""
        LOG.debug("plug_vifs: %s", locals())
        for (network, mapping) in network_info:
            self._vif_driver.plug(instance, network, mapping)

    def _unplug_vifs(self, instance, network_info):
        LOG.debug("_unplug_vifs: %s", locals())
        for (network, mapping) in network_info:
            self._vif_driver.unplug(instance, network, mapping)

    def manage_image_cache(self, context):
        """Manage the local cache of images."""
        self._image_cache_manager.verify_base_images(context)
    
    def get_console_output(self, instance):
        node = _get_baremetal_node_by_instance_id(instance['id'])
        return self.baremetal_nodes.get_console_output(node, instance)


""" end add by NTT DOCOMO """