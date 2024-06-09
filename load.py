from threading import Thread, Timer
from queue import Queue
import logging
import os.path
import sys
import tkinter as tk
import logging
import plug
from monitor import monitor
from companion import CAPIData
from tkinter import ttk
from ttkHyperlinkLabel import HyperlinkLabel
from typing import TYPE_CHECKING, Any, List, Dict, Mapping, MutableMapping, Optional, Tuple
import urllib.parse

import myNotebook as nb
from requests import Response, Session
from config import appname, user_agent, config

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

this = sys.modules[__name__] 
this.base_url : str = "https://twt.cia-gaming.de/api/v2"
this.version : str = "0.1.6"
this.git_version: str = None
this.cmdr_name : str = None
this.browsersource_url : tk.StringVar = tk.StringVar(master=None, value="placeholder")
this.mission_list : List[str] = [
 "Mission_TW_Rescue_Alert", "Mission_TW_PassengerEvacuation_Alert",
 "Mission_TW_RefugeeBulk", "Mission_TW_Rescue_UnderAttack",
 "Mission_TW_PassengerEvacuation_UnderAttack", "Mission_TW_Rescue_Burning",
 "Mission_TW_PassengerEvacuation_Burning",
 "Mission_TW_Collect_Alert", "Mission_TW_CollectWing_Alert",
 "Mission_TW_Collect_Repairing", "Mission_TW_CollectWing_Repairing",
 "Mission_TW_Collect_Recovery", "Mission_TW_CollectWing_Recovery",
 "Mission_TW_Collect_UnderAttack", "Mission_TW_CollectWing_UnderAttack",
 "Mission_TW_OnFoot_Reboot_NR", "Mission_TW_OnFoot_Reboot_MB"
]

this.cargo_list : List[str] = [
 "DamagedEscapePod",
 "OccupiedCryoPod",
 "ThargoidPod",
 "USSCargoBlackBox",
 "ThargoidTissueSample",
 "ThargoidScoutTissueSample"
]

# state
this.last_cmdr_lookup : Any = None
this.last_cmdractivtiy_lookup : Any = None
this.last_cmdrhistory_lookup : Any = None

this.current_star_system_name : str = None
this.current_star_system_address : str = None
this.current_station: str = None
this.current_station_market_id : str = None

#config
this.apikey : str = None

# UI elements
    # Preferences
this.browsersource_url_entry : nb.EntryMenu = None
this.apikey_entry : nb.EntryMenu = None
this.browsersource_url_tk : tk.StringVar = tk.StringVar(master=None, value="")
this.apikey_tk : tk.StringVar = tk.StringVar(master=None, value="")

    # Main Window
this.goidkills_label : tk.Label = None
this.refugees_label : tk.Label = None
this.wounded_label : tk.Label = None
this.emergencysupplies_label : tk.Label = None
this.recoverysupplies_label : tk.Label = None

# internals
this.initialization_type : str = "INITIALIZATION"
this.getcmdr_type : str = "GET_CMDR"
this.getcmdractivity_type : str = "GET_CMDR_ACTIVITY"
this.getcmdrhistory_type : str = "GET_CMDR_HISTORY"
this.recordactivity_type : str = "TRACK_ACTIVITY"

this.is_initialized = False
this.shutting_down : bool = False

this.session: Session = Session()
this.session.headers['User-Agent'] = user_agent

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

    timer = Timer(1.0, check_cmdr_name)
    timer.start()

    response = this.session.get('https://api.github.com/repos/CIA-Gaming/ThargoidWarTracker/releases/latest')  # check latest version
    latest = response.json()
    this.git_version = latest['tag_name']

    return "Thargoid War Tracker v" + this.version

