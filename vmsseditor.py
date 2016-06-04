# VMSS test - program to test VMSS class
"""
Copyright (c) 2016, Guy Bowerman
Description: Graphical dashboard to show and set Azure VM Scale Set properties
License: MIT (see LICENSE.txt file for details)
"""

import azurerm
import json
import sys
import threading
import time
import tkinter as tk
import vmss
import subscription

# Load Azure app defaults
try:
    with open('vmssconfig.json') as configFile:
        configData = json.load(configFile)
except FileNotFoundError:
    print("Error: Expecting vmssconfig.json in current folder")
    sys.exit()

sub = subscription.subscription(configData['tenantId'], configData['appId'], configData['appSecret'], configData['subscriptionId'])
current_vmss = None

# vmss property containers
vmss_properties = dict()
ud0_list = []
ud1_list = []
ud2_list = []
ud3_list = []
ud4_list = []

# thread to keep access token alive
def subidkeepalive():
    while True:
        time.sleep(2000)
        sub.auth()
        current_vmss.update_token(sub.access_token)


# start timer thread
timer_thread = threading.Thread(target=subidkeepalive, args=())
timer_thread.start()

def get_power_state(statuses):
    for status in statuses:
        if status['code'].startswith('Power'):
            return status['code'][11:]


# draw a heat map for the VMSS VMs
# to do: find a more pythonic way to represent 5 sets of UDs and associated variables
def draw_vms(vmssinstances):
    global ud0_list
    global ud1_list
    global ud2_list
    global ud3_list
    global ud4_list
    xdelta0 = 0
    xdelta1 = 0
    xdelta2 = 0
    xdelta3 = 0
    xdelta4 = 0
    x1 = 20
    x2 = 30
    vmcanvas.delete("all")
    del ud0_list[:]
    del ud1_list[:]
    del ud2_list[:]
    del ud3_list[:]
    del ud4_list[:]
    for instance in vmssinstances['value']:
        try:
            ud = instance['properties']['instanceView']['platformUpdateDomain']
            powerstate = get_power_state(instance['properties']['instanceView']['statuses'])
        except KeyError:
            continue
        if powerstate == 'running':
            statuscolor = 'green'
        elif powerstate == 'stopped' or powerstate == 'deallocated':
            statuscolor = 'red'
        else:
            statuscolor = 'orange'
        if ud == 0:
            ud0_list.append(instance)
            vmcanvas.create_oval(x1 + xdelta0, 15, x2 + xdelta0, 25, fill=statuscolor)
            xdelta0 += 15
        elif ud == 1:
            ud1_list.append(instance)
            vmcanvas.create_oval(x1 + xdelta1, 30, x2 + xdelta1, 40, fill=statuscolor)
            xdelta1 += 15
        elif ud == 2:
            ud2_list.append(instance)
            vmcanvas.create_oval(x1 + xdelta2, 45, x2 + xdelta2, 55, fill=statuscolor)
            xdelta2 += 15
        elif ud == 3:
            ud3_list.append(instance)
            vmcanvas.create_oval(x1 + xdelta3, 60, x2 + xdelta3, 70, fill=statuscolor)
            xdelta3 += 15
        elif ud == 4:
            ud4_list.append(instance)
            vmcanvas.create_oval(x1 + xdelta4, 75, x2 + xdelta4, 85, fill=statuscolor)
            xdelta4 += 15

def getuds():
    ud = selectedud.get()
    udinstancelist = []
    # build list of UDs
    if ud == '0':
        for instance in ud0_list:
            udinstancelist.append(instance['instanceId'])
    elif ud == '1':
        for instance in ud1_list:
            udinstancelist.append(instance['instanceId'])
    elif ud == '2':
        for instance in ud2_list:
            udinstancelist.append(instance['instanceId'])
    elif ud == '3':
        for instance in ud3_list:
            udinstancelist.append(instance['instanceId'])
    elif ud == '4':
        for instance in ud4_list:
            udinstancelist.append(instance['instanceId'])
    return udinstancelist


