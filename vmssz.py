'''vmssz.py - class of basic Azure VM scale set operations, without UDs, with zones'''
import json

import azurerm


class VMSSZ():
    '''VMSSZ class - encapsulates the model and status of a zone redundant VM scale set'''

    def __init__(self, vmssname, vmssmodel, subscription_id, access_token):
        '''class initializtion routine - set basic VMSS properties'''
        self.name = vmssname
        vmssid = vmssmodel['id']
        self.rgname = vmssid[vmssid.index('resourceGroups/') + 15:vmssid.index('/providers')]
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
        self.vm_model_view = None
        self.pg_list = []
        self.zones = []
        if 'zones' in vmssmodel:
            self.zonal = True
        else:
            self.zonal = False

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
        # get an instance view list in order to build FD heatmap
        self.vm_instance_view = \
            azurerm.list_vmss_vm_instance_view(self.access_token, self.sub_id, self.rgname,
                                               self.name)

    def init_vm_model_view(self):
        '''get the VMSS instance view and set the class property'''
        # get a model view list in order to build a zones heatmap
        self.vm_model_view = \
            azurerm.list_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name)

    def reimagevm(self, vmstring):
        '''reaimge individual VMs or groups of VMs in a scale set'''
        result = azurerm.reimage_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                          vmstring)
        self.status = result

    def upgradevm(self, vmstring):
        '''upgrade individual VMs or groups of VMs in a scale set'''
        result = azurerm.upgrade_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                          vmstring)
        self.status = result

    def deletevm(self, vmstring):
        '''delete individual VMs or groups of VMs in a scale set'''
        result = azurerm.delete_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                         vmstring)
        self.status = result

    def startvm(self, vmstring):
        '''start individual VMs or groups of VMs in a scale set'''
        result = azurerm.start_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                        vmstring)
        self.status = result

    def restartvm(self, vmstring):
        '''restart individual VMs or groups of VMs in a scale set'''
        result = azurerm.restart_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                          vmstring)
        self.status = result

    def deallocvm(self, vmstring):
        '''dealloc individual VMs or groups of VMs in a scale set'''
        result = azurerm.stopdealloc_vmss_vms(self.access_token, self.sub_id, self.rgname,
                                              self.name, vmstring)
        self.status = result

    def poweroffvm(self, vmstring):
        '''power off individual VMs or groups of VMs in a scale set'''
        result = azurerm.poweroff_vmss_vms(self.access_token, self.sub_id, self.rgname, self.name,
                                           vmstring)
        self.status = result

    def get_power_state(self, statuses):
        '''get power state from a list of VM isntance statuses'''
        for status in statuses:
            if status['code'].startswith('Power'):
                return status['code'][11:]

    def init_zones(self):
        '''create a structure to represent VMs by zone and FD
           - ignore placement groups for now.
        '''
        self.zones = []
        for zone_id in range(1, 4):
            zone = {'zone': zone_id}
            fds = []
            for fd_num in range(5):
                fault_domain = {'fd': fd_num, 'vms': []}
                fds.append(fault_domain)
            zone['fds'] = fds
            self.zones.append(zone)

    def init_vm_details(self):
        '''Populate the self.zones structure
           - with a physically ordered representation of the VMs in a scale set.
        '''
        self.init_zones()
        # get the model view
        self.vm_model_view = azurerm.list_vmss_vms(self.access_token, self.sub_id, self.rgname,
                                                   self.name)
        # get the instance view
        self.vm_instance_view = azurerm.list_vmss_vm_instance_view(self.access_token, self.sub_id,
                                                                   self.rgname, self.name)
        # do a loop through the number of VMs and populate VMs properties in the zones structure
        # make an assumption that len(vm_model_view) == len(vm_instance_view)
        #   - true if not actively scaling
        for idx in range(len(self.vm_model_view['value'])):
            vm_id = self.vm_model_view['value'][idx]['instanceId']
            zone_num = self.vm_model_view['value'][idx]['zones'][0]
            power_state = self.get_power_state(
                self.vm_instance_view['value'][idx]['properties']['instanceView']['statuses'])
            fault_domain = self.vm_instance_view['value'][idx]['properties']['instanceView']['platformFaultDomain']
            vm_data = {'vmid': vm_id, 'power_state': power_state}
            self.zones[int(zone_num)-1]['fds'][fault_domain]['vms'].append(vm_data)
        #print(json.dumps(self.zones))
