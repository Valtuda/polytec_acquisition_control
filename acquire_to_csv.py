# Copyright (c) 2021 Polytec GmbH, Waldbronn
# Released under the terms of the GNU Lesser General Public License version 3.

# Minor changes noted as comments by Jasper Smits, 2022

from datetime import datetime
import logging
import time

# JS 2022, commented out
#from acquisition_control.config import DaqConfig, ConfigurationError, log_config

from polytec.io.channel_activation import ChannelActivation
from polytec.io.data_acquisition import DataAcquisition
from polytec.io.channel_type import ChannelType
from polytec.io.device_command import DeviceCommand
from polytec.io.device_type import DeviceType
from polytec.io.item_list import ItemList
from polytec.io.miscellaneous_tag import MiscellaneousTag

from polytec.quantity_conversion import value_from_quantity_string


def __channel_scale_factor_and_unit(communication, data_acquisition, channel_type):
    """
    Determines the scale factor and base unit for the channel type specified

    The scale factor calculated by this function can be used to convert the received data samples to their base unit

    Args:
        communication:      The DeviceCommunication instance
        data_acquisition:   The DataAcquisition instance
        channel_type:       The ChannelType
    Returns:
        [channel scale factor, base unit]
    """
    def scale_factor_and_unit(decoder_device, max_value, base_unit):
        range_string = ItemList(communication, decoder_device, DeviceCommand.Range).current_item()
        range_value = value_from_quantity_string(range_string, base_unit)
        head_room = communication.get_float(decoder_device, DeviceCommand.HeadroomDigitalOut)
        return head_room * range_value / max_value, base_unit

    channel_max_value = data_acquisition.channel_max_value(channel_type)
    if channel_type == ChannelType.Velocity:
        return scale_factor_and_unit(DeviceType.VelocityDecoderDigital, channel_max_value, "m/s")
    elif channel_type == ChannelType.Displacement:
        return scale_factor_and_unit(DeviceType.DisplacementDecoderDigital, channel_max_value, "m")
    elif channel_type == ChannelType.Acceleration:
        return scale_factor_and_unit(DeviceType.AccelerationDecoderDigital, channel_max_value, "m/s²")
    elif channel_type == ChannelType.RSSI:
        return 100 / channel_max_value, "%"
    elif channel_type == ChannelType.Trigger or channel_type == ChannelType.DataValidity:
        return 1 / channel_max_value, "bool"
    else:
        return 1 / channel_max_value, ""


def __get_active_channels(communication, data_acquisition):
    """
    Provide a list of all active acquisition channels incuding additional information and placeholders used for the data
    acquisition.

    Next to the channel type and ID the active channels list also provides the scale factor and base unit for each
    active channel. Also two buffers are being added to buffer the extracted signal and overrange samples for each data
    chunk until they are written out to the CSV file.

    Args:
        communication:      The DeviceCommunication instance
        data_acquisition:   The DataAcquisition instance
    Returns:
        The active channels list
    """
    channel_activation = ChannelActivation(communication)
    active_channels = []
    for channel_type in ChannelType:
        if channel_activation.is_channel_type_supported(channel_type):
            for channel_id in range(channel_activation.max_channel_count(channel_type)):
                if channel_activation.is_channel_enabled(channel_type, channel_id):
                    scale_factor, unit = __channel_scale_factor_and_unit(communication, data_acquisition, channel_type)
                    active_channels.append({
                        "Type": channel_type,
                        "ID": channel_id,
                        "ScaleFactor": scale_factor,
                        "Unit": unit,
                        "Samples": None,
                        "Overrange": None
                    })
    return active_channels


def __calculate_frequency_factor(communication):
    """
    Calculates the frequency factor

    Some channels may have a higher bandwidth than the base bandwidth (e.g. all channels other than RSSI for the
    VFX-F-110). Thus they also provide more than one signal sample for each base sample. Use this factor to calculate
    the signal sample count from the base sample count (signalSamples = baseSamples * frequencyFactor).

    Args:
        communication:  The DeviceCommunication instance

    Returns:
        The frequency factor
    """
    if not communication.has_command(DeviceType.SignalProcessing, DeviceCommand.DaqBaseSampleRate) or \
            not communication.has_command(DeviceType.SignalProcessing, DeviceCommand.DaqSampleRate):
        return 1
    else:
        return int(communication.get_int32(DeviceType.SignalProcessing, DeviceCommand.DaqSampleRate)
                   / communication.get_int32(DeviceType.SignalProcessing, DeviceCommand.DaqBaseSampleRate))