def startud():
    vmssname = current_vmss.name
    udinstancelist = getuds()
    result = azurerm.start_vmss_vms(current_vmss.access_token, current_vmss.sub_id, current_vmss.rgname, vmssname, json.dumps(udinstancelist))
    statusmsg(result)


def powerud():
    vmssname = current_vmss.name
    udinstancelist = getuds()
    result = azurerm.poweroff_vmss_vms(current_vmss.access_token, current_vmss.sub_id, current_vmss.rgname, vmssname,
                                       json.dumps(udinstancelist))
    statusmsg(result)


def upgradeud():
    vmssname = current_vmss.name
    udinstancelist = getuds()
    result = azurerm.upgrade_vmss_vms(current_vmss.access_token, current_vmss.sub_id, current_vmss.rgname, vmssname,
                                      json.dumps(udinstancelist))
    statusmsg(result)


def reimagevm():
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.reimagevm(vmstring)
    statusmsg(current_vmss.status)

def upgradevm():
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.upgradevm(vmstring)
    statusmsg(current_vmss.status)

def deletevm():
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.deletevm(vmstring)
    statusmsg(current_vmss.status)

# begin tkinter components
btnwidth = 10
btnwidthud = 10
root = tk.Tk()  # Makes the window
root.wm_title("VM Scale Set Editor")
root.geometry('350x350')
root.wm_iconbitmap('vm.ico')
topframe = tk.Frame(root)
middleframe = tk.Frame(root)
udframe = tk.Frame(root)
selectedud = tk.StringVar()
heatmaplabel = tk.Label(middleframe, text='VM Heatmap', width=45, anchor=tk.W)
vmcanvas = tk.Canvas(middleframe, height=100, width=350)
vmframe = tk.Frame(root)
baseframe = tk.Frame(root)
topframe.pack()
middleframe.pack()
udframe.pack()
# UD operations - UD frame
udlabel = tk.Label(udframe, text='UD:')
udoption = tk.OptionMenu(udframe, selectedud, '0', '1', '2', '3', '4')
upgradebtm = tk.Button(udframe, text='Upgrade', command=upgradeud, width=btnwidthud)
startbtmud = tk.Button(udframe, text='Start', command=startud, width=btnwidthud)
powerbtmud = tk.Button(udframe, text='Power off', command=powerud, width=btnwidthud)
# VM operations - VM frame
vmlabel = tk.Label(vmframe, text='VM:')
vmtext = tk.Entry(vmframe, width=7)
reimagebtn = tk.Button(vmframe, text='Reimage', command=reimagevm, width=btnwidthud)
vmupgradebtn = tk.Button(vmframe, text='Upgrade', command=upgradevm, width=btnwidthud)
vmdeletebtn = tk.Button(vmframe, text='Delete', command=deletevm, width=btnwidthud)
vmframe.pack()

baseframe.pack()
#vmsstext = tk.Entry(topframe, width=20)
versiontext = tk.Entry(topframe, width=btnwidth)
capacitytext = tk.Entry(topframe, width=btnwidth)
statustext = tk.Text(baseframe, height=1, width=40)

def statusmsg(statusstring):
    if statustext.get(1.0, tk.END):
        statustext.delete(1.0, tk.END)
    statustext.insert(tk.END, statusstring)


