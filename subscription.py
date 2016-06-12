import json

import azurerm


# Azure subscription class
class subscription():
    def __init__(self, tenant_id, app_id, app_secret, subscription_id):
        self.sub_id = subscription_id
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.app_secret = app_secret

        self.access_token = azurerm.get_access_token(tenant_id, app_id, app_secret)

    # update the authentication token for this subscription
    def auth(self):
        self.access_token = azurerm.get_access_token(self.tenant_id, self.app_id, self.app_secret)
        return self.access_token

    # list VM Scale Sets in this subscription - names only
    def get_vmss_list(self):
        vmss_sub_list = azurerm.list_vmss_sub(self.access_token, self.sub_id)
        self.vmsslist = []
        self.vmssdict = {}
        # build a simple list of VM Scale Set names and a dictionary of VMSS model views
        try:
            for vmss in vmss_sub_list['value']:
                vmssname = vmss['name']
                self.vmsslist.append(vmssname)
                self.vmssdict[vmssname] = vmss

        except KeyError:
            self.status = 'KeyError: azurerm.list_vmss_sub() returned: ' + json.dumps(vmss_sub_list)
        return self.vmsslist
