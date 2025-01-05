# python
from iqoptionapi.api import IQOptionAPI
import iqoptionapi.constants as OP_code
import iqoptionapi.country_id as Country
import threading
import time
import logging
import operator
import iqoptionapi.global_value as global_value
from collections import defaultdict
from collections import deque
from iqoptionapi.expiration import get_expiration_time, get_remaning_time
from datetime import datetime, timedelta
import json

def nested_dict(n, type):
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n-1, type))


class IQ_Option:
    __version__ = "8.9"

    def __init__(self, email, password,http_proxy_host=None,http_proxy_port=None,http_proxy_auth=None,set_ssid=None,auto_logout=True):
        self.size = [1, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800,
                     3600, 7200, 14400, 28800, 43200, 86400, 604800, 2592000]
        self.email = email
        self.password = password
        self.suspend = 0.1
        self.thread = None
        self.subscribe_candle = []
        self.subscribe_candle_all_size = []
        self.subscribe_mood = []
        # for digit
        self.get_digital_spot_profit_after_sale_data = nested_dict(2, int)
        self.get_realtime_strike_list_temp_data = {}
        self.get_realtime_strike_list_temp_expiration = 0
        self.SESSION_HEADER={"User-Agent":r"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36"}
        self.SESSION_COOKIE={}
        
        self.http_proxy_host=http_proxy_host
        self.http_proxy_port=http_proxy_host
        self.http_proxy_auth=http_proxy_host
 

        self.set_ssid=set_ssid
        self.auto_logout=auto_logout
        self._2FA_TOKEN=None
        #

        # --start
        #self.connect()
        # this auto function delay too long

 # --------------------------------------------------------------------------
    def logout(self):
        self.api.logout()
    def set_call_back_for_client(self,function):
        global_value.client_callback[self.api.object_id]=function
         
    def get_server_timestamp(self):
        return self.api.timesync.server_timestamp


    def re_subscribe_stream(self):
        try:
            for ac in self.subscribe_candle:
                sp = ac.split(",")
                self.start_candles_one_stream(sp[0], sp[1])
        except:
            pass
        # -----------------
        try:
            for ac in self.subscribe_candle_all_size:
                self.start_candles_all_size_stream(ac)
        except:
            pass
        # -------------reconnect subscribe_mood
        try:
            for ac in self.subscribe_mood:
                self.start_mood_stream(ac)
        except:
            pass
    def set_session(self,header,cookie):
        self.SESSION_HEADER=header
        self.SESSION_COOKIE=cookie
     
    def get_ssid(self):
        return global_value.SSID[self.api.object_id] 

    def setting_2FA_TOKEN(self,code):
        self._2FA_TOKEN=code
    def TWO_FA(self, token,method=None,code=None):
        r=self.api.TWO_FA(token,method,code)
        return json.loads(r.text)
    def close(self):
        try:
            self.api.close()
            if self.auto_logout:
                self.api.logout()
        except:
            pass
    def connect(self):
         
        try:
            self.api.close()
        except:
            pass
            #logging.error('**warning** self.api.close() fail')
 
        #id-iqoption.com some country only can using this url
        #Iqoption.com
        try:   
            self.set_ssid=global_value.SSID[self.api.object_id]
        except:
            pass
        self.api = IQOptionAPI(
            "iqoption.com", self.email, self.password,http_proxy_host=self.http_proxy_host,http_proxy_port=self.http_proxy_port,http_proxy_auth=self.http_proxy_auth,set_ssid=self.set_ssid,auto_logout=self.auto_logout,_2FA_TOKEN=self._2FA_TOKEN)
        check = None
      
        self.api.set_session(headers=self.SESSION_HEADER,cookies=self.SESSION_COOKIE)
        check,reason = self.api.connect()
       
        if check == True:
            # -------------reconnect subscribe_candle
            self.re_subscribe_stream()

            # ---------for async get name: "position-changed", microserviceName
            while global_value.balance_id[self.api.object_id]==None:
                pass

            balances=self.get_balances()
            #print(balances)


             
            for i in balances["msg"]:
                id=i["id"]
                self.position_change_all("subscribeMessage",id)

            rout=["internal-billing.balance-created","internal-billing.auth-balance-changed","internal-billing.balance-changed","internal-billing.marginal-changed","tournaments.user-registered-in-tournament","tournaments.user-tournament-position-changed"]
            for name in rout:
                self.api.subscribeMessage_routingFilters_None(name)
            self.order_changed_all("subscribeMessage")
            self.api.setOptions("", True)
             
            """
            self.api.subscribe_position_changed(
                "position-changed", "multi-option", 2)

            self.api.subscribe_position_changed(
                "trading-fx-option.position-changed", "fx-option", 3)

            self.api.subscribe_position_changed(
                "position-changed", "crypto", 4)

            self.api.subscribe_position_changed(
                "position-changed", "forex", 5)

            self.api.subscribe_position_changed(
                "digital-options.position-changed", "digital-option", 6)

            self.api.subscribe_position_changed(
                "position-changed", "cfd", 7)
            """
             
            #self.get_balance_id()
            return True,None
        else:
            return False,reason
    # self.update_ACTIVES_OPCODE()

    def check_connect(self):
        # True/False
         
        if global_value.check_websocket_if_connect[self.api.object_id] == 0:
            return False
        else:
            return True
        # wait for timestamp getting

# _________________________UPDATE ACTIVES OPCODE_____________________
    def get_all_ACTIVES_OPCODE(self):
        return OP_code.ACTIVES

    def update_ACTIVES_OPCODE(self):
        # update from binary option
        self.get_ALL_Binary_ACTIVES_OPCODE()
        self.get_All_Digital_ACTIVES_OPCODE()
        #crypto /dorex/cfd
        self.instruments_input_all_in_ACTIVES()
        dicc = {}
        for lis in sorted(OP_code.ACTIVES.items(), key=operator.itemgetter(1)):
            dicc[lis[0]] = lis[1]
        OP_code.ACTIVES = dicc

    def get_name_by_activeId(self, activeId):
        info = self.get_financial_information(activeId)
        try:
            return info["msg"]["data"]["active"]["name"]
        except:
            return None

    def get_financial_information(self, activeId):
        self.api.financial_information = None
        self.api.get_financial_information(activeId)
        while self.api.financial_information == None:
            pass
        return self.api.financial_information
    def get_leader_board(self,country,from_position,to_position,near_traders_count,user_country_id=0,near_traders_country_count=0,top_country_count=0,top_count=0,top_type=2):
        self.api.leaderboard_deals_client=None
         
        country_id=Country.ID[country]
        self.api.Get_Leader_Board(country_id,user_country_id,from_position,to_position,near_traders_country_count,near_traders_count,top_country_count,top_count,top_type)
        while self.api.leaderboard_deals_client==None:
            pass
        return self.api.leaderboard_deals_client

    def get_active_exposure(self,instrument_type,active,duration,currency="USD"):
        #instrument_type=["digital-option","turbo-option","binary-option"]
        request_id=global_value.get_req_id(self.api.object_id)
         
        active_id=OP_code.ACTIVES[active]
        self.api.get_active_exposure(instrument_type,active_id,duration,request_id,currency) 
        self.api.active_exposure[request_id]=None
        while self.api.active_exposure[request_id]==None:
            pass
        _tmp=self.api.active_exposure[request_id]
        del self.api.active_exposure[request_id]
        ans = {}
        
        try:
            ans["call"]=_tmp["msg"]["call"]
            ans["put"]=_tmp["msg"]["put"]
        except:
            pass
        
        return ans
         

    def get_instruments(self, type,polling=0):
        # type="crypto"/"forex"/"cfd"
        time.sleep(self.suspend)
        self.api.instruments = None
        while self.api.instruments == None:
            try:
                self.api.get_instruments(type)
                start = time.time()
                while self.api.instruments == None and time.time()-start < 10:
                    pass
            except:
                logging.error('**error** api.get_instruments need reconnect')
                self.connect()
            time.sleep(polling)
        return self.api.instruments

    def instruments_input_to_ACTIVES(self, type):
        instruments = self.get_instruments(type)
        for ins in instruments["instruments"]:
            OP_code.ACTIVES[ins["id"]] = ins["active_id"]

    def instruments_input_all_in_ACTIVES(self):
        self.instruments_input_to_ACTIVES("crypto")
        self.instruments_input_to_ACTIVES("forex")
        self.instruments_input_to_ACTIVES("cfd")
    def get_All_Digital_ACTIVES_OPCODE(self):
        underlying_list_data=self.get_digital_underlying_list_data()
        for list_data in underlying_list_data["underlying"]:
            active_id=list_data["active_id"]
            name=list_data["name"]
            OP_code.ACTIVES[name]=active_id

    def get_ALL_Binary_ACTIVES_OPCODE(self):
        init_info = self.get_all_init()
        for dirr in (["binary", "turbo"]):
            for i in init_info["result"][dirr]["actives"]:
                OP_code.ACTIVES[(init_info["result"][dirr]
                                 ["actives"][i]["name"]).split(".")[1]] = int(i)

