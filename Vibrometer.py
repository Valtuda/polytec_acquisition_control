### This class will import all the other classes.
# DaqConfig (c) 2021 Polytec GmbH, Waldbrunn, released under LGPLv3.
# Other files (c) 2021 Jasper Smits, released under LGPLv3.

#from polytec.io.device_type import DeviceType
#from polytec.io.device_command import DeviceCommand
#from polytec.io.item_list import ItemList
from polytec.io.device_communication import DeviceCommunication

from DaqConfig import DaqConfig
from VelEncConfig import VelEncConfig
from MiscConfig import MiscConfig

class Vibrometer(DaqConfig, VelEncConfig, MiscConfig):
    """This class controls all features of the vibrometer."""

    def __init__(self,dc):
        """Constructor, takes DeviceCommunication object as argument."""
    
        # Polytec turns acquisition off, but I've never seen the need, so I'll put the line here but comment it out.
        #ItemList(device_communication, DeviceType.SignalProcessing, DeviceCommand.OperationMode).set_current_item("Off")

        self.__communication = dc

        DaqConfig.__init__(self,dc,True)
        VelEncConfig.__init__(self,dc,True)
        MiscConfig.__init__(self,dc,True)


    @staticmethod
    def from_ip(ip):
        return Vibrometer(DeviceCommunication(ip))
