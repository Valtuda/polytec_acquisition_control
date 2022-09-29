# (c) Jasper Smits 2022, release under LGPLv3

# This small class will handle saving the results of an experimental run to a HDF5 file. As an input it will take mainly the buffer of Vibrometer class, and a dict-of-dicts describing properties of the vibrometer, laser, etc. This class will only support writing, for now.

import h5py
import os

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

    @property
    def average_velocity(self):
        arr = np.zeros(self._total_samples,dtype=float)
        for it in range(self._block_count):
            arr += self.velocity(it)

        return arr/self._block_count

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
        subgroup[f"avgVelocity"] = read_file.average_velocity

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




