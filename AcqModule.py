# (c) 2022 Jasper Smits, released under LGPLv3

## I might just merge this into the Vibrometer class, as it requires stuff from DaqConfig and this is just inconvenient.

from polytec.io.channel_activation import ChannelActivation
from polytec.io.data_acquisition import DataAcquisition
from polytec.io.channel_type import ChannelType
from polytec.io.device_command import DeviceCommand
from polytec.io.device_type import DeviceType
from polytec.io.item_list import ItemList
from polytec.io.miscellaneous_tag import MiscellaneousTag
from polytec.io.device_communication import DeviceCommunication

from threading import Thread

class AcqModule:
    """This class will control the acquisition of data using the vibrometer."""

    def __init__(self,dc):
        """Constructor, takes a device_communication instance"""

        # Not sure how big to make the buffer, so we'll just make it big. This should triggers being lost if we're acquiring a lot of data. If there are problems, look here first.
        self.__data_acquisition = DataAcquisition(dc,10000000)

        self.__acquisition_thread = Thread(target = self.__acquisition_loop)

        self.__buffer = None

         




    ### The part below deals with data acquisition, including the data acquisition loop.
    def __acquisition_loop(self):
        while self.__acquiring:
            ## Do the acquisition thing.
            # This comes down to:
            # - Reserve memory (dict with numpy arrays in it)
            # - Start the acquisition
            # - Wait for the trigger
            # - As data comes in, write it to memory (Maybe the lib already does this? Don't know, we'll handle it here.)
            #   - As for structuring the buffer: Each channel can have a different sample rate (DaqRate / DaqBaseRate)
            #     so we will store the data as ... / <channelname> / <number of block>

            # 'pass' won't really do here
            self.__acquiring = False


