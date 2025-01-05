import datetime
import time
from iqoptionapi.ws.chanels.base import Base
import iqoptionapi.global_value as global_value

class Get_positions(Base):
    name = "sendMessage"
    def __call__(self,instrument_type):
        if instrument_type=="digital-option":
            name="digital-options.get-positions"
        elif instrument_type=="fx-option":
            name="trading-fx-option.get-positions"
        else:
            name="get-positions"
        data = {
            "name":name ,
            "body":{
                "instrument_type":instrument_type,
                "user_balance_id":int(global_value.balance_id[self.api.object_id])
                }
        }
        self.send_websocket_request(self.name, data)
class Get_position(Base):
    name = "sendMessage"
    def __call__(self,position_id):
        data = {
            "name":"get-position",
            "body":{
                "position_id":position_id,
                }
        }
        self.send_websocket_request(self.name, data)
class Get_history_positions(Base):
    name = "sendMessage"
    def __call__(self,external_id,request_id):
        data = {
            "name":"get-history-positions",
            "body":{
                "external_id":external_id
                }
        }
        self.send_websocket_request(self.name, data,request_id=request_id)
 


class Get_position_history(Base):
    name = "sendMessage"
    def __call__(self,instrument_type):
        data = {
            "name":"get-position-history",
            "body":{
                "instrument_type":instrument_type,
                "user_balance_id":int(global_value.balance_id[self.api.object_id])
                }
        }
        self.send_websocket_request(self.name, data)
 
class Get_position_history_v2(Base):
    name = "sendMessage"#instrument_types,limit,offset,start=0,end=0
    def __call__(self,user_balance_id,start,end,offset,limit,instrument_type,request_id):
        data = {
            "name":"get-history",
            "body":{
                "instrument_types":instrument_type,
                "user_balance_id":user_balance_id,
                "start":start,
                "end":end,
                "offset":offset,
                "limit":limit
                },
            "version":"2.0"
        }
     
        self.send_websocket_request(self.name, data,request_id=request_id)

class Get_digital_position(Base):
    name = "sendMessage"
    def __call__(self,position_id):
        data = {
            "name":"digital-options.get-position",
            "body":{
                "position_id":position_id,
                }
        }
        self.send_websocket_request(self.name, data)



 