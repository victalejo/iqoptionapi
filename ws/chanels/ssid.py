"""Module for IQ option API ssid websocket chanel."""

from iqoptionapi.ws.chanels.base import Base


class Ssid(Base):
    """Class for IQ option API ssid websocket chanel."""
    # pylint: disable=too-few-public-methods

    name = "authenticate"

    def __call__(self, ssid,req_id):
        """Method to send message to ssid websocket chanel.

        :param ssid: The session identifier.
        """
        data={"ssid":ssid,"protocol":3}
        self.send_websocket_request(self.name, data,request_id=req_id)
