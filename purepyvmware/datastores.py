"""For general maintenance of VMware datastores that are backed by Pure Storage FlashArrays."""

import time

from purepyvmware.lib import datastore_utils
from pyVmomi import vim
from pyVmomi import sms


class Datastores(object):
    """Maintenance of Pure Storage based datastores and associated array volumes."""

    def __init__(self, vsphere_content, flasharray):
        """Setting up vSphere and FlashArray environment for use.

        Args:
            vsphere_content (vim.ServiceInstanceContent): All available content within the vSphere env.
            flasharray (purestorage.FlashArray): Existing session to FlashArray.
        """
        self.flasharray = flasharray
        self.vsphere_content = vsphere_content

    def create_compute_container_view(self):
        """Create compute container view for an inventory of managed object references.

        Returns:
            resources (vim.view.ContainerView): Object view of compute resources.
        """
        compute_container = self.vsphere_content.viewManager.CreateContainerView(
            container=self.vsphere_content.rootFolder,
            type=[vim.ComputeResource],
            recursive=True)
        compute_resources = compute_container.view
        # Container is no longer required once the most up-to-date information is available for use. This does not
        # destroy any information within vCenter. Only the object we created to view the contents of vCenter.
        compute_container.Destroy()

        return compute_resources

    def create_datastore_container_view(self):
        """Create datastore container view for an inventory of managed object references.

        Returns:
            datastores (vim.view.ContainerView): Object view of datastore resources.
        """
        datastore_container = self.vsphere_content.viewManager.CreateContainerView(
            container=self.vsphere_content.rootFolder,
            type=[vim.Datastore],
            recursive=True)
        datastores = datastore_container.view
        # Container is no longer required once the most up-to-date information is available for use. This does not
        # destroy any information within vCenter. Only the object we created to view the contents of vCenter.
        datastore_container.Destroy()

        return datastores

    def get_all_pure_datastores(self):
        """Retrieve all datastores backed by Pure Storage FlashArray volumes.

        Returns:
            pure_datastores (list): List of vim.Datastore objects associated with Pure Storage FlashArray(s).
        """
        pure_datastores = []
        all_datastores = self.create_datastore_container_view()

        for datastore in all_datastores:
            devices = datastore_utils.get_datastore_identifier(datastore)
            for device in devices:
                dev_match = datastore_utils.compare_identifier(device)
                if dev_match:
                    pure_datastores.append(datastore)

        return pure_datastores

    @staticmethod
    def rescan_esxi_storage(esxi_hosts):
        """Rescan all storage HBAs on selected ESXi hosts.

        Args:
            esxi_hosts (list): ESXi hosts to perform a storage rescan on.
        """
        for esxi_host in esxi_hosts:
            esxi_host.configManager.storageSystem.RescanAllHba()

    def verify_vsphere_cluster(self, cluster_name):
        """Verify host objects and host groups associated with the vSphere Cluster are configured on the FlashArray.

        Args:
            cluster_name (str): Name of the vSphere Cluster to verify.
            flasharray (purestorage.FlashArray): Existing session to FlashArray.

        Returns:
            hgroup (dict): Host group associated with vSphere cluster.
            connected_esxi_hosts (list): List of ESXi hosts in a connected state for vSphere cluster..
        """
        msg = 'Cancelling datastore creation. Please verify the object exists and is online, then try again.'

        cluster = None
        connected_esxi_hosts = []
        esxi_hosts = []

        compute_resources = self.create_compute_container_view()
        for compute in compute_resources:
            if compute.name == cluster_name:
                cluster = compute

        if cluster:
            hgroup = datastore_utils.fa_hgroup_to_vc_cluster_mapping(cluster, self.flasharray)
            esxi_hosts = cluster.host
        else:
            raise ValueError(f'Cluster "{cluster_name}" not found on specified vCenter Server. {msg}')

        if esxi_hosts:
            for esxi in esxi_hosts:
                if esxi.runtime.connectionState == 'connected':
                    connected_esxi_hosts.append(esxi)
        else:
            raise ValueError(f'No ESXi hosts found for "{cluster_name}". {msg}')

        return hgroup, connected_esxi_hosts


