### This class will import all the other classes.
# DaqConfig,acquire_from_csv (c) 2021 Polytec GmbH, Waldbrunn, released under LGPLv3.
# Other files (c) 20222 Jasper Smits, released under LGPLv3.

from polytec.io.channel_activation import ChannelActivation
from polytec.io.data_acquisition import DataAcquisition
from polytec.io.channel_type import ChannelType
from polytec.io.device_command import DeviceCommand
from polytec.io.device_type import DeviceType
from polytec.io.item_list import ItemList
from polytec.io.miscellaneous_tag import MiscellaneousTag

from polytec.io.device_communication import DeviceCommunication

from acquire_to_csv import __get_active_channels as get_active_channels # Args: communication, acquisition

from DaqConfig import DaqConfig
from VelEncConfig import VelEncConfig
from MiscConfig import MiscConfig

from threading import Thread

import numpy as np

from time import sleep

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

        # Below deals with data acquisition
        self.__acquisition = DataAcquisition(dc,10000000)
        self.__acquisition_thread = Thread(target = self.__acquisition_loop)
        self.__acq_loop   = True
        self.__acquiring  = False
        self.__buffer     = None

    @staticmethod
    def from_ip(ip):
        """Constructor which creates the class from a provided IP address (string). No checks on validity of the IP."""
        return Vibrometer(DeviceCommunication(ip))

    # Relevant configuration settings from daq config for acquisition.
    """
        # configure acquisition
        daq_config = DaqConfig(device_communication)
        daq_config.daq_mode = "Block"  # not supported by every device (e.g. IVS-500 and VGO-200)
        daq_config.block_size = 4000  # base samples (samples in lowest common denominator sample rate of all channels)
        daq_config.block_count = 25
        daq_config.trigger_mode = "Extern"
        daq_config.trigger_edge = "Rising"
        daq_config.analog_trigger_level = 0.5  # value between -1 and 1
        daq_config.pre_post_trigger = 1000  # actual signal channel samples not base samples
    """

    def get_active_channels(self):
        """Exposes the acquire_from_csv function get_active_channels. Transforms it into a dict, easier to process later."""
        active_channels = get_active_channels(self.__communication,self.__acquisition)
        channels_dict   = dict()

        for channel in active_channels:
            channels_dict[channel["Type"].name] = channel

        return channels_dict
            

    def __freq_factor(self):
        """Calculate the factor stemming from sampling frequency."""
        return self.daq_sample_rate // self.daq_base_sample_rate

    def generate_buffer(self,output=False):
        """Generated buffers in the "Samples" area of the provided active channels of get_active_channels."""
        active_channels = self.get_active_channels()
        for ch_type,channel in active_channels.items():
            freq_factor = 1 if channel["Type"] == ChannelType.RSSI else self.__freq_factor()
            active_channels[ch_type]["Samples"] = np.zeros((self.block_count,self.block_size*freq_factor))

        self.__buffer = active_channels

        if output:
            return self.__buffer

    ### The part below deals with data acquisition, including the data acquisition loop.
    def __acquisition_loop(self):
        while self.__acq_loop:
            while not self.__acquiring:
                sleep(0.1)
            
            ## At the start of the acquisition, the buffer has to be empty
            if not self._buffer == None:
                raise RuntimeError("Buffer was defined before acquisition started. This should not be possible.")

            ## Do the acquisition thing.
            # This comes down to:
            # - Reserve memory (dict with numpy arrays in it)
            # - Start the acquisition
            # - Wait for the trigger
            # - As data comes in, write it to memory (Maybe the lib already does this? Don't know, we'll handle it here.)
            #   - As for structuring the buffer: Each channel can have a different sample rate (DaqRate / DaqBaseRate)
            #     so we will store the data as ... / <channelname> / <number of block>

            # 'pass' won't really do here

            self.__buffer = None
            self.__acquiring = False