def displayvmss(vmssname):
    global current_vmss
    current_vmss = vmss.vmss(vmssname, sub.vmssdict[vmssname], sub.sub_id, sub.access_token)
    # capacity - row 0
    tk.Label(topframe, text='VMs').grid(row=0, column=2, sticky=tk.W)
    capacitytext.grid(row=0, column=1, sticky=tk.W)
    capacitytext.delete(0, tk.END)
    capacitytext.insert(0, str(current_vmss.capacity))
    scalebtn = tk.Button(topframe, text="Scale", command=scalevmss, width=btnwidth)
    scalebtn.grid(row=0, column=3, sticky=tk.W)
    # VMSS properties - row 2
    sizelabel = tk.Label(topframe, text=current_vmss.vmsize)
    locationlabel = tk.Label(topframe, text=current_vmss.location)
    offerlabel = tk.Label(topframe, text=current_vmss.offer)
    sizelabel.grid(row=2, column=0, sticky=tk.W)
    offerlabel.grid(row=2, column=1, sticky=tk.W)
    locationlabel.grid(row=2, column=2, sticky=tk.W)
    # OS version - row 3
    skulabel = tk.Label(topframe, text=current_vmss.sku)
    skulabel.grid(row=3, column=0, sticky=tk.W)
    versiontext.grid(row=3, column=1, sticky=tk.W)
    versiontext.delete(0, tk.END)
    versiontext.insert(0, current_vmss.version)
    updatebtn = tk.Button(topframe, text='Update model', command=updatevmss, width=btnwidth)
    updatebtn.grid(row=3, column=2, sticky=tk.W)
    # vmss operations - row 4
    onbtn = tk.Button(topframe, text="Start", command=poweronvmss, width=btnwidth)
    onbtn.grid(row=4, column=0, sticky=tk.W)
    offbtn = tk.Button(topframe, text="Power off", command=poweroffvmss, width=btnwidth)
    offbtn.grid(row=4, column=1, sticky=tk.W)
    deallocbtn = tk.Button(topframe, text="Stop Dealloc", command=deallocvmss, width=btnwidth)
    deallocbtn.grid(row=4, column=2, sticky=tk.W)
    detailsbtn = tk.Button(topframe, text="Details", command=vmssdetails, width=btnwidth)
    detailsbtn.grid(row=4, column=3, sticky=tk.W)
    # status line
    statustext.pack()
    statusmsg(current_vmss.status)

def scalevmss():
    newcapacity = capacitytext.get()
    current_vmss.scale(newcapacity)
    statusmsg(current_vmss.status)
    #displayvmss()

def updatevmss():
    newversion = versiontext.get()
    current_vmss.update_version(newversion)
    statusmsg(current_vmss.status)

def poweronvmss():
    current_vmss.poweron()
    statusmsg(current_vmss.status)

def poweroffvmss():
    current_vmss.poweroff()
    statusmsg(current_vmss.status)

def deallocvmss():
    current_vmss.stopdealloc()
    statusmsg(current_vmss.status)

def vmssdetails():
    # VMSS VM canvas - middle frame
    heatmaplabel.pack()
    vmcanvas.pack()
    current_vmss.init_vm_instance_view()
    draw_vms(current_vmss.vm_instance_view)
    udlabel.grid(row=0, column=0, sticky=tk.W)
    udoption.grid(row=0, column=1, sticky=tk.W)
    upgradebtm.grid(row=0, column=2, sticky=tk.W)
    startbtmud.grid(row=0, column=3, sticky=tk.W)
    powerbtmud.grid(row=0, column=4, sticky=tk.W)
    vmlabel.grid(row=0, column=0, sticky=tk.W)
    vmtext.grid(row=0, column=1, sticky=tk.W)
    reimagebtn.grid(row=0, column=2, sticky=tk.W)
    vmupgradebtn.grid(row=0, column=3, sticky=tk.W)
    vmdeletebtn.grid(row=0, column=4, sticky=tk.W)
    root.mainloop()


# start by listing VM Scale Sets
vmsslist = sub.get_vmss_list()
selectedvmss = tk.StringVar()
selectedvmss.set(vmsslist[0])
selectedud.set('0')
displayvmss(vmsslist[0])

# create GUI components

# VMSS picker - row 0
vmsslistoption = tk.OptionMenu(topframe, selectedvmss, *vmsslist, command=displayvmss)
vmsslistoption.grid(row=0, column=0, sticky=tk.W)

root.mainloop()