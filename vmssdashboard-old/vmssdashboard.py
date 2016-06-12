#!/usr/bin/env python
# VMSS Dashboard - program to show the properties of an Azure VM Scale Set app
"""
Copyright (c) 2016, Guy Bowerman
Description: Graphical dashboard to show and set Azure VM Scale Set properties
License: MIT (see LICENSE.txt file for details)
"""
import json
import sys
import threading
import time
import webbrowser

import pygame

import azurerm

# Load Azure app defaults
try:
    with open('vmssConfig.json') as configFile:
        configData = json.load(configFile)
except FileNotFoundError:
    print("Error: Expecting vmssConfig.json in current folder")
    sys.exit()

tenant_id = configData['tenantId']
app_id = configData['appId']
app_secret = configData['appSecret']
subscription_id = configData['subscriptionId']
# this is the resource group, VM Scale Set to monitor..
rgname = configData['resourceGroup']
vmssname = configData['vmssName']
configFile.close()

# vmss property containers
vmssProperties = dict()
vmssVmProperties = []
vmssVmInstanceView = ''

# resource group level network properties
ipaddr = ''
dns = ''

# app state variables
clickLoopCount = 50
showScaleIn = False
showScaleOut = False

# screen message locations
msg_xstart = 80  # defines the location on the map where VMSS details appear
msg_ystart = 400
status_coords = [80, 620]
vm_start_coords = [100, 10]  # where to start display icons for each VM

dc_map = {'eastasia': [1000, 290], 'centralus': [275, 215], 'eastus': [330, 250],
          'eastus2': [330, 250], 'westus': [175, 225], 'northcentralus': [300, 225],
          'southcentralus': [270, 275], 'northeurope': [580, 190], 'westeurope': [630, 185],
          'japanwest': [1085, 250], 'japaneast': [1100, 235], 'brazilsouth': [450, 445],
          'australiaeast': [1140, 490], 'australiasoutheast': [1110, 500], 'southindia': [890, 325],
          'centralindia': [875, 300], 'westindia': [860, 295], 'southeastasia': [950, 350]}

# define colors
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
WHITE = (255, 255, 255)

# initial setup
size = [1300, 650]
pygame.init()
screen = pygame.display.set_mode(size)
pygame.display.set_caption("VMSS Dashboard")

# Load images and set screen attributes
background = pygame.image.load("img/datacenter.png").convert()
vmss_image = pygame.image.load("img/vmss.png").convert_alpha()
vm_image = pygame.image.load("img/vm.png").convert_alpha()
minus_icon = pygame.image.load("img/minus.png").convert_alpha()
plus_icon = pygame.image.load("img/plus.png").convert_alpha()
minus_click = pygame.image.load("img/minus_click.png").convert_alpha()
plus_click = pygame.image.load("img/plus_click.png").convert_alpha()
background = pygame.transform.scale(background, size)


# thread to loop around monitoring the VM Scale Set state and its VMs
# sleep between loops sets the update frequency
def get_vmss_properties(access_token, subscription_id):
    global vmssProperties
    global vmssVmProperties
    while True:
        try:
            # get VMSS details
            vmssget = azurerm.get_vmss(access_token, subscription_id, rgname, vmssname)
            vmssProperties['name'] = vmssget['name']
            vmssProperties['capacity'] = vmssget['sku']['capacity']
            vmssProperties['location'] = vmssget['location']
            vmssProperties['vmsize'] = vmssget['sku'][
                'name']  # needed for scale operations (and displayed on dashboard)
            vmssProperties['tier'] = vmssget['sku']['tier']  # needed for scale operations
            vmssProperties['offer'] = \
                vmssget['properties']['virtualMachineProfile']['storageProfile']['imageReference']['offer']
            vmssProperties['sku'] = vmssget['properties']['virtualMachineProfile']['storageProfile']['imageReference'][
                'sku']
            vmssProperties['provisioningState'] = vmssget['properties']['provisioningState']

            vmssvms = azurerm.list_vmss_vms(access_token, subscription_id, rgname, vmssname)
            # get VM details
            vmssVmTempProperties = []
            for vm in vmssvms['value']:
                instanceId = vm['instanceId']
                vmName = vm['name']
                provisioningState = vm['properties']['provisioningState']
                powerState = ''
                if provisioningState == 'Succeeded':
                    instanceView = azurerm.get_vmss_vm_instance_view(access_token, subscription_id, rgname, vmssname,
                                                                     instanceId)
                    powerState = instanceView['statuses'][1]['displayStatus']
                vmssVmTempProperties.append([instanceId, vmName, provisioningState, powerState])
            vmssVmProperties = list(vmssVmTempProperties)
            print(json.dumps(vmssVmProperties, sort_keys=False, indent=2, separators=(',', ': ')))
        except:
            # this catches errors like throttling from the Azure server
            f = open('error.log', 'w')
            if len(vmssvms) > 0:
                for p in vmssvms.items():
                    f.write("%s:%s\n" % p)
            f.close()
            # break out of loop when an error is encountered
            break
        # sleep before before each loop to avoid throttling
        time.sleep(5)


