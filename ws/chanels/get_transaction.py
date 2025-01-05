import datetime
import time
from iqoptionapi.ws.chanels.base import Base
import iqoptionapi.global_value as global_value

class Get_transactions(Base):
    name = "sendMessage"
    def __call__(self,from_t:int,to_t:int,limit:int,offset:int,types:list,request_id):
        data = {
            "name":"get-transactions" ,
            "body":{
                "from":from_t,
                "to":to_t,
                "limit":limit,
                "offset":offset,
                "types":types
                }
        }
        self.send_websocket_request(self.name, data,request_id=request_id)