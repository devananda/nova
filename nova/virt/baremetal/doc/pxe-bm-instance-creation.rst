PXE Baremetal Instance Creation
======

1) A user requests a baremetal instance.

::

  euca-run-instances -t baremetal.small --kernel aki-AAA --ramdisk ari-BBB ami-CCC

2) nova-scheduler selects a baremetal nova-compute.

::

  nova-compute with a special nova.conf
  compute_driver = nova.virt.baremetal.driver.BareMetalDriver
  baremetal_deploy_kernel = xxxxxxxxxx
  baremetal_deploy_ramdisk = yyyyyyyy

3) The nova-compute selects a baremetal host from its pool based on hardware resources and the instance type (# of cpus, memory, HDDs).

4) kernel and ramdisk for the deployment, and the user specified kernel and ramdisk are put to TFTP server.  PXE are configured for the baremetal host.

5) The baremetal nova-compute powers on the baremetal host thorough IPMI.

6) The host uses the deployment kernel and ramdisk, and the baremetal nova-copute writes AMI to the host's local disk via iSCSI.

7) The host is rebooted.

8) Next, the host is booted up by the user specified kernel, ramdisk and its local disk.

9) Done.
