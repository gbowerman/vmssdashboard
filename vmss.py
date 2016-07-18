import json

import azurerm


class vmss():
    def __init__(self, vmssname, vmssmodel, subscription_id, access_token):
        self.name = vmssname
        id = vmssmodel['id']
        self.rgname = id[id.index('resourceGroups/') + 15:id.index('/providers')]
        self.sub_id = subscription_id
        self.access_token = access_token

        self.model = vmssmodel
        self.adminuser = vmssmodel['properties']['virtualMachineProfile']['osProfile']['adminUsername']
        self.capacity = vmssmodel['sku']['capacity']
        self.location = vmssmodel['location']
        self.nameprefix = vmssmodel['properties']['virtualMachineProfile']['osProfile']['computerNamePrefix']
        self.overprovision = vmssmodel['properties']['overprovision']
        self.tier = vmssmodel['sku']['tier']
        self.upgradepolicy = vmssmodel['properties']['upgradePolicy']['mode']
        self.vmsize = vmssmodel['sku']['name']

        # if it's a platform image, the model will have these
        if 'imageReference' in vmssmodel['properties']['virtualMachineProfile']['storageProfile']:
            self.image_type = 'platform'
            self.offer = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['offer']
            self.sku = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['sku']
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version']
        # else it's a custom image it will have an image URI - to do: add something to display the image URI
        else:
            # for now just set these values so it doesn't break
            self.image_type = 'custom'
            self.offer = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['osType']
            self.sku = 'custom'
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri']

        self.provisioningState = vmssmodel['properties']['provisioningState']
        self.status = self.provisioningState

    # update the model, useful to see if provisioning is complete
    def refresh_model(self):
        vmssmodel = azurerm.get_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.model = vmssmodel
        self.capacity = vmssmodel['sku']['capacity']
        self.vmsize = vmssmodel['sku']['name']
        if self.image_type == 'platform':
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version']
        else:
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri']
        self.provisioningState = vmssmodel['properties']['provisioningState']
        self.status = self.provisioningState

    # update the token property
    def update_token(self, access_token):
        self.access_token = access_token

    # update the VMSS model with any updated properties - extend this to include updatePolicy etc.
    def update_model(self, newversion, newvmsize):
        changes = 0
        if self.version != newversion:
            changes += 1
            if self.image_type == 'platform':
                self.model['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version'] = newversion
            else:
                self.model['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri'] = newversion
        if self.vmsize != newvmsize:
            changes += 1
            self.model['sku']['name'] = newvmsize # to do - add a check that the new vm size matches the tier
            self.version = newversion
            self.vmsize = newvmsize
        if changes == 0:
            self.status = 'VMSS model is unchanged, skipping update'
        else:
            # put the vmss model
            updateresult = azurerm.update_vmss(self.access_token, self.sub_id, self.rgname, self.name,
                                               json.dumps(self.model))
            self.status = updateresult


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

    def restart(self):
        result = azurerm.restart_vmss(self.access_token, self.sub_id, self.rgname, self.name)
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

    # operations on individual VMs or groups of VMs in a scale set
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

    def get_power_state(self, statuses):
        for status in statuses:
            if status['code'].startswith('Power'):
                return status['code'][11:]

    # create lists of VMs in the scale set by fault domain, update domain, and an all-up
    def set_domain_lists(self):
        self.fd_dict = {f: [] for f in range(5)}
        self.ud_dict = {u: [] for u in range(5)}
        self.vm_list = []
        for instance in self.vm_instance_view['value']:
            try:
                instanceId = instance['instanceId']
                ud = instance['properties']['instanceView']['platformUpdateDomain']
                fd = instance['properties']['instanceView']['platformFaultDomain']
                power_state = self.get_power_state(instance['properties']['instanceView']['statuses'])
                self.ud_dict[ud].append([instanceId, power_state])
                self.fd_dict[fd].append([instanceId, power_state])
                self.vm_list.append([instanceId, fd, ud, power_state])
            except KeyError:
                print('KeyError - UD/FD may not be assigned yet. Instance view: ' + json.dumps(instance))
                break