def __wait_for_trigger(data_acquisition, trigger_mode):
    """
    This function blocks until the configured trigger condition (if any) has been satisfied.

    Args:
        data_acquisition:   The DataAcquisition instance
        trigger_mode:       The active trigger mode
    """
    if trigger_mode != "None":
        logging.info(f"Waiting for {trigger_mode} trigger...")
        while data_acquisition.available_samples() == 0:
            time.sleep(0.01)


def __write_csv_headers(csv_file, active_channels):
    """
    This function writes the CSV header row to the CSV file, including the channel name, id and Unit for each active
    channel.

    Args:
        csv_file:           The CVS file to write the extracted data to
        active_channels:    The list of active channels including additional information (see __get_active_channels())
    """
    csv_file.write("Timestamp (s)")
    for channel in active_channels:
        if channel["Type"] != ChannelType.DataValidity:
            csv_file.write(f";{channel['Type'].name} {channel['ID']} ({channel['Unit']})")
            if channel["Type"] in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
                csv_file.write(f";{channel['Type'].name} {channel['ID']} (Overrange)")
    csv_file.write("\n")


def __write_chunk_data_to_csv(csv_file, active_channels, base_sample_count, frequency_factor, chunk_timestamp,
                              sample_interval):
    """
    Write the extracted data of a single data chunk to the CSV file

    Args:
        csv_file:           The CVS file to write the extracted data to
        active_channels:    The list of active channels including additional information (see __get_active_channels())
        base_sample_count:  The amount of base samples to be acquired (=1 for streaming)
        frequency_factor:   The frequency factor (see __calculate_frequency_factor() above for more information)
        chunk_timestamp:    The timestamp of the first sample in this data chunk
        sample_interval:    The time interval between two signal samples
    """
    for base_id in range(base_sample_count):
        for sample_id in range(frequency_factor):
            csv_file.write(f"{chunk_timestamp + (base_id * frequency_factor + sample_id) * sample_interval:.8e}")

            for channel in active_channels:
                index = base_id if channel["Type"] == ChannelType.RSSI else base_id * frequency_factor + sample_id

                if channel["Type"] == ChannelType.DataValidity:
                    if not channel["Samples"][index]:
                        raise RuntimeError("Data packet lost")
                elif channel["Type"] == ChannelType.Trigger:
                    csv_file.write(f";{channel['Samples'][index]}")
                else:
                    csv_file.write(f";{channel['ScaleFactor'] * channel['Samples'][index]:.8e}")
                    if channel["Type"] in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
                        csv_file.write(f";{channel['Overrange'][index]}")

            csv_file.write("\n")


