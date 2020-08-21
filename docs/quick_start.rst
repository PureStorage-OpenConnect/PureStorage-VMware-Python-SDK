Quick Start
===========

Authentication
--------------

This section documents the instantiation of valid, working FlashArray and VMware
clients required to subsequently call other client methods.

BaseConnector Client
~~~~~~~~~~~~~~~~~

Start by importing the ``base_connector`` submodule in ``purepyvmware``:

.. code-block:: python

   from purepyvmware import base_connector

Instantiation of a FlashArray client and VMware client requires authentication. More information
is available in the `REST API 1.0 Authentication Guide for the Pure Storage FlashArray:
<https://support.purestorage.com/FlashArray/PurityFA/Purity_FA_REST_API/REST_API_1.16/POST_auth%2F%2Fapitoken>`__

.. code-block:: python

   from purepyvmware import base_connector
   connector = base_connector.BaseConnector('flasharray.example.com',
                              fa_ip
                              fa_usr,
                              vcenter_ip,
                              vcenter_user,
                              fa_passwd=Password,
                              vcenter_passwd=Password,
                              verify_ssl=True)

As you will see above the password for the FlashArray and the vCenter Server are optional. This is
for those who are uncomfortable with typing clear text passwords on screen. If omitted you will
be prompted to enter the password for each user.

Alternatively, if you prefer to use an API token for the FlashArray you can input the API token and
exclude the password and that will authenticate successfully as well.

.. code-block:: python

   from purepyvmware import base_connector
   connector = base_connector.BaseConnector('flasharray.example.com',
                              fa_ip
                              fa_usr,
                              vcenter_ip,
                              vcenter_user,
                              api_token=token,
                              vcenter_passwd=Password,
                              verify_ssl=True)

Certificates
--------------

Certificate verification is enabled by default (verify_ssl=True). If you prefer to bypass and/or ignore
certificate checks then you must set this value to 'False'. This will import 'urllib3' and supress any
warnings regarding InsecureRequests being made.