# draw the icon_image at the specified coords
def draw_icon(icon_image, icon_coords):
    screen.blit(icon_image, icon_coords)


# write a message at the specified coords and size
def draw_text(message, text_coords, size):
    msgFont = pygame.font.SysFont('Courier', size)
    label = msgFont.render(message, 1, BLUE)
    screen.blit(label, text_coords)


# draw a VMSS icon in the right geo. Write details in a separate part of the image
def draw_vmss():
    vmss_coords = dc_map[vmssProperties['location']]  # locating VMSS on world map
    label_coords = [vmss_coords[0], vmss_coords[1] + 50]
    draw_icon(vmss_image, vmss_coords)

    # draw name under VMSS icon and in label coords section
    draw_text(vmssProperties['name'], label_coords, 14)
    draw_text('Name: ' + vmssProperties['name'], [msg_xstart, msg_ystart], 28)

    # draw capacity
    draw_text('Capacity: ' + str(vmssProperties['capacity']), [msg_xstart, msg_ystart + 30], 28)
    minus_coords = [msg_xstart + 210, msg_ystart + 30]
    plus_coords = [msg_xstart + 270, msg_ystart + 30]
    if showScaleIn == True:
        draw_text('Decreasing capacity by 1', status_coords, 24)
        draw_icon(minus_click, minus_coords)
        draw_icon(plus_icon, plus_coords)
    elif showScaleOut == True:
        draw_text('Increasing capacity by 1', status_coords, 24)
        draw_icon(plus_click, plus_coords)
        draw_icon(minus_icon, minus_coords)
    else:
        draw_icon(minus_icon, minus_coords)
        draw_icon(plus_icon, plus_coords)

    # draw sku
    draw_text('VM size: ' + vmssProperties['vmsize'], [msg_xstart, msg_ystart + 60], 28)
    draw_text('OS: ' + vmssProperties['offer'] + ' ' + vmssProperties['sku'], [msg_xstart, msg_ystart + 90], 28)

    # draw dns details
    if len(dns) > 0 and len(ipaddr) > 0:
        draw_text(dns + ' (' + ipaddr + ')', [msg_xstart, msg_ystart + 170], 28)

    # draw provisioning state
    draw_text('Provisioning state: ' + vmssProperties['provisioningState'], [msg_xstart, msg_ystart + 200], 28)


# show all the VMs in the VMSS with their provisioning state
def draw_vmssvms():
    xinc = 0
    yinc = 0
    for vm in vmssVmProperties:
        draw_icon(vm_image, [vm_start_coords[0] + xinc, vm_start_coords[1] + yinc])
        draw_text(vm[1], [vm_start_coords[0] - 30 + xinc, vm_start_coords[1] + 20 + yinc], 16)
        draw_text(vm[2], [vm_start_coords[0] - 30 + xinc, vm_start_coords[1] + 35 + yinc], 16)
        draw_text(vm[3], [vm_start_coords[0] - 30 + xinc, vm_start_coords[1] + 50 + yinc], 16)
        xinc += 120
        if xinc >= 1200:
            xinc = 0
            yinc += 70


