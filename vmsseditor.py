# VMSS Editor - Azure VM Scale Set management tool
# vmsseditor.py - GUI component of Rolling Upgrade, tkinter based
#  - uses vmss.py and subscription.py classes for Azure operations
"""
Copyright (c) 2016, Guy Bowerman
Description: Graphical dashboard to show and set Azure VM Scale Set properties
License: MIT (see LICENSE.txt file for details)
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import subscription
import vmss

# size and color defaults
btnwidth = 14
entrywidth = 15
if os.name == 'mac':
    geometry1 = '740x328'
    geometry2 = '740x640'
else:
    geometry1 = '540x128'
    geometry2 = '540x440'
frame_bgcolor = '#B0E0E6'
canvas_bgcolor = '#F0FFFF'
btncolor = '#F8F8FF'

# Load Azure app defaults
try:
    with open('vmssconfig.json') as configFile:
        configData = json.load(configFile)
except FileNotFoundError:
    print("Error: Expecting vmssconfig.json in current folder")
    sys.exit()

sub = subscription.subscription(configData['tenantId'], configData['appId'], configData['appSecret'],
                                configData['subscriptionId'])
current_vmss = None
refresh_thread_running = False

# thread to keep access token alive
def subidkeepalive():
    while True:
        time.sleep(2000)
        sub.auth()
        current_vmss.update_token(sub.access_token)

# thread to refresh details until provisioning is complete
def refresh_loop():
    global refresh_thread_running
    while True:
        while (refresh_thread_running == True):
            current_vmss.refresh_model()
            if current_vmss.status == 'Succeeded' or current_vmss.status == 'Failed':
                refresh_thread_running = False
            time.sleep(10)
            vmssdetails()
        time.sleep(10)

# rolling upgrade thread
def rolling_upgrade_engine(batchsize, pausetime, vmbyfd_list):
    global refresh_thread_running
    # loop through all VMs
    num_vms_to_upgrade = len(vmbyfd_list)
    upgrade_index = 0 # running count of VMs updated or in batch to update
    while upgrade_index < num_vms_to_upgrade:
        # determine the next batch of VM IDs
        batch_list = []
        for batch_index in range(batchsize):
            batch_list.append(vmbyfd_list[upgrade_index][0])
            upgrade_index += 1
            if upgrade_index == num_vms_to_upgrade:
                break

        # do an upgrade on the batch
        print('Upgrading batch')
        current_vmss.upgradevm(json.dumps(batch_list))
        statusmsg(current_vmss.status)
        refresh_thread_running = True

        # wait for upgrade to complete
        print('Starting refresh wait')
        while (refresh_thread_running == True):
            time.sleep(1)
        print('Batch complete')
        # wait for pausetime
        time.sleep(pausetime)

# start timer thread
timer_thread = threading.Thread(target=subidkeepalive, args=())
timer_thread.daemon = True
timer_thread.start()

# start refresh thread
refresh_thread = threading.Thread(target=refresh_loop, args=())
refresh_thread.daemon = True
refresh_thread.start()


def assign_color_to_power_state(powerstate):
    if powerstate == 'running':
        return 'green'
    elif powerstate == 'stopped':
        return 'red'
    elif powerstate == 'starting':
        return 'yellow'
    elif powerstate == 'stopping':
        return 'orange'
    elif powerstate == 'deallocating':
        return 'grey'
    elif powerstate == 'deallocated':
        return 'black'
    else: # unknown
        return 'blue'

# draw a grid to delineate fault domains and update domains on the VMSS heatmap
def draw_grid():
    vmcanvas.delete("all")
    # horizontal lines for UDs
    for y in range(4):
        ydelta = y * 35
        vmcanvas.create_text(15, ydelta + 30, text='UD ' + str(y))
        vmcanvas.create_line(35, 50 + ydelta, 520, 50 + ydelta)
    vmcanvas.create_text(15, 170, text='UD 4')

    # vertical lines for FDs
    for x in range(4):
        xdelta = x * 100
        vmcanvas.create_text(45 + xdelta, 10, text='FD ' + str(x))
        vmcanvas.create_line(132 + xdelta, 20, 132 + xdelta, 180, dash=(4, 2))
    vmcanvas.create_text(445, 10, text='FD 4')

# draw a heat map for the VMSS VMs - uses the set_domain_lists() function from the vmss class
def draw_vms(vmssinstances):
    xval = 35
    yval = 20
    diameter = 15
    draw_grid()
    # current_vmss.clear_domain_lists()
    current_vmss.set_domain_lists()
    matrix = [[0 for x in range(5)] for y in range(5)]
    for vm in current_vmss.vm_list:
        instance_id = vm[0]
        fd = vm[1]
        ud = vm[2]
        powerstate = vm[3]
        statuscolor = assign_color_to_power_state(powerstate)
        xdelta = (fd * 100) + (matrix[ud][fd] * 20)
        ydelta = ud * 35
        # colored circle represents machine power state
        vmcanvas.create_oval(xval + xdelta, yval + ydelta, xval + xdelta + diameter, yval + ydelta + diameter, fill=statuscolor)
        # print VM ID under each circle
        vmcanvas.create_text(xval + xdelta + 7, yval + ydelta + 22, text=instance_id)
        matrix[ud][fd] += 1


def getfds():
    fd = int(selectedfd.get())
    fdinstancelist = []
    # print(json.dumps(current_vmss.fd_dict))
    for entry in current_vmss.fd_dict[fd]:
        fdinstancelist.append(entry[0])  # entry[0] is the instance id
    # build list of UDs
    return fdinstancelist


def startfd():
    global refresh_thread_running
    fdinstancelist = getfds()
    current_vmss.startvm(json.dumps(fdinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def powerfd():
    global refresh_thread_running
    fdinstancelist = getfds()
    current_vmss.poweroffvm(json.dumps(fdinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def reimagefd():
    global refresh_thread_running
    fdinstancelist = getfds()
    current_vmss.reimagevm(json.dumps(fdinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def upgradefd():
    global refresh_thread_running
    fdinstancelist = getfds()
    current_vmss.upgradevm(json.dumps(fdinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def rollingupgrade():
    batchsize = int(batchtext.get())
    pausetime = int(pausetext.get())

    # get list of VMs ordered by FD - get this by concatenating the vmss fd_dict into a single list
    vmbyfd_list = []
    for fdval in range(5):
        vmbyfd_list += current_vmss.fd_dict[fdval]
    num_vms_to_upgrade = len(vmbyfd_list) # should be the same of vmss capacity if starting in consistent state

    # launch rolling update thread
    rolling_upgrade_thread = threading.Thread(target=rolling_upgrade_engine, args=(batchsize, pausetime, vmbyfd_list,))
    rolling_upgrade_thread.daemon = True
    rolling_upgrade_thread.start()


def reimagevm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.reimagevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def upgradevm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.upgradevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deletevm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.deletevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def startvm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.startvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def restartvm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.restartvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deallocvm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.deallocvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def poweroffvm():
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.poweroffvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


# begin tkinter components
root = tk.Tk()  # Makes the window
root.wm_title("Azure VM Scale Set Editor")
root.geometry(geometry1)
root.configure(background = frame_bgcolor)
root.wm_iconbitmap('vmss.ico')
topframe = tk.Frame(root, bg = frame_bgcolor)
middleframe = tk.Frame(root, bg = frame_bgcolor)
selectedfd = tk.StringVar()
vmcanvas = tk.Canvas(middleframe, height=195, width=530, bg = canvas_bgcolor)
vmframe = tk.Frame(root, bg = frame_bgcolor)
baseframe = tk.Frame(root, bg = frame_bgcolor)
topframe.pack(fill=tk.X)
middleframe.pack(fill=tk.X)

# Rolling upgrade operations - VM frame
batchsizelabel= tk.Label(vmframe, text='Batch size:', bg = frame_bgcolor)
batchtext = tk.Entry(vmframe, width=11, bg = canvas_bgcolor)
batchtext.delete(0, tk.END)
batchtext.insert(0, '1')
pausetimelabel= tk.Label(vmframe, text='Pause time:', bg = frame_bgcolor)
pausetext = tk.Entry(vmframe, width=11, bg = canvas_bgcolor)
pausetext.delete(0, tk.END)
pausetext.insert(0, '0')
rollingbtn = tk.Button(vmframe, text='Rolling upgrade', command=rollingupgrade, width=btnwidth, bg = btncolor)

# FD operations - VM frame
fdlabel = tk.Label(vmframe, text='FD:', bg = frame_bgcolor)
fdoption = tk.OptionMenu(vmframe, selectedfd, '0', '1', '2', '3', '4')
fdoption.config(width=6, bg = btncolor, activebackground = btncolor)
fdoption["menu"].config(bg=btncolor)
reimagebtnfd = tk.Button(vmframe, text='Reimage', command=reimagefd, width=btnwidth, bg = btncolor)
upgradebtnfd = tk.Button(vmframe, text='Upgrade', command=upgradefd, width=btnwidth, bg = btncolor)
startbtnfd = tk.Button(vmframe, text='Start', command=startfd, width=btnwidth, bg = btncolor)
powerbtnfd = tk.Button(vmframe, text='Power off', command=powerfd, width=btnwidth, bg = btncolor)

# VM operations - VM frame
vmlabel = tk.Label(vmframe, text='VM:', bg = frame_bgcolor)
vmtext = tk.Entry(vmframe, width=11, bg = canvas_bgcolor)
reimagebtn = tk.Button(vmframe, text='Reimage', command=reimagevm, width=btnwidth, bg = btncolor)
vmupgradebtn = tk.Button(vmframe, text='Upgrade', command=upgradevm, width=btnwidth, bg = btncolor)
vmdeletebtn = tk.Button(vmframe, text='Delete', command=deletevm, width=btnwidth, bg = btncolor)
vmstartbtn = tk.Button(vmframe, text='Start', command=startvm, width=btnwidth, bg = btncolor)
vmrestartbtn = tk.Button(vmframe, text='Restart', command=restartvm, width=btnwidth, bg = btncolor)
vmdeallocbtn = tk.Button(vmframe, text='Dealloc', command=deallocvm, width=btnwidth, bg = btncolor)
vmpoweroffbtn = tk.Button(vmframe, text='Power off', command=poweroffvm, width=btnwidth, bg = btncolor)
vmframe.pack(fill=tk.X)
baseframe.pack(fill=tk.X)

versiontext = tk.Entry(topframe, width=entrywidth, bg = canvas_bgcolor)
capacitytext = tk.Entry(topframe, width=entrywidth, bg = canvas_bgcolor)
vmsizetext = tk.Entry(topframe, width=entrywidth, bg = canvas_bgcolor)
statustext = tk.Text(baseframe, height=1, width=67, bg = canvas_bgcolor)


def statusmsg(statusstring):
    if statustext.get(1.0, tk.END):
        statustext.delete(1.0, tk.END)
    statustext.insert(tk.END, statusstring)


def displayvmss(vmssname):
    global current_vmss
    current_vmss = vmss.vmss(vmssname, sub.vmssdict[vmssname], sub.sub_id, sub.access_token)
    # capacity - row 0
    locationlabel = tk.Label(topframe, text=current_vmss.location, width=btnwidth, justify=tk.LEFT, bg = frame_bgcolor)
    locationlabel.grid(row=0, column=1, sticky=tk.W)
    tk.Label(topframe, text='Capacity: ', bg = frame_bgcolor).grid(row=0, column=2)
    capacitytext.grid(row=0, column=3, sticky=tk.W)
    capacitytext.delete(0, tk.END)
    capacitytext.insert(0, str(current_vmss.capacity))
    scalebtn = tk.Button(topframe, text="Scale", command=scalevmss, width=btnwidth, bg = btncolor)
    scalebtn.grid(row=0, column=4, sticky=tk.W)

    # VMSS properties - row 1
    vmsizetext.grid(row=1, column=3, sticky=tk.W)
    vmsizetext.delete(0, tk.END)
    vmsizetext.insert(0, str(current_vmss.vmsize))
    vmsizetext.grid(row=1, column=0, sticky=tk.W)
    offerlabel = tk.Label(topframe, text=current_vmss.offer, width=btnwidth, justify=tk.LEFT, bg = frame_bgcolor)
    offerlabel.grid(row=1, column=1, sticky=tk.W)
    skulabel = tk.Label(topframe, text=current_vmss.sku, width=btnwidth, justify=tk.LEFT, bg = frame_bgcolor)
    skulabel.grid(row=1, column=2, sticky=tk.W)
    versiontext.grid(row=1, column=3, sticky=tk.W)
    versiontext.delete(0, tk.END)
    versiontext.insert(0, current_vmss.version)
    updatebtn = tk.Button(topframe, text='Update model', command=updatevmss, width=btnwidth, bg = btncolor)
    updatebtn.grid(row=1, column=4, sticky=tk.W)

    # more VMSS properties - row 2
    if current_vmss.overprovision == True:
        optext = "overprovision: true"
    else:
        optext = "overprovision: false"
    overprovisionlabel = tk.Label(topframe, text=optext, width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    overprovisionlabel.grid(row=2, column=0, sticky=tk.W)
    upgradepolicylabel = tk.Label(topframe, text=current_vmss.upgradepolicy + ' upgrade', width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    upgradepolicylabel.grid(row=2, column=1, sticky=tk.W)
    adminuserlabel = tk.Label(topframe, text=current_vmss.adminuser, width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    adminuserlabel.grid(row=2, column=2, sticky=tk.W)
    compnameprefixlabel = tk.Label(topframe, text='Prefix: ' + current_vmss.nameprefix, width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    compnameprefixlabel.grid(row=2, column=3, sticky=tk.W)

    # vmss operations - row 3
    onbtn = tk.Button(topframe, text="Start", command=poweronvmss, width=btnwidth, bg = btncolor)
    onbtn.grid(row=3, column=0, sticky=tk.W)
    onbtn = tk.Button(topframe, text="Restart", command=restartvmss, width=btnwidth, bg = btncolor)
    onbtn.grid(row=3, column=1, sticky=tk.W)
    offbtn = tk.Button(topframe, text="Power off", command=poweroffvmss, width=btnwidth, bg = btncolor)
    offbtn.grid(row=3, column=2, sticky=tk.W)
    deallocbtn = tk.Button(topframe, text="Stop Dealloc", command=deallocvmss, width=btnwidth, bg = btncolor)
    deallocbtn.grid(row=3, column=3, sticky=tk.W)
    detailsbtn = tk.Button(topframe, text="Show Details", command=vmssdetails, width=btnwidth, bg = btncolor)
    detailsbtn.grid(row=3, column=4, sticky=tk.W)

    # status line
    statustext.pack()
    statusmsg(current_vmss.status)


def scalevmss():
    global refresh_thread_running
    newcapacity = int(capacitytext.get())
    current_vmss.scale(newcapacity)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def updatevmss():
    global refresh_thread_running
    newversion = versiontext.get()
    newvmsize = vmsizetext.get()
    current_vmss.update_model(newversion, newvmsize)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def poweronvmss():
    global refresh_thread_running
    current_vmss.poweron()
    statusmsg(current_vmss.status)
    refresh_thread_running = True

def restartvmss():
    global refresh_thread_running
    current_vmss.restart()
    statusmsg(current_vmss.status)
    refresh_thread_running = True

def poweroffvmss():
    global refresh_thread_running
    current_vmss.poweroff()
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deallocvmss():
    global refresh_thread_running
    current_vmss.dealloc()
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def vmssdetails():
    # VMSS VM canvas - middle frame
    root.geometry(geometry2)
    vmcanvas.pack()
    current_vmss.init_vm_instance_view()
    draw_vms(current_vmss.vm_instance_view)

    # draw rollingframe components
    batchsizelabel.grid(row=0, column=1, sticky=tk.W)
    batchtext.grid(row=0, column=2, sticky=tk.W)
    pausetimelabel.grid(row=0, column=3, sticky=tk.W)
    pausetext.grid(row=0, column=4, sticky=tk.W)
    rollingbtn.grid(row=0, column=5, sticky=tk.W)

    # draw VM frame components
    fdlabel.grid(row=1, column=0, sticky=tk.W)
    fdoption.grid(row=1, column=1, sticky=tk.W)
    reimagebtnfd.grid(row=1, column=2, sticky=tk.W)
    upgradebtnfd.grid(row=1, column=3, sticky=tk.W)
    startbtnfd.grid(row=1, column=4, sticky=tk.W)
    powerbtnfd.grid(row=1, column=5, sticky=tk.W)
    vmlabel.grid(row=2, column=0, sticky=tk.W)
    vmtext.grid(row=2, column=1, sticky=tk.W)
    reimagebtn.grid(row=2, column=2, sticky=tk.W)
    vmupgradebtn.grid(row=2, column=3, sticky=tk.W)
    vmstartbtn.grid(row=2, column=4, sticky=tk.W)
    vmpoweroffbtn.grid(row=2, column=5, sticky=tk.W)
    vmdeletebtn.grid(row=3, column=2, sticky=tk.W)
    vmrestartbtn.grid(row=3, column=3, sticky=tk.W)
    vmdeallocbtn.grid(row=3, column=4, sticky=tk.W)

    # draw status frame
    statusmsg(current_vmss.status)

# start by listing VM Scale Sets
vmsslist = sub.get_vmss_list()
selectedvmss = tk.StringVar()
if len(vmsslist) > 0:
    selectedvmss.set(vmsslist[0])
    selectedfd.set('0')
    displayvmss(vmsslist[0])
    # create top level GUI components
    vmsslistoption = tk.OptionMenu(topframe, selectedvmss, *vmsslist, command=displayvmss)
    vmsslistoption.config(width=8, bg = btncolor, activebackground = btncolor)
    vmsslistoption["menu"].config(bg=btncolor)
    vmsslistoption.grid(row=0, column=0, sticky=tk.W)
else:
    messagebox.showwarning("Warning", "Your subscription:\n" + sub.sub_id + "\ncontains no VM Scale Sets")

root.mainloop()