# _________________________self.api.get_api_option_init_all() wss______________________
    def get_all_init(self):

        while True:
            self.api.api_option_init_all_result = None
            while True:
                try:
                    self.api.get_api_option_init_all()
                    break
                except:
                    logging.error('**error** get_all_init need reconnect')
                    self.connect()
                    time.sleep(5)
            start = time.time()
            while True:
                if time.time()-start > 30:
                    logging.error('**warning** get_all_init late 30 sec')
                    break
                try:
                    if self.api.api_option_init_all_result != None:
                        break
                except:
                    pass
            try:
                if self.api.api_option_init_all_result["isSuccessful"] == True:
                    return self.api.api_option_init_all_result
            except:
                pass

    def get_all_init_v2(self,polling=0):
        self.api.api_option_init_all_result_v2 = None

        self.api.get_api_option_init_all_v2()
        start_t = time.time()
        while self.api.api_option_init_all_result_v2 == None:
            if time.time()-start_t >= 30:
                logging.error('**warning** get_all_init_v2 late 30 sec')
                return None
            time.sleep(polling)
        return self.api.api_option_init_all_result_v2

        # return OP_code.ACTIVES
# ------- chek if binary/digit/cfd/stock... if open or not

    def get_all_open_time(self,polling):
        # for binary option turbo and binary
        OPEN_TIME = nested_dict(3, dict)
        binary_data = self.get_all_init_v2(polling)
        binary_list = ["binary", "turbo"]
        for option in binary_list:
            for actives_id in binary_data[option]["actives"]:
                active = binary_data[option]["actives"][actives_id]
                name = str(active["name"]).split(".")[1]
                if active["enabled"] == True:
                    if active["is_suspended"] == True:
                        OPEN_TIME[option][name]["open"] = False
                    else:
                        OPEN_TIME[option][name]["open"] = True
                else:
                    OPEN_TIME[option][name]["open"] = active["enabled"]

        # for digital
        digital_data = self.get_digital_underlying_list_data(polling)["underlying"]
        for digital in digital_data:
            name = digital["underlying"]
            schedule = digital["schedule"]
            OPEN_TIME["digital"][name]["open"] = False
            for schedule_time in schedule:
                start = schedule_time["open"]
                end = schedule_time["close"]
                if start < time.time() < end:
                    OPEN_TIME["digital"][name]["open"] = True

        # for OTHER
        instrument_list = ["cfd", "forex", "crypto"]
        for instruments_type in instrument_list:
            ins_data = self.get_instruments(instruments_type,polling)["instruments"]
            for detail in ins_data:
                name = detail["name"]
                schedule = detail["schedule"]
                OPEN_TIME[instruments_type][name]["open"] = False
                for schedule_time in schedule:
                    start = schedule_time["open"]
                    end = schedule_time["close"]
                    if start < time.time() < end:
                        OPEN_TIME[instruments_type][name]["open"] = True

        return OPEN_TIME


