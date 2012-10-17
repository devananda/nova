============================
nova-baremetal-deploy-helper
============================

------------------------------------------------------------------
Writes images to a bare-metal node and switch it to instance-mode
------------------------------------------------------------------

:Author: openstack@lists.launchpad.net
:Date:   2012-10-17
:Copyright: OpenStack LLC
:Version: 2013.1
:Manual section: 1
:Manual group: cloud computing

SYNOPSIS
========

  nova-baremetal-deploy-helper

DESCRIPTION
===========

Writes images to bare-metal nodes in their 1st boot via iSCSI. Then switches
them to instance-mode.

OPTIONS
=======

 **General options**

FILES
========

* /etc/nova/nova.conf
* /etc/nova/rootwrap.conf
* /etc/nova/rootwrap.d/

SEE ALSO
========

* `OpenStack Nova <http://nova.openstack.org>`__

BUGS
====

* Nova is sourced in Launchpad so you can view current bugs at `OpenStack Nova <http://nova.openstack.org>`__