def plugin_stop() -> None:
    """Stop this plugin."""

    logger.debug("Shutting down...")   

    if this.cmdr_name is not None:
        config.set(f'twt_{this.cmdr_name}_lastSystemName', this.current_star_system_name)
        config.set(f'twt_{this.cmdr_name}_lastSystemAddress', this.current_star_system_address)
        config.set(f'twt_{this.cmdr_name}_lastStationName', this.current_station)
        config.set(f'twt_{this.cmdr_name}_lastStationMarketId', this.current_station_market_id)

    this.shutting_down = True
    this.queue.put(None)

    this.thread.join()  # type: ignore
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

    this.cmdr_name = cmdr
    this.apikey = config.get_str(f'twt_{cmdr}_apikey')

    frame = nb.Frame(parent)
    # Make the second column fill available space
    frame.columnconfigure(1, weight=1)

    nb.Label(frame, text="API Key").grid(padx=10, sticky=tk.W)
    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW, row=2)
    nb.Label(frame, text="Paste the API Key you got from your profile page from https://twt.cia-gaming.de here").grid(padx=10, columnspan=2, sticky=tk.W)
    nb.Label(frame, text="Your API Key:").grid(column=0, padx=10, sticky=tk.W, row=4)
    this.apikey_entry = nb.EntryMenu(frame, textvariable=this.apikey_tk).grid(column=1, padx=10, pady=2, sticky=tk.EW, row=4)
    nb.Label(frame, text="Browser Source").grid(padx=10, sticky=tk.W, row=7)
    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW, row=8)
    nb.Label(frame, text="You can use this browser source to show your statistics through OBS while streaming").grid(padx=10, columnspan=2, sticky=tk.W, row=9)
    nb.Label(frame, text="Your Browser Source URL:").grid(column=0, padx=10, sticky=tk.W, row=9)
    this.browsersource_url_entry = nb.EntryMenu(frame, textvariable=this.browsersource_url_tk, state="readonly").grid(column=1, padx=10, pady=2, sticky=tk.EW, row=10)

    return frame

def plugin_app(parent: tk.Tk) -> tk.Frame:
    """
    Construct this plugin's main UI, if any.
    :param parent: The tk parent to place our widgets into.
    :return: See PLUGINS.md#display
    """

    this.frame = tk.Frame(parent)
    this.frame.columnconfigure(1, weight=1)
    this.frame.bind_all("<<Initialization>>", initialize)
    this.frame.bind_all("<<GetCMDR>>", update_browser_source)
    this.frame.bind_all("<<GetCMDRActivity>>", update_war_data)
    this.frame.bind_all("<<RecordedActivity>>", fetch_cmdr_activity)
    Title = tk.Label(this.frame, text=f'Thargoid War Tracker v{this.version}')
    Title.grid(row=0, column=0, sticky=tk.W)
    if version_tuple(this.git_version) > version_tuple(this.version):
        HyperlinkLabel(this.frame, text="New version available", background=nb.Label().cget("background"), url="https://github.com/CIA-Gaming/ThargoidWarTracker/releases/latest", underline=True).grid(row=0, column=1, sticky=tk.W)
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
    this.settlementsrebooted_label = tk.Label(this.frame, text='Settlements rebooted: 0')
    this.settlementsrebooted_label.grid(row=6, column=0, sticky=tk.W)
    this.searchandrescue_label = tk.Label(this.frame, text='Search and Rescues: 0')
    this.searchandrescue_label.grid(row=7, column=0, sticky=tk.W)
    this.tissuesamples_label = tk.Label(this.frame, text='Tissue samples collected: 0')
    this.tissuesamples_label.grid(row=8, column=0, sticky=tk.W)

    return this.frame

