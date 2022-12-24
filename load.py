from threading import Thread
from queue import Queue
import logging
import os.path
import sys
import tkinter as tk
import logging
import plug
import monitor
from tkinter import ttk
from typing import TYPE_CHECKING, Any, List, Dict, Mapping, MutableMapping, Optional, Tuple

import myNotebook as nb
from requests import Response, Session
from config import appname, user_agent

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

this = sys.modules[__name__] 
this.base_url : str = "https://api.cia-gaming.de/v1/thargoid-war"
this.version : str = "0.0.5"
this.api_key : str = ""
this.commander_id : str = ""
this.browsersource_url : tk.StringVar = tk.StringVar(master=None, value="placeholder")
this.mission_list : List[str] = [
 "Mission_TW_Rescue_Alert", "Mission_TW_Rescue_UnderAttack",
 "Mission_TW_Rescue_Burning","Mission_TW_PassengerEvacuation_Alert",
 "Mission_TW_PassengerEvacuation_UnderAttack", "Mission_TW_PassengerEvacuation_Burning",
 "Mission_TW_CollectWing_Repairing", "Mission_TW_Collect_Recovery",
 "Mission_TW_CollectWing_Alert", "Mission_TW_Collect_Alert",
 "Mission_TW_CollectWing_UnderAttack", "Mission_TW_Collect_UnderAttack"
]

this.last_cmdr_lookup : Any = None
this.last_cmdrhistory_lookup : Any = None

# UI elements
    # Preferences
this.browsersource_url_entry : nb.Entry = None

    # Main Window
this.goidkills_label : tk.Label = None
this.refugees_label : tk.Label = None
this.wounded_label : tk.Label = None
this.emergencysupplies_label : tk.Label = None
this.recoverysupplies_label : tk.Label = None

# internals
this.getcmdr_type : str = "GET_CMDR"
this.getcmdrhistory_type : str = "GET_CMDR_HISTORY"
this.recordactivity_type : str = "RECORD_ACTIVITY"

this.shutting_down : bool = False

this.session: Session = Session()
this.session.headers['User-Agent'] = user_agent
this.session.headers['Authorization'] = this.api_key

this.queue : Queue = Queue()
this.thread : Optional[Thread] = None

# setup logging
plugin_name : str = os.path.basename(os.path.dirname(__file__))

logger = logging.getLogger(f'{appname}.{plugin_name}')

if not logger.hasHandlers():
    level = logging.INFO

    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(f'%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s')
    logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    logger_formatter.default_msec_format = '%s.%03d'
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)

def plugin_start3(plugin_dir: str) -> str:
    """
    Load this plugin into EDMC
    """     
    logger.debug('Starting worker thread...')
    this.thread = Thread(target=worker, name='TWT worker')
    this.thread.daemon = True
    this.thread.start()

    return "Thargoid War Tracker v" + this.version

def plugin_stop() -> None:
    """Stop this plugin."""

    logger.debug("Shutting down...")

    this.shutting_down = True
    this.queue.put(None)

    this.thread.stop()
    this.thread.join()
    this.thread = None

    this.session.close()
    logger.debug("TWT stopped.")

def plugin_prefs(parent: tk.Tk, cmdr: str, is_beta: bool) -> tk.Frame:
    """
    Plugin preferences setup hook.
    Any tkinter UI set up *must* be within an instance of `myNotebook.Frame`,
    which is the return value of this function.
    :param parent: tkinter Widget to place items in.
    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    :return: An instance of `myNotebook.Frame`.
    """

    frame = nb.Frame(parent)
    # Make the second column fill available space
    frame.columnconfigure(1, weight=1)

    nb.Label(frame, text="Browser Source").grid(padx=10, sticky=tk.W)
    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW)
    nb.Label(frame, text="You can use this browser source to show your statistics through OBS while streaming").grid(padx=10, columnspan=2, sticky=tk.W)
    nb.Label(frame, text="Your Browser Source URL:").grid(column=0, padx=10, sticky=tk.W, row=4)
    this.browsersource_url_entry = nb.Entry(frame, textvariable=this.browsersource_url, state="readonly").grid(column=1, padx=10, pady=2, sticky=tk.EW, row=4)

    return frame

def plugin_app(parent: tk.Tk) -> tk.Frame:
    """
    Construct this plugin's main UI, if any.
    :param parent: The tk parent to place our widgets into.
    :return: See PLUGINS.md#display
    """
    this.frame = tk.Frame(parent)
    this.frame.bind_all("<<GetCMDR>>", update_war_data)
    this.frame.bind_all("<<RecordedActivity>>", fetch_cmdr)
    # tk.Button(this.frame, text='Update', command=update_war_data).grid(row=1, column=2, padx=8)
    Title = tk.Label(
    this.frame, text=f'Thargoid War Tracker v{this.version}')
    Title.grid(row=0, column=0, sticky=tk.W)
    this.goidkills_label = tk.Label(this.frame, text='Thargoids killed: 0')
    this.goidkills_label.grid(row=1, column=0, sticky=tk.W)
    this.refugees_label = tk.Label(this.frame, text='Refugees evacuated: 0')
    this.refugees_label.grid(row=2, column=0, sticky=tk.W)
    this.wounded_label = tk.Label(this.frame, text='Wounded rescued: 0')
    this.wounded_label.grid(row=3, column=0, sticky=tk.W)
    this.emergencysupplies_label = tk.Label(this.frame, text='Emergency supplies delivered: 0')
    this.emergencysupplies_label.grid(row=4, column=0, sticky=tk.W)
    this.recoverysupplies_label = tk.Label(this.frame, text='Recovery supplies delivered: 0')
    this.recoverysupplies_label.grid(row=5, column=0, sticky=tk.W)

    params : Dict =  { 'id': this.commander_id }
    this.queue.put((this.getcmdr_type, params))

    return this.frame

