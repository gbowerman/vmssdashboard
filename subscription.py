'''subscription.py - subscription class for basic subscription level operations'''
import json

import azurerm


# Azure subscription class
class subscription():
    '''basic subscription level operations for VMSS Editor'''
    def __init__(self, tenant_id, app_id, app_secret, subscription_id):
        self.sub_id = subscription_id
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.vmsslist = []
        self.vmssdict = {}
        self.status = ""

        self.access_token = azurerm.get_access_token(tenant_id, app_id, app_secret)

    def auth(self):
        '''update the authentication token for this subscription'''
        self.access_token = azurerm.get_access_token(self.tenant_id, self.app_id, self.app_secret)
        return self.access_token

    def get_vmss_list(self):
        '''list VM Scale Sets in this subscription - names only'''
        vmss_sub_list = azurerm.list_vmss_sub(self.access_token, self.sub_id)
        # build a simple list of VM Scale Set names and a dictionary of VMSS model views
        try:
            for vmss in vmss_sub_list['value']:
                vmssname = vmss['name']
                self.vmsslist.append(vmssname)
                self.vmssdict[vmssname] = vmss

        except KeyError:
            self.status = 'KeyError: azurerm.list_vmss_sub() returned: ' + json.dumps(vmss_sub_list)
        return self.vmsslist
