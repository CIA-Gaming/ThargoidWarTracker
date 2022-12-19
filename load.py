import logging
import os.path
import sys
import tkinter as tk
import logging
from os import path
from tkinter import ttk

import myNotebook as nb
import requests
from config import appname

this = sys.modules[__name__] 
this.Version = "0.0.4"
this.ApiKey = "" #Insert API key here
this.CommanderId = "" # Insert FID from main menu here
this.BrowserSourceUrl = tk.StringVar(master=None, value="placeholder")
this.MissionList = [
 "Mission_TW_Rescue_Alert", "Mission_TW_Rescue_UnderAttack",
 "Mission_TW_Rescue_Burning","Mission_TW_PassengerEvacuation_Alert",
 "Mission_TW_PassengerEvacuation_UnderAttack", "Mission_TW_PassengerEvacuation_Burning",
 "Mission_TW_CollectWing_Repairing", "Mission_TW_Collect_Recovery",
 "Mission_TW_CollectWing_Alert", "Mission_TW_Collect_Alert",
 "Mission_TW_CollectWing_UnderAttack", "Mission_TW_Collect_UnderAttack"
]

# This could also be returned from plugin_start3()
plugin_name = os.path.basename(os.path.dirname(__file__))

# A Logger is used per 'found' plugin to make it easy to include the plugin's
# folder name in the logging output format.
# NB: plugin_name here *must* be the plugin's folder name as per the preceding
#     code, else the logger won't be properly set up.
logger = logging.getLogger(f'{appname}.{plugin_name}')

# If the Logger has handlers then it was already set up by the core code, else
# it needs setting up here.
if not logger.hasHandlers():
    level = logging.INFO  # So logger.info(...) is equivalent to print()

    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(f'%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s')
    logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    logger_formatter.default_msec_format = '%s.%03d'
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)

def plugin_start3(plugin_dir):
    """
    Load this plugin into EDMC
    """     

    headers = { 'Authorization': this.ApiKey }
    params = dict(id=this.CommanderId)
    response = requests.get("https://api.cia-gaming.de/v1/thargoid-war/commander", params=params, headers=headers)
    if response.status_code == requests.codes.ok:
        cmdr = response.json()
        this.BrowserSourceUrl.set(cmdr["commander"]["browserSourceUrl"])

    return "[TCIA] Thargoid War Tracker v" + this.Version

def plugin_prefs(parent, cmdr, is_beta):
    """
    Return a TK Frame for adding to the EDMC settings dialog.
    """

    frame = nb.Frame(parent)
    # Make the second column fill available space
    frame.columnconfigure(1, weight=1)

    nb.Label(frame, text="Browser Source").grid(padx=10, sticky=tk.W)
    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW)
    nb.Label(frame, text="You can use this browser source to show your statistics through OBS while streaming").grid(padx=10, columnspan=2, sticky=tk.W)
    nb.Label(frame, text="Your Browser Source URL:").grid(column=0, padx=10, sticky=tk.W, row=4)
    EntryPlus(frame, textvariable=this.BrowserSourceUrl, state="readonly").grid(column=1, padx=10, pady=2, sticky=tk.EW, row=4)

    return frame

def plugin_app(parent):
    """
    Create a frame for the EDMC main window
    """
    headers = { 'Authorization': this.ApiKey }
    params = dict(id=this.CommanderId)
    response = requests.get("https://api.cia-gaming.de/v1/thargoid-war/commander", params=params, headers=headers)
    if response.status_code == requests.codes.ok:
        cmdr = response.json()
        #this.goidsDestroyed == cmdr["commander"]["activityStatistics"]["thargoidsDestroyed"]
        global GoidKills
        global Refugees
        global Wounded
        global EmergencySupplies
        global RecoverySupplies
        this.frame = tk.Frame(parent)
        #tk.Button(this.frame, text='Update', command=update_war_data).grid(row=1, column=2, padx=8)
        Title = tk.Label(this.frame, text=f'[TCIA] Thargoid War Tracker v{this.Version}')
        Title.grid(row=0, column=0, sticky=tk.W)
        GoidKills = tk.Label(this.frame, text=f'Thargoids killed: {cmdr["commander"]["activityStatistics"]["thargoidsDestroyed"]}')
        GoidKills.grid(row=1, column=0, sticky=tk.W)
        Refugees = tk.Label(this.frame, text=f'Refugees evacuated: {cmdr["commander"]["activityStatistics"]["refugeesEvacuated"]}')
        Refugees.grid(row=2, column=0, sticky=tk.W)
        Wounded = tk.Label(this.frame, text=f'Wounded rescued: {cmdr["commander"]["activityStatistics"]["woundedRescued"]}')
        Wounded.grid(row=3, column=0, sticky=tk.W)
        EmergencySupplies = tk.Label(this.frame, text=f'Emergency supplies delivered: {cmdr["commander"]["activityStatistics"]["emergencySuppliesDelivered"]}')
        EmergencySupplies.grid(row=4, column=0, sticky=tk.W)
        RecoverySupplies = tk.Label(this.frame, text=f'Recovery supplies delivered: {cmdr["commander"]["activityStatistics"]["recoverySuppliesDelivered"]}')
        RecoverySupplies.grid(row=5, column=0, sticky=tk.W)
        return this.frame

