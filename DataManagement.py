# (c) Jasper Smits 2022, release under LGPLv3

# This small class will handle saving the results of an experimental run to a HDF5 file. As an input it will take mainly the buffer of Vibrometer class, and a dict-of-dicts describing properties of the vibrometer, laser, etc. This class will only support writing, for now.

import h5py
import os

from glob import glob

import numpy as np

class HDF5Writer:
    def __init__(self):
        self._active_file = None

    @property
    def active_file(self):
        if self._active_file:
            return self._active.filename
        else:
            raise ValueError("No active file.")

    def open_file(self, filename, overwrite=False):
        if (not overwrite) and os.path.exists(filename):
            return IOError(f"File {filename} exists. Turn on overwrite or choose another file.")

        self._active_file = h5py.File(filename, "w")

    def close_file(self):
        self._active_file.close()
        self._active_file = None

    ## Writing part, what does it have to do?
    # Take channel data, and write it into a HDF5 structure ( <channel> / <run_num>, also include <channel>/<avg> ), include metadata
    # Take (to be produced) dict-of-dicts which stores all setting data.
    # Store the executed script (this is not yet possible, and more of a feature of the entire control software, we will have to see how we do this.)

    def write_channel_data(self,channel_data):
        """Takes a set of channel_data as from the generate_buffers() of the Vibrometer class. Writes it to file as described above."""

        for ch_name,channel in channel_data.items():
            if channel["Overrange"] is not None:
                has_overrange = True
            else:
                has_overrange = False

            ch_grp = self._active_file.create_group("/"+ch_name)
            if has_overrange:
                overrange_grp = ch_grp.create_group("overrange")

            # Store the metadata in the channel group.
            ch_grp["unit"]        = channel["Unit"]
            ch_grp["scalefactor"] = channel["ScaleFactor"]
            ch_grp["ID"]          = channel["ID"]

            my_data  = channel["Samples"]

            # Something about the datatype for each array. Of course, we store bools as bools.
            if channel["Unit"] == "bool":
                data_type = "b" # 1 byte
            else:
                data_type = "i" # 4 bytes (=32bit)

            # Now the data

            num_runs,num_samples = my_data.shape

            for num in range(num_runs):
                dataset = ch_grp.create_dataset(f"{num}",(num_samples,),dtype=data_type)

                # Store the data in the file.
                dataset[:] = channel["Samples"][num,:]
                if has_overrange:
                    overrange_dataset = overrange_grp.create_dataset(f"{num}",(num_samples,),dtype="b")
                    overrange_dataset[:] = channel["Overrange"][num,:]
    
    def write_metadata(self,dict_of_dicts):
        """A very inflexible function to write metadata from a dictionary of dictionaries."""
        for _key,_dict in dict_of_dicts.items():
            for _skey,_item in _dict.items():
                self._active_file[_key+"__"+_skey] = _item


