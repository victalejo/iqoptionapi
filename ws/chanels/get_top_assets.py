import datetime
import time
from iqoptionapi.ws.chanels.base import Base
import iqoptionapi.global_value as global_value

class Get_Top_Assets(Base):
    name = "sendMessage"
    def __call__(self,instrument_type,req_id):
        #instrument_type=binary-option/digital-option/forex/cfd/crypto
        data = {"name":"get-top-assets",
                "version":"1.2",
                "body":{
                    "instrument_type": instrument_type
                    }
                }
        self.send_websocket_request(self.name, data,request_id=req_id)