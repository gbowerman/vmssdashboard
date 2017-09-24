'''VMSS Zones - tool to visualize multi-zone scale sets'''

import json
import os
import sys
import threading
import tkinter as tk
from time import sleep, strftime
from tkinter import messagebox

import subscription
import vmssz

# size and color defaults
btnwidth = 14
entrywidth = 15
if os.name == 'posix':  # Mac OS
    geometry1 = '700x140'
    geometry100 = '700x450'
    geometry_wide = '1500x450'
    list_width = 14
    status_width = 98
    canvas_width100 = 690
    canvas_width1000 = 1300
else:
    geometry1 = '540x128'
    geometry100 = '540x410'
    geometry_wide = '1230x410'
    list_width = 8
    status_width = 67
    canvas_width100 = 520
    canvas_width1000 = 1230

canvas_height100 = 195
canvas_height1000 = 700
frame_bgcolor = '#B0E0E6'
canvas_bgcolor = '#F0FFFF'
btncolor = '#F8F8FF'

# Load Azure app defaults
try:
    with open('vmssconfig.json') as configFile:
        config_data = json.load(configFile)
except FileNotFoundError:
    sys.exit('Error: Expecting vmssconfig.json in current folder')

sub = subscription.subscription(config_data['tenantId'], config_data['appId'],
                                config_data['appSecret'], config_data['subscriptionId'])
current_vmss = None
refresh_thread_running = False

def subidkeepalive():
    '''thread to keep access token alive'''
    while True:
        sleep(2000)
        sub.auth()
        current_vmss.update_token(sub.access_token)

def refresh_loop():
    '''thread to refresh details until provisioning is complete'''
    global refresh_thread_running
    sleep_time = 5
    while True:
        while refresh_thread_running is True:
            current_vmss.refresh_model()
            # for demoing small scale sets - dont' switch off refresh
            # if current_vmss.status == 'Succeeded' or current_vmss.status == 'Failed':
            if current_vmss.status == 'Failed':
                refresh_thread_running = False
            sleep(sleep_time)
            vmssdetails()
        sleep(sleep_time)


# start timer thread
timer_thread = threading.Thread(target=subidkeepalive, args=())
timer_thread.daemon = True
timer_thread.start()

# start refresh thread
refresh_thread = threading.Thread(target=refresh_loop, args=())
refresh_thread.daemon = True
refresh_thread.start()


def assign_color_to_power_state(powerstate):
    '''visually represent VM powerstate with a color'''
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

def draw_grid(originx, originy, row_height, ystart, zone):
    '''draw a grid to delineate zones and fault domains on the VMSS heatmap'''
    vmcanvas.create_text(originx + 180, originy + 10, text='Zone: ' + str(zone))

    # horizontal lines for FDs
    for y in range(5):
        ydelta = y * row_height
        vmcanvas.create_text(originx + 20, originy + ydelta + 50, text='FD ' + str(y))
        if y < 4:
            vmcanvas.create_line(originx + 35, originy + ystart + ydelta, originx + 390, \
                originy + ystart + ydelta)


def draw_vms():
    '''draw a heat map for the VMSS VMs'''
    xval = 55
    yval = 40
    diameter = 10
    row_height = 27
    ystart = 60
    originx = 0
    originy = 0

    vmcanvas.delete("all")
    # one rectangle for each zone
    vmcanvas.create_rectangle(0, 0, canvas_width1000/3, canvas_height100,
                              outline="#FFFACD", fill="#FFFACD")
    vmcanvas.create_rectangle(canvas_width1000/3, 0, 2*canvas_width1000/3, canvas_height100,
                              outline="#C1FFC1", fill="#C1FFC1")
    vmcanvas.create_rectangle(2*canvas_width1000/3, 0, canvas_width1000, canvas_height100,
                              outline="#fd0", fill="#fd0")
    # draw 3 'zones' on canvas
    fontsize = 5
    for zone in current_vmss.zones:
        draw_grid(originx, originy, row_height, ystart, zone['zone'])
        for zfd in zone['fds']:
            fd_id = zfd['fd']
            xinc = xval
            for vm_info in zfd['vms']:
                instance_id = vm_info['vmid']
                powerstate = vm_info['power_state']
                statuscolor = assign_color_to_power_state(powerstate)
                ydelta = int(fd_id) * 26
                # colored circle represents machine power state
                vmcanvas.create_oval(originx + xinc, originy + yval + ydelta,
                                     originx + xinc + diameter,
                                     originy + yval + ydelta + diameter, fill=statuscolor)
                # print VM ID under each circle
                vmcanvas.create_text(originx + xinc + 7, originy + yval + ydelta + 15,
                                     font=("Purisa", fontsize), text=instance_id)
                xinc += 20

        originx += canvas_width1000/3
    vmcanvas.update_idletasks() # refresh the display
    sleep(0.01) # add a little nap seems to make the display refresh more reliable

