#python

from collections import defaultdict
def nested_dict(n, type):
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n-1, type))

check_websocket_if_connect={}#None
# try fix ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2361)
ssl_Mutex={}


low_level_reconnect_session={}
#
account=nested_dict(1, dict)
#if false websocket can sent self.websocket.send(data)
#else can not sent self.websocket.send(data)
 

SSID={}#None
auto_reconnect={}

happen_close={}


check_websocket_if_error={}#False
websocket_error_reason={}#None

balance_id={}#None
_tmp_raw_balance_id = nested_dict(2, dict)
         
client_callback={}

req_mutex={}#True or object_id
req_id={}

def get_req_id(object_id):
    req_mutex[object_id].acquire()
    get_req_id=req_id[object_id]
    req_id[object_id]=req_id[object_id]+1
    req_mutex[object_id].release()

    return str(get_req_id)
