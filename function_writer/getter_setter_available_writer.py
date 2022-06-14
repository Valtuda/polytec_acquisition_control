"""
It is fastest, instead of writing a setter, getter and available() function for every property, to just write a script to write these for me. This file is rudimentary and will not cover every case, but beats implementing every function seperately.
"""

# Copyright (c) Jasper Smits
# Released under the terms of the GNU LPGLv3

# Function format taken from Polytec's DaqConfig class. (c) Polytec GmbH 2021, Walbrunn, under LGPLv3

# We supply a single JSON or dict.
# The format will be as follows:

def output_functions_string(**func_dict):
    """
    Outputs a function string for controlling the associated property. It will output a single line to be used in __init__ of the class and a larger string with line-breaks which represents the pack of functions.

    Argumennts:
    - func_dict: A dictionary containing all info related to the function.

    func_dict should contain:
    - "name":  Property name
    - "hname": Human readable property name
    - "dtype": DeviceType Enum property
    - "dcomm": DeviceCommand Enum property
    """
    
    name  = func_dict["name"]
    hname = func_dict["hname"]
    dtype = func_dict["dtype"]
    dcomm = func_dict["dcomm"]
    
    return(f'        self.__{name} = ItemList(self.__communication, DeviceType.{dtype}, DeviceCommand.{dcomm})',
           f'    # {hname}\n'
           f'    @property\n'
           f'    def {name}(self):\n'
           f'        """Gets the {hname}"""\n'
           f'        return self.__{name}.current_item()\n'
           f'    \n'
           f'    @{name}.setter\n'
           f'    def {name}(self,new_value):\n'
           f'        """Sets the {hname}"""\n'
           f'        if self.__{name}.is_item_available(new_value):\n'
           f'            self.__{name}.set_current_item(new_value)\n'
           f'        else:\n'
           f'            raise ConfigurationError(f"{hname} mode not available: {{new_value}}. Available values: {{self.all_{name}()}}.")\n'
           f'    \n'
           f'    def all_{name}(self):\n'
           f'        """Gets all available settings for property {hname}"""\n'
           f'        return self.__{name}.available_items()\n'
           f'    \n')

if __name__ == "__main__":
    # Might as well send it straight to the clipboard?
    import pyperclip

    while True:
        print("Welcome to the function printer utility. Exit using Ctrl-C.")
        name = input("Property name (no spaces!)")
        hname = input("Human readable property name/description")
        dtype = input("DeviceType Enum associated with this property. (Default: VelocityDecoderDigital)")
        if dtype=="":
            dtype = "VelocityDecoderDigital"
        dcomm = input("DeviceCommand Enum associted with this property.")

        init_part, functions = output_functions_string(name=name,hname=hname,dtype=dtype,dcomm=dcomm)
        pyperclip.copy(init_part)
        _ = input("Init part sent to clipboard. Press enter to receive the function part.")
        pyperclip.copy(functions)