# --------for binary option detail

    def get_binary_option_detail(self):
        detail = nested_dict(2, dict)
        init_info = self.get_all_init()
        for actives in init_info["result"]["turbo"]["actives"]:
            name = init_info["result"]["turbo"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            detail[name]["turbo"] = init_info["result"]["turbo"]["actives"][actives]

        for actives in init_info["result"]["binary"]["actives"]:
            name = init_info["result"]["binary"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            detail[name]["binary"] = init_info["result"]["binary"]["actives"][actives]
        return detail

    def get_all_profit(self):
        all_profit = nested_dict(2, dict)
        init_info = self.get_all_init()
        for actives in init_info["result"]["turbo"]["actives"]:
             
            name = init_info["result"]["turbo"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            if init_info["result"]["turbo"]["actives"][actives]["enabled"]==False:
                all_profit[name]["turbo"]={}
                continue
            all_profit[name]["turbo"] = (
                100.0-init_info["result"]["turbo"]["actives"][actives]["option"]["profit"]["commission"])/100.0

        for actives in init_info["result"]["binary"]["actives"]:
             
            name = init_info["result"]["binary"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            if init_info["result"]["binary"]["actives"][actives]["enabled"]==False:
                all_profit[name]["binary"]={}
                continue

            all_profit[name]["binary"] = (
                100.0-init_info["result"]["binary"]["actives"][actives]["option"]["profit"]["commission"])/100.0
        return all_profit
    def get_all_profit_v2(self):
        all_profit = nested_dict(2, dict)
        init_info = self.get_all_init_v2()
        for actives in init_info["turbo"]["actives"]:
             
            name = init_info["turbo"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            if init_info["turbo"]["actives"][actives]["enabled"]==False:
                all_profit[name]["turbo"]={}
                continue
            all_profit[name]["turbo"] = (
                100.0-init_info["turbo"]["actives"][actives]["option"]["profit"]["commission"])/100.0

        for actives in init_info["binary"]["actives"]:
             
            name = init_info["binary"]["actives"][actives]["name"]
            name = name[name.index(".")+1:len(name)]
            if init_info["binary"]["actives"][actives]["enabled"]==False:
                all_profit[name]["binary"]={}
                continue

            all_profit[name]["binary"] = (
                100.0-init_info["binary"]["actives"][actives]["option"]["profit"]["commission"])/100.0
        return all_profit

# ----------------------------------------


# ______________________________________self.api.getprofile() https________________________________

    def get_profile(self):
        req_id=global_value.get_req_id(self.api.object_id)
        self.api.get_profile_ws(req_id)
        while self.api.profile.msg==None:
            pass
        return self.api.profile.msg
    def get_profile_ansyc(self):
        while self.api.profile.msg==None:
            pass
        return self.api.profile.msg
    
    """def get_profile(self):
        while True:
            try:
                 
                respon = self.api.getprofile().json()
                time.sleep(self.suspend)
            
                if respon["isSuccessful"] == True:
                    return respon
            except:
                logging.error('**error** get_profile try reconnect')
                self.connect()"""

    def get_currency(self):
        balances_raw=self.get_balances()
        for balance in balances_raw["msg"]:
            if balance["id"]==global_value.balance_id[self.api.object_id]:
                return balance["currency"]

         
    def get_balance_id(self):
        return global_value.balance_id[self.api.object_id]
        

    """ def get_balance(self):
        self.api.profile.balance = None
        while True:
            try:
                respon = self.get_profile()
                self.api.profile.balance = respon["result"]["balance"]
                break
            except:
                logging.error('**error** get_balance()')

            time.sleep(self.suspend)
        return self.api.profile.balance"""

    def get_balance(self):
        self.api.get_balances()
        balances_raw=self.get_balances()
        for balance in balances_raw["msg"]:
            if balance["id"]==global_value.balance_id[self.api.object_id]:
                return balance["amount"]
    def get_balance_v2(self):
        #more hight performance, asnyc
        current_balance_id=global_value.balance_id[self.api.object_id]
        if current_balance_id  in self.api.balance:
            return self.api.balance[current_balance_id]
        else:
            self.api.balance[current_balance_id]=self.get_balance()
        return self.api.balance[current_balance_id]
         

    def _get_balances(self):
        self.api.balances_raw=None
        self.api.get_balances()
        while self.api.balances_raw == None:
            pass
        return self.api.balances_raw

    def get_balances(self):
        self.api.get_balances()
        if self.api.balances_raw!=None:
            return self.api.balances_raw
        else:
            while self.api.balances_raw == None:
                pass
                time.sleep(self.suspend)
            return self.api.balances_raw


    def get_balance_mode(self):
        # self.api.profile.balance_type=None
      
        for balance in self.get_balances()["msg"]:
            if balance["id"]==global_value.balance_id[self.api.object_id]:
                if balance["type"]==1:
                    return "REAL" 
                elif balance["type"]==4:
                    return "PRACTICE"


    def reset_practice_balance(self):
        self.api.training_balance_reset_request = None
        self.api.reset_training_balance()
        while self.api.training_balance_reset_request == None:
            pass
        return self.api.training_balance_reset_request

    def position_change_all(self,Main_Name,user_balance_id):
        instrument_type=["cfd","forex","crypto","digital-option","turbo-option","binary-option"]
        for ins in instrument_type:
            self.api.portfolio(Main_Name=Main_Name,name="portfolio.position-changed",instrument_type=ins,user_balance_id=user_balance_id)
    def order_changed_all(self,Main_Name):
        instrument_type=["cfd","forex","crypto","digital-option","turbo-option","binary-option"]
        for ins in instrument_type:
            self.api.portfolio(Main_Name=Main_Name,name="portfolio.order-changed",instrument_type=ins)
    
    def portfolio_get_positions(self,limit=1,offset=0,polling_time=1):
        self.api.positions=None
        instrument_type=["cfd","forex","crypto","digital-option","turbo-option","binary-option"]     
        self.api.portfolio(Main_Name="sendMessage",name="portfolio.get-positions",instrument_type=instrument_type,limit=limit,offset=offset)
        while self.api.positions==None:
            time.sleep(polling_time)
            pass
        return self.api.positions   
    def get_balance_id_by_mode(self,mode):
         
        for balance in self.get_balances()["msg"]:
            if balance["type"] == 1:
                real_id = balance["id"]
            if balance["type"] == 4:
                practice_id = balance["id"]
        if mode=="REAL":
            return real_id
        elif mode=="PRACTICE":
            return practice_id
        else:
            return None
            
    def change_balance(self, Balance_MODE):
        def set_id(b_id):
            #if global_value.balance_id[self.api.object_id]!=None:
            #        self.position_change_all("unsubscribeMessage",global_value.balance_id[self.api.object_id])

            global_value.balance_id[self.api.object_id]=b_id
                
            #self.position_change_all("subscribeMessage",b_id)
         
        if global_value._tmp_raw_balance_id[self.api.object_id]=={}:
            for balance in self.get_balances()["msg"]:
                if balance["type"] == 1:
                    real_id = balance["id"]
                    global_value._tmp_raw_balance_id[self.api.object_id]["REAL"]=real_id
                if balance["type"] == 4:
                    practice_id = balance["id"]
                    global_value._tmp_raw_balance_id[self.api.object_id]["PRACTICE"]=practice_id

        real_id = global_value._tmp_raw_balance_id[self.api.object_id]["REAL"]
        practice_id = global_value._tmp_raw_balance_id[self.api.object_id]["PRACTICE"]
        if Balance_MODE == "REAL":
            set_id(real_id)
            
        elif Balance_MODE == "PRACTICE":
            
            set_id(practice_id)
            
        else:
            logging.error("ERROR doesn't have this mode")
            exit(1)
# ________________________________________________________________________
# _______________________        CANDLE      _____________________________
# ________________________self.api.getcandles() wss________________________

    def get_candles(self, ACTIVES, interval, count, endtime):
        self.api.candles.candles_data = None
        while True:
            try:
                self.api.getcandles(
                    OP_code.ACTIVES[ACTIVES], interval, count, endtime)
                while self.check_connect and self.api.candles.candles_data == None:
                    pass
                if self.api.candles.candles_data != None:
                    break
            except:
                logging.error('**error** get_candles need reconnect')
                self.connect()

        return self.api.candles.candles_data
#######################################################
# ______________________________________________________
# _____________________REAL TIME CANDLE_________________
# ______________________________________________________
#######################################################

    def start_candles_stream(self, ACTIVE, size, maxdict):

        if size == "all":
            for s in self.size:
                self.full_realtime_get_candle(ACTIVE, s, maxdict)
                self.api.real_time_candles_maxdict_table[ACTIVE][s] = maxdict
            self.start_candles_all_size_stream(ACTIVE)
        elif size in self.size:
            self.api.real_time_candles_maxdict_table[ACTIVE][size] = maxdict
            self.full_realtime_get_candle(ACTIVE, size, maxdict)
            self.start_candles_one_stream(ACTIVE, size)

        else:
            logging.error(
                '**error** start_candles_stream please input right size')

    def stop_candles_stream(self, ACTIVE, size):
        if size == "all":
            self.stop_candles_all_size_stream(ACTIVE)
        elif size in self.size:
            self.stop_candles_one_stream(ACTIVE, size)
        else:
            logging.error(
                '**error** start_candles_stream please input right size')

    def get_realtime_candles(self, ACTIVE, size):
        if size == "all":
            try:
                return self.api.real_time_candles[ACTIVE]
            except:
                logging.error(
                    '**error** get_realtime_candles() size="all" can not get candle')
                return False
        elif size in self.size:
            try:
                return self.api.real_time_candles[ACTIVE][size]
            except:
                logging.error(
                    '**error** get_realtime_candles() size='+str(size)+' can not get candle')
                return False
        else:
            logging.error(
                '**error** get_realtime_candles() please input right "size"')

    def get_all_realtime_candles(self):
        return self.api.real_time_candles
################################################
# ---------REAL TIME CANDLE Subset Function---------
################################################
# ---------------------full dict get_candle-----------------------

    def full_realtime_get_candle(self, ACTIVE, size, maxdict):
        candles = self.get_candles(
            ACTIVE, size, maxdict, self.api.timesync.server_timestamp)
        for can in candles:
            self.api.real_time_candles[str(
                ACTIVE)][int(size)][can["from"]] = can

# ------------------------Subscribe ONE SIZE-----------------------
    def start_candles_one_stream(self, ACTIVE, size):
        if (str(ACTIVE+","+str(size)) in self.subscribe_candle) == False:
            self.subscribe_candle.append((ACTIVE+","+str(size)))
        start = time.time()
        self.api.candle_generated_check[str(ACTIVE)][int(size)] = {}
        while True:
            if time.time()-start > 20:
                logging.error(
                    '**error** start_candles_one_stream late for 20 sec')
                return False
            try:
                if self.api.candle_generated_check[str(ACTIVE)][int(size)] == True:
                    return True
            except:
                pass
            try:

                self.api.subscribe(OP_code.ACTIVES[ACTIVE], size)
            except:
                logging.error('**error** start_candles_stream reconnect')
                self.connect()
            time.sleep(1)

    def stop_candles_one_stream(self, ACTIVE, size):
        if ((ACTIVE+","+str(size)) in self.subscribe_candle) == True:
            self.subscribe_candle.remove(ACTIVE+","+str(size))
        while True:
            try:
                if self.api.candle_generated_check[str(ACTIVE)][int(size)] == {}:
                    return True
            except:
                pass
            self.api.candle_generated_check[str(ACTIVE)][int(size)] = {}
            self.api.unsubscribe(OP_code.ACTIVES[ACTIVE], size)
            time.sleep(self.suspend*10)
# ------------------------Subscribe ALL SIZE-----------------------

    def start_candles_all_size_stream(self, ACTIVE):
        self.api.candle_generated_all_size_check[str(ACTIVE)] = {}
        if (str(ACTIVE) in self.subscribe_candle_all_size) == False:
            self.subscribe_candle_all_size.append(str(ACTIVE))
        start = time.time()
        while True:
            if time.time()-start > 20:
                logging.error('**error** fail '+ACTIVE +
                              ' start_candles_all_size_stream late for 10 sec')
                return False
            try:
                if self.api.candle_generated_all_size_check[str(ACTIVE)] == True:
                    return True
            except:
                pass
            try:
                self.api.subscribe_all_size(OP_code.ACTIVES[ACTIVE])
            except:
                logging.error(
                    '**error** start_candles_all_size_stream reconnect')
                self.connect()
            time.sleep(1)

    def stop_candles_all_size_stream(self, ACTIVE):
        if (str(ACTIVE) in self.subscribe_candle_all_size) == True:
            self.subscribe_candle_all_size.remove(str(ACTIVE))
        while True:
            try:
                if self.api.candle_generated_all_size_check[str(ACTIVE)] == {}:
                    break
            except:
                pass
            self.api.candle_generated_all_size_check[str(ACTIVE)] = {}
            self.api.unsubscribe_all_size(OP_code.ACTIVES[ACTIVE])
            time.sleep(self.suspend*10)
# ------------------------top_assets_updated---------------------------------------------

    def subscribe_top_assets_updated(self, instrument_type):
        self.api.Subscribe_Top_Assets_Updated(instrument_type)

    def unsubscribe_top_assets_updated(self, instrument_type):
        self.api.Unsubscribe_Top_Assets_Updated(instrument_type)

    def get_top_assets_updated(self, instrument_type):
        if instrument_type in self.api.top_assets_updated_data:
            return self.api.top_assets_updated_data[instrument_type]
        else:
            return None

# ------------------------commission_________
#instrument_type: "binary-option"/"turbo-option"/"digital-option"/"crypto"/"forex"/"cfd"
    def subscribe_commission_changed(self, instrument_type):

        self.api.Subscribe_Commission_Changed(instrument_type)

    def unsubscribe_commission_changed(self, instrument_type):
        self.api.Unsubscribe_Commission_Changed(instrument_type)

    def get_commission_change(self, instrument_type):
        return self.api.subscribe_commission_changed_data[instrument_type]

# -----------------------------------------------

# -----------------traders_mood----------------------

    def start_mood_stream(self, ACTIVES):
        if ACTIVES in self.subscribe_mood == False:
            self.subscribe_mood.append(ACTIVES)

        while True:
            self.api.subscribe_Traders_mood(OP_code.ACTIVES[ACTIVES])
            try:
                self.api.traders_mood[OP_code.ACTIVES[ACTIVES]]
                break
            except:
                time.sleep(5)

    def stop_mood_stream(self, ACTIVES):
        if ACTIVES in self.subscribe_mood == True:
            del self.subscribe_mood[ACTIVES]
        self.api.unsubscribe_Traders_mood(OP_code.ACTIVES[ACTIVES])

    def get_traders_mood(self, ACTIVES):
        # return highter %
        return self.api.traders_mood[OP_code.ACTIVES[ACTIVES]]

    def get_all_traders_mood(self):
        # return highter %
        return self.api.traders_mood
    
##############################################################################################
    def raw_check_win(self,external_id):
        position_data=self.get_history_positions(external_id=external_id)
        ans_data=None
        for row in position_data["msg"]["positions"]:
            if row["external_id"]==external_id:
                ans_data=row
                
        if ans_data!=None:
            return round(ans_data["pnl_realized"], 2)
        
        return None

    def check_win(self, external_id,polling_time=0.5):
    
        ok_id=None
        check,data=self.get_order(external_id)
         
        def get_position_id():
            nonlocal ok_id,data,check
            if ok_id!=None:
                return ok_id
            if check:
                #for forex...
                position_id=None
                position_id=data["position_id"]
                while position_id==None:
                    _,data=self.get_order(external_id)
                    position_id=data["position_id"]
                    if data["status"]=="canceled":
                        return "canceled" 
                    time.sleep(polling_time)  
                ok_id=position_id
            else:
                ok_id=external_id
            return ok_id
        while True:
            external_id=get_position_id()
            if external_id=="canceled":
                return None
            PL=self.raw_check_win(external_id)
            if PL !=None:
                return PL
            time.sleep(polling_time)


    def check_win_v2(self, id_number, polling_time):
        while True:
            check, data = self.get_betinfo(id_number)
            win=data["result"]["data"][str(id_number)]["win"]
            if check and win!="":
                try:
                    return data["result"]["data"][str(id_number)]["profit"]-data["result"]["data"][str(id_number)]["deposit"]
                except:
                    pass
            time.sleep(polling_time)

    def check_win_v3(self, id_number,polling_time):
        while True:
            try:
                if self.get_async_order(id_number)["option-closed"] !={}:
                    break
            except:
                pass
            time.sleep(polling_time)

        return self.get_async_order(id_number)["option-closed"]["msg"]["profit_amount"]-self.get_async_order(id_number)["option-closed"]["msg"]["amount"]


# -------------------get infomation only for binary option------------------------

    def get_betinfo(self, id_number):
        # INPUT:int
        while True:
            self.api.game_betinfo.isSuccessful = None
            start = time.time()
            try:
                self.api.get_betinfo(id_number)
            except:
                logging.error(
                    '**error** def get_betinfo  self.api.get_betinfo reconnect')
                self.connect()
            while self.api.game_betinfo.isSuccessful == None:
                if time.time()-start > 10:
                    logging.error(
                        '**error** get_betinfo time out need reconnect')
                    self.connect()
                    self.api.get_betinfo(id_number)
                    time.sleep(self.suspend*10)
            if self.api.game_betinfo.isSuccessful == True:
                return self.api.game_betinfo.isSuccessful, self.api.game_betinfo.dict
            else:
                return self.api.game_betinfo.isSuccessful, None
            time.sleep(self.suspend*10)

    def get_optioninfo(self, limit):
        self.api.api_game_getoptions_result = None
        self.api.get_options(limit)
        while self.api.api_game_getoptions_result == None:
            pass

        return self.api.api_game_getoptions_result

    def get_optioninfo_v2(self, limit):
        self.api.get_options_v2_data = None
        self.api.get_options_v2(limit, "binary,turbo")
        while self.api.get_options_v2_data == None:
            pass

        return self.api.get_options_v2_data


# __________________________BUY__________________________

# __________________FOR OPTION____________________________
    #thread safe
    def buy_multi(self, price, ACTIVES, ACTION, expirations,polling=0.1):
        
        req_id=[]
        buy_len = len(price)
        for i in range(buy_len):
            req_id.append(global_value.get_req_id(self.api.object_id))


        if len(price) == len(ACTIVES) == len(ACTION) == len(expirations):
             
            for idx in range(buy_len):
                self.api.buyv3(
                    price[idx], OP_code.ACTIVES[ACTIVES[idx]], ACTION[idx], expirations[idx], req_id[idx])
             
            while True:
                check_ok=True
                for i in range(buy_len):
                    if req_id[i] not in self.api.buy_multi_option:
                        check_ok=False
                if check_ok==True:
                    break
                time.sleep(polling)
            buy_id = []
            for i in range(buy_len):
                order_data=self.api.buy_multi_option[req_id[i]]
                if "message" in order_data.keys():
                    buy_id.append(None)
                else:
                    buy_id.append(order_data["id"])
            return buy_id
        else:
            logging.error('buy_multi error please input all same len')

    def get_remaning(self, duration,time=None):
        if time==None:
            time=self.api.timesync.server_timestamp
        for remaning in get_remaning_time(time):
            if remaning[0] == duration:
                return remaning[1]
        logging.error('get_remaning(self,duration) ERROR duration')
        return "ERROR duration"

    def buy_by_raw_expirations(self, price, active, direction, option, expired):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
 
        try:
            self.api.buy_multi_option[req_id] = None
        except:
            pass
         
        if isinstance(active,int):
            self.api.buyv3_by_raw_expired(price, active, direction, option, expired, request_id=req_id)
        else:
            self.api.buyv3_by_raw_expired(price, OP_code.ACTIVES[active], direction, option, expired, request_id=req_id)
         
        while self.api.buy_multi_option[req_id] == None:
            try:
                if "message" in self.api.buy_multi_option[req_id].keys():
                    logging.error(
                        '**warning** buy'+str(self.api.buy_multi_option[req_id]["message"]))
                    return False, self.api.buy_multi_option[req_id]["message"]
            except:
                pass
            time.sleep(self.suspend)
        _order=self.api.buy_multi_option[req_id]
        
        del self.api.buy_multi_option[req_id]
       
        return True, _order
    #thread safe
    def buy(self, price, ACTIVES, ACTION, expirations,polling=0.1):    
        req_id = global_value.get_req_id(self.api.object_id)
        self.api.buy_multi_option[req_id]=None
        self.api.buyv3(
            price, OP_code.ACTIVES[ACTIVES], ACTION, expirations, req_id) 
        while self.api.buy_multi_option[req_id] == None:
            time.sleep(polling)
            pass
        try:
            if "message" in self.api.buy_multi_option[req_id].keys():
                return False, self.api.buy_multi_option[req_id]["message"]
        except:
            pass
        return True, self.api.buy_multi_option[req_id]["id"]

    
    def sell_option(self, options_ids):
        req_id=global_value.get_req_id(self.api.object_id)
        self.api.sell_option(options_ids,req_id)
        return
        """# try to low complex code for more stabel trade
        self.api.sold_options_respond[req_id] = None
        while self.api.sold_options_respond[req_id] == None:
            pass
        _tmp=self.api.sold_options_respond[req_id]
        del self.api.sold_options_respond[req_id]
        return _tmp
        """
        
# __________________for Digital___________________

    def get_digital_underlying_list_data(self,polling=0):
        self.api.underlying_list_data = None
        self.api.get_digital_underlying()
        start_t = time.time()
        while self.api.underlying_list_data == None:
            if time.time()-start_t >= 30:
                logging.error(
                    '**warning** get_digital_underlying_list_data late 30 sec')
                return None
            time.sleep(polling)
        return self.api.underlying_list_data

    def get_strike_list(self, ACTIVES, duration):
        self.api.strike_list = None
        self.api.get_strike_list(ACTIVES, duration)
        ans = {}
        while self.api.strike_list == None:
            pass
        try:
            for data in self.api.strike_list["msg"]["strike"]:
                temp = {}
                temp["call"] = data["call"]["id"]
                temp["put"] = data["put"]["id"]
                ans[("%.6f" % (float(data["value"])*10e-7))] = temp
        except:
            logging.error('**error** get_strike_list read problem...')
            return self.api.strike_list, None
        return self.api.strike_list, ans

    def subscribe_strike_list(self, ACTIVE, expiration_period):
        self.api.subscribe_instrument_quites_generated(
            ACTIVE, expiration_period)

    def unsubscribe_strike_list(self, ACTIVE, expiration_period):
        self.api.unsubscribe_instrument_quites_generated(
            ACTIVE, expiration_period)

    def get_instrument_quites_generated_data(self, ACTIVE, duration):
        while self.api.instrument_quotes_generated_raw_data[ACTIVE][duration*60] == {}:
            pass
        return self.api.instrument_quotes_generated_raw_data[ACTIVE][duration*60]

    def get_realtime_strike_list(self, ACTIVE, duration):
        while True:
            if not self.api.instrument_quites_generated_data[ACTIVE][duration*60]:
                pass
            else:
                break
        
        """ans = {}
        now_timestamp = self.api.instrument_quites_generated_timestamp[ACTIVE][duration*60]

        while ans == {}:
            if self.get_realtime_strike_list_temp_data == {} or now_timestamp != self.get_realtime_strike_list_temp_expiration:
                raw_data, strike_list = self.get_strike_list(ACTIVE, duration)
                self.get_realtime_strike_list_temp_expiration = raw_data["msg"]["expiration"]
                self.get_realtime_strike_list_temp_data = strike_list
            else:
                strike_list = self.get_realtime_strike_list_temp_data

            profit = self.api.instrument_quites_generated_data[ACTIVE][duration*60]
            for price_key in strike_list:
                try:
                    side_data = {}
                    for side_key in strike_list[price_key]:
                        detail_data = {}
                        profit_d = profit[strike_list[price_key][side_key]]
                        detail_data["profit"] = profit_d
                        detail_data["id"] = strike_list[price_key][side_key]
                        side_data[side_key] = detail_data
                    ans[price_key] = side_data
                except:
                    pass"""

        return self.api.instrument_quites_generated_data[ACTIVE][duration*60]
    def get_top_asset(self,instrument_type):
        #instrument_type=binary-option/digital-option/forex/cfd/crypto
        req_id=global_value.get_req_id(self.api.object_id)
        self.api.get_top_assets_data[req_id]=None
        self.api.get_top_assets(instrument_type,req_id)
        while self.api.get_top_assets_data[req_id]==None:
            pass
        _tmp=self.api.get_top_assets_data[req_id]
        del self.api.get_top_assets_data[req_id]
        return _tmp
    def get_digital_current_profit(self, ACTIVE, duration):
        
        profit = self.api.digital_profit[ACTIVE][duration*60]
        if profit!={}:
            return profit
        else:
            return False
         
    # thank thiagottjv
    # https://github.com/Lu-Yi-Hsun/iqoptionapi/issues/65#issuecomment-513998357

    def old_buy_digital_spot(self, active, amount, action, duration):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
         
        # Expiration time need to be formatted like this: YYYYMMDDHHII
        # And need to be on GMT time

        #Type - P or C
        if action == 'put':
            action = 'P'
        elif action == 'call':
            action = 'C'
        else:
            logging.error('buy_digital_spot active error')
            return -1
        # doEURUSD201907191250PT5MPSPT
        # do1A20210224D154900T1MCSPT
        timestamp = int(self.api.timesync.server_timestamp)
        if duration == 1:
            exp, _ = get_expiration_time(timestamp, duration)
        else:
            now_date = datetime.fromtimestamp(
                timestamp)+timedelta(minutes=1, seconds=30)
            while True:
                if now_date.minute % duration == 0 and time.mktime(now_date.timetuple())-timestamp > 30:
                    break
                now_date = now_date+timedelta(minutes=1)
            exp = time.mktime(now_date.timetuple())

        dateFormated = str(datetime.utcfromtimestamp(
            exp).strftime("%Y%m%d%H%M"))
        instrument_id = "do" + active + dateFormated + \
            "PT" + str(duration) + "M" + action + "SPT"
         
        self.api.digital_option_placed[req_id] = None
      
        self.api.place_digital_option(instrument_id, amount,request_id=req_id)
        while self.api.digital_option_placed[req_id] == None:
            pass
        _tmp=self.api.digital_option_placed[req_id]
        del self.api.digital_option_placed[req_id]
        try:
            id=_tmp["msg"]["id"]
        except:
            return False,_tmp
        while len(self.api.order_async[int(id)]["position-changed"])==0:
            print(self.api.order_async[int(id)]["position-changed"])
            time.sleep(self.suspend)
            pass
        try:
            ok=self.api.order_async[int(id)]["position-changed"]["msg"]["external_id"]
            return True,ok
        except:
            return False,None
    def buy_digital_spot(self, active, amount, action, duration):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
        # Expiration time need to be formatted like this: YYYYMMDDHHII
        # And need to be on GMT time
        #Type - P or C
        if action == 'put':
            action = 'P'
        elif action == 'call':
            action = 'C'
        else:
            logging.error('buy_digital_spot active error')
            return -1
        # doEURUSD 20190719 1250PT5MPSPT
        # do1A     20210224D154900T1MCSPT
        
        timestamp = int(self.api.timesync.server_timestamp)
        if duration == 1:
            exp, _ = get_expiration_time(timestamp, duration)
        else:
            now_date = datetime.fromtimestamp(
                timestamp)+timedelta(minutes=1, seconds=30)
            while True:
                if now_date.minute % duration == 0 and time.mktime(now_date.timetuple())-timestamp > 30:
                    break
                now_date = now_date+timedelta(minutes=1)
            exp = time.mktime(now_date.timetuple())

        dateFormated = str(datetime.utcfromtimestamp(
            exp).strftime("%Y%m%dD%H%M"))
        instrument_id = "do" + str(OP_code.ACTIVES[active]) +"A"+ dateFormated +"00"+ \
            "T" + str(duration) + "M" + action + "SPT"
         
        self.api.digital_option_placed[req_id] = None
      
        self.api.place_digital_option_v2(instrument_id, amount,request_id=req_id)
        while self.api.digital_option_placed[req_id] == None:
            time.sleep(self.suspend)
            pass
        _tmp=self.api.digital_option_placed[req_id]
        del self.api.digital_option_placed[req_id]
        try:
            id=_tmp["msg"]["id"]
        except:
            return False,_tmp
        while len(self.api.order_async[int(id)]["position-changed"])==0:
            time.sleep(self.suspend)
            pass
        try:
            ok=self.api.order_async[int(id)]["position-changed"]["msg"]["external_id"]
            return True,ok
        except:
            return False,None


    def get_digital_spot_profit_after_sale(self, position_id):
        def get_instrument_id_to_bid(data, instrument_id):
            for row in data["msg"]["prices"]:
                if row["call"]["symbol"] == instrument_id:
                    return row["call"]["bid"]
                if row["put"]["symbol"] == instrument_id:
                    return row["put"]["bid"]
            return None
        # Author:Lu-Yi-Hsun 2019/11/04
        # email:yihsun1992@gmail.com
        # Source code reference
        # https://github.com/Lu-Yi-Hsun/Decompiler-IQ-Option/blob/master/Source%20Code/5.27.0/sources/com/iqoption/dto/entity/position/Position.java#L564
        while self.get_async_order(position_id)["position-changed"] == {}:
            pass
        # ___________________/*position*/_________________
        position = self.get_async_order(position_id)["position-changed"]["msg"]["raw_event"]
        # doEURUSD201911040628PT1MPSPT
        # z mean check if call or not
        if position["instrument_id"].find("MPSPT"):
            z = False
        elif position["instrument_id"].find("MCSPT"):
            z = True
        else:
            logging.error(
                'get_digital_spot_profit_after_sale position error'+str(position["instrument_id"]))
      
        ACTIVES = position["instrument_underlying"]
        amount = max(position["buy_amount"], position["sell_amount"])
        start_duration = position["instrument_id"].find("PT")+2
        end_duration = start_duration + \
            position["instrument_id"][start_duration:].find("M")

        duration = int(position["instrument_period"]/60)
        z2 = False

        getAbsCount = position["count"]
        instrumentStrikeValue = position["instrument_strike_value"]/1000000.0
        spotLowerInstrumentStrike = position["extra_data"]["lower_instrument_strike"]/1000000.0
        spotUpperInstrumentStrike = position["extra_data"]["upper_instrument_strike"]/1000000.0

        aVar = position["extra_data"]["lower_instrument_id"]
        aVar2 = position["extra_data"]["upper_instrument_id"]
        getRate = position["currency_rate"]
         
        # ___________________/*position*/_________________
        instrument_quites_generated_data = self.get_instrument_quites_generated_data(
            ACTIVES, duration)
        
        # https://github.com/Lu-Yi-Hsun/Decompiler-IQ-Option/blob/master/Source%20Code/5.5.1/sources/com/iqoption/dto/entity/position/Position.java#L493
        f_tmp = get_instrument_id_to_bid(
            instrument_quites_generated_data, aVar)
        # f is bidprice of lower_instrument_id ,f2 is bidprice of upper_instrument_id
        if f_tmp != None:
            self.get_digital_spot_profit_after_sale_data[position_id]["f"] = f_tmp
            f = f_tmp
        else:
            f = self.get_digital_spot_profit_after_sale_data[position_id]["f"]

        f2_tmp = get_instrument_id_to_bid(
            instrument_quites_generated_data, aVar2)
        if f2_tmp != None:
            self.get_digital_spot_profit_after_sale_data[position_id]["f2"] = f2_tmp
            f2 = f2_tmp
        else:
            f2 = self.get_digital_spot_profit_after_sale_data[position_id]["f2"]

        if (spotLowerInstrumentStrike != instrumentStrikeValue) and f != None and f2 != None:

            if (spotLowerInstrumentStrike > instrumentStrikeValue or instrumentStrikeValue > spotUpperInstrumentStrike):
                if z:
                    instrumentStrikeValue = (spotUpperInstrumentStrike - instrumentStrikeValue) / abs(
                        spotUpperInstrumentStrike - spotLowerInstrumentStrike)
                    f = abs(f2 - f)
                else:
                    instrumentStrikeValue = (instrumentStrikeValue - spotUpperInstrumentStrike) / abs(
                        spotUpperInstrumentStrike - spotLowerInstrumentStrike)
                    f = abs(f2 - f)

            elif z:
                f += ((instrumentStrikeValue - spotLowerInstrumentStrike) /
                      (spotUpperInstrumentStrike - spotLowerInstrumentStrike)) * (f2 - f)
            else:
                instrumentStrikeValue = (spotUpperInstrumentStrike - instrumentStrikeValue) / (
                    spotUpperInstrumentStrike - spotLowerInstrumentStrike)
                f -= f2
            f = f2 + (instrumentStrikeValue * f)

        if z2:
            pass
        if f != None:
            # price=f/getRate
            # https://github.com/Lu-Yi-Hsun/Decompiler-IQ-Option/blob/master/Source%20Code/5.27.0/sources/com/iqoption/dto/entity/position/Position.java#L603
            price = (f/getRate)
            # getAbsCount Reference
            # https://github.com/Lu-Yi-Hsun/Decompiler-IQ-Option/blob/master/Source%20Code/5.27.0/sources/com/iqoption/dto/entity/position/Position.java#L450
            return price*getAbsCount-amount
        else:
            return None

    def buy_digital(self, amount, instrument_id):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
        self.api.digital_option_placed[req_id] = None
        self.api.place_digital_option_v2(instrument_id, amount,request_id=req_id)
        while self.api.digital_option_placed[req_id] == None:
            pass
        _tmp=self.api.digital_option_placed[req_id]
        del self.api.digital_option_placed[req_id]
        if "id" in _tmp["msg"]:
            
            _id=int(_tmp["msg"]["id"])
            while True:
                 
                if _id in self.api.order_async:
                     
                    if "order-changed" in self.api.order_async[_id]:
                        return True,self.api.order_async[_id]["order-changed"]
        return False,None

    def close_digital_option(self, external_id):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
        self.api.result[req_id] = None
        self.api.close_digital_option(external_id,req_id)
        while self.api.result[req_id] == None:
            pass
        return self.api.result[req_id]

    def close_digital_option_batch(self, external_id:list):
        #thread safe
        req_id = global_value.get_req_id(self.api.object_id)
        self.api.result[req_id] = None
        self.api.close_digital_option_batch(external_id,req_id)
        while self.api.result[req_id] == None:
            pass
        return self.api.result[req_id]

    def check_win_digital(self, buy_order_id, polling_time):
        while True:
            time.sleep(polling_time)
            data = self.get_digital_position(buy_order_id)

            if data["msg"]["position"]["status"] == "closed":
                if data["msg"]["position"]["close_reason"] == "default":
                    return data["msg"]["position"]["pnl_realized"]
                elif data["msg"]["position"]["close_reason"] == "expired":
                    return data["msg"]["position"]["pnl_realized"]-data["msg"]["position"]["buy_amount"]

    def check_win_digital_v2(self, buy_order_id):
         
        while self.get_async_order(buy_order_id)["position-changed"]=={}:
            pass
        order_data = self.get_async_order(buy_order_id)["position-changed"]["msg"]
        if order_data != None:
            if order_data["status"] == "closed":
                if order_data["close_reason"] == "expired":
                    return True,order_data["close_profit"]- order_data["invest"] 
                elif order_data["close_reason"] == "default":
                    return True, order_data["pnl_realized"]
            else:
                return False, None
        else:
            return False, None

# ----------------------------------------------------------
# -----------------BUY_for__Forex__&&__stock(cfd)__&&__ctrpto

    def buy_order(self,
                  instrument_type, instrument_id,
                  side, amount, leverage,
                  type, limit_price=None, stop_price=None,

                  stop_lose_kind=None, stop_lose_value=None,
                  take_profit_kind=None, take_profit_value=None,

                  use_trail_stop=False, auto_margin_call=False,
                  use_token_for_commission=False):
        req_id=global_value.get_req_id(self.api.object_id)
         
        self.api.buy_order_id[req_id] = None
        self.api.buy_order(
            instrument_type=instrument_type, instrument_id=instrument_id,
            side=side, amount=amount, leverage=leverage,
            type=type, limit_price=limit_price, stop_price=stop_price,
            stop_lose_value=stop_lose_value, stop_lose_kind=stop_lose_kind,
            take_profit_value=take_profit_value, take_profit_kind=take_profit_kind,
            use_trail_stop=use_trail_stop, auto_margin_call=auto_margin_call,
            use_token_for_commission=use_token_for_commission,req_id=req_id
        )

        while self.api.buy_order_id[req_id] == None:
            pass
        check, data = self.get_order(self.api.buy_order_id[req_id])
        while data["status"] == "pending_new":
            check, data = self.get_order(self.api.buy_order_id[req_id])
            time.sleep(1)

        if check:
            if data["status"] != "rejected":
                return True, self.api.buy_order_id[req_id]
            else:
                return False, data["reject_status"]
        else:

            return False, None

    def change_auto_margin_call(self, ID_Name, ID, auto_margin_call):
        self.api.auto_margin_call_changed_respond = None
        self.api.change_auto_margin_call(ID_Name, ID, auto_margin_call)
        while self.api.auto_margin_call_changed_respond == None:
            pass
        if self.api.auto_margin_call_changed_respond["status"] == 2000:
            return True, self.api.auto_margin_call_changed_respond
        else:
            return False, self.api.auto_margin_call_changed_respond

    def change_order(self, ID_Name, order_id,
                     stop_lose_kind, stop_lose_value,
                     take_profit_kind, take_profit_value,
                     use_trail_stop, auto_margin_call):
        check = True
        if ID_Name == "position_id":
            check, order_data = self.get_order(order_id)
            position_id = order_data["position_id"]
            ID = position_id
        elif ID_Name == "order_id":
            ID = order_id
        else:
            logging.error('change_order input error ID_Name')

        if check:
            self.api.tpsl_changed_respond = None
            self.api.change_order(
                ID_Name=ID_Name, ID=ID,
                stop_lose_kind=stop_lose_kind, stop_lose_value=stop_lose_value,
                take_profit_kind=take_profit_kind, take_profit_value=take_profit_value,
                use_trail_stop=use_trail_stop)
            self.change_auto_margin_call(
                ID_Name=ID_Name, ID=ID, auto_margin_call=auto_margin_call)
            while self.api.tpsl_changed_respond == None:
                pass
            if self.api.tpsl_changed_respond["status"] == 2000:
                return True, self.api.tpsl_changed_respond["msg"]
            else:
                return False, self.api.tpsl_changed_respond
        else:
            logging.error('change_order fail to get position_id')
            return False, None

    def get_async_order(self, buy_order_id):
        #name': 'position-changed', 'microserviceName': "portfolio"/"digital-options"
        return self.api.order_async[buy_order_id]
       

    def get_order(self, buy_order_id):
        #thread safe
        # self.api.order_data["status"]
        # reject:you can not get this order
        # pending_new:this order is working now
        # filled:this order is ok now
        # new
        req_id=global_value.get_req_id(self.api.object_id)

        self.api.order_data[req_id] = None
        self.api.get_order(buy_order_id,request_id=req_id)
        while self.api.order_data[req_id] == None:
            pass
        if self.api.order_data[req_id]["status"] == 2000:
            return True, self.api.order_data[req_id]["msg"]
        else:
            return False, None

    def get_pending(self, instrument_type):
        self.api.deferred_orders = None
        self.api.get_pending(instrument_type)
        while self.api.deferred_orders == None:
            pass
        if self.api.deferred_orders["status"] == 2000:
            return True, self.api.deferred_orders["msg"]
        else:
            return False, None

    def get_transactions(self,from_t:int,to_t:int,limit:int,offset:int,types:list):
        """
        "types":["airdrop","commission","deposit","emission",
        "manual","order_purchase","order_sell","tournament_rebuy",
        "tournament_registration","tournament_reward","transfer","withdrawal"]
        """
        req_id=global_value.get_req_id(self.api.object_id)
        self.api.transactions[req_id]=None
        self.api.get_transactions(from_t,to_t,limit,offset,types,request_id=req_id)
        while self.api.transactions[req_id]==None:
            pass
        _tmp=self.api.transactions[req_id]
        del self.api.transactions[req_id]
        return _tmp
    # this function is heavy
    def get_positions(self, instrument_type):
        self.api.positions = None
        self.api.get_positions(instrument_type)
        while self.api.positions == None:
            pass
        if self.api.positions["status"] == 2000:
            return True, self.api.positions["msg"]
        else:
            return False, None

    def get_position(self, buy_order_id):
        self.api.position = None
        check, order_data = self.get_order(buy_order_id)
        position_id = order_data["position_id"]
        self.api.get_position(position_id)
        while self.api.position == None:
            pass
        if self.api.position["status"] == 2000:
            return True, self.api.position["msg"]
        else:
            return False, None
    # this function is heavy

    def get_digital_position_by_position_id(self, position_id):
        self.api.position = None
        self.api.get_digital_position(position_id)
        while self.api.position == None:
            pass
        return self.api.position

    def get_digital_position(self, order_id):
        self.api.position = None
        while self.get_async_order(order_id)["position-changed"] == {}:
            pass
        position_id = self.get_async_order(order_id)["position-changed"]["msg"]["external_id"]
        self.api.get_digital_position(position_id)
        while self.api.position == None:
            pass
        return self.api.position

    def get_position_history(self, instrument_type):
        self.api.position_history = None
        self.api.get_position_history(instrument_type)
        while self.api.position_history == None:
            pass

        if self.api.position_history["status"] == 2000:
            return True, self.api.position_history["msg"]
        else:
            return False, None
    def get_history_positions(self,external_id,polling_time=0.5):
        req_id=global_value.get_req_id(self.api.object_id)
        self.api.history_positions[req_id]=None
        self.api.get_history_positions(external_id,request_id=req_id)
        while self.api.history_positions[req_id]==None:
            time.sleep(polling_time)
        _tmp=self.api.history_positions[req_id]
        del self.api.history_positions[req_id]
        return _tmp

    def get_position_history_v2(self,user_balance_id,start,end,offset,limit,instrument_type):
        # instrument_type=crypto forex fx-option multi-option cfd digital-option turbo-option
        req_id=global_value.get_req_id(self.api.object_id)
        
        self.api.position_history_v2[req_id] = {}
        self.api.get_position_history_v2(user_balance_id,start,end,offset,limit,instrument_type,request_id=req_id)
        while self.api.position_history_v2[req_id] == {}:
            pass
        req=self.api.position_history_v2[req_id]
        del self.api.position_history_v2[req_id]
        if req["status"] == 2000:
            return True,req["msg"]
        else:
            return False, None

    def get_available_leverages(self, instrument_type, actives=""):
        self.api.available_leverages = None
        if actives == "":
            self.api.get_available_leverages(instrument_type, "")
        else:
            self.api.get_available_leverages(
                instrument_type, OP_code.ACTIVES[actives])
        while self.api.available_leverages == None:
            pass
        if self.api.available_leverages["status"] == 2000:
            return True, self.api.available_leverages["msg"]
        else:
            return False, None

    def cancel_order(self, buy_order_id):
        self.api.order_canceled = None
        self.api.cancel_order(buy_order_id)
        while self.api.order_canceled == None:
            pass
        if self.api.order_canceled["status"] == 2000:
            return True
        else:
            return False

    def close_position(self, position_id):
        check, data = self.get_order(position_id)
        if data["position_id"] != None:
            self.api.close_position_data = None
            self.api.close_position(data["position_id"])
            while self.api.close_position_data == None:
                pass
            if self.api.close_position_data["status"] == 2000:
                return True
            else:
                return False
        else:
            return False

    def close_position_v2(self, position_id):
        while self.get_async_order(position_id) == None:
            pass
        position_changed = self.get_async_order(position_id)
        self.api.close_position(position_changed["id"])
        while self.api.close_position_data == None:
            pass
        if self.api.close_position_data["status"] == 2000:
            return True
        else:
            return False

    def get_overnight_fee(self, instrument_type, active):
        self.api.overnight_fee = None
        self.api.get_overnight_fee(instrument_type, OP_code.ACTIVES[active])
        while self.api.overnight_fee == None:
            pass
        if self.api.overnight_fee["status"] == 2000:
            return True, self.api.overnight_fee["msg"]
        else:
            return False, None

    def get_option_open_by_other_pc(self):
        return self.api.socket_option_opened
    def del_option_open_by_other_pc(self, id):
        try:
            del self.api.socket_option_opened[id]
        except:
            pass
    def get_digital_open_by_other_pc(self):
        return self.api.digital_opened
    def del_digital_open_by_other_pc(self, id):
        try:
            del self.api.digital_opened[id]
        except:
            pass


# -----------------------------------------------------------------

    def opcode_to_name(self, opcode):
        return list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(opcode)]

    # name:
    # "live-deal-binary-option-placed"
    # "live-deal-digital-option"
    def subscribe_live_deal(self, name, active, _type, buffersize):
        active_id = OP_code.ACTIVES[active]
        self.api.Subscribe_Live_Deal(name, active_id, _type)
        """
        self.api.live_deal_data[name][active][_type]=deque(list(),buffersize) 
        
        while len(self.api.live_deal_data[name][active][_type])==0:
            self.api.Subscribe_Live_Deal(name,active_id,_type)
            time.sleep(1)
        """

    def unscribe_live_deal(self, name, active, _type):
        active_id = OP_code.ACTIVES[active]
        self.api.Unscribe_Live_Deal(name, active_id, _type)
        """
         
        while len(self.api.live_deal_data[name][active][_type])!=0:
            self.api.Unscribe_Live_Deal(name,active_id,_type)
            del self.api.live_deal_data[name][active][_type]
            time.sleep(1)
        """

    def get_live_deal(self, name, active, _type):
        return self.api.live_deal_data[name][active][_type]

    def pop_live_deal(self, name, active, _type):
        return self.api.live_deal_data[name][active][_type].pop()

    def clear_live_deal(self, name, active, _type, buffersize):
        self.api.live_deal_data[name][active][_type] = deque(
            list(), buffersize)

    def get_user_profile_client(self, user_id):
        self.api.user_profile_client = None
        self.api.Get_User_Profile_Client(user_id)
        while self.api.user_profile_client == None:
            pass

        return self.api.user_profile_client

    def request_leaderboard_userinfo_deals_client(self, user_id, country_id):
        self.api.leaderboard_userinfo_deals_client = None

        while True:
            try:
                if self.api.leaderboard_userinfo_deals_client["isSuccessful"] == True:
                    break
            except:
                pass
            self.api.Request_Leaderboard_Userinfo_Deals_Client(
                user_id, country_id)
            time.sleep(0.2)

        return self.api.leaderboard_userinfo_deals_client

    def get_users_availability(self, user_id):
        self.api.users_availability = None

        while self.api.users_availability == None:
            self.api.Get_Users_Availability(user_id)
            time.sleep(0.2)
        return self.api.users_availability
