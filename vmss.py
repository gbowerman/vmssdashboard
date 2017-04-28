import json
import azurerm
from operator import methodcaller


class vmss():
    def __init__(self, vmssname, vmssmodel, subscription_id, access_token):
        self.name = vmssname
        id = vmssmodel['id']
        self.rgname = id[id.index('resourceGroups/') +
                         15:id.index('/providers')]
        self.sub_id = subscription_id
        self.access_token = access_token

        self.model = vmssmodel
        self.adminuser = vmssmodel['properties']['virtualMachineProfile']['osProfile']['adminUsername']
        self.capacity = vmssmodel['sku']['capacity']
        self.location = vmssmodel['location']
        self.nameprefix = vmssmodel['properties']['virtualMachineProfile']['osProfile']['computerNamePrefix']
        self.overprovision = vmssmodel['properties']['overprovision']

        # see if it's a tenant spanning scale set'
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

    # update the model, useful to see if provisioning is complete
    def refresh_model(self):
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

    # update the token property
    def update_token(self, access_token):
        self.access_token = access_token

    # update the VMSS model with any updated properties - extend this to
    # include updatePolicy etc.
    def update_model(self, newsku, newversion, newvmsize):
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
            if self.image_type == 'platform':
                self.model['properties']['virtualMachineProfile']['storageProfile']['imageReference']['version'] = newversion
            else:
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
            updateresult = azurerm.update_vmss(self.access_token, self.sub_id, self.rgname, self.name,
                                               json.dumps(self.model))
            self.status = updateresult

    # set the VMSS to a new capacity
    def scale(self, capacity):
        self.model['sku']['capacity'] = capacity
        scaleoutput = azurerm.scale_vmss(self.access_token, self.sub_id, self.rgname, self.name, self.vmsize,
                                         self.tier, capacity)
        self.status = scaleoutput

    # power on all the VMs in the scale set
    def poweron(self):
        result = azurerm.start_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    def restart(self):
        result = azurerm.restart_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # power off all the VMs in the scale set
    def poweroff(self):
        result = azurerm.poweroff_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # stop deallocate all the VMs in the scale set
    def dealloc(self):
        result = azurerm.stopdealloc_vmss(
            self.access_token, self.sub_id, self.rgname, self.name)
        self.status = result

    # get the VMSS instance view and set the class property
    def init_vm_instance_view(self):
        # get an instance view list in order to build a heatmap
        self.vm_instance_view = \
            azurerm.list_vmss_vm_instance_view(
                self.access_token, self.sub_id, self.rgname, self.name)
        # print('Counted instances: ' + str(len(self.vm_instance_view['value'])))
        # print(json.dumps(self.vm_instance_view, sort_keys=False, indent=2, separators=(',', ': ')))

    # grow the VMSS instance view by one page (calls paginated list instance
    # view fn one time)
    def grow_vm_instance_view(self, link=None):
        # get an instance view list in order to build a heatmap
        if link == None:
            self.vm_instance_view = \
                azurerm.list_vmss_vm_instance_view_pg(
                    self.access_token, self.sub_id, self.rgname, self.name)
        else:
            instance_page = azurerm.list_vmss_vm_instance_view_pg(
                self.access_token, self.sub_id, self.rgname, self.name, link)
            if 'nextLink' in instance_page:
                self.vm_instance_view['nextLink'] = instance_page['nextLink']
            else:
                del(self.vm_instance_view['nextLink'])
            self.vm_instance_view['value'].extend(instance_page['value'])

    # operations on individual VMs or groups of VMs in a scale set
    def reimagevm(self, vmstring):
        result = azurerm.reimage_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def upgradevm(self, vmstring):
        result = azurerm.upgrade_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deletevm(self, vmstring):
        result = azurerm.delete_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def startvm(self, vmstring):
        result = azurerm.start_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def restartvm(self, vmstring):
        result = azurerm.restart_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def deallocvm(self, vmstring):
        result = azurerm.stopdealloc_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def poweroffvm(self, vmstring):
        result = azurerm.poweroff_vmss_vms(
            self.access_token, self.sub_id, self.rgname, self.name, vmstring)
        self.status = result

    def get_power_state(self, statuses):
        for status in statuses:
            if status['code'].startswith('Power'):
                return status['code'][11:]

    # create lists of VMs in the scale set by fault domain, update domain, and
    # an all-up
    def set_domain_lists(self):
        # sort the list of VM instance views by group id
        self.pg_list = []
        if self.singlePlacementGroup == False:
            self.vm_instance_view['value'] = sorted(self.vm_instance_view['value'],
                                                    key=lambda k: k['properties']['instanceView']['placementGroupId'])
            last_group_id = self.vm_instance_view['value'][0]['properties']['instanceView']['placementGroupId']
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
                if self.singlePlacementGroup == False:
                    if instance['properties']['instanceView']['placementGroupId'] != last_group_id:
                        self.pg_list.append(
                            {'guid': last_group_id, 'fd_dict': fd_dict, 'ud_dict': ud_dict, 'vm_list': vm_list})
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
                print(
                    'KeyError - UD/FD may not be assigned yet. Instance view: ' + json.dumps(instance))
                break
        self.pg_list.append(
            {'guid': last_group_id, 'fd_dict': fd_dict, 'ud_dict': ud_dict, 'vm_list': vm_list})