# change the VM scale set capacity by scaleNum (can be positive or negative for scale-out/in)
def scale_event(scaleNum, access_token):
    newCapacity = vmssProperties['capacity'] + scaleNum
    scaleoutput = azurerm.scale_vmss(access_token, subscription_id, rgname, vmssname, vmssProperties['vmsize'],
                                     vmssProperties['tier'], newCapacity)


# Figure out which of the interactive screen locations the user clicked on
# and act accordingly
def process_click(clickpos, access_token):
    global clickLoopCount
    global showScaleIn
    global showScaleOut
    # print click location in default messaging area
    draw_text(str(clickpos[0]) + ',' + str(clickpos[1]), [msg_xstart, 80], 28)
    # check if user clicked on minus sign
    if clickpos[0] > msg_xstart + 210 and clickpos[0] < msg_xstart + 250 and clickpos[1] > msg_ystart + 30 and clickpos[
        1] < msg_ystart + 60:
        showScaleIn = True
        clickLoopCount = 10
        scale_thread = threading.Thread(target=scale_event, args=(-1, access_token))
        scale_thread.start()
    # check if user clicked on plus sign
    elif clickpos[0] > msg_xstart + 270 and clickpos[0] < msg_xstart + 300 and clickpos[1] > msg_ystart + 30 and \
                    clickpos[1] < msg_ystart + 60:
        showScaleOut = True
        clickLoopCount = 10
        scale_thread = threading.Thread(target=scale_event, args=(1, access_token))
        scale_thread.start()
    # check if user clicked on DNS addr of load balancer IP and launch a browser tab
    elif clickpos[0] > msg_xstart and clickpos[0] < msg_xstart + 900 and clickpos[1] > msg_ystart + 145 and clickpos[
        1] < msg_ystart + 170:
        webbrowser.open('http://' + vmssProperties[7], new=2)


def main():
    global clickLoopCount
    global showScaleIn, showScaleOut
    global ipaddr, dns

    # get an access token for Azure authentication
    access_token = azurerm.get_access_token(tenant_id, app_id, app_secret)

    # get public ip address for resource group (don't need to query this in a loop)
    # this gets the first ip address - modify this if your RG has multiple ips
    ips = azurerm.list_public_ips(access_token, subscription_id, rgname)
    # print(ips)
    if len(ips['value']) > 0:
        dns = ips['value'][0]['properties']['dnsSettings']['fqdn']
        ipaddr = ips['value'][0]['properties']['ipAddress']

    # start a timer in order to refresh the access token in 10 minutes
    start_time = time.time()

    # start a VMSS monitoring thread
    vmss_thread = threading.Thread(target=get_vmss_properties, args=(access_token, subscription_id))
    vmss_thread.start()

    # Loop until the user clicks the close button.
    done = False
    clock = pygame.time.Clock()
    pygame.key.set_repeat(1, 2)  # keyboard monitoring [pause before repeat, repeats/sec]

    while not done:
        screen.blit(background, [0, 0])
        # set how many times per second to run the loop - if you reduce this value, then reduce clickLoopCount
        # reduce it too low and clicking on things becomes less responsive
        clock.tick(20)
        mousepos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            elif event.type == pygame.MOUSEBUTTONDOWN and pygame.mouse.get_pressed()[0]:
                process_click(event.pos, access_token)

        # refresh screen if VMSS and VM details are available
        if len(vmssProperties) > 0:
            draw_vmss()
        if len(vmssVmProperties) > 0:
            draw_vmssvms()

        # loop counters to show transient messages for a few moments
        if showScaleIn == True:
            clickLoopCount -= 1
            if clickLoopCount < 1:
                showScaleIn = False

        if showScaleOut == True:
            clickLoopCount -= 1
            if clickLoopCount < 1:
                showScaleOut = False

        # update display
        pygame.display.flip()

        # renew Azure access token before timeout (600 secs), then reset timer
        if int(start_time - time.time()) > 600:
            access_token = azurerm.get_access_token(tenant_id, app_id, app_secret)
            start_time = time.time()

    pygame.quit()


if __name__ == "__main__":
    main()
