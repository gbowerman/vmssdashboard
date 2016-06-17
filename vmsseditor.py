# VMSS test - program to test VMSS class
"""
Copyright (c) 2016, Guy Bowerman
Description: Graphical dashboard to show and set Azure VM Scale Set properties
License: MIT (see LICENSE.txt file for details)
"""

import json
import sys
import threading
import time
import tkinter as tk

import subscription
import vmss

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

# start timer thread
timer_thread = threading.Thread(target=subidkeepalive, args=())
timer_thread.start()

# start refresh thread
refresh_thread = threading.Thread(target=refresh_loop, args=())
refresh_thread.start()


def assign_color_to_power_state(powerstate):
    if powerstate == 'running':
        return 'green'
    elif powerstate == 'stopped' or powerstate == 'deallocated':
        return 'red'
    else:
        return 'orange'


# draw a heat map for the VMSS VMs - uses the set_domain_lists() functon from the vmss class
def draw_vms(vmssinstances):
    ydelta = 0
    xdelta = 0
    xval = 20
    yval = 10
    diameter = 15
    vmcanvas.delete("all")
    # current_vmss.clear_domain_lists()
    current_vmss.set_domain_lists()
    for faultdomain in range(5):
        for entry in current_vmss.fd_dict[faultdomain]:
            instance_id = entry[0]
            powerstate = entry[1]
            statuscolor = assign_color_to_power_state(powerstate)
            # colored circle represents machine power state
            vmcanvas.create_oval(xval + xdelta, yval, xval + xdelta + diameter, yval + diameter, fill=statuscolor)
            # print VM ID under each circle
            vmcanvas.create_text(xval + xdelta + 7, yval + 22, text=instance_id)
            xdelta += 20
        xdelta = 0
        yval += 30


def getuds():
    ud = int(selectedud.get())
    udinstancelist = []
    # print(json.dumps(current_vmss.ud_dict))
    for entry in current_vmss.ud_dict[ud]:
        udinstancelist.append(entry[0])  # entry[0] is the instance id
    # build list of UDs
    return udinstancelist


def startud():
    global refresh_thread_running
    udinstancelist = getuds()
    current_vmss.startvm(json.dumps(udinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def powerud():
    global refresh_thread_running
    udinstancelist = getuds()
    current_vmss.poweroffvm(json.dumps(udinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def upgradeud():
    global refresh_thread_running
    udinstancelist = getuds()
    current_vmss.upgradevm(json.dumps(udinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


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
btnwidth = 12
btnwidthud = 12
root = tk.Tk()  # Makes the window
root.wm_title("VM Scale Set Editor")
root.geometry('420x410')
root.wm_iconbitmap('vm.ico')
topframe = tk.Frame(root)
middleframe = tk.Frame(root)
udframe = tk.Frame(root)
selectedud = tk.StringVar()
heatmaplabel = tk.Label(middleframe, text='VM Heatmap - 1 row = 1 FD', width=55, anchor=tk.W)
vmcanvas = tk.Canvas(middleframe, height=170, width=420)
vmframe = tk.Frame(root)
baseframe = tk.Frame(root)
topframe.pack()
middleframe.pack()
udframe.pack()
# UD operations - UD frame
udlabel = tk.Label(udframe, text='UD:')
udoption = tk.OptionMenu(udframe, selectedud, '0', '1', '2', '3', '4')
udoption.config(width=9)
upgradebtm = tk.Button(udframe, text='Upgrade', command=upgradeud, width=btnwidthud)
startbtmud = tk.Button(udframe, text='Start', command=startud, width=btnwidthud)
powerbtmud = tk.Button(udframe, text='Power off', command=powerud, width=btnwidthud)
# VM operations - VM frame
vmlabel = tk.Label(vmframe, text='VM:')
vmtext = tk.Entry(vmframe, width=15)
reimagebtn = tk.Button(vmframe, text='Reimage', command=reimagevm, width=btnwidthud)
vmupgradebtn = tk.Button(vmframe, text='Upgrade', command=upgradevm, width=btnwidthud)
vmdeletebtn = tk.Button(vmframe, text='Delete', command=deletevm, width=btnwidthud)
vmstartbtn = tk.Button(vmframe, text='Start', command=startvm, width=btnwidthud)
vmrestartbtn = tk.Button(vmframe, text='Restart', command=restartvm, width=btnwidthud)
vmdeallocbtn = tk.Button(vmframe, text='Dealloc', command=deallocvm, width=btnwidthud)
vmpoweroffbtn = tk.Button(vmframe, text='Power off', command=poweroffvm, width=btnwidthud)
vmframe.pack()

baseframe.pack()

versiontext = tk.Entry(topframe, width=btnwidth)
capacitytext = tk.Entry(topframe, width=btnwidth)
statustext = tk.Text(baseframe, height=1, width=50)


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
    sizelabel = tk.Label(topframe, text=current_vmss.vmsize, width=btnwidth, justify=tk.LEFT)
    locationlabel = tk.Label(topframe, text=current_vmss.location, width=btnwidth, justify=tk.LEFT)
    offerlabel = tk.Label(topframe, text=current_vmss.offer, width=btnwidth, justify=tk.LEFT)
    sizelabel.grid(row=2, column=0, sticky=tk.W)
    offerlabel.grid(row=2, column=1, sticky=tk.W)
    locationlabel.grid(row=2, column=2, sticky=tk.W)
    # OS version - row 3
    skulabel = tk.Label(topframe, text=current_vmss.sku, width=btnwidth, justify=tk.LEFT)
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
    global refresh_thread_running
    newcapacity = int(capacitytext.get())
    current_vmss.scale(newcapacity)
    statusmsg(current_vmss.status)
    refresh_thread_running = True
    # displayvmss()


def updatevmss():
    global refresh_thread_running
    newversion = versiontext.get()
    current_vmss.update_version(newversion)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def poweronvmss():
    global refresh_thread_running
    current_vmss.poweron()
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
    vmstartbtn.grid(row=1, column=1, sticky=tk.W)
    vmrestartbtn.grid(row=1, column=2, sticky=tk.W)
    vmpoweroffbtn.grid(row=1, column=3, sticky=tk.W)
    vmdeallocbtn.grid(row=1, column=4, sticky=tk.W)
    statusmsg(current_vmss.status)

# start by listing VM Scale Sets
vmsslist = sub.get_vmss_list()
selectedvmss = tk.StringVar()
selectedvmss.set(vmsslist[0])
selectedud.set('0')
displayvmss(vmsslist[0])

# create GUI components

# VMSS picker - row 0
vmsslistoption = tk.OptionMenu(topframe, selectedvmss, *vmsslist, command=displayvmss)
vmsslistoption.config(width=9)
vmsslistoption.grid(row=0, column=0, sticky=tk.W)

root.mainloop()
