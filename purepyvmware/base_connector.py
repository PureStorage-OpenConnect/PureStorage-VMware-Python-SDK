"""Establish connectivity and retrieve content from Pure Storage and VMware Environments."""

import getpass
import ssl
import urllib3

from purestorage import FlashArray
from pyVim import connect
from pyVmomi import sms
from pyVmomi import vmodl


class BaseConnector(object):
    """Focused on establishing connections to Pure Storage and vSphere environments.

    Once connectivity has been acheived content from each environment can be requested for further analysis and use.
    """

    def __init__(
        self,
        fa_ip,
        fa_usr,
        vcenter_ip,
        vcenter_usr,
        fa_passwd=None,
        api_token=None,
        vcenter_passwd=None,
        verify_ssl=True):
        """Connect to FlashArray and vSphere environments as requested by end-user.

        Args:
            flasharray (str): FlashArray IP address or FQDN.
            fa_usr (str): Authenticated user for FlashArray.
            fa_passwd (str): Password for FlashArray authenticated user.
            api_token (str): Authenticated API token for FlashArray.
            vcenter_ip (str): vCenter Server IP address or FQDN.
            vcenter_usr (str): Authenticated User for vCenter Server.
            vcenter_passwd (str): Password for vCenter authenticated user.
            verify_ssl (bool): Whether or not the session should be verified.
        """
        self.fa_instance = self.connect_purestorage_fa(self, fa_ip, fa_usr, fa_passwd=None, api_token=None, verify_ssl=True)
        self.vc_instance = self.connect_vsphere_env(self, vcenter_ip, vcenter_usr, vcenter_passwd=None, verify_ssl=True)
        self.vsphere_content = self.get_env_content(self.vc_instance)
        self.sms_instance = self.connect_sms_env(self, vcenter_ip)

    def connect_purestorage_fa(self, target, username, password=None, api_token=None, verify_https=True):
        """Create a session (verified or unverified) with the requested FlashArray.

        Args:
            target (str): FlashArray IP address or FQDN.
            username (str): Authenticated user for FlashArray.
            password (str): Password for FlashArray authenticated user.
            api_token (str): Authenticated API token for FlashArray.
            verify_https (bool): Whether or not the session should be verified.

        Returns:
            fa_instance (purestorage.FlashArray): Verified or unverified session to FlashArray.
        """
        # If end-user is using CLI and doesn't want to type their password in clear text on screen they can use this
        # option to input their password.
        if not (api_token or password):
            password = getpass.getpass(prompt='FlashArray Password: ', stream=None)

        if not verify_https:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            fa_instance = FlashArray(target, username=username, password=password, api_token=api_token,
                                     verify_https=verify_https)
        else:
            fa_instance = FlashArray(target, username, password, api_token)

        return fa_instance

    def connect_sms_env(self, vcenter_ip):
        """Create a session (verified or unverified) with the SMS service on the requested vCenter Server.

        Args:
            vcenter_ip (str): IP address of the vCenter Server you wish to connect to the SMS service on.

        Returns:
            sms_instance (sms.ServiceInstance): Service Instance for the SMS service on vCenter.
        """
        client_stub = self.vc_instance._GetStub()
        ssl_context = client_stub.schemeArgs.get('context')
        session_cookie = client_stub.cookie.split('"')[1]
        additional_headers = {'vcSessionCookie': session_cookie}
        stub = connect.SoapStubAdapter(vcenter_ip, path='/sms/sdk', version='sms.version.version5',
                                       sslContext=ssl_context, requestContext=additional_headers)
        sms_instance = sms.ServiceInstance('ServiceInstance', stub)

        return sms_instance

    def connect_vsphere_env(self, host, user, pwd=None, ssl_context=True):
        """Create a session (verified or unverified) with the requested vCenter Server.

        Args:
            host (str): vCenter Server IP address or FQDN.
            user (str): Authenticated User for vCenter Server.
            pwd (str): Password for vCenter authenticated user.
            ssl_context (bool): Whether or not the session should be verified.

        Returns:
            vsphere_session(vim.ServiceInstance): Verified or unverified session to vCenter Server.
        """
        # If end-user is using CLI and doesn't want to type their password in clear text on screen they can use this
        # option to input their password.
        if not pwd:
            pwd = getpass.getpass(prompt='vSphere Password: ', stream=None)

        if not ssl_context:
            ssl_context = None
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.verify_mode = ssl.CERT_NONE

            vc_instance = connect.SmartConnect(host=host, user=user, pwd=pwd, sslContext=ssl_context)
        else:

            vc_instance = connect.SmartConnect(host=host, user=user, pwd=pwd)

        return vc_instance

    @staticmethod
    def get_env_content(vsphere_instance):
        """Retrieve all available content for the vSphere environment (vCenter or ESXi).

        Args:
            vsphere_instance (vim.ServiceInstance): Root object of the vSphere inventory.

        Returns:
            vsphere_content (vim.ServiceInstanceContent): All available content within the vSphere env.
        """
        vsphere_content = vsphere_instance.RetrieveContent()

        return vsphere_content
