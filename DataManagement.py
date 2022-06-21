# (c) Jasper Smits 2022, release under LGPLv3

# This small class will handle saving the results of an experimental run to a HDF5 file. As an input it will take mainly the buffer of Vibrometer class, and a dict-of-dicts describing properties of the vibrometer, laser, etc. This class will only support writing, for now.

import h5py
import os

class HDF5Writer:
    self.__active_file = None
    def __init__(self):
        pass

    @property
    def active_file(self):
        if self.__active_file:
            return f.filename
        else:
            raise ValueError("No active file.")

    def open_file(self, filename, overwrite=False):
        if (not overwrite) and os.path.exists(filename):
            return IOError(f"File {filename} exists. Turn on overwrite or choose another file.")

        self.__active_file = h5py.File(filename, "w")

    def close_file(self):
        self.__active_file.close()
        self.__active_file = None

    ## Writing part, what does it have to do?
    # Take channel data, and write it into a HDF5 structure ( <channel> / <run_num>, also include <channel>/<avg> ), include metadata
    # Take (to be produced) dict-of-dicts which stores all setting data.
    # Store the executed script (this is not yet possible, and more of a feature of the entire control software, we will have to see how we do this.)

    def __write_channel_data(self,channel_data):
        """Takes a set of channel_data as from the generate_buffers() of the Vibrometer class. Writes it to file as described above."""

        for ch_name,channel in channel_data:
            if channel["Overrange"] is not None:
                has_overrange = True

            ch_grp = f.create_group("/"+ch_name)
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
    
    def __write_metadata(self,dict_of_dicts):
        """A very inflexible function to write metadata from a dictionary of dictionaries."""
        for _key,_dict in dict_of_dicts.items():
            for _skey,_item in _dict:
                f[_key+"__"+_skey] = _item


