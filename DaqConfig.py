# Original:
# Copyright (c) 2021 Polytec GmbH, Waldbronn
# Released under the terms of the GNU Lesser General Public License version 3.

# Modifications by Jasper Smits (2022):
# - File renamed to DaqConfig to be in line with file name = class name.
# - Added the init_connecton paramter to the class constructor. This prevents connection initialization from taking place so the library
#   can be used as part of a class inheriting all config files.

import logging

from polytec.io.device_type import DeviceType
from polytec.io.device_command import DeviceCommand
from polytec.io.item_list import ItemList
from polytec.io.channel_activation import ChannelActivation
from polytec.io.channel_type import ChannelType


def log_config(daq_config):
    """
    Log the current data acquisition configuration of a device

    Args:
        daq_config: A DaqConfig instance to get the current configuration from
    """
    logging.info(f"Data acquisition mode:   {daq_config.daq_mode}")
    if daq_config.daq_mode == "Block":
        logging.info(f"Block count:             {daq_config.block_count}")
        logging.info(f"Block size:              {daq_config.block_size}")
        logging.info(f"Trigger mode:            {daq_config.trigger_mode}")
        if daq_config.trigger_mode != "None":
            logging.info(f"Trigger edge:            {daq_config.trigger_edge}")
            if daq_config.trigger_mode == "Analog":
                logging.info(f"Analog trigger source:   {daq_config.analog_trigger_source}")
                logging.info(f"Analog trigger level:    {daq_config.analog_trigger_level}")
            logging.info(f"Gated trigger:           {daq_config.gated_trigger}")
            logging.info(f"Pre-/Post-trigger:       {daq_config.pre_post_trigger}")


