# (c) Jasper Smits 2022, released under LGPLv3

from time import sleep

from polytec.io.device_type import DeviceType
from polytec.io.device_command import DeviceCommand

# Some implementation notes:
# AF:           device_communication.set_int16(DeviceType.SensorHead, DeviceCommand.Autofocus,1)
# AF Status:    device_communication.get_int16(DeviceType.SensorHead, DeviceCommand.AutofocusResult) [busy: 0, done: 1]
# Signal Level: device_communication.get_int16(DeviceType.SensorHead, DeviceCommand.SignalLevel) [max: 512]
# QTec On:      device_communication.[set/get]_int32(DeviceType.QTecModule, DeviceCommand.QTecOn, 1 [0 for off])
# AF Range:     Is associated with DeviceType.SensorHead, DeviceType.AutofocusArea, which returns 4 bytes (= 2 int16s), but the
#               C library does not allow us to get or set it. So we'd have to make some pretty low-level changes, and we won't do that
#               now. I would really like to be able to set this though. :(
# Focus Pos.:   Focus position, number [int16] between 0 and 1835 (why?), Type.SensorHead, Command.FocusPositon. 
#               Can use this to make a manual autofocus script if you'd want (but why?)


class MiscConfig:
    """Configuration class for all Misc settings we want to setVibroFlex Connect with VibroFlex QTec head."""

    def __init__(self,device_communication, init_connection = False):
        """
        Constructor
        
        Arguments:
        - device_communication instance from the polytec library
        """
        if init_connection:
            self.__communication = device_communication

        # This is empty, all settings are int16s which are accessed directly.

    # Autofocus, possibility to have this function block
    def autofocus(self,block=False):
        """Forces the Sensor head to autofocus"""
        self.__communication.set_int16(DeviceType.SensorHead, DeviceCommand.Autofocus,1)
        
        # If this function is chosen to block until AF is done, we query af_status until it returns 1 (done).
        if block:
            while self.af_status != 1:
                sleep(0.1)

    @property
    def af_status(self):
        """Queries the autofocus status, 0 is busy, 1 is done."""
        return self.__communication.get_int16(DeviceType.SensorHead, DeviceCommand.AutofocusResult)
    
    # Signal level, read only, [0,512]
    @property
    def signal_level(self):
        """Returns the signal level, integer between 0 and 512"""
        return self.__communication.get_int16(DeviceType.SensorHead, DeviceCommand.SignalLevel)

    # QTec
    @property
    def qtec(self):
        """QTec status, 1 [on] or 0 [off]."""
        return self.__communication.get_int32(DeviceType.QTecModule, DeviceCommand.QTecOn)

    @qtec.setter
    def qtec(self,val):
        """Sets the QTec 1 [on] or 0 [off]"""
        if not isinstance(val,int):
            raise ValueError("Value has to be integer.")
        if val!=0 and val !=1:
            raise ValueError("Value has to be 0 or 1.")

        self.__communication.set_int32(DeviceType.QTecModule, DeviceCommand.QTecOn,val)

    
    # Focus Position
    @property
    def focus_position(self):
        """Focus position, between 0 and 1835."""
        return self.__communication.get_int16(DeviceType.SensorHead, DeviceCommand.FocusPosition)

    @focus_position.setter
    def focus_position(self,val):
        """Sets the Focus Position, between 0 and 1835"""
        if not isinstance(val,int):
            raise ValueError("Value has to be integer.")
        if val<0 or val > 1835:
            raise ValueError("Value has to be between 0 and 1835.")

        self.__communication.set_int16(DeviceType.SensorHead, DeviceCommand.FocusPosition,val)


