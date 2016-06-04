import azurerm
import json


class vmss():
    def __init__(self, vmssname, vmssmodel, subscription_id, access_token):
        self.name = vmssname
        id = vmssmodel['id']
        self.rgname = id[id.index('resourceGroups/') + 15:id.index('/providers')]
        self.sub_id = subscription_id
        self.access_token = access_token

        self.model = vmssmodel
        self.capacity = vmssmodel['sku']['capacity']
        self.location = vmssmodel['location']
        self.vmsize = vmssmodel['sku']['name']
        self.tier = vmssmodel['sku']['tier']
        self.offer = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['offer']
        self.sku = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['sku']
        self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version']
        self.provisioningState = vmssmodel['properties']['provisioningState']
        self.status = self.provisioningState

    # update the token property
    def update_token(self, access_token):
        self.access_token = access_token

    # update the VMSS model version property
    def update_version(self, newversion):
        if self.version != newversion:
            self.model['properties']['virtualMachineProfile']['storageProfile']['imageReference'][
                'version'] = newversion
            self.version = newversion
            # put the vmss model
            updateresult = azurerm.update_vmss(self.access_token, self.sub_id, self.rgname, self.name,
                                               json.dumps(self.model))
            self.status = updateresult
        else:
            self.status = 'Versions are the same, skipping update'

    # set the VMSS to a new capacity
    def scale(self, capacity):
        self.model['sku']['capacity'] = capacity
        scaleoutput = azurerm.scale_vmss(self.access_token, self.sub_id, self.rgname, self.name, self.vmsize, self.tier,
                                         capacity)
        self.status = scaleoutput

    # power on all the VMs in the scale set
    def poweron(self):
        result = azurerm.start_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # power off all the VMs in the scale set
    def poweroff(self):
        result = azurerm.poweroff_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # stop deallocate all the VMs in the scale set
    def dealloc(self):
        result = azurerm.stopdealloc_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # get the VMSS instance view and set the class property
    def init_vm_instance_view(self):
        # get an instance view list in order to build a heatmap
        self.vm_instance_view = \
            azurerm.list_vmss_vm_instance_view(self.access_token, self.sub_id, self.rgname, self.name)

    def reimagevm(self, vmstring):
        result = azurerm.reimage_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def upgradevm(self, vmstring):
        result = azurerm.upgrade_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deletevm(self, vmstring):
        result = azurerm.delete_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def startvm(self, vmstring):
        result = azurerm.start_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def restartvm(self, vmstring):
        result = azurerm.restart_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deallocvm(self, vmstring):
        result = azurerm.stopdealloc_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def poweroffvm(self, vmstring):
        result = azurerm.poweroff_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result