class DaqConfig:
    """Thd data acquisition configurator class is used to configure a device for a data acquisition"""

    def __init__(self, device_communication,init_connection = False):
        """
        Constructor

        Args:
            device_communication:   An active communication to a device to be configured

        Raises:
             DeviceNotConnectedError, LibraryFunctionCallError
        """
        if init_connection:
            # Some settings cannot be manipulated during an active data acquisition
            ItemList(device_communication, DeviceType.SignalProcessing, DeviceCommand.OperationMode).set_current_item("Off")

            # initialize member variables
            self.__communication = device_communication

        self.__daq_mode = ItemList(self.__communication, DeviceType.SignalProcessing, DeviceCommand.DaqMode) \
            if self.__communication.has_command(DeviceType.SignalProcessing, DeviceCommand.DaqMode) else None
        self.__trigger_mode = ItemList(self.__communication, DeviceType.SignalProcessing, DeviceCommand.DaqTriggerMode)
        self.__trigger_edge = ItemList(self.__communication, DeviceType.SignalProcessing, DeviceCommand.DaqTriggerEdge)
        self.__analog_trigger_source = ItemList(self.__communication, DeviceType.SignalProcessing,
                                                DeviceCommand.DaqAnalogTriggerSource)
        self._channel_activation = ChannelActivation(self.__communication)

    # DAQ Mode
    @property
    def daq_mode(self):
        """Gets the data acquisition mode"""
        return self.__daq_mode.current_item() if self.__daq_mode else "Streaming"

    @daq_mode.setter
    def daq_mode(self, new_value):
        """Sets the data acquisition mode"""
        if self.__daq_mode:
            if self.__daq_mode.is_item_available(new_value):
                self.__daq_mode.set_current_item(new_value)
            else:
                raise ConfigurationError(f"DAQ mode not available: {new_value}")
        elif new_value != "Streaming":
            raise ConfigurationError(f"DAQ mode not available: {new_value}")

    def available_daq_modes(self):
        """Gets all available data acquisition modes"""
        return self.__daq_mode.available_items() if self.__daq_mode else ["Streaming"]

    # Block count
    @property
    def block_count(self):
        """Gets the block count"""
        return self.__communication.get_int16(DeviceType.SignalProcessing, DeviceCommand.DaqBlockCount)

    @block_count.setter
    def block_count(self, new_value):
        """Sets the block count"""
        value_range = self.block_count_range()
        if value_range[0] <= new_value <= value_range[1]:
            self.__communication.set_int16(DeviceType.SignalProcessing, DeviceCommand.DaqBlockCount, new_value)
        else:
            raise ConfigurationError(f"Block count out of range [{value_range[0]}, {value_range[1]}]")

    def block_count_range(self):
        """Gets the block count range"""
        return self.__communication.get_int16_range(DeviceType.SignalProcessing, DeviceCommand.DaqBlockCount)

    # Block size
    @property
    def block_size(self):
        """Gets the block size"""
        return self.__communication.get_int32(DeviceType.SignalProcessing, DeviceCommand.DaqBlockSize)

    @block_size.setter
    def block_size(self, new_value):
        """Sets the block size"""
        value_range = self.block_size_range()
        if value_range[0] <= new_value <= value_range[1]:
            self.__communication.set_int32(DeviceType.SignalProcessing, DeviceCommand.DaqBlockSize, new_value)
        else:
            raise ConfigurationError(f"Block count out of range [{value_range[0]}, {value_range[1]}]")

    def block_size_range(self):
        """Gets the block size range"""
        return self.__communication.get_int32_range(DeviceType.SignalProcessing, DeviceCommand.DaqBlockSize)

    # Trigger mode
    @property
    def trigger_mode(self):
        """Gets the trigger mode"""
        return self.__trigger_mode.current_item()

    @trigger_mode.setter
    def trigger_mode(self, new_value):
        """Sets the trigger mode"""
        if new_value in self.available_trigger_modes():
            self.__trigger_mode.set_current_item(new_value)
        else:
            raise ConfigurationError(f"Trigger mode not available: {new_value}")

    def available_trigger_modes(self):
        """Gets all available trigger modes"""
        return self.__trigger_mode.available_items()

    # Trigger edge
    @property
    def trigger_edge(self):
        """Gets the trigger edge"""
        return self.__trigger_edge.current_item()

    @trigger_edge.setter
    def trigger_edge(self, new_value):
        """Sets the trigger edge"""
        if new_value in self.available_trigger_edges():
            self.__trigger_edge.set_current_item(new_value)
        else:
            raise ConfigurationError(f"Trigger edge not available: {new_value}")

    def available_trigger_edges(self):
        """Gets all available trigger edges"""
        return self.__trigger_edge.available_items()

    # Analog trigger source
    @property
    def analog_trigger_source(self):
        """Gets the analog trigger source"""
        return self.__analog_trigger_source.current_item()

    @analog_trigger_source.setter
    def analog_trigger_source(self, new_value):
        """Sets the analog trigger source"""
        if new_value in self.available_analog_trigger_sources():
            self.__analog_trigger_source.set_current_item(new_value)
        else:
            raise ConfigurationError(f"Analog trigger source not available: {new_value}")

    def available_analog_trigger_sources(self):
        """Gets all available trigger sources"""
        return self.__analog_trigger_source.available_items()

    # Analog trigger level
    @property
    def analog_trigger_level(self):
        """Gets the analog trigger level"""
        return self.__communication.get_float(DeviceType.SignalProcessing, DeviceCommand.DaqAnalogTriggerLevel)

    @analog_trigger_level.setter
    def analog_trigger_level(self, new_value):
        """Sets the analog trigger level"""
        value_range = self.analog_trigger_level_range()
        if value_range[0] <= new_value <= value_range[1]:
            self.__communication.set_float(DeviceType.SignalProcessing, DeviceCommand.DaqAnalogTriggerLevel, new_value)
        else:
            raise ConfigurationError(f"Analog trigger level out of range [{value_range[0]}, {value_range[1]}]")

    def analog_trigger_level_range(self):
        """Gets the analog trigger level range"""
        return self.__communication.get_float_range(DeviceType.SignalProcessing, DeviceCommand.DaqAnalogTriggerLevel)

    # Gated trigger
    @property
    def gated_trigger(self):
        """Gets the gated trigger state"""
        return self.__communication.get_int16(DeviceType.SignalProcessing, DeviceCommand.DaqGatedTrigger) == 1

    @gated_trigger.setter
    def gated_trigger(self, new_value):
        """Sets the gated trigger state"""
        self.__communication.set_int16(DeviceType.SignalProcessing, DeviceCommand.DaqGatedTrigger,
                                       1 if new_value else 0)

    # Pre/Post trigger
    @property
    def pre_post_trigger(self):
        """Sets the pre- or post-trigger"""
        return self.__communication.get_int32(DeviceType.SignalProcessing, DeviceCommand.DaqPreTrigger)

    @pre_post_trigger.setter
    def pre_post_trigger(self, new_value):
        """Gets the pre- or post-trigger"""
        value_range = self.pre_post_trigger_range()
        if value_range[0] <= new_value <= value_range[1]:
            self.__communication.set_int32(DeviceType.SignalProcessing, DeviceCommand.DaqPreTrigger, new_value)
        else:
            raise ConfigurationError(f"Block count out of range [{value_range[0]}, {value_range[1]}]")

    def pre_post_trigger_range(self):
        """Gets the pre- or post-trigger range"""
        return self.__communication.get_int32_range(DeviceType.SignalProcessing, DeviceCommand.DaqPreTrigger)

    # Active output
    @property
    def active_output(self):
        """
        Gets the active output channel of a device (only used for devices not supporting the ChannelActivation command,
        e.g. IVS-500 and VGO-200.
        """
        for output_channel in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
            if self._channel_activation.is_channel_enabled(output_channel):
                return output_channel
        return ChannelType.Unknown

    @active_output.setter
    def active_output(self, new_value):
        """
        Sets the active output channel of a device (only used for devices not supporting the ChannelActivation command,
        e.g. IVS-500 and VGO-200.
        """
        if not self._channel_activation.is_channel_available(new_value) \
                or new_value not in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
            raise RuntimeError(f"{new_value.name} is not a valid output channel on the connected device")

        if new_value == ChannelType.Displacement:
            self.__communication.set_int16(DeviceType.DisplacementDecoderDigital, DeviceCommand.OutputActive, 1)
        elif new_value == ChannelType.Acceleration:
            self.__communication.set_int16(DeviceType.AccelerationDecoderDigital, DeviceCommand.OutputActive, 1)
        elif self.__communication.has_device(DeviceType.VelocityDecoderDigital):
            self.__communication.set_int16(DeviceType.VelocityDecoderDigital, DeviceCommand.OutputActive, 1)
        else:
            raise ConfigurationError(f"{new_value} is not a valid active output channel")

    def available_active_outputs(self):
        """
        Gets all available active output channels of a device (only used for devices not supporting the
        ChannelActivation command, e.g. IVS-500 and VGO-200.
        """
        if self.__communication.has_device(DeviceType.VelocityDecoderDigital) \
                and self.__communication.has_command(DeviceType.VelocityDecoderDigital, DeviceCommand.OutputActive):
            return [channel for channel in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]
                    if self._channel_activation.is_channel_available(channel)]
        else:
            return []


class ConfigurationError(Exception):
    """Exception class raised when trying to to setup an invalid configuration"""
    pass