class HDF5Reader(h5py.File):
    """A class to deal with conversion of data from the HDF5Writer. Unpacks the metadata back into the dict-of-dicts format. Converts data to SI units in a convenient way. One instance per file, wraps around the HDF5 reader, basically. Based on the h5py.File class."""
    def __init__(self,filename,**kwargs):
        super().__init__(filename,"r",**kwargs)
        self._freq_factor = self["vibrometer__daq_sample_rate"][()]//self["vibrometer__daq_base_sample_rate"][()]
        self._pre_post_trig = self["vibrometer__pre_post_trigger"][()]
        self._base_samples  = self["vibrometer__block_size"][()]
        self._total_samples = self._base_samples * self._freq_factor
        self._base_sample_rate  = self["vibrometer__daq_base_sample_rate"][()]
        self._sample_rate   = self._base_sample_rate/self._freq_factor
        self._block_count  = self["vibrometer__block_count"][()]

        self._metadata = self.__reconstruct_dict()

    def average_velocity(self,start=0,end=None):
        # Apparently we can't use self variables in the function definition
        if end == None:
            end = self._block_count

        arr = np.zeros(self._total_samples,dtype=float)
        for it in range(start,end):
            arr += self.velocity(it)

        return arr/(end-start)

    @property
    def metadata(self):
        return self._metadata

    def generate_t_array(self,freq_factor=True):
        if freq_factor:
            return ( np.arange(self._total_samples * self._freq_factor) - self._pre_post_trig ) / self._sample_rate
        else:
            return ( np.arange(self._total_samples) - self._pre_post_trig//self._freq_factor ) / self._base_sample_rate

    def velocity(self,num):
        """Output the velocity of a specific run number, scaled to the proper SI units."""
        return self[f"Velocity/{num}"][()] * self["Velocity/scalefactor"][()]

    def __reconstruct_dict(self):
        _dict = dict()
        for key in self.keys():
            split_key = key.split("__")
            if len(split_key)>1:
                if not split_key[0] in _dict:
                    _dict[split_key[0]] = dict()
                _dict[split_key[0]][split_key[1]] = self[key][()] 

        return _dict
    
    def write_si_data_file(self):
        """To share data, it can be desirable to have a file to share in SI units, we'll still use hdf5.

        We write:
        - Time
        - BaseTime
        - Velocity/<num>
        - Overrange/<num>
        - RSSI/<num>
        - Trigger/<num>

        - Metadata saved in metadata/<type>/<variable>"""

        _file = h5py.File(self.filename+".si","w")

        _file["Time"] = self.generate_t_array()
        _file["BaseTime"] = self.generate_t_array(False)

        for num in range(self._block_count):
            _file[f"Time"] = self.generate_t_array()
            _file[f"BaseTime"] = self.generate_t_array(freq_factor=False)
            _file[f"Velocity/{num}"] = self[f"Velocity/{num}"][()] * self["Velocity/scalefactor"][()]
            _file[f"Overrange/{num}"] = self[f"Velocity/overrange/{num}"][()]
            _file[f"RSSI/{num}"] = self[f"RSSI/{num}"][()] * self["RSSI/scalefactor"][()]
            _file[f"Trigger/{num}"] = self[f"Trigger/{num}"][()]

        # Now the metadata
        for key,_dict in self.metadata.items():
            for key2,value2 in _dict.items():
                _file[f"metadata/{key}/{key2}"] = value2

        _file.close()
        del _file

## Old function that dealt with single-trace files.
def series_to_one_file(location,prefix,param_range,postfix=".hdf5"):
    """To convert a series of measurements to a single file, reducing everything to SI units like in the above code."""
    filename = f"{location}/{prefix}{postfix}"

    _file = h5py.File(filename,"w")

    first = True

    # For each param, we open the file and load the relevant data.
    for param in param_range:
        file_loc = f"{location}/{prefix}_{param}{postfix}"
        subgroup = _file.create_group(f"{param}")

        read_file = HDF5Reader(file_loc)

        for num in range(read_file["vibrometer__block_count"][()]):
            subgroup[f"Velocity/{num}"] = read_file[f"Velocity/{num}"][()] * read_file["Velocity/scalefactor"][()]
            subgroup[f"Overrange/{num}"] = read_file[f"Velocity/overrange/{num}"][()]
            subgroup[f"RSSI/{num}"] = read_file[f"RSSI/{num}"][()] * read_file["RSSI/scalefactor"][()]
            subgroup[f"Trigger/{num}"] = read_file[f"Trigger/{num}"][()]

        subgroup[f"Time"] = read_file.generate_t_array()
        subgroup[f"BaseTime"] = read_file.generate_t_array(freq_factor=False)
        subgroup[f"avgVelocity"] = read_file.average_velocity()

        if first:
            first = False
            # Now the metadata
            for key,_dict in read_file.metadata.items():
                for key2,value2 in _dict.items():
                    _file[f"metadata/{key}/{key2}"] = value2

        read_file.close()
        del read_file

    _file.close()
    del _file

# HDF5 does not play nice with dictionaries so this is just a quick work-around to make it work nicely.
def write_simple_dict_to_hdf5_subgroup(subgroup,_dict):
    for key,value in _dict.items():
        subgroup[key] = value
    


def recv_gather_to_one_file(location,prefix,postfix=".hdf5"):
    # What filename will we save to?
    filename = f"{location}/{prefix}{postfix}"

    # Create this file.
    _file = h5py.File(filename,"w")

    # Find all files which match the pattern. These will be fused into one file.
    data_files = glob(f"{location}/{prefix}_*{postfix}")

    # Aux variables for looping over traces
    first    = True
    trace_it = 0

    for data_file in data_files:
        # file_it tracks which shot we're at in this specific file.
        file_it = 0

        # Read file using the HDF5 reader.
        read_file = HDF5Reader(data_file)

        # Files in the HDF5 reader are sorted chronologically. We first want to identify how many traces and their metadata.
        # In the receiver gather format, this is saved in the traces dictionary.
        src_location  = read_file.metadata["traces"]["receiver_loc"]
        rcv_locations = read_file.metadata["traces"]["src_locations"]

        # Derive the number of unique traces in this file from the rcv_locations
        num_traces = len(rcv_locations)
        shots_per_tr  = read_file.metadata["traces"]["shots_per_point"]

        # If the data is complete, the total number of blocks for the vibrometer should be
        # the number of traces * number of points. Let's check this. The vib doesn't save if this is not the case.
        if shots_per_tr*num_traces != read_file.metadata["vibrometer"]["block_count"]:
            raise IOError(f"The datafile {data_file} does not seem to be complete. Expected: {shots_per_tr*num_traces}. Present: {read_file.metadata['vibrometer']['block_count']}.")

        # If this is the first time this file is written to, we need to write the data structure.
        if first:
            first = False  # Don't do this again

            write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/experiment"),read_file.metadata["experiment"])

            # Devices
            write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/devices/laser"),read_file.metadata["laser"])
            write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/devices/vibrometer"),read_file.metadata["vibrometer"])

            # If there is galvo or rotator metadata, we write this as well
            if "galvo" in read_file.metadata.keys():
                write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/devices/galvo"),read_file.metadata["galvo"])

            if "rotator" in read_file.metadata.keys():
                write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/devices/rotator"),read_file.metadata["rotator"])

            # If there is information about the sample, add it here as well.
            if "sample" in read_file.metadata.keys():
                write_simple_dict_to_hdf5_subgroup(_file.create_group("metadata/sample"),read_file.metadata["sample"])
            else: # Otherwise we create an empty group.
                _file.create_group("metadata/sample")

            # Create the group for trace metadata, data
            _file.create_group("data/sample")
            _file.create_group("data/trace")
            _file.create_group("metadata/trace")

        # Ok, that concludes organizing the data file. Now onto data copying/output.
        # For each trace, we make a variable called subgroup.
        for rcv_location in rcv_locations:
            # Iterators in the file run between these 2 values.
            start_num = file_it * shots_per_tr
            end_num   = (file_it+1) * shots_per_tr

            subgroup = _file.create_group(f"data/trace/{trace_it}")
            subgroup_metadata = _file.create_group(f"metadata/trace/{trace_it}")

            # We save all the raw data.
            for num in range(shots_per_tr):
                subgroup[f"Velocity/{num}"] = read_file[f"Velocity/{num+start_num}"][()] * read_file["Velocity/scalefactor"][()]
                subgroup[f"Overrange/{num}"] = read_file[f"Velocity/overrange/{num+start_num}"][()]
                subgroup[f"RSSI/{num}"] = read_file[f"RSSI/{num+start_num}"][()] * read_file["RSSI/scalefactor"][()]
                subgroup[f"Trigger/{num}"] = read_file[f"Trigger/{num+start_num}"][()]

            # We generate both time arrays and an average velocity array. Note that this is not very efficient but it makes
            # sharing data a lot easier, and does not take that much space compared to the raw data storage.
            subgroup[f"Time"] = read_file.generate_t_array()
            subgroup[f"BaseTime"] = read_file.generate_t_array(freq_factor=False)
            subgroup[f"avgVelocity"] = read_file.average_velocity(start_num,end_num)

            # That was all the data. Now the metadata.
            # For now, this just stores source and receiver locations.
            subgroup_metadata[f"rcv_location"] = rcv_location
            subgroup_metadata[f"src_location"] = src_location

            # Increment the trace iterator and the file iterator
            trace_it += 1
            file_it  += 1


        read_file.close()
        del read_file
    
    # At the end of the import, we should write the total number of traces to the experiment metadata.
    _file["metadata/experiment/total_traces"] = trace_it

    _file.close()
    del _file






    