class VmfsDatastores(Datastores):
    """Maintenance of VMware VMFS datastores associated with Pure Storage FlashArrays."""

    def create_vmfs_datastore(self, cluster_name, ds_name, ds_size, vmfs_version=None):
        """Create a new VMFS datastore on a Pure Storage FlashArray and connect it to the requested vSphere cluster.

        Args:
            cluster_name (str): Name of the cluster to create datastore in.
            ds_name (str): Requested name of the datastore.
            ds_size (int): Size in GB the rquested datastore should be.
            vmfs_version (int): Version of VMFS datastore to be created.

        Returns:
            datastore (vim.Datastore): Newly created datastore object.

        Raises:
            ValueError:
                - If cluster resource is not found within vCenter.
                - If no ESXi hosts are found (empty cluster).
                - If no connected ESXi hosts are found within the cluster.
                - If disk device is not found on ESXi host.
        """
        hgroup, connected_esxi_hosts = self.verify_vsphere_cluster(cluster_name)

        if connected_esxi_hosts:
            esxi_host = connected_esxi_hosts[0]
            fa_volume = self.flasharray.create_volume(ds_name, f'{ds_size}G')
            self.flasharray.connect_hgroup(hgroup, fa_volume['name'])
            esxi_host.configManager.storageSystem.RescanAllHba()
        else:
            raise ValueError(f'No connected hosts found for cluster "{cluster_name}".')

        vol_serial_num = fa_volume['serial'].lower()
        host_dssystem = esxi_host.configManager.datastoreSystem
        avail_disks = host_dssystem.QueryAvailableDisksForVmfs()

        # Confirm the selected FlashArray volume is seen by the ESXi host.
        device_path = datastore_utils.get_device_path(avail_disks, vol_serial_num)

        if not device_path:
            disk_msg = f'Unable to find specified device on {esxi_host.name}.'
            raise ValueError(disk_msg)

        vmfs_creation_options = host_dssystem.QueryVmfsDatastoreCreateOptions(device_path)
        # VMware only returns one item to be used here, and always will, since it is just specifying creation options.
        vmfs_creation_options[0].spec.vmfs.volumeName = ds_name

        if vmfs_version:
            # VMware only returns one item to be used here since it is just specifying creation options.
            vmfs_creation_options[0].spec.vmfs.majorVersion = vmfs_version

        datastore = host_dssystem.CreateVmfsDatastore(vmfs_creation_options[0].spec)

        Datastores.rescan_esxi_storage(connected_esxi_hosts)

        return datastore


