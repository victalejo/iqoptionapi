"""Module for IQ option websocket."""

import json
import logging
import websocket
import iqoptionapi.constants as OP_code
import iqoptionapi.global_value as global_value

from collections import defaultdict
def nested_dict(n, type):
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n-1, type))

                
class WebsocketClient(object):
    """Class for work with IQ option websocket."""

    def __init__(self, api):
        """
        :param api: The instance of :class:`IQOptionAPI
            <iqoptionapi.api.IQOptionAPI>`.
        """
        self.api = api
        self.wss = websocket.WebSocketApp(
            self.api.wss_url, on_message=self.on_message,
            on_error=self.on_error, on_close=self.on_close,
            on_open=self.on_open)
    def dict_queue_add(self,dict,maxdict,key1,key2,key3,value):
        if key3 in dict[key1][key2]:
                    dict[key1][key2][key3]=value
        else:
            while True:
                try:
                    dic_size=len(dict[key1][key2])
                except:
                    dic_size=0
                if dic_size<maxdict:
                    dict[key1][key2][key3]=value
                    break
                else:
                    #del mini key
                    del dict[key1][key2][sorted(dict[key1][key2].keys(), reverse=False)[0]]   
    def on_message(self, ws, message): # pylint: disable=unused-argument
         
        """Method to process websocket messages."""
         
        global_value.ssl_Mutex[self.api.object_id].acquire()
        logger = logging.getLogger(__name__)
        logger.debug(message)

        message = json.loads(str(message))
        if self.api.object_id in global_value.client_callback:
            global_value.client_callback[self.api.object_id](message)
        if message["name"] == "timeSync":
            self.api.timesync.server_timestamp = message["msg"]
         #######################################################
        #---------------------for_realtime_candle______________
        #######################################################
        elif message["name"] == "candle-generated":
            Active_name=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(message["msg"]["active_id"])]            
            
            active=str(Active_name)
            size=int(message["msg"]["size"])
            from_=int(message["msg"]["from"])
            msg=message["msg"]
            maxdict=self.api.real_time_candles_maxdict_table[Active_name][size]

            self.dict_queue_add(self.api.real_time_candles,maxdict,active,size,from_,msg)
            self.api.candle_generated_check[active][size]=True
            
        elif message["name"]=="options":
            self.api.get_options_v2_data=message
        elif message["name"] == "candles-generated":
            Active_name=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(message["msg"]["active_id"])] 
            active=str(Active_name)      
            for k,v in message["msg"]["candles"].items():
                v["active_id"]=message["msg"]["active_id"]
                v["at"]=message["msg"]["at"]
                v["ask"]=message["msg"]["ask"]
                v["bid"]=message["msg"]["bid"]
                v["close"]=message["msg"]["value"]
                v["size"]=int(k)
                size=int(v["size"])
                from_=int(v["from"])
                maxdict=self.api.real_time_candles_maxdict_table[Active_name][size]
                msg=v
                self.dict_queue_add(self.api.real_time_candles,maxdict,active,size,from_,msg)
            self.api.candle_generated_all_size_check[active]=True 
        elif message["name"]=="commission-changed":
            instrument_type=message["msg"]["instrument_type"]
            active_id=message["msg"]["active_id"]
            Active_name=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(active_id)]            
            commission=message["msg"]["commission"]["value"]
            self.api.subscribe_commission_changed_data[instrument_type][Active_name][self.api.timesync.server_timestamp]=int(commission)
            
        #######################################################
        #______________________________________________________
        #######################################################
        elif message["name"] =="heartbeat":
            try:
                self.api.heartbeat(message["msg"])
            except:
                pass
        elif message["name"]=="balances":
            if global_value.balance_id[self.api.object_id]==None:
                for balance in message["msg"]:
                    if balance["type"]==4:
                        global_value.balance_id[self.api.object_id]=balance["id"]
            self.api.balances_raw=message
            
        elif message["name"] == "profile":
            #--------------all-------------
            self.api.profile.msg=message["msg"]
             
        elif message["name"] == "authenticated":
            #--------------all-------------
            try:
                self.api.authenticated=message["msg"]
            except:
                pass
        elif message["name"] == "candles":
            try:
                self.api.candles.candles_data = message["msg"]["candles"]
            except:
                pass
        #Make sure ""self.api.buySuccessful"" more stable
        #check buySuccessful have two fail action
        #if "user not authorized" we get buyV2_result !!!need to reconnect!!!
        #elif "we have user authoget_balancerized" we get buyComplete
        #I Suggest if you get selget_balancef.api.buy_successful==False you need to reconnect iqoption server
        elif message["name"] == "buyComplete":
            try:
                self.api.buy_successful = message["msg"]["isSuccessful"]
                self.api.buy_id= message["msg"]["result"]["id"]
            except:
                pass
        elif message["name"] == "buyV2_result":
            self.api.buy_successful = message["msg"]["isSuccessful"]
        #*********************buyv3
        #buy_multi_option
        elif message["name"] == "option":
            self.api.buy_multi_option[str(message["request_id"])] = message["msg"]
        #**********************************************************   
        elif message["name"] == "listInfoData":
           for get_m in message["msg"]:
               self.api.listinfodata.set(get_m["win"],get_m["game_state"],get_m["id"])
        
    
            
        elif message["name"] == "api_option_init_all_result":
            self.api.api_option_init_all_result = message["msg"]
        elif message["name"] == "initialization-data":
            self.api.api_option_init_all_result_v2 = message["msg"]
        elif message["name"] == "underlying-list":
            self.api.underlying_list_data=message["msg"]
        elif message["name"] == "instruments":
            self.api.instruments=message["msg"]
        elif message["name"]=="financial-information":
            self.api.financial_information=message
 
        elif message["name"]=="order-changed":
            if message["microserviceName"]=="portfolio":
                if message["msg"]["source"]=="digital-options":
                    self.api.order_async[int(message["msg"]["raw_event"]["position_id"])][message["name"]]=message
                    self.api.order_async[int(message["msg"]["raw_event"]["id"])][message["name"]]=message
                    
        elif message["name"]=="position-changed":
            
            self.api.position_changed=message
            if message["microserviceName"]=="portfolio" and (message["msg"]["source"]=="digital-options") or message["msg"]["source"]=="trading":
                
                self.api.order_async[int(message["msg"]["raw_event"]["order_ids"][0])] [message["name"]]=message
                
                self.api.order_async[int(message["msg"]["external_id"])][message["name"]]=message
            elif message["microserviceName"]=="portfolio" and message["msg"]["source"]=="binary-options":
                self.api.order_async[int(message["msg"]["external_id"])] [message["name"]]=message
                #print(message)
            if message["msg"]["source"]=="binary-options"and message["msg"]["status"]=="open":
                id=message["msg"]["external_id"]
                self.api.socket_option_opened[id]=message
            elif message["msg"]["source"]=="digital-options"and message["msg"]["status"]=="open":
                id=message["msg"]["external_id"]
                self.api.digital_opened[id]=message

        elif message["name"]=="option-opened":
            self.api.order_async[int(message["msg"]["option_id"])][message["name"]]=message
       
        elif message["name"]=="option-closed":
             
            self.api.order_async[int(message["msg"]["option_id"])][message["name"]]=message
        
       
        elif message["name"]=="top-assets-updated":
            self.api.top_assets_updated_data[str(message["msg"]["instrument_type"])]=message["msg"]["data"]
        elif message["name"]=="strike-list":  
            self.api.strike_list=message
        elif message["name"]=="api_game_betinfo_result":
            try:
                self.api.game_betinfo.isSuccessful=message["msg"]["isSuccessful"]
                self.api.game_betinfo.dict=message["msg"]
            except:
                pass
        elif message["name"]=="traders-mood-changed":
            self.api.traders_mood[message["msg"]["asset_id"]]=message["msg"]["value"]
        #------for forex&cfd&crypto..
        elif message["name"]=="order-placed-temp":
            self.api.buy_order_id[message["request_id"]]= message["msg"]["id"]
        elif message["name"]=="order":
            self.api.order_data[message["request_id"]]=message
        elif message["name"]=="positions":
            self.api.positions=message
        elif message["name"]=="position":
            self.api.position=message
        elif message["name"]=="deferred-orders":
            self.api.deferred_orders=message

        elif message["name"]=="position-history":
            self.api.position_history=message
        elif message["name"]=="history":
            self.api.position_history_v2[str(message["request_id"])]=message   
        elif message["name"]=="history-positions":
            self.api.history_positions[str(message["request_id"])]=message
        elif message["name"]=="available-leverages":
            self.api.available_leverages=message
        elif message["name"]=="order-canceled":
            self.api.order_canceled=message
        elif message["name"]=="position-closed":
            self.api.close_position_data=message
        elif message["name"]=="overnight-fee":
            self.api.overnight_fee=message
        elif message["name"]=="api_game_getoptions_result":
            self.api.api_game_getoptions_result=message
        elif message["name"]=="sold-options":
            self.api.sold_options_respond[message["request_id"]]=message
        elif message["name"]=="tpsl-changed":
            self.api.tpsl_changed_respond=message
        elif message["name"]=="auto-margin-call-changed":
            self.api.auto_margin_call_changed_respond=message
        elif message["name"]=="digital-option-placed":
        
            try:
                self.api.digital_option_placed[message["request_id"]]=message
            except:
                pass
        elif message["name"]=="result":
            """{"name":"result","request_id":"","msg":{"success":true}}"""
            if message["request_id"]!="":
                self.api.result[str(message["request_id"])]=message["msg"]["success"]
        elif message["name"]=="client-price-generated":
            
            Active_name=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(message["msg"]["asset_id"])] 
            ans=nested_dict(2,dict)
            for strike in message["msg"]["prices"]:
                
                if "ask" not in strike["call"]:
                    ProfitPercent=None
                else:
                    askPrice=(float)(strike["call"]["ask"])
                    ProfitPercent=((100-askPrice)*100)/askPrice

                if "ask" not in strike["put"]: 
                    ProfitPercent_put=None
                else:
                    askPrice=(float)(strike["put"]["ask"])
                    ProfitPercent_put=((100-askPrice)*100)/askPrice

                if strike["strike"]=="SPT":
                    
                    symbol=strike["call"]["symbol"]
                    try:
                        minute=int(symbol.split("T")[1].split("M")[0])
                    except:
                        return
                    self.api.digital_profit[Active_name][minute*60]=ProfitPercent
                    self.api.instrument_quotes_generated_raw_data[Active_name][minute*60]=message
                
                ans[strike["strike"]]["call"]["id"]=strike["call"]["symbol"]
                ans[strike["strike"]]["call"]["profit"]=ProfitPercent#strike["call"]["symbol"]

                ans[strike["strike"]]["put"]["id"]=strike["put"]["symbol"]
                ans[strike["strike"]]["put"]["profit"]=ProfitPercent_put#strike["put"]["symbol"]
            #print(ans)
            self.api.instrument_quites_generated_data[Active_name][minute*60]=ans


        elif message["name"]=="instrument-quotes-generated":
             
            Active_name=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(message["msg"]["active"])]  
            period=message["msg"]["expiration"]["period"] 
            ans={}
            for data in message["msg"]["quotes"]:
                #FROM IQ OPTION SOURCE CODE
                #https://github.com/Lu-Yi-Hsun/Decompiler-IQ-Option/blob/master/Source%20Code/5.5.1/sources/com/iqoption/dto/entity/strike/Quote.java#L91
                if data["price"]["ask"]==None:
                    ProfitPercent=None
                else:
                    askPrice=(float)(data["price"]["ask"])
                    ProfitPercent=((100-askPrice)*100)/askPrice
                
                for symble in data["symbols"]:
                    try:
                        """
                        ID SAMPLE:doUSDJPY-OTC201811111204PT1MC11350481
                        """

                        """
                        dict ID-prodit:{ID:profit}
                        """

                        ans[symble]=ProfitPercent
                    except:
                        pass
            self.api.instrument_quites_generated_timestamp[Active_name][period]=message["msg"]["expiration"]["timestamp"]
            self.api.instrument_quites_generated_data[Active_name][period]=ans

            self.api.instrument_quotes_generated_raw_data[Active_name][period]=message
        elif message["name"]=="training-balance-reset":
            self.api.training_balance_reset_request=message["msg"]["isSuccessful"]
        elif message["name"]=="top-assets":
            self.api.get_top_assets_data[message["request_id"]]=message["msg"]
            
        elif message["name"]=="live-deal-binary-option-placed":
            name=message["name"]
            active_id=message["msg"]["active_id"]
            active=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(active_id)] 
            _type=message["msg"]["option_type"]
            try:
                self.api.live_deal_data[name][active][_type].appendleft(message["msg"])
            except:
                pass
        elif message["name"]=="live-deal-digital-option":
            name=message["name"]
            active_id=message["msg"]["instrument_active_id"]
            active=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(active_id)] 
            _type=message["msg"]["expiration_type"]
            try:
                self.api.live_deal_data[name][active][_type].appendleft(message["msg"])
            except:
                pass

        elif message["name"]=="leaderboard-deals-client":
            self.api.leaderboard_deals_client=message["msg"]
        elif message["name"]=="live-deal":
            name=message["name"]
            active_id=message["msg"]["instrument_active_id"]
            active=list(OP_code.ACTIVES.keys())[list(OP_code.ACTIVES.values()).index(active_id)] 
            _type=message["msg"]["instrument_type"]
            try:
                self.api.live_deal_data[name][active][_type].appendleft(message["msg"])
            except:
                pass


        elif message["name"]=="user-profile-client":
            self.api.user_profile_client=message["msg"]
        elif message["name"]=="leaderboard-userinfo-deals-client":
            self.api.leaderboard_userinfo_deals_client=message["msg"]
        elif message["name"]=="users-availability":
            self.api.users_availability=message["msg"]
        elif message["name"]=="transactions":
            self.api.transactions[message["request_id"]]=message
        elif message["name"]=="active-exposure":
            self.api.active_exposure[message["request_id"]]=message
        elif message["name"]=="balance-changed":
             
            self.api.balance[message["msg"]["current_balance"]["id"]]=message["msg"]["current_balance"]["amount"]
        
        else:
            pass
        global_value.ssl_Mutex[self.api.object_id].release()
                
    
    @staticmethod
    def on_error(wss, error): # pylint: disable=unused-argument
        """Method to process websocket errors."""
        logger = logging.getLogger(__name__)
        logger.error(error)
        global_value.websocket_error_reason[id(wss)]=str(error)
        global_value.check_websocket_if_error[id(wss)]=True
    @staticmethod
    def on_open(wss): # pylint: disable=unused-argument
        """Method to process websocket open."""
        logger = logging.getLogger(__name__)
        logger.debug("Websocket client connected.")
        global_value.check_websocket_if_connect[id(wss)]=1

        if id(wss) not in global_value.auto_reconnect:
            return
        
        if id(wss) not in global_value.happen_close:
            return 

        if global_value.auto_reconnect[id(wss)]==True and global_value.happen_close[id(wss)]==True:
            import requests

            headers={"User-Agent":r"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36"}
            #headers=None
            try:
                #logout
                old_sesion=global_value.low_level_reconnect_session[id(wss)]
                old_sesion.request(method="POST", url="https://auth.iqoption.com/api/v1.0/logout",headers=headers)
            except:
                pass


                
            session=requests.Session()
             
            global_value.low_level_reconnect_session[id(wss)]=session



            data = {"identifier": global_value.account[id(wss)]["email"],
                    "password": global_value.account[id(wss)]["password"],
                    "token":None}
            response=session.request(method="POST", url="https://auth.iqoption.com/api/v2/login",data=data,headers=headers)
             
            try:
                global_value.SSID[id(wss)] = response.cookies["ssid"]     
            except:
                global_value.auto_reconnect[id(wss)]=False
                global_value.ssl_Mutex[id(wss)].release()
                return 

            data={"ssid":response.cookies["ssid"],"protocol":3}
            data=json.dumps(dict(name="authenticate",
                                msg=data))
            wss.send(data)
            global_value.happen_close[id(wss)]=False

        global_value.ssl_Mutex[id(wss)].release()

    @staticmethod
    def on_close(wss,close_status_code,close_msg): # pylint: disable=unused-argument
        global_value.ssl_Mutex[id(wss)].acquire()
       
        """Method to process websocket close."""
        logger = logging.getLogger(__name__)
        logger.debug("Websocket connection closed."+str(close_msg))
        global_value.check_websocket_if_connect[id(wss)]=0
        #print(global_value.auto_reconnect,"ssssss")
        if global_value.auto_reconnect[id(wss)]==True:
             
            global_value.happen_close[id(wss)]=True
            wss.sock=None
            wss.run_forever()
