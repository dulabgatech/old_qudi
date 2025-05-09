# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control R&S SMB100A or SMBV100A microwave device.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Parts of this file were developed from a PI3diamond module which is
Copyright (C) 2009 Helmut Rathgen <helmut.rathgen@gmail.com>

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import pyvisa as visa
import time
import numpy as np

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge
from interface.microwave_interface import MicrowaveTriggerMode


class MicrowaveSMB100B(Base, MicrowaveInterface):
    """ Hardware file to control a R&S SMBV100A microwave device.

    Example config for copy-paste:

    mw_source_sgs100B:
        module.Class: 'microwave.mw_source_sgs100B.MicrowaveSGS100B'
        tcpip_address: 'TCPIP0::172.16.27.118::inst0::INSTR'
        tcpip_timeout: 10

    """

    # visa address of the hardware : this can be over ethernet, the name is here for
    # backward compatibility
    _address = ConfigOption('tcpip_address', missing='error')
    _timeout = ConfigOption('tcpip_timeout', 10, missing='warn')
    _dwell_time = ConfigOption('dwell_time', 120000) # dwell time in us 

    # to limit the power to a lower value that the hardware can provide
    _max_power = ConfigOption('max_power', None)

    # Indicate how fast frequencies within a list or sweep mode can be changed:
    _FREQ_SWITCH_SPEED = 0.001  # Frequency switching speed in s (acc. to specs)

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self._timeout = self._timeout * 1000
        # trying to load the visa connection to the module
        self.rm = visa.ResourceManager()
        try:
            self._connection = self.rm.open_resource(self._address,
                                                          timeout=self._timeout)
        except:
            self.log.error('Could not connect to the address >>{}<<.'.format(self._address))
            raise

        self.model = self._connection.query('*IDN?').split(',')[1]
        self.log.info('MW {} initialised and connected.'.format(self.model))
        self._command_wait('*CLS')
        self._command_wait('*RST')
        # self._command_wait('SYSTem:DISPlay:UPDate OFF')
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self.rm.close()
        return

    def _command_wait(self, command_str):
        """
        Writes the command in command_str via ressource manager and waits until the device has finished
        processing it.

        @param command_str: The command to be written
        """
        self._connection.write(command_str)
        self._connection.write('*WAI')
        while int(float(self._connection.query('*OPC?'))) != 1:
            time.sleep(0.2)
        return

    def get_limits(self):
        """ Create an object containing parameter limits for this microwave source.

            @return MicrowaveLimits: device-specific parameter limits
        """
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.SWEEP)

        limits.min_power = -145
        limits.max_power = -1

        limits.min_frequency = 8e3
        limits.max_frequency = 6e9

        limits.list_minstep = 0.1
        limits.list_maxstep = limits.max_frequency - limits.min_frequency
        limits.list_maxentries = 10001 # No list mode available

        limits.sweep_minstep = 0.1
        limits.sweep_maxstep = limits.max_frequency - limits.min_frequency
        limits.sweep_maxentries = 10001

        # in case a lower maximum is set in config file
        if self._max_power is not None and self._max_power < limits.max_power:
            limits.max_power = self._max_power

        return limits

    def off(self):
        """
        Switches off any microwave output.
        Must return AFTER the device is actually stopped.

        @return int: error code (0:OK, -1:error)
        """
        mode, is_running = self.get_status()
        if not is_running:
            return 0

        self._connection.write('OUTP:STAT OFF')
        self._connection.write('*WAI')
        while int(float(self._connection.query('OUTP:STAT?'))) != 0:
            time.sleep(0.2)
        return 0

    def get_status(self):
        """
        Gets the current status of the MW source, i.e. the mode (cw, list or sweep) and
        the output state (stopped, running)

        @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
        """
        is_running = bool(int(float(self._connection.query('OUTP:STAT?'))))
        mode = self._connection.query(':FREQ:MODE?').strip('\n').lower()
        if mode == 'swe':
            mode = 'sweep'
        return mode, is_running

    def get_power(self):
        """
        Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        # This case works for cw AND sweep mode
        return float(self._connection.query(':POW?'))

    def set_power(self, power=None):
        """ Sets the microwave source in CW mode, and sets the MW power.
        Method ignores whether the output is on or off

        @param (float) power: power to set in dBm

        @return int: error code (0:OK, -1:error)
        """
        mode, is_running = self.get_status()

        # Activate CW mode
        if mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        # Set CW power
        if power is not None:
            self._command_wait(':POW {0:f}'.format(power))

        return 0

    def get_frequency(self):
        """
        Gets the frequency of the microwave output.
        Returns single float value if the device is in cw mode.
        Returns list like [start, stop, step] if the device is in sweep mode.
        Returns list of frequencies if the device is in list mode.

        @return [float, list]: frequency(s) currently set for this device in Hz
        """
        mode, is_running = self.get_status()
        if 'cw' in mode:
            return_val = float(self._connection.query(':FREQ?'))
        elif 'sweep' in mode:
            start = float(self._connection.query(':FREQ:STAR?'))
            stop = float(self._connection.query(':FREQ:STOP?'))
            step = float(self._connection.query(':SWE:STEP?'))
            return_val = [start+step, stop, step]
        return return_val

    def set_frequency(self, frequency=None):
        """ Sets the microwave source in CW mode, and sets the MW power.
        Method ignores whether the output is on or off

        @param (float) frequency: frequency to set in Hz

        @return int: error code (0:OK, -1:error)
        """
        mode, is_running = self.get_status()

        # Activate CW mode
        if mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        # Set CW frequency
        if frequency is not None:
            self._command_wait(':FREQ {0:f}'.format(frequency))

        return 0

    def cw_on(self):
        """
        Switches on cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        current_mode, is_running = self.get_status()
        if is_running:
            if current_mode == 'cw':
                return 0
            else:
                self.off()

        if current_mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        self._connection.write(':OUTP:STAT ON')
        self._connection.write('*WAI')
        dummy, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_cw(self, frequency=None, power=None):
        """
        Configures the device for cw-mode and optionally sets frequency and/or power

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm

        @return tuple(float, float, str): with the relation
            current frequency in Hz,
            current power in dBm,
            current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        # Activate CW mode
        if mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        # Set CW frequency
        if frequency is not None:
            self._command_wait(':FREQ {0:f}'.format(frequency))

        # Set CW power
        if power is not None:
            self._command_wait(':POW {0:f}'.format(power))

        # Return actually set values
        mode, dummy = self.get_status()
        actual_freq = self.get_frequency()
        actual_power = self.get_power()
        return actual_freq, actual_power, mode

    def list_on(self):
        """
        Switches on the list mode microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        current_mode, is_running = self.get_status()
        if is_running:
            if current_mode == 'list':
                return 0
            else:
                self.off()

        # This needs to be done due to stupid design of the list mode (sweep is better)
        self.cw_on()
        self._command_wait(':FREQ:MODE LIST')
        dummy, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_frequency_modulation(self, frequency=2.87e9,deviation = 2e7, source = 'EXT'):
        """
        Configure the device for frequency modulation using Path 1, Defaut being deviation of 2e7 Hz and source being external
        
        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('*RST')
        self.set_frequency(frequency)
        self._connection.write('SOURce1:INPut:MODext:COUPling AC')
        self._connection.write('SOURce1:INPut:MODext:IMPedance G50')
        self._connection.write('SOURce1:FM1:SOURce '+source)
        self._connection.write('SOURce1:FM1:DEViation '+str(deviation))
        self._connection.write('SOURce1:FM1:DEViation:MODE UNCoupled')
        self._connection.write('SOURce1:FM1:STATe 1')
        return 0
    
    def set_phase_modulation(self, deviation = 3, source = 'EXT', mode = 'LNOise'):
        """
        Configure the device for phase modulation using Path 1, Defaut being deviation of 2pi and source being external
        
        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('*RST')
        self._connection.write('SOURce1:PM1:MODE '+mode)
        self._connection.write('SOURce1:INPut:MODext:COUPling AC')
        self._connection.write('SOURce1:INPut:MODext:IMPedance G50')
        self._connection.write('SOURce1:PM1:SOURce '+source)
        self._connection.write('SOURce1:PM1:DEViation '+str(deviation))
        self._connection.write('SOURce1:PM1:DEViation:MODE UNCoupled')
        self._connection.write('SOURce1:PM1:STATe 1')
        return 0

    def set_list(self, frequency=None, power=None, mw_trigger_mode = 'STEP_EXT'):
        """
        Configures the device for list-mode and optionally sets frequencies and/or power

        @param list frequency: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        @return tuple(list, float, str):
            current frequencies in Hz,
            current power in dBm,
            current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        # Cant change list parameters if in list mode
        if mode != 'cw':
            self.set_cw()

        self._command_wait(":LIST:SEL '/var/user/QUDI.lsw'")

        #set dwell time mode to list
        self._command_wait(':LIST:DWEL:MODE LIST')

        # Set list frequencies
        if frequency is not None:
            s = ''
            dwell = ''
            for f in frequency[:-1]:
                s += ' {0:f} Hz,'.format(f)
                dwell += ' {0:f},'.format(self._dwell_time)
            s += ' {0:f} Hz'.format(frequency[-1])
            dwell += ' {0:f}'.format(self._dwell_time)

            self._command_wait(':LIST:FREQ' + s)
            self._command_wait(':LIST:DWEL:LIST' + dwell)

        if power is not None:
            s = ''
            for p in range(len(frequency[:-1])):
                s += ' {0:f} dBm,'.format(power)
            s += ' {0:f}'.format(power)

            self._command_wait(':LIST:POW' + s)

        if mw_trigger_mode == MicrowaveTriggerMode.STEP_EXT:
            self._command_wait(':LIST:MODE STEP')
            self._command_wait(':TRIG1:LIST:SOUR EXT')
        elif mw_trigger_mode == MicrowaveTriggerMode.SINGLE_EXT:
            self._command_wait(':LIST:MODE AUTO')
            self._command_wait(':TRIG1:LIST:SOUR EXT')
        elif mw_trigger_mode == MicrowaveTriggerMode.SINGLE:
            # self._command_wait(':LIST:MODE AUTO')
            self._command_wait(':TRIG1:LIST:SOUR SING')

        else:
            self.log.warning('Incorrect trigger mode for CW ODMR')
        
        #FIXME: figure out how to set list mode without turning power on (maybe unnecessary)
        # Also get frequency from device, instead of assuming things went well.
        # Perhaps: actual_frequencies = self.query(':LIST:FREQ?')
        # self._command_wait(':FREQ:MODE LIST')
        # mode, dummy = self.get_status()
        return frequency, self.get_power(), 'list'

    def reset_listpos(self):
        """
        Reset of MW list mode position to start (first frequency step)

        @return int: error code (0:OK, -1:error)
        """
        self._command_wait(':LIST:RES')
        return 0

    def sweep_on(self):
        """ Switches on the sweep mode.

        @return int: error code (0:OK, -1:error)
        """
        current_mode, is_running = self.get_status()
        if is_running:
            if current_mode == 'sweep':
                return 0
            else:
                self.off()

        # if current_mode != 'sweep':
        #     self._command_wait(':FREQ:MODE SWEEP')

        self._connection.write(':OUTP:STAT ON') 
        dummy, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_sweep(self, start=None, stop=None, step=None, power=None,mw_trigger_mode = 'AUTO'):
        """
        Configures the device for sweep-mode and optionally sets frequency start/stop/step
        and/or power

        @param TriggerMode trig_mode: trigger mode for MW

        @return float, float, float, float, str: current start frequency in Hz,
                                                 current stop frequency in Hz,
                                                 current frequency step in Hz,
                                                 current power in dBm,
                                                 current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        if mode != 'sweep':
            self._command_wait(':FREQ:MODE SWEEP')

        if mw_trigger_mode == MicrowaveTriggerMode.AUTO:
            self._command_wait(':SWE:MODE AUTO')
            self._command_wait(':TRIG:FSW:SOUR AUTO')
        else:
            self.log.warning('Incorrect trigger mode for pulsed ODMR')


        if (start is not None) and (stop is not None) and (step is not None):
            # self._connection.write(':SWE:MODE STEP')
            self._connection.write(':SWE:SPAC LIN')
            self._connection.write('*WAI')
            self._connection.write(':FREQ:START {0:f}'.format(start - step))
            self._connection.write(':FREQ:STOP {0:f}'.format(stop))
            self._connection.write(':SWE:STEP:LIN {0:f}'.format(step))
            self._connection.write('*WAI')

        if power is not None:
            self._connection.write(':POW {0:f}'.format(power))
            self._connection.write('*WAI')

        #self._command_wait('TRIG:FSW:SOUR AUTO')
        # self._command_wait('TRIG:FSW:SOUR EXT')

        actual_power = self.get_power()
        freq_list = self.get_frequency()
        mode, dummy = self.get_status()
        return freq_list[0], freq_list[1], freq_list[2], actual_power, mode

    def reset_sweeppos(self):
        """
        Reset of MW sweep mode position to start (start frequency)

        @return int: error code (0:OK, -1:error)
        """
        self._command_wait(':SWEep:RESet:ALL')
        return 0

    def set_ext_trigger(self, pol, timing):
        """ Set the external trigger for this device with proper polarization.

        @param TriggerEdge pol: polarisation of the trigger (basically rising edge or falling edge)
        @param float timing: estimated time between triggers

        @return object, float: current trigger polarity [TriggerEdge.RISING, TriggerEdge.FALLING],
            trigger timing
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        if pol == TriggerEdge.RISING:
            edge = 'POS'
        elif pol == TriggerEdge.FALLING:
            edge = 'NEG'
        else:
            self.log.warning('No valid trigger polarity passed to microwave hardware module.')
            edge = None

        if edge is not None:
            #self._command_wait('PULM:TRIG1:EXT:SLOP {0}'.format(edge))
            self._command_wait('TRIG1:SLOP {0}'.format(edge))
            self._command_wait(':SWEep:FREQuency:DWEL {}'.format(timing)) # Nathan Added

        #polarity = self._connection.query('PULM:TRIG1:EXT:SLOP?')
        polarity = self._connection.query('TRIG1:SLOP?')
        if 'NEG' in polarity:
            return TriggerEdge.FALLING, timing
        else:
            return TriggerEdge.RISING, timing

    def trigger(self):
        """ Trigger the next element in the list or sweep mode programmatically.

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write(':TRIGger:IMMediate')
        time.sleep(self._FREQ_SWITCH_SPEED)
        return 0

    def set_cw_sweep(self, frequency=None, power=None):
        """ 

        @param list freq: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        """
        """
        Configures the device for cw-mode and optionally sets frequency and/or power

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm

        @return tuple(float, float, str): with the relation
            current frequency in Hz,
            current power in dBm,
            current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        self.final_freq_list = frequency
        self.mw_power = power

        # Activate CW mode
        if mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        # Set CW frequency
        if frequency is not None:
            self._command_wait(':FREQ {0:f}'.format(frequency[0]))

        # Set CW power
        if power is not None:
            self._command_wait(':POW {0:f}'.format(power))

        # self.set_ext_trigger()

        # Return actually set values
        mode, dummy = self.get_status()
        actual_freq = frequency
        actual_power = self.get_power()
        return actual_freq, actual_power, mode