# [acquire_data_to_csv]
def __acquire_data_to_csv(communication, data_acquisition, daq_config, sample_count, base_samples_chunk_size,
                          timeout_ms, base_file_name):
    """
    Acquire data over an existing Data Acquisition connection and write it to CSV files

    Args:
        communication:              The DeviceCommunication instance
        data_acquisition:           The DataAcquisition instance
        daq_config:                 The DaqConfig instance
        sample_count:               The amount of base samples to acquire when streaming
        base_samples_chunk_size:    The amount of base samples to read at once from a device
        timeout_ms:                 The acquisition timeout
        base_file_name:             The base file name format string used for all CSV files created
    """
    # Gather DAQ configuration and other necessary information
    is_block_mode = daq_config.daq_mode == "Block"
    block_count = daq_config.block_count if is_block_mode else 1
    block_size = daq_config.block_size if is_block_mode else sample_count
    pre_post_trigger = daq_config.pre_post_trigger if is_block_mode else 0
    frequency_factor = __calculate_frequency_factor(communication)
    sample_interval = 1 / (data_acquisition.base_sample_rate_in_hz() * frequency_factor)
    active_channels = __get_active_channels(communication, data_acquisition)
    now = datetime.now()

    if block_count == 0:
        raise RuntimeError("Endless block mode (blockCount=0) is not supported by this example. "
                           "Configure a block count > 0.")

    # Acquire each block individually
    data_acquisition.start_data_acquisition()
    for block_id in range(block_count):
        if is_block_mode:
            __wait_for_trigger(data_acquisition, daq_config.trigger_mode)

        file_name = base_file_name.format(date=now.strftime("%Y-%m-%d"), time=now.strftime("%H%M%S"), block_id=block_id)
        logging.info(f"Writing {block_size} samples to \"{file_name}\"")

        with open(file_name, mode="w", encoding="utf-8") as csv_file:
            __write_csv_headers(csv_file, active_channels)

            # Process the acquired data in chunks
            base_samples_written = 0
            while base_samples_written < block_size:
                base_sample_count = min(base_samples_chunk_size, block_size - base_samples_written)
                # Blocks until the specified amount of samples is available to be extracted
                data_acquisition.read_data(base_sample_count, timeout_ms)

                # Copy the data for each active channel to its respective buffer in the active channels list
                for channel in active_channels:
                    sample_count = data_acquisition.extracted_sample_count(channel["Type"], channel["ID"])
                    channel["Samples"] = data_acquisition.get_int32_data(channel["Type"], channel["ID"], sample_count)
                    if channel["Type"] in [ChannelType.Velocity, ChannelType.Displacement, ChannelType.Acceleration]:
                        channel["Overrange"] = data_acquisition.get_overrange(channel["Type"], channel["ID"],
                                                                              sample_count)

                # Write the acquired data to the CSV file
                chunk_timestamp = ((base_samples_written * frequency_factor) - pre_post_trigger) * sample_interval
                __write_chunk_data_to_csv(csv_file, active_channels, base_sample_count, frequency_factor,
                                          chunk_timestamp, sample_interval)
                base_samples_written += base_sample_count

        if is_block_mode:
            data_acquisition.next_data_acquisition_block()
    logging.info("Acquisition complete")
    data_acquisition.stop_data_acquisition()
    # [acquire_data_to_csv]


def __test_not_iq_mode(communication):
    """
    Raise a ConfigurationError if the connected device is currently in IQ mode

    Args:
        communication:  The DeviceCommunication instance
    """
    if communication.has_command(DeviceType.Controller, DeviceCommand.IQMode) and \
       communication.get_int16(DeviceType.Controller, DeviceCommand.IQMode,
                               miscellaneous_tag=MiscellaneousTag.StartUpValue) == 1:
        raise ConfigurationError("This example does not support IQ mode (would require other data interpretation).")


# [acquire_data]
def acquire_data(communication, sample_count=None, base_samples_chunk_size=250, timeout_ms=2000,
                 base_file_name="{date}_{time}_AcquisitionData_{block_id}.csv"):
    """
    Acquire data from a device and write it to CSV files

    Args:
        communication:              A DeviceCommunication instance providing the connection to the device
        sample_count:               The amount of base samples to acquire (overwrite block size in block mode)
        base_samples_chunk_size:    The amount of base samples to read at once from a device
        timeout_ms:                 The acquisition timeout
        base_file_name:             The base file name format string used for all CSV files created
                                    (supports {date}, {time} and {block_id} placeholders)
    """
    __test_not_iq_mode(communication)

    # Load the data acquisition configuration
    daq_config = DaqConfig(communication)

    if daq_config.daq_mode == "Streaming" and sample_count is None:
        raise RuntimeError("No sample count specified. Sample count is mandatory for streaming.")
    if daq_config.daq_mode == "Block" and sample_count is not None:
        daq_config.block_size = sample_count

    # Log the data acquisition configuration
    logging.info(40*"-")
    log_config(daq_config)
    logging.info(40*"-")

    # Calculate the data acquisition ring buffer size (for streaming the buffer should be able
    # to hold all data expected to be acquired if real time processing is not guaranteed)
    buffer_capacity = sample_count if daq_config.daq_mode == "Streaming" else 10*base_samples_chunk_size

    data_acquisition = DataAcquisition(communication, buffer_capacity)
    __acquire_data_to_csv(communication, data_acquisition, daq_config, sample_count, base_samples_chunk_size,
                          timeout_ms, base_file_name)
    # [acquire_data]