def getzones():
    '''build a list of vm ids by zone'''
    zone_num = int(selectedz.get())
    zinstancelist = []
    # loop through fds
    for fdomain in current_vmss.zones[int(zone_num)-1]['fds']:
        for vm_info in fdomain['vms']:
            zinstancelist.append(vm_info['vmid'])
    # build list of VM IDs in the zone
    return zinstancelist


def startz():
    '''start all the VMs in a fault domain'''
    global refresh_thread_running
    zinstancelist = getzones()
    current_vmss.startvm(json.dumps(zinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def powerz():
    '''power off all the VMs in a fault domain'''
    global refresh_thread_running
    zinstancelist = getzones()
    current_vmss.poweroffvm(json.dumps(zinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def reimagez():
    '''reimage all the VMs in a fault domain'''
    global refresh_thread_running
    zinstancelist = getzones()
    current_vmss.reimagevm(json.dumps(zinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def upgradez():
    '''upgrade all the VMs in a fault domain'''
    global refresh_thread_running
    zinstancelist = getzones()
    current_vmss.upgradevm(json.dumps(zinstancelist))
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def reimagevm():
    '''reimage a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.reimagevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def upgradevm():
    '''upgrade a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.upgradevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deletevm():
    '''delete a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.deletevm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def startvm():
    '''start a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.startvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def restartvm():
    '''restart a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.restartvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deallocvm():
    '''stop dealloc a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.deallocvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def poweroffvm():
    '''power off a VM or list of VMs'''
    global refresh_thread_running
    vmid = vmtext.get()
    vmstring = '["' + vmid + '"]'
    current_vmss.poweroffvm(vmstring)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


# begin tkinter components
root = tk.Tk()  # Makes the window
root.wm_title("Azure VM Scale Set Editor - Zones")
root.geometry(geometry1)
root.configure(background=frame_bgcolor)
root.wm_iconbitmap('vmss.ico')
topframe = tk.Frame(root, bg=frame_bgcolor)
middleframe = tk.Frame(root, bg=frame_bgcolor)
selectedz = tk.StringVar()
vmcanvas = tk.Canvas(middleframe, height=canvas_height100, width=canvas_width100,
                     scrollregion=(0, 0, canvas_width1000, canvas_height1000 + 110),
                     bg=canvas_bgcolor)
vbar = tk.Scrollbar(middleframe, orient=tk.VERTICAL)
vmframe = tk.Frame(root, bg=frame_bgcolor)
baseframe = tk.Frame(root, bg=frame_bgcolor)
topframe.pack(fill=tk.X)
middleframe.pack(fill=tk.X)

# Zone operations - VM frame
zlabel = tk.Label(vmframe, text='Zone:', bg=frame_bgcolor)
zoption = tk.OptionMenu(vmframe, selectedz, '1', '2', '3')
zoption.config(width=6, bg=btncolor, activebackground=btncolor)
zoption["menu"].config(bg=btncolor)
reimagebtnz = tk.Button(vmframe, text='Reimage', command=reimagez, width=btnwidth, bg=btncolor)
upgradebtnz = tk.Button(vmframe, text='Upgrade', command=upgradez, width=btnwidth, bg=btncolor)
startbtnz = tk.Button(vmframe, text='Start', command=startz, width=btnwidth, bg=btncolor)
powerbtnz = tk.Button(vmframe, text='Power off', command=powerz, width=btnwidth, bg=btncolor)

# VM operations - VM frame
vmlabel = tk.Label(vmframe, text='VM:', bg=frame_bgcolor)
vmtext = tk.Entry(vmframe, width=11, bg=canvas_bgcolor)
reimagebtn = tk.Button(vmframe, text='Reimage', command=reimagevm, width=btnwidth, bg=btncolor)
vmupgradebtn = tk.Button(vmframe, text='Upgrade', command=upgradevm, width=btnwidth, bg=btncolor)
vmdeletebtn = tk.Button(vmframe, text='Delete', command=deletevm, width=btnwidth, bg=btncolor)
vmstartbtn = tk.Button(vmframe, text='Start', command=startvm, width=btnwidth, bg=btncolor)
vmrestartbtn = tk.Button(vmframe, text='Restart', command=restartvm, width=btnwidth, bg=btncolor)
vmdeallocbtn = tk.Button(vmframe, text='Dealloc', command=deallocvm, width=btnwidth, bg=btncolor)
vmpoweroffbtn = tk.Button(vmframe, text='Power off', command=poweroffvm, width=btnwidth,
                          bg=btncolor)
vmframe.pack(fill=tk.X)
baseframe.pack(fill=tk.X)

capacitytext = tk.Entry(topframe, width=entrywidth, bg=canvas_bgcolor)
vmsizetext = tk.Entry(topframe, width=entrywidth, bg=canvas_bgcolor)
skutext = tk.Entry(topframe, width=entrywidth, bg=canvas_bgcolor)
versiontext = tk.Entry(topframe, width=entrywidth, bg=canvas_bgcolor)
statustext = tk.Text(baseframe, height=1, width=status_width, bg=canvas_bgcolor)


def statusmsg(statusstring):
    '''output a status message to screen'''
    st_message = strftime("%Y-%m-%d %H:%M:%S ") + str(statusstring)
    if statustext.get(1.0, tk.END):
        statustext.delete(1.0, tk.END)
    statustext.insert(tk.END, st_message)


def displayvmss(vmssname):
    '''Display scale set details'''
    global current_vmss
    global refresh_thread_running
    current_vmss = vmssz.VMSSZ(vmssname, sub.vmssdict[vmssname], sub.sub_id, sub.access_token)
    # capacity - row 0
    locationlabel = tk.Label(topframe, text=current_vmss.location, width=btnwidth, justify=tk.LEFT,
                             bg=frame_bgcolor)
    locationlabel.grid(row=0, column=1, sticky=tk.W)
    tk.Label(topframe, text='Capacity: ', bg=frame_bgcolor).grid(row=0, column=2)
    capacitytext.grid(row=0, column=3, sticky=tk.W)
    capacitytext.delete(0, tk.END)
    capacitytext.insert(0, str(current_vmss.capacity))
    scalebtn = tk.Button(topframe, text="Scale", command=scalevmss, width=btnwidth, bg=btncolor)
    scalebtn.grid(row=0, column=4, sticky=tk.W)

    # VMSS properties - row 1
    vmsizetext.grid(row=1, column=3, sticky=tk.W)
    vmsizetext.delete(0, tk.END)
    vmsizetext.insert(0, str(current_vmss.vmsize))
    vmsizetext.grid(row=1, column=0, sticky=tk.W)
    offerlabel = tk.Label(topframe, text=current_vmss.offer, width=btnwidth, justify=tk.LEFT,
                          bg=frame_bgcolor)
    offerlabel.grid(row=1, column=1, sticky=tk.W)
    skutext.grid(row=1, column=2, sticky=tk.W)
    skutext.delete(0, tk.END)
    skutext.insert(0, current_vmss.sku)
    versiontext.grid(row=1, column=3, sticky=tk.W)
    versiontext.delete(0, tk.END)
    versiontext.insert(0, current_vmss.version)
    updatebtn = tk.Button(topframe, text='Update model', command=updatevmss, width=btnwidth,
                          bg=btncolor)
    updatebtn.grid(row=1, column=4, sticky=tk.W)

    # more VMSS properties - row 2
    if current_vmss.overprovision == True:
        optext = "overprovision: true"
    else:
        optext = "overprovision: false"
    overprovisionlabel = tk.Label(topframe, text=optext, width=btnwidth, justify=tk.LEFT,
                                  bg=frame_bgcolor)
    overprovisionlabel.grid(row=2, column=0, sticky=tk.W)
    upgradepolicylabel = tk.Label(topframe, text=current_vmss.upgradepolicy + ' upgrade',
                                  width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    upgradepolicylabel.grid(row=2, column=1, sticky=tk.W)
    adminuserlabel = tk.Label(topframe, text=current_vmss.adminuser, width=btnwidth,
                              justify=tk.LEFT, bg=frame_bgcolor)
    adminuserlabel.grid(row=2, column=2, sticky=tk.W)
    compnameprefixlabel = tk.Label(topframe, text='Prefix: ' + current_vmss.nameprefix,
                                   width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    compnameprefixlabel.grid(row=2, column=3, sticky=tk.W)
    rglabel = tk.Label(topframe, text='RG: ' + current_vmss.rgname,
                       width=btnwidth, justify=tk.LEFT, bg=frame_bgcolor)
    rglabel.grid(row=2, column=4, sticky=tk.W)

    # vmss operations - row 3
    onbtn = tk.Button(topframe, text="Start", command=poweronvmss, width=btnwidth, bg=btncolor)
    onbtn.grid(row=3, column=0, sticky=tk.W)
    onbtn = tk.Button(topframe, text="Restart", command=restartvmss, width=btnwidth, bg=btncolor)
    onbtn.grid(row=3, column=1, sticky=tk.W)
    offbtn = tk.Button(topframe, text="Power off", command=poweroffvmss, width=btnwidth,
                       bg=btncolor)
    offbtn.grid(row=3, column=2, sticky=tk.W)
    deallocbtn = tk.Button(topframe, text="Stop Dealloc", command=deallocvmss, width=btnwidth,
                           bg=btncolor)
    deallocbtn.grid(row=3, column=3, sticky=tk.W)
    detailsbtn = tk.Button(topframe, text="Show Heatmap", command=vmssdetails, width=btnwidth,
                           bg=btncolor)
    detailsbtn.grid(row=3, column=4, sticky=tk.W)

    # status line
    statustext.pack(side=tk.LEFT)
    statusmsg(current_vmss.status)
    if current_vmss.status != 'Failed':
        refresh_thread_running = True


def scalevmss():
    '''scale a scale set in or out'''
    global refresh_thread_running
    newcapacity = int(capacitytext.get())
    current_vmss.scale(newcapacity)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def updatevmss():
    '''Update a scale set to VMSS model'''
    global refresh_thread_running
    newsku = skutext.get()
    newversion = versiontext.get()
    newvmsize = vmsizetext.get()
    current_vmss.update_model(newsku=newsku, newversion=newversion, newvmsize=newvmsize)
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def poweronvmss():
    '''Power on a VM scale set'''
    global refresh_thread_running
    current_vmss.poweron()
    statusmsg(current_vmss.status)
    refresh_thread_running = True

def restartvmss():
    '''Restart' a VM scale set'''
    global refresh_thread_running
    current_vmss.restart()
    statusmsg(current_vmss.status)
    refresh_thread_running = True

def poweroffvmss():
    '''Power off a VM scale set'''
    global refresh_thread_running
    current_vmss.poweroff()
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def deallocvmss():
    '''Stop deallocate on a VM scale set'''
    global refresh_thread_running
    current_vmss.dealloc()
    statusmsg(current_vmss.status)
    refresh_thread_running = True


def vmssdetails():
    '''Show VM scale set zone placement details'''
    global vmsslist
    # refresh VMSS model details
    vmsslist = sub.get_vmss_list()
    # VMSS VM canvas - middle frame
    geometry2 = geometry_wide
    canvas_height = canvas_height100
    canvas_width = canvas_width1000

    root.geometry(geometry2)
    vmcanvas.config(height=canvas_height, width=canvas_width)
    vmcanvas.pack(side=tk.LEFT)
    current_vmss.init_vm_details()
    draw_vms()

    # draw VM frame components
    zlabel.grid(row=1, column=0, sticky=tk.W)
    zoption.grid(row=1, column=1, sticky=tk.W)
    reimagebtnz.grid(row=1, column=2, sticky=tk.W)
    upgradebtnz.grid(row=1, column=3, sticky=tk.W)
    startbtnz.grid(row=1, column=4, sticky=tk.W)
    powerbtnz.grid(row=1, column=5, sticky=tk.W)
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
    selectedz.set('1')
    displayvmss(vmsslist[0])
    # create top level GUI components
    vmsslistoption = tk.OptionMenu(topframe, selectedvmss, *vmsslist, command=displayvmss)
    vmsslistoption.config(width=list_width, bg=btncolor, activebackground=btncolor)
    vmsslistoption["menu"].config()
    vmsslistoption.grid(row=0, column=0, sticky=tk.W)
else:
    messagebox.showwarning("Warning", "Your subscription:\n" + sub.sub_id +\
                           "\ncontains no VM Scale Sets")

root.mainloop()
