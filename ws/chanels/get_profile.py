import datetime
import time
from iqoptionapi.ws.chanels.base import Base
import iqoptionapi.global_value as global_value

class Get_profile(Base):
    name = "sendMessage"
    def __call__(self,req_id):
        data = {"name":"get-profile","version":"1.0","body":{}}

        self.send_websocket_request(self.name, data,request_id=req_id)