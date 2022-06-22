### This class will import all the other classes.
# DaqConfig,acquire_from_csv (c) 2021 Polytec GmbH, Waldbrunn, released under LGPLv3.
# Other files (c) 20222 Jasper Smits, released under LGPLv3.

from polytec.io.channel_activation import ChannelActivation
from polytec.io.data_acquisition import DataAcquisition
from polytec.io.channel_type import ChannelType
#from polytec.io.device_command import DeviceCommand
#from polytec.io.device_type import DeviceType
#from polytec.io.item_list import ItemList

from polytec.io.device_communication import DeviceCommunication

from acquire_to_csv import __get_active_channels as get_active_channels # Args: communication, acquisition
from acquire_to_csv import __wait_for_trigger as wait_for_trigger # acquisition, self.trigger_mode

from DaqConfig import DaqConfig
from VelEncConfig import VelEncConfig
from MiscConfig import MiscConfig
from DataManagement import HDF5Writer

from threading import Thread

import numpy as np

from time import sleep

class Vibrometer(DaqConfig, VelEncConfig, MiscConfig, HDF5Writer):
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

        # Do we automatically autofocus before each acquisition?
        self.__auto_af    = False

        # Data will be copied from the buffer to here at the end of a run.
        self.__data       = None
        
        # Are we ready for data? Read-only so internal param.
        self.__ready_for_data = False

        # Guess this requires another @property.
        self.__chunk_size     = 1000
        self.__acq_timeout    = 1000


    @staticmethod
    def from_ip(ip):
        """Constructor which creates the class from a provided IP address (string). No checks on validity of the IP."""
        return Vibrometer(DeviceCommunication(ip))

    def to_dict(self):
        """Dictionary representation of the Vibrometer state."""
        daq_dict    = DaqConfig.to_dict(self)
        velenc_dict = VelEncConfig.to_dict(self)
        misc_dict   = MiscConfig.to_dict(self)

        _dict = {**daq_dict,**velenc_dict,**misc_dict}

        _dict["chunk_size"] = self.chunk_size
        _dict["acq_timeout"] = self.acq_timeout
        _dict["auto_af"] = self.auto_af

        return _dict

    def settings_from_dict(self,settings_dict):
        """Set the properties of the vibrometer state from the dictionary. Coded out manually, since order matters."""

        # A dictionary with all setable parameters.
        property_dtype_dict = {"daq_mode": str,"block_count": int, "block_size": int, "trigger_mode": str,
                "trigger_edge": str,"analog_trigger_source":str,"analog_trigger_level":float,"gated_trigger":bool,
                "pre_post_trigger":int,"bandwidth":str,"range":str,"tracking_filter":str,"high_pass_filter":str,
                "max_velocity_range":str,"qtec":bool,"chunk_size":int,"acq_timeout":int,"auto_af":bool}

        for key in settings_dict:
            if key in property_dtype_dict:
                try:
                    val = property_dtype_dict[key](settings_dict[key])
                except:
                    raise ValueError(f"Could not convert {key} to type {property_dtype_dict[key]}.")

                setattr(self,key,val)



    # Need this to be a read-only property.
    @property
    def ready_for_data(self):
        return self.__ready_for_data

    @property
    def chunk_size(self):
        return self.__chunk_size

    @chunk_size.setter
    def chunk_size(self,val):
        if not isinstance(val,int):
            raise ValueError("chunk_size must be an integer.")
        elif val < 1:
            raise ValueError("chunk_size must be larger than 1.")
        self.__chunk_size = val

    @property
    def acq_timeout(self):
        return self.__acq_timeout

    @acq_timeout.setter
    def acq_timeout(self,val):
        if not isinstance(val,int):
            raise ValueError("acq_timeout must be an integer.")
        elif val < 1:
            raise ValueError("acq_timeout must be larger than 1.")
        self.__acq_timeout = val
    
    @property
    def auto_af(self):
        return self.__auto_af

    @auto_af.setter
    def auto_af(self,val):
        if val != True and val != False:
            raise ValueError("auto_af needs to be either True or False.")
        
        self.__auto_af = val


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

    def __get_active_channels(self):
        """Exposes the acquire_from_csv function get_active_channels. Transforms it into a dict, easier to process later."""
        active_channels = get_active_channels(self.__communication,self.__acquisition)
        channels_dict   = dict()

        for channel in active_channels:
            channels_dict[channel["Type"].name] = channel

        return channels_dict
            

    def __freq_factor(self):
        """Calculate the factor stemming from sampling frequency."""
        return self.daq_sample_rate // self.daq_base_sample_rate

    def __generate_buffer(self,output=False):
        """Generated buffers in the "Samples" area of the provided active channels of get_active_channels."""
        active_channels = self.__get_active_channels()
        for ch_type,channel in active_channels.items():
            freq_factor = 1 if channel["Type"] == ChannelType.RSSI else self.__freq_factor()

            if channel["Unit"] == "bool":
                data_type = bool # 1 byte
            else:
                data_type = int # 4 bytes (=32bit)


            active_channels[ch_type]["Samples"] = np.zeros((self.block_count,self.block_size*freq_factor),dtype=data_type)
            
            # If this is a measurement channel, also create the overrange array.
            if channel["Type"] in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
                active_channels[ch_type]["Overrange"] = np.zeros((self.block_count,self.block_size*freq_factor),dtype=bool)

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

            ## Start data acquisition
            self.__acquisition.start_data_acquisition()
            self.__generate_buffer()

            ## Do we want to auto af? If so, do a blocking AF
            if self.__auto_af:
                self.autofocus(block=True)

            self.__ready_for_data = True

            ## Main acquisition/data storage loop. Inspired by __acquire_data_to_csv from acquire_to_csv.
            # Loop over blocks.
            for block_id in range(self.block_count):
                wait_for_trigger(self.__acquisition, self.trigger_mode)

                # Polytec pulls the data off the device in chunks. I don't really see the need, but we'll mimick it.
                samples_this_block = 0
                while samples_this_block < self.block_size:
                    # Read the chunk size, or at most what we still have to buffer
                    read_this_loop = min(self.block_size - samples_this_block, self.__chunk_size)

                    # Blocks until timeout is reached. read_this_loop in base sample frequency
                    self.__acquisition.read_data(read_this_loop, self.__acq_timeout)

                    # Fetch the data and write it to buffer
                    for channel in active_channels:
                        sample_count = self.__acquisition.extracted_sample_count(channel["Type"], channel["ID"])
                        
                        # Here we differ from the example code, writing it directly into the numpy array.
                        channel["Samples"][block_id, samples_this_block:samples_this_block+sample_count] = \
                                self.__acquisition.get_int32_data(channel["Type"],channel["ID"],sample_count)

                        # If we are on a "measurement" channel, register overrange too
                        if channel["Type"] in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
                            channel["Overrange"][block_id, samples_this_block:samples_this_block+sample_count] = \
                                    self.__acquisition.get_overrange(channel["Type"],channel["ID"],sample_count)

                    # Here Polytec goes on to write the chunks to csv, but we don't do that.
                    # (also, why do they do that? I/O during data acq is a big no-no)
                    # We do need to update the number of samples written this block.
                    # Note that we update with read_this_loop, since we're tracking the base sample rate.
                    samples_this_block += read_this_loop

            # The above should wrap up the main acquisition loop. We haven't stored any data yet.
            # Let's tell the device it can stop acquiring.
            self.__acquisition.stop_data_acquisition()

            ## Do the acquisition thing.
            # This comes down to:
            # x Reserve memory (dict with numpy arrays in it)
            # x Start the acquisition
            # x Wait for the trigger
            # x As data comes in, write it to memory (Maybe the lib already does this? Don't know, we'll handle it here.)
            #   - As for structuring the buffer: Each channel can have a different sample rate (DaqRate / DaqBaseRate)
            #     so we will store the data as ... / <channelname> / <number of block>

            # The above is slightly outdated but leaving it there for now

            # Set the buffer back to None. Set acquiring to false.
            self.__data = self.__buffer
            self.__buffer = None
            self.__acquiring = False
            self.__ready_for_data = False

    ### Data storage related functions, insofar they're not in the HDF5Writer class.
    def write_data(self,filename,_dict=dict()):
        """Write data to the disk."""
        _dict["vibrometer"] = self.to_dict()
        self.__write_channel_data(self.__data)

        # Dereference the data point and garbage coll. will get it.
        self.__data = None
