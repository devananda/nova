=====================
nova-baremetal-manage
=====================

------------------------------------------------------
Manage bare-metal DB in OpenStack Nova
------------------------------------------------------

:Author: openstack@lists.launchpad.net
:Date:   2012-10-17
:Copyright: OpenStack LLC
:Version: 2013.1
:Manual section: 1
:Manual group: cloud computing

SYNOPSIS
========

  nova-baremetal-manage <category> <action> [<args>]

DESCRIPTION
===========

nova-baremetal-manage manages bare-metal DB schema, and lists/creates/destroys records in bare-metal DB.

OPTIONS
=======

The standard pattern for executing a nova-baremetal-manage command is:
``nova-baremetal-manage <category> <command> [<args>]``

Run without arguments to see a list of available command categories:
``nova-baremetal-manage``

Categories are db, node, interface and pxe_ip. Detailed descriptions are below.

You can also run with a category argument such as "node" to see a list of all commands in that category:
``nova-baremetal-manage node``

These sections describe the available categories and arguments for nova-baremetal-manage.

Bare-Metal DB
~~~~~~~~~~~~~

``nova-baremetal-manage db version``

    Print the current database version.

``nova-baremetal-manage db sync``

    Sync the database up to the most recent version. This is the standard way to create the db as well.

Node
~~~~

``nova-baremetal-manage node create <args>``

    Creates a bare-metal node. Takes parameters below.
     * --host=<host>    Compute service's hostname
     * --cpus=<cpus>    CPU count
     * --memory_mb=<memory_mb>    Memory size in MB
     * --local_gb=<local_gb>    Disk size in GB
     * --pm_address=<pm_address>    Power manager address
     * --pm_user=<pm_user>    Power manager username
     * --pm_password=<pm_password>    Power manager password
     * --terminal_port=<terminal_port>    TCP port for terminal access
     * --prov_mac_address=<prov_mac_address>    MAC address of provisioning interface in the form of xx:xx:xx:xx:xx:xx
     * --prov_vlan_id=<prov_vlan_id>    VLAN ID used to isolate PXE network(optional)

``nova-baremetal-manage node create --id=<ID>``

    Deletes a bare-metal node.

``nova-baremetal-manage node list``

    Displays a list of all bare-metal nodes.

Network Interface
~~~~~~~~~~~~~~~~~

``nova-baremetal-manage interface create <args>``

    Creates a bare-metal node. Takes parameters below.
     * --node_id=<node_id>   ID of bare-metal node
     * --mac_address=<mac_address>    MAC address in the form of xx:xx:xx:xx:xx:xx
     * --datapath_id=<datapath_id>    OpenFlow datapath ID (put 0 if not use OpenFlow)
     * --port_no=<port_no>   OpenFlow port number (put 0 if not use OpenFlow)

``nova-baremetal-manage interface delete --id=<ID>``

    Deletes a network interface.

``nova-baremetal-manage interface list [--node=<node ID>]``

    Displays a list of all network interfaces. Optionally filters by node.

PXE IP Address
~~~~~~~~~~~~~~

``nova-baremetal-manage pxe_ip create --cidr=<Network CIDR>``

    Creates IPs by range

``nova-baremetal-manage pxe_ip delete --id=<ID>|--cidr=<Network CIDR>``

    Deletes IPs by ID or range.

``nova-baremetal-manage pxe_ip list``

    Displays a list of all IPs.


FILES
========

/etc/nova/nova.conf: get location of bare-metal DB

SEE ALSO
========

* `OpenStack Nova <http://nova.openstack.org>`__

BUGS
====

* Nova is sourced in Launchpad so you can view current bugs at `OpenStack Nova <http://nova.openstack.org>`__



