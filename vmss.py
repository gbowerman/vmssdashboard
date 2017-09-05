'''vmss.py - class of basic Azure VM scale set operations'''
import json

import azurerm


class vmss():
    '''vmss class - encapsulates the model and status of a VM scale set'''

    def __init__(self, vmssname, vmssmodel, subscription_id, access_token):
        '''class initializtion routine - set basic VMSS properties'''
        self.name = vmssname
        id = vmssmodel['id']
        self.rgname = id[id.index('resourceGroups/') + 15:id.index('/providers')]
        self.sub_id = subscription_id
        self.access_token = access_token

        self.model = vmssmodel
        self.adminuser = \
            vmssmodel['properties']['virtualMachineProfile']['osProfile']['adminUsername']
        self.capacity = vmssmodel['sku']['capacity']
        self.location = vmssmodel['location']
        self.nameprefix = \
            vmssmodel['properties']['virtualMachineProfile']['osProfile']['computerNamePrefix']
        self.overprovision = vmssmodel['properties']['overprovision']
        self.vm_instance_view = None
        self.pg_list = []

        # see if it's a tenant spanning scale set
        self.singlePlacementGroup = True
        if 'singlePlacementGroup' in vmssmodel['properties']:
            self.singlePlacementGroup = vmssmodel['properties']['singlePlacementGroup']
        self.tier = vmssmodel['sku']['tier']
        self.upgradepolicy = vmssmodel['properties']['upgradePolicy']['mode']
        self.vmsize = vmssmodel['sku']['name']

        # if it's a platform image, or managed disk based custom image, it has
        # an imageReference
        if 'imageReference' in vmssmodel['properties']['virtualMachineProfile']['storageProfile']:
            # if it's a managed disk based custom image it has an id
            if 'id' in vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']:
                self.image_type = 'custom'
                self.offer = 'custom'
                self.sku = 'custom'
                img_ref_id = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['id']
                self.version = img_ref_id.split(".Compute/", 1)[1]
                self.image_resource_id = img_ref_id.split(".Compute/", 1)[0]
            else:  # platform image
                self.image_type = 'platform'
                self.offer = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['offer']
                self.sku = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['sku']
                self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version']

        # else it's an unmanaged disk custom image and has an image URI
        else:
            self.image_type = 'custom'
            if 'osType' in vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']:
                self.offer = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['osType']
            else:
                self.offer = 'custom'
            self.sku = 'custom'
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri']

        self.provisioningState = vmssmodel['properties']['provisioningState']
        self.status = self.provisioningState

    def refresh_model(self):
        '''update the model, useful to see if provisioning is complete'''
        vmssmodel = azurerm.get_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.model = vmssmodel
        self.capacity = vmssmodel['sku']['capacity']
        self.vmsize = vmssmodel['sku']['name']
        if self.image_type == 'platform':
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version']
        else:
            self.version = vmssmodel['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri']
        self.provisioningState = vmssmodel['properties']['provisioningState']
        self.status = self.provisioningState

    def update_token(self, access_token):
        '''update the token property'''
        self.access_token = access_token

    def update_model(self, newsku, newversion, newvmsize):
        '''update the VMSS model with any updated properties'''
        changes = 0
        if self.sku != newsku:
            if self.image_type == 'platform':  # sku not relevant for custom image
                changes += 1
                self.model['properties']['virtualMachineProfile']['storageProfile']['imageReference']['sku'] = newsku
                self.sku = newsku
            else:
                self.status = 'You cannot change sku setting for custom image'
        if self.version != newversion:
            changes += 1
            self.version = newversion
            if self.image_type == 'platform':  # for platform image modify image reference
                self.model['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version'] = newversion
            else:
                # check for managed disk
                if 'imageReference' in self.model['properties']['virtualMachineProfile']['storageProfile']:
                    self.model['properties']['virtualMachineProfile']['storageProfile'][
                        'imageReference']['id'] = self.image_resource_id + '.Compute/' + newversion
                else:
                    # unmanaged custom image - has a URI which points directly
                    # to image blob
                    self.model['properties']['virtualMachineProfile']['storageProfile']['osDisk']['image']['uri'] = newversion

        if self.vmsize != newvmsize:
            changes += 1
            # to do - add a check that the new vm size matches the tier
            self.model['sku']['name'] = newvmsize
            self.vmsize = newvmsize
        if changes == 0:
            self.status = 'VMSS model is unchanged, skipping update'
        else:
            # put the vmss model
            updateresult = azurerm.update_vmss(self.access_token, self.sub_id, self.rgname,
                                               self.name, json.dumps(self.model))
            self.status = updateresult

    def scale(self, capacity):
        '''set the VMSS to a new capacity'''
        self.model['sku']['capacity'] = capacity
        scaleoutput = azurerm.scale_vmss(self.access_token, self.sub_id, self.rgname, self.name,
                                         capacity)
        self.status = scaleoutput

    def poweron(self):
        '''power on all the VMs in the scale set'''
        result = azurerm.start_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    def restart(self):
        '''restart all the VMs in the scale set'''
        result = azurerm.restart_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    def poweroff(self):
        '''power off all the VMs in the scale set'''
        result = azurerm.poweroff_vmss(self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    def dealloc(self):
        '''stop deallocate all the VMs in the scale set'''
        result = azurerm.stopdealloc_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    def init_vm_instance_view(self):
        '''get the VMSS instance view and set the class property'''
        # get an instance view list in order to build a heatmap
        self.vm_instance_view = \
            azurerm.list_vmss_vm_instance_view(self.access_token, self.sub_id, self.rgname,
                                               self.name)

    def grow_vm_instance_view(self, link=None):
        '''grow the VMSS instance view by one page'''
        # get an instance view list in order to build a heatmap
        if link is None:
            self.vm_instance_view = \
                azurerm.list_vmss_vm_instance_view_pg(
                    self.access_token, self.sub_id, self.rgname, self.name)
        else:
            instance_page = azurerm.list_vmss_vm_instance_view_pg(
                self.access_token, self.sub_id, self.rgname, self.name, link)
            if 'nextLink' in instance_page:
                self.vm_instance_view['nextLink'] = instance_page['nextLink']
            else:
                del self.vm_instance_view['nextLink']
            self.vm_instance_view['value'].extend(instance_page['value'])

    def reimagevm(self, vmstring):
        '''reaimge individual VMs or groups of VMs in a scale set'''
        result = azurerm.reimage_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def upgradevm(self, vmstring):
        '''upgrade individual VMs or groups of VMs in a scale set'''
        result = azurerm.upgrade_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deletevm(self, vmstring):
        '''delete individual VMs or groups of VMs in a scale set'''
        result = azurerm.delete_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def startvm(self, vmstring):
        '''start individual VMs or groups of VMs in a scale set'''
        result = azurerm.start_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def restartvm(self, vmstring):
        '''restart individual VMs or groups of VMs in a scale set'''
        result = azurerm.restart_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deallocvm(self, vmstring):
        '''dealloc individual VMs or groups of VMs in a scale set'''
        result = azurerm.stopdealloc_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def poweroffvm(self, vmstring):
        '''power off individual VMs or groups of VMs in a scale set'''
        result = azurerm.poweroff_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def get_power_state(self, statuses):
        '''get power state from a list of VM isntance statuses'''
        for status in statuses:
            if status['code'].startswith('Power'):
                return status['code'][11:]

    def set_domain_lists(self):
        '''create lists of VMs in the scale set by fault domain, update domain, and all-up'''
        # sort the list of VM instance views by group id
        if self.singlePlacementGroup is False:
            self.vm_instance_view['value'] = \
                sorted(self.vm_instance_view['value'],
                       key=lambda k: k['properties']['instanceView']['placementGroupId'])
            last_group_id = \
                self.vm_instance_view['value'][0]['properties']['instanceView']['placementGroupId']
        else:
            last_group_id = "single group"
        # now create a list of group id + FD/UD list objects
        # each time group id changes append a new value to the list
        fd_dict = {f: [] for f in range(5)}
        ud_dict = {u: [] for u in range(5)}
        vm_list = []
        for instance in self.vm_instance_view['value']:
            try:
                # when group Id changes, load fd/ud/vm dictionaries into the placement group list
                # may need to change this to copy by value
                # debug: print(json.dumps(instance))
                if self.singlePlacementGroup is False:
                    if instance['properties']['instanceView']['placementGroupId'] != last_group_id:
                        self.pg_list.append(
                            {'guid': last_group_id, 'fd_dict': fd_dict, 'ud_dict': ud_dict,
                             'vm_list': vm_list})
                        fd_dict = {f: [] for f in range(5)}
                        ud_dict = {u: [] for u in range(5)}
                        vm_list = []
                        last_group_id = instance['properties']['instanceView']['placementGroupId']
                instanceId = instance['instanceId']
                ud = instance['properties']['instanceView']['platformUpdateDomain']
                fd = instance['properties']['instanceView']['platformFaultDomain']
                power_state = self.get_power_state(
                    instance['properties']['instanceView']['statuses'])
                ud_dict[ud].append([instanceId, power_state])
                fd_dict[fd].append([instanceId, power_state])
                vm_list.append([instanceId, fd, ud, power_state])
            except KeyError:
                print('KeyError - UD/FD may not be assigned yet. Instance view: '\
                    + json.dumps(instance))
                break
        self.pg_list.append(
            {'guid': last_group_id, 'fd_dict': fd_dict, 'ud_dict': ud_dict, 'vm_list': vm_list})
