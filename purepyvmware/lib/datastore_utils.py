"""Utils for working with Pure Storage Volumes and VMware VMFS/vVol Datastores."""

from pyVmomi import vim

PURE_IDENTIFIER = '24a937'

def compare_identifier(device):
    """ Compare device canonical name to the Pure Storage identifier.

    Args:
        device (string): Device canonical names. (See below for examples)

    Returns:
        pure_devices (list): List of confirmed Pure Storage backed devices.
    """
    # Examples of valid device canonical name formats:
    # naa.624a93703b7b308d98f9425e000113e9
    # eui.003b7b308d98f94224a9375e00018816

    pure_device = None
    if device.startswith('naa'):
        if device[5:11] == PURE_IDENTIFIER:
            pure_device = device
    elif device.startswith('eui'):
        if device[20:26] == PURE_IDENTIFIER:
            pure_device = device
    return pure_device


def fa_host_to_esxi_mapping(esxi_host, fa_hosts, flasharray):
    """Map an ESXi host to a Pure Storage FlashArray host object.

    Args:
        esxi_host (vim.HostSystem): ESXi host to verify against FA host objects.
        fa_hosts (list): List of FlashArray host objects and their properties.
        flasharray (purestorage.FlashArray): Verified or unverified session to
        a Pure Storage FlashArray.

    Returns:
        match (dict): FlashArray host object and properties.

    Raises:
        ValueError: If the ESXi host is unable to be matched to any host object.

    """
    match = None

    hbas = esxi_host.config.storageDevice.hostBusAdapter

    for hba in hbas:
        if isinstance(hba, vim.host.FibreChannelHba):
            # We need to remove the '0x' to properly match against the FA port.
            hba_identifier = hex(hba.portWorldWideName)[2:]
        elif isinstance(hba, vim.host.InternetScsiHba):
            hba_identifier = hba.iScsiName
        else:
            # VMware doesn't have the API to get the NVMe NQN yet but this code
            # will be updated once it is available.
            continue

        if hba_identifier[0].isdigit():
            for host in fa_hosts:
                if match:
                    break
                for wwpn in host['wwn']:
                    if hba_identifier.lower() == wwpn.lower():
                        match = host
                        break
        elif hba_identifier.startswith('iqn'):
            for host in fa_hosts:
                if match:
                    break
                for iqn in host['iqn']:
                    if hba_identifier.lower() == iqn.lower():
                        match = host
                        break
    if not match:
        fa_info = flasharray.get()
        raise ValueError(f'No host object could be found on Pure Storage Flasharray '
                         f'"{fa_info.get("array_name")}" for ESXi host "{esxi_host.name}".')

    return match


def fa_hgroup_to_vc_cluster_mapping(vc_cluster, flasharray):
    """Map a vSphere Cluster to a FlashArray host group object.

    Args:
        vc_cluster (vim.ClusterComputeResource): vSphere cluster to verify
        against the Pure Storage FlashArray host group object.

    Returns:
        host_group (str): Name of the host group associated with the ESXi cluster.

    Raises:
        ValueError: If a matched FlashArray host object is not associated with
        a host group.
    """
    fa_name = flasharray.get().get("array_name")
    host_groups = set()

    fa_hosts = flasharray.list_hosts()
    esxi_hosts = vc_cluster.host

    for esxi in esxi_hosts:
        matched_host = (fa_host_to_esxi_mapping(esxi, fa_hosts, flasharray))

        if matched_host['hgroup']:
            host_groups.add(matched_host['hgroup'])
        else:
            raise ValueError(f'ESXi host "{esxi.name}" maps to FlashArray host object "{matched_host["name"]}"'
                             f' on Pure Storage FlashArray "{fa_name}", but is not associated with any host group'
                             f' object.')

    if not len(host_groups):
        raise ValueError(f'No host group found for vSphere Cluster "{vc_cluster.name}" on FlashArray "{fa_name}".')

    if len(host_groups) > 1:
        raise ValueError(f'vSphere Cluster "{vc_cluster.name}" spans more than one host group on Pure Storage'
                         f' FlashArray "{fa_name}". The recommendation is to have only one host group per cluster')

    # Since host_groups is a set there is no indexing, thus taking the 'next' item in our 1 item set will pull out the
    # host group name needed.
    return next(iter(host_groups))


def get_datastore_identifier(datastore):
    """Revieve the NAA identifiers for the requested datastore object.

    Args:
        ds(vim.Datastore): Datastore object that the NAA is needed for.

    Returns:
        naa_ids(set): Returns a set of NAA(s) associated with the datastore.
    """
    # The variable 'devices' is returned as a set() due to vVols reporting
    # the device ID multiple times. That way VMFS and vVol are consistent.
    ds_type = datastore.summary.type

    if ds_type == 'VMFS':
        extents = datastore.info.vmfs.extent
        devices = {extent.diskName for extent in extents}
    elif ds_type == 'VVOL':
        host_endpoints = datastore.info.vvolDS.hostPE
        # VMware only returns one item to be used thus specifying the first available item.
        devices = {endpoint.protocolEndpoint[0].deviceId for endpoint in host_endpoints}

    return devices


def get_device_path(devices, vol_serial_num):
    """Get ESXi host disk device path associated with an array volume.

    Args:
        devices (list): List of ESXi host disk devices to compare.
        vol_serial_num (string): Vol serial number as represented on array.

    Returns:
        device_path (string): Device path required for datastore creation.
    """
    # Example of volume serial number format (as seen from 'purevol list'):
    # 3B7B308D98F9425E00018819

    # Example of devices format:
    # /vmfs/devices/disks/eui.003b7b308d98f94224a9375e00018816
    # /vmfs/devices/disks/naa.624a93703b7b308d98f9425e000113e9

    potential_device_paths = []
    match = None

    for device in devices:
        # Example output after split: naa.624a93703b7b308d98f9425e000113e9
        dev = device.devicePath.split('/')[4]
        if dev.startswith('naa'):
            if dev[12:] == vol_serial_num:
                match = device.devicePath
                break
        elif dev.startswith('eui'):
            temp_dev = dev[6:].replace(PURE_IDENTIFIER, '')
            if temp_dev == vol_serial_num:
                match = device.devicePath
                break

    return match