def fetch_cmdr(event = None) -> None:
    params : Dict =  { 'id': this.commander_id }
    this.queue.put((this.getcmdr_type, params))

def update_war_data(event = None) -> None:
        if this.last_cmdr_lookup: 
            this.goidkills_label.config(text=f'Thargoids killed: {this.last_cmdr_lookup["commander"]["activityStatistics"]["thargoidsDestroyed"]}')
            this.refugees_label.config(text=f'Refugees evacuated: {this.last_cmdr_lookup["commander"]["activityStatistics"]["refugeesEvacuated"]}')
            this.wounded_label.config(text=f'Wounded rescued: {this.last_cmdr_lookup["commander"]["activityStatistics"]["woundedRescued"]}')
            this.emergencysupplies_label.config(text=f'Emergency supplies delivered: {this.last_cmdr_lookup["commander"]["activityStatistics"]["emergencySuppliesDelivered"]}')
            this.recoverysupplies_label.config(text=f'Recovery supplies delivered: {this.last_cmdr_lookup["commander"]["activityStatistics"]["recoverySuppliesDelivered"]}')
            update_browser_source(event)

def update_browser_source(event = None) -> None:
        if this.last_cmdr_lookup:
            this.browsersource_url.set(this.last_cmdr_lookup["commander"]["browserSourceUrl"])

def journal_entry(cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, any]) -> None:
    if is_beta == True:
        return

    if entry["event"] == "FactionKillBond":
        if entry["VictimFaction"] == "$faction_Thargoid;":
            logger.debug(f'FID: {state["FID"]}')
            body : Dict = { "commanderId": this.commander_id, "type": "FactionKillBond", "bondTargetFaction": entry["VictimFaction"] }
            this.queue.put((this.recordactivity_type, body))
            return
    
    if entry["event"] == "MissionAccepted":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            logger.debug(f'FID: {state["FID"]}')
            body : Dict = { 
                "commanderId": this.commander_id, 
                "type": "MissionAccepted",
                 "missions": [
                    {
                        "id": entry["MissionID"], 
                        "type": entry["Name"],
                        "count": entry["PassengerCount"] if "PassengerCount" in entry else entry["Count"]
                    } 
                ]
            }
            this.queue.put((this.recordactivity_type, body))
            return
    
    if entry["event"] == "MissionCompleted":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            logger.debug(f'CMDR: {cmdr} - FID: {state["FID"]}')            
            body : Dict = { 
                "commanderId": this.commander_id, 
                "type": "MissionCompleted",
                "missionId": entry["MissionID"]
            }
            this.queue.put((this.recordactivity_type, body))
            return

    if entry["event"] == "MissionFailed":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            logger.debug(f'FID: {state["FID"]}')
            body = { 
                "commanderId": this.commander_id, 
                "type": "MissionFailed",
                "missionId": entry["MissionID"]
            }
            this.queue.put((this.recordactivity_type, body))
            return

    if entry["event"] == "MissionAbandoned":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            logger.debug(f'FID: {state["FID"]}')
            body = { 
                "commanderId": this.commander_id, 
                "type": "MissionAbandoned",
                "missionId": entry["MissionID"]
            }
            this.queue.put((this.recordactivity_type, body))
            return

def worker() -> None:
    """
    Handle communication with the API.
    Target function of a thread.
    Processes `this.queue` until the queued item is None.
    """
    logger.debug('Starting worker...')

    closing = False

    type : str = None
    params: Dict = {}

    while True:
        if this.shutting_down:
            logger.debug(f'{this.shutting_down=}, so setting closing = True')
            closing = True

        item : Optional[Tuple[str, Dict]] = this.queue.get()

        if item:
            (type, params) = item
        else:
            logger.debug('Empty queue message, setting closing = True')
            closing = True

        if closing:
            logger.debug('closing, so returning.')
            return

        retrying = 0
        while retrying < 3:
            try:
                if type == this.getcmdr_type:
                    response : Response = this.session.get(f'{this.base_url}/commander', params=params)
                    response.raise_for_status()
                    this.last_cmdr_lookup = response.json()
                    this.frame.event_generate("<<GetCMDR>>", when="tail")
                elif type == this.getcmdrhistory_type: 
                    response : Response = this.session.get(f'{this.base_url}/commander/history', params=params)
                    response.raise_for_status()
                    this.last_cmdrhistory_lookup = response.json()
                    #this.frame.event_generate("<<GetCMDRHistory>>", when="tail")
                elif type == this.recordactivity_type:
                    if not monitor.monitor.is_live_galaxy():
                        logger.error("TWT only supports the live galaxy")
                        break                    
                    response : Response = this.session.post(f'{this.base_url}/activity', json=params)
                    response.raise_for_status()
                    this.frame.event_generate("<<RecordedActivity>>", when="tail")

                break
            except Exception as err:
                logger.debug(f'Attempt to connect to TWT API: retrying == {retrying}', exc_info=err)
                logger.debug("Closing session as it seems to be dead. It's dead Jim!")
                this.session.close()
                retrying += 1
        else:
            plug.show_error("Error: Can't connect to TWT API")