def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle any changes to Settings once the dialog is closed.
    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    """

    if is_beta == True:
        return

    config.set(f'twt_{cmdr}_apikey', this.apikey_tk.get().strip())
    this.apikey = this.apikey_tk.get().strip()

    this.session.headers['Authorization'] = this.apikey

    params: Dict = { }
    this.queue.put((this.initialization_type, params))

def check_cmdr_name():
    this.cmdr_name = monitor.cmdr

    if this.cmdr_name is None:
        timer = Timer(1.0, check_cmdr_name)
        timer.start()
        return

    this.apikey = config.get_str(f'twt_{this.cmdr_name}_apikey')
    this.apikey_tk.set(this.apikey)
    this.session.headers['Authorization'] = this.apikey

    this.current_star_system_name = config.get_str(f'twt_{this.cmdr_name}_lastSystemName')
    this.current_star_system_address = config.get_str(f'twt_{this.cmdr_name}_lastSystemAddress')
    this.current_station = config.get_str(f'twt_{this.cmdr_name}_lastStationName')
    this.current_station_market_id = config.get_str(f'twt_{this.cmdr_name}_lastStationMarketId')

    logger.debug(this.current_star_system_name)
    logger.debug(this.current_star_system_address)
    logger.debug(this.current_station)
    logger.debug(this.current_station_market_id)

    if this.is_initialized == False and this.apikey is not None:
        params: Dict = { }
        this.queue.put((this.initialization_type, params))

def initialize(event = None) -> None:
    update_browser_source(event)
    update_war_data(event)
    
    this.is_initialized = True

def fetch_cmdr_activity(event = None) -> None:
    params : Dict = { }
    this.queue.put((this.getcmdractivity_type, params))

def update_war_data(event = None) -> None:
        if this.last_cmdractivity_lookup: 
            this.goidkills_label.config(text=f'Thargoids killed: {this.last_cmdractivity_lookup["activityStatistic"]["overallThargoidKills"]}')
            this.refugees_label.config(text=f'Refugees rescued: {this.last_cmdractivity_lookup["activityStatistic"]["overallRefugeesRescued"]}')
            this.wounded_label.config(text=f'Wounded evacuated: {this.last_cmdractivity_lookup["activityStatistic"]["overallWoundedEvacuated"]}')
            this.emergencysupplies_label.config(text=f'Emergency supplies delivered: {this.last_cmdractivity_lookup["activityStatistic"]["overallEmergencySuppliesDelivered"]}')
            this.recoverysupplies_label.config(text=f'Recovery supplies delivered: {this.last_cmdractivity_lookup["activityStatistic"]["overallRecoverySuppliesDelivered"]}')
            this.settlementsrebooted_label.config(text=f'Settlements rebooted: {this.last_cmdractivity_lookup["activityStatistic"]["overallSettlementsRebooted"]}')
            this.searchandrescue_label.config(text=f'Search and Rescues: {this.last_cmdractivity_lookup["activityStatistic"]["overallSearchAndRescue"]}')
            this.tissuesamples_label.config(text=f'Tissue samples collected: {this.last_cmdractivity_lookup["activityStatistic"]["overallTissueSamplesCollected"]}')

def update_browser_source(event = None) -> None:
        if this.last_cmdr_lookup:
            this.browsersource_url_tk.set(this.last_cmdr_lookup["browserSourceUrl"])

def cmdr_data(data: CAPIData, is_beta: bool) -> Optional[str]:
    return ''

def version_tuple(version):
    """
    Parse the plugin version number into a tuple
    """
    try:
        version = version.replace('v', '')
        ret = tuple(map(int, version.split(".")))
    except:
        ret = (0,)
    return ret

def journal_entry(cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, any]) -> None:
    if is_beta == True:
        return

    if this.is_initialized == False:
        return

    this.cmdr_name = cmdr

    if entry["event"] == "Location":
        this.current_star_system_name = entry["StarSystem"]
        this.current_star_system_address = str(entry["SystemAddress"])
        if entry["Docked"] == True:
            this.current_station = entry["StationName"]
            this.current_station_market_id = str(entry["MarketID"])
        else:
            this.current_station = entry["StationName"] if "StationName" in entry else "Deep Space"
            this.current_station_market_id = str(0 if "StationName" in entry else 1)
        return

    if entry["event"] == "FSDJump":
        this.current_star_system_name = entry["StarSystem"]       
        this.current_star_system_address = str(entry["SystemAddress"])
        this.current_station = "Deep Space"
        this.current_station_market_id = str(1)
        return

    if entry["event"] == "CarrierJump":
        this.current_star_system_name = entry["StarSystem"]
        this.current_star_system_address = str(entry["SystemAddress"])
        if entry["Docked"] == True:
            this.current_station = entry["StationName"]
            this.current_station_market_id = str(entry["MarketID"])
        else:
            this.current_station = entry["StationName"] if "StationName" in entry else "Deep Space"
            this.current_station_market_id = str(0 if "StationName" in entry else 1)
        return

    if entry["event"] == "Docked":
        this.current_star_system_name = entry["StarSystem"]
        this.current_star_system_address = str(entry["SystemAddress"])
        this.current_station = entry["StationName"]
        this.current_station_market_id = str(entry["MarketID"])
        return

    if entry["event"] == "SupercruiseEntry":
        this.current_station = "Deep Space"
        this.current_station_market_id = str(1)

    if entry["event"] == "SupercruiseExit":
        if entry["BodyType"] == "Station":
            this.current_station = entry["Body"]
            this.current_station_market_id = str(0)
        else:
            this.current_station = "Deep Space"
            this.current_station_market_id = str(1)
        return

    if entry["event"] == "ApproachBody":
        this.current_star_system_name = entry["StarSystem"]
        this.current_star_system_address = str(entry["SystemAddress"]) 
    
    if entry["event"] == "ApproachSettlement":
        this.current_star_system_address = str(entry["SystemAddress"])
        if (str(entry["Name"]).startswith("$Settlement_Unflattened_TGMegaBarnacle")):
            this.current_station = "Thargoid Spire Site"
            this.current_Station_market_id = str(2)
        else:
            this.current_station = entry["Name"]
            this.current_Station_market_id = str(entry["MarketID"])
        return

    if this.apikey is None:
        return

    if entry["event"] == "FactionKillBond":
        if entry["VictimFaction"] == "$faction_Thargoid;":
            body : Dict = { 
                "type": "FactionKillBond",
                "targetFaction": entry["VictimFaction"],
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id,
                "boundsAmount": entry["Reward"]
            }
            this.queue.put((this.recordactivity_type, body))
            return
    
    if entry["event"] == "MissionAccepted":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            body : Dict = { 
                "type": "MissionAccepted",
                "mission": {
                    "id": entry["MissionID"], 
                    "type": entry["Name"],
                    "expiresAt": entry["Expiry"],
                    "count": entry["PassengerCount"] if "PassengerCount" in entry else entry["Count"]
                },
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id                  
            }
            this.queue.put((this.recordactivity_type, body))
            return
    
    if entry["event"] == "MissionCompleted":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):         
            body : Dict = { 
                "type": "MissionCompleted",
                "mission": {
                    "id": entry["MissionID"],
                },
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id
            }
            this.queue.put((this.recordactivity_type, body))
            return

    if entry["event"] == "MissionFailed":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            body = { 
                "type": "MissionFailed",
                "mission": {
                    "id": entry["MissionID"]
                },
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id
            }
            this.queue.put((this.recordactivity_type, body))
            return

    if entry["event"] == "MissionAbandoned":
        if str(entry["Name"]).startswith(tuple(this.mission_list)):
            body = {
                "type": "MissionAbandoned",
                "mission": {
                    "id": entry["MissionID"]
                },
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id
            }
            this.queue.put((this.recordactivity_type, body))
            return
        
    if entry["event"] == "CollectCargo":
        if str(entry["Type"]).startswith(tuple(this.cargo_list)):
            body = {
                "type": "CollectCargo",
                "cargo": {
                    "type": entry["Type"]
                },
                "starSystemName": this.current_star_system_name, 
                "starSystemId64":  this.current_star_system_address,
                "stationName": this.current_station,
                "stationMarketId64": this.current_station_market_id
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
        while retrying < 5:
            try:
                sanitized_commander_name: str = urllib.parse.quote(this.cmdr_name)
                if type == this.initialization_type:
                    responseCmdr : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}')
                    responseCmdr.raise_for_status()
                    this.last_cmdr_lookup = responseCmdr.json()
                    responseActivity : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}/activity')
                    responseActivity.raise_for_status()
                    this.last_cmdractivity_lookup = responseActivity.json()
                    responseHistory : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}/history')
                    responseHistory.raise_for_status()
                    this.last_cmdrhistory_lookup = responseHistory.json()
                    this.frame.event_generate("<<Initialization>>", when="tail")
                if type == this.getcmdr_type:
                    response : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}')
                    response.raise_for_status()
                    this.last_cmdr_lookup = response.json()
                    this.frame.event_generate("<<GetCMDR>>", when="tail")
                if type == this.getcmdractivity_type:
                    response : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}/activity')
                    response.raise_for_status()
                    this.last_cmdractivity_lookup = response.json()
                    this.frame.event_generate("<<GetCMDRActivity>>", when="tail")
                elif type == this.getcmdrhistory_type: 
                    response : Response = this.session.get(f'{this.base_url}/commanders/{sanitized_commander_name}/history')
                    response.raise_for_status()
                    this.last_cmdrhistory_lookup = response.json()
                    #this.frame.event_generate("<<GetCMDRHistory>>", when="tail")
                elif type == this.recordactivity_type:
                    if not monitor.is_live_galaxy():
                        logger.error("TWT only supports the live galaxy")
                        break                    
                    response : Response = this.session.post(f'{this.base_url}/commanders/{sanitized_commander_name}/activity', json=params)
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