def update_war_data():
    headers = { 'Authorization': this.ApiKey }
    params = dict(id=this.CommanderId)
    response = requests.get("https://api.cia-gaming.de/v1/thargoid-war/commander", params=params, headers=headers)
    if response.status_code == requests.codes.ok:
        cmdr = response.json()
        GoidKills.config(text=f'Thargoids killed: {cmdr["commander"]["activityStatistics"]["thargoidsDestroyed"]}')
        Refugees.config(text=f'Refugees evacuated: {cmdr["commander"]["activityStatistics"]["refugeesEvacuated"]}')
        Wounded.config(text=f'Wounded rescued: {cmdr["commander"]["activityStatistics"]["woundedRescued"]}')
        EmergencySupplies.config(text=f'Emergency supplies delivered: {cmdr["commander"]["activityStatistics"]["emergencySuppliesDelivered"]}')
        RecoverySupplies.config(text=f'Recovery supplies delivered: {cmdr["commander"]["activityStatistics"]["recoverySuppliesDelivered"]}')

def journal_entry(cmdr, is_beta, system, station, entry, state):
    if entry["event"] == "FactionKillBond":
        if entry["VictimFaction"] == "$faction_Thargoid;":
            headers = { 'Authorization': this.ApiKey }
            body = { "commanderId": this.CommanderId, "type": "FactionKillBond", "bondTargetFaction": entry["VictimFaction"] }
            response = requests.post("https://api.cia-gaming.de/v1/thargoid-war/activity", json=body, headers=headers)
            if response.status_code == 400:
                logger.info(response.json())
                return

            update_war_data()
    
    if entry["event"] == "MissionAccepted":
        if str(entry["Name"]).startswith(tuple(this.MissionList)):
            headers = { 'Authorization': this.ApiKey }
            body = { 
                "commanderId": this.CommanderId, 
                "type": "MissionAccepted",
                 "missions": [
                    {
                        "id": entry["MissionID"], 
                        "type": entry["Name"],
                        "count": entry["PassengerCount"] if "PassengerCount" in entry else entry["Count"]
                    } 
                ]
            }
            response = requests.post("https://api.cia-gaming.de/v1/thargoid-war/activity", json=body, headers=headers)
            if response.status_code == 400:
                logger.info(response.json())
                return

            update_war_data()
    
    if entry["event"] == "MissionCompleted":
        if str(entry["Name"]).startswith(tuple(this.MissionList)):            
            headers = { 'Authorization': this.ApiKey }
            body = { 
                "commanderId": this.CommanderId, 
                "type": "MissionCompleted",
                "missionId": entry["MissionID"]
            }
            response = requests.post("https://api.cia-gaming.de/v1/thargoid-war/activity", json=body, headers=headers)
            if response.status_code == 400:
                logger.info(response.json())
                return

            update_war_data()

    if entry["event"] == "MissionFailed":
        if str(entry["Name"]).startswith(tuple(this.MissionList)):
            headers = { 'Authorization': this.ApiKey }
            body = { 
                "commanderId": this.CommanderId, 
                "type": "MissionFailed",
                "missionId": entry["MissionID"]
            }
            response = requests.post("https://api.cia-gaming.de/v1/thargoid-war/activity", json=body, headers=headers)        
            if response.status_code == 400:
                logger.info(response.json())
                return

            update_war_data()

    if entry["event"] == "MissionAbandoned":
        if str(entry["Name"]).startswith(tuple(this.MissionList)):
            headers = { 'Authorization': this.ApiKey }
            body = { 
                "commanderId": this.CommanderId, 
                "type": "MissionAbandoned",
                "missionId": entry["MissionID"]
            }
            response = requests.post("https://api.cia-gaming.de/v1/thargoid-war/activity", json=body, headers=headers)  
            if response.status_code == 400:
                logger.info(response.json())
                return

            update_war_data()
    
class EntryPlus(ttk.Entry):
    """
    Subclass of ttk.Entry to install a context-sensitive menu on right-click
    """
    def __init__(self, *args, **kwargs):
        ttk.Entry.__init__(self, *args, **kwargs)
        # overwrite default class binding so we don't need to return "break"
        self.bind_class("Entry", "<Control-a>", self.event_select_all)
        self.bind("<Button-3><ButtonRelease-3>", self.show_menu)

    def event_select_all(self, *args):
        self.focus_force()
        self.selection_range(0, tk.END)

    def show_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)