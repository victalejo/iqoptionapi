#python

import datetime
import time
from iqoptionapi.ws.chanels.base import Base
import iqoptionapi.global_value as global_value
#work for forex digit cfd(stock)

class Digital_options_place_digital_option(Base):
    name = "sendMessage"
    def __call__(self,instrument_id,amount,request_id):
        data = {
        "name": "digital-options.place-digital-option",
        "version":"1.0",
        "body":{
            "user_balance_id":int(global_value.balance_id[self.api.object_id]),
            "instrument_id":str(instrument_id),
            "amount":str(amount)
            
            }
        }
        self.send_websocket_request(self.name, data,request_id=request_id)
class Digital_options_place_digital_option_V2(Base):
    name = "sendMessage"
    def __call__(self,instrument_id,amount,request_id):
        if instrument_id.find("do")==0:
            asset_id=str(instrument_id).split("do")[1].split("A")[0]
            data = {
            "name": "digital-options.place-digital-option",
            "version":"2.0",
            "body":{
                "user_balance_id":int(global_value.balance_id[self.api.object_id]),
                "instrument_id":str(instrument_id),
                "instrument_index":0,
                "amount":str(amount),
                "asset_id":int(asset_id)
                }
            }
        else:
            data = {
            "name": "digital-options.place-digital-option",
            "version":"1.0",
            "body":{
                "user_balance_id":int(global_value.balance_id[self.api.object_id]),
                "instrument_id":str(instrument_id),
                "amount":str(amount)
                }
            }
        self.send_websocket_request(self.name, data,request_id=request_id)
 
class Digital_options_close_position(Base):
    name = "sendMessage"
    def __call__(self,position_id,request_id):
        data = {
        "name": "digital-options.close-position",
        "version":"1.0",
        "body":{
            "position_id":int(position_id)
            }
        }
        self.send_websocket_request(self.name, data,request_id=request_id)
 
class Digital_options_close_position_batch(Base):
    name = "sendMessage"
    def __call__(self,position_ids,request_id):
        data = {
        "name": "digital-options.close-position-batch",
        "version":"1.0",
        "body":{
            "position_ids":position_ids
            }
        }
        self.send_websocket_request(self.name, data,request_id=request_id)
 