class VvolDatastores(Datastores):
    """Maintenance of VMware vVol datastores associated with Pure Storage FlashArrays."""

    def __init__(self, sms_instance, vsphere_content, flasharray):
        super(VvolDatastores, self).__init__(vsphere_content, flasharray)
        self.sms_instance = sms_instance

    def create_vvol_datastore(self, cluster_name, ds_name, protocol_endpoint_name=None):
        """Create a new vVol datastore on a Pure Storage FlashArray and connect it to the requested vSphere cluster.

        Args:
            cluster_name (str): Name of the cluster to create datastore in.
            ds_name (str): Requested name of the datastore.
            protocol_endpoint_name (optional, str): Name of the protocol endpoint to be used on a FlashArray.

        Returns:
            vvol_ds (vim.Datastore): Newly created vVol datastore object.
        """
        sc_id = None

        if not protocol_endpoint_name:
            protocol_endpoint_name = 'pure-protocol-endpoint'

        hgroup, connected_esxi_hosts = self.verify_vsphere_cluster(cluster_name)
        existing_protocol_endpoints = self.flasharray.list_volumes(protocol_endpoint=True)

        if connected_esxi_hosts:
            if not existing_protocol_endpoints:
                fa_protocol_endpoint = self.flasharray.create_conglomerate_volume(protocol_endpoint_name)
                self.flasharray.connect_hgroup(hgroup, fa_protocol_endpoint['name'])
            else:
                for endpoint in existing_protocol_endpoints:
                    if endpoint['name'] == protocol_endpoint_name:
                        raise ValueError(f'"{protocol_endpoint_name}" already exists. Cancelling creation of vVol'
                                         f' datastore.')
                    else:
                        fa_protocol_endpoint = self.flasharray.create_conglomerate_volume(protocol_endpoint_name)
                        self.flasharray.connect_hgroup(hgroup, fa_protocol_endpoint['name'])

        Datastores.rescan_esxi_storage(connected_esxi_hosts)
        storage_manager = self.sms_instance.QueryStorageManager()
        storage_containers = storage_manager.QueryStorageContainer().storageContainer

        for container in storage_containers:
            # Example of arrayId output:
            # (str) ['com.purestorage:3b7b308d-98f9-425e-87a1-3e57ada49658']
            if container.arrayId[0].split(':')[1] == self.flasharray.get().get('id'):
                sc_id = container.uuid

        for esxi_host in connected_esxi_hosts:
            host_dssystem = esxi_host.configManager.datastoreSystem
            vvol_spec = vim.HostDatastoreSystemVvolDatastoreSpec(name=ds_name, scId=sc_id)
            vvol_datastore = host_dssystem.CreateVvolDatastore(vvol_spec)

        Datastores.rescan_esxi_storage(connected_esxi_hosts)

        return vvol_datastore

    def get_pure_provider(self, storage_manager, registration_url):
        """Get specified Pure Storage Provider from Storage Monitoring Services (SMS) instance.

        Args:
            storage_manager (sms.StorageManager): SMS storage manager from authenticated instance.
            registration_url (str): URL that the storage provider was registered with.

        Returns:
            matched_provider (sms.provider.VasaProvider): Requested VASA Provider object from SMS.

        Raises:
            ValueError:
                - If specified provider is not found on SMS instance.
        """
        matched_provider = None
        providers = storage_manager.QueryProvider()

        for provider in providers:
            # Example URL: https://10.10.10.10:8084/version.xml
            if provider.QueryProviderInfo().url == registration_url:
                matched_provider = provider
                break

        if not matched_provider:
            raise ValueError('Registered provider not found. Verify the registration URL and try again.')

        return matched_provider

    def register_storage_provider(self, ip_address):
        """Register a Pure Storage FlashArray as a storage provider with vCenter Server.

        Args:
            ip_address (str): IP address of the controller you want to register with vCenter (not the 'vir0/1' address)

        Returns:
            new_provider (sms.provider.VasaProvider): Newly created VASA Provider object from SMS.

        Raises:
            ValueError:
                - If FlashArray controller is not found as correlated with the supplied IP address.
        """
        all_networks = self.flasharray.list_network_interfaces()
        fa_ctlr = None
        fa_name = self.flasharray.get()['array_name']
        storage_manager = self.sms_instance.QueryStorageManager()

        for network in all_networks:
            if ('vir' not in network.get('name')) and network.get('address') == ip_address:
                fa_ctlr = network.get('name').split('.')[0]

        if fa_ctlr:
            spec = sms.VasaProviderSpec()
            spec.name = f'{fa_name}-{fa_ctlr}'
            spec.url = f'https://{ip_address}:8084/version.xml'
            spec.username = 'pureuser'
            spec.password = 'pureuser'
        else:
            raise ValueError('Unable to determine FlashArray controller. Verify the IP address and try again.')

        register_sp_task = storage_manager.RegisterProvider(spec)
        register_sp_status = VvolDatastores.wait_for_sms_task(register_sp_task)

        if register_sp_status.state == sms.SmsTaskState.success:
            new_provider = self.get_pure_provider(storage_manager, spec.url)
        elif register_sp_status.state == sms.SmsTaskState.error:
            raise register_sp_status.error

        return new_provider

    @staticmethod
    def wait_for_sms_task(task, timeout=30):
        """Monitor running Storage Monitoring Services (SMS) tasks.

        Args:
            task (): SMS task to monitor
            timeout (optional, int): Timeout value (in seconds) for task to complete by.

        Returns:
            task_state (): State of the requested task.

        Raises:
            TimeoutException:
                - If task runs longer than the timeout value (in seconds).
            vim.fault:
                - See VIM documentation for all possible exceptions raised.
        """
        start_time = time.time()
        while task.QuerySmsTaskInfo().state in sms.SmsTaskState.running:
            time.sleep(0.1)
            elapsed_time = time.time()
            if (elapsed_time - start_time) > timeout:
                raise TimeoutException("Timed out waiting for task to complete. Please try again.")

        task_state = task.QuerySmsTaskInfo()

        return task_state
