# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control R&S SGS100A microwave device.

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

import visa
import time
import numpy as np

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge


class MicrowaveSgs(Base,MicrowaveInterface):
    """ Hardware file to control a R&S SGS100A microwave device.

    Example config for copy-paste:

    mw_source_sgs:
        module.Class: 'microwave.mw_source_sgs.MicrowaveSgs'
        gpib_address: 'GPIB0::12::INSTR'
        gpib_timeout: 10

    """

    # visa address of the hardware : this can be over ethernet, the name is here for
    # backward compatibility
    _address = ConfigOption('tcpip_address', missing='error')
    _timeout = ConfigOption('tcpip_timeout', 10, missing='warn')

    # to limit the power to a lower value that the hardware can provide
    _max_power = ConfigOption('max_power', None)

    # Indicate how fast frequencies within a list or sweep mode can be changed:
    _FREQ_SWITCH_SPEED = 0.003  # Frequency switching speed in s (acc. to specs)

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
        self._command_wait(':LOCK? 72349234')
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self.unlock()
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

        # values for SMBV100A
        limits.min_power = -145
        limits.max_power = 30

        limits.min_frequency = 9e3
        limits.max_frequency = 6e9

        if self.model == 'SGS100A':
            limits.max_frequency = 3.2e9

        limits.list_minstep = 0.1
        limits.list_maxstep = limits.max_frequency - limits.min_frequency
        limits.list_maxentries = 1

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
        return float(self._connection.query(':POWer:POWer?'))
    
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
            self._command_wait(':OPMode NORMal')

        # Set CW frequency
        if frequency is not None:
            self._command_wait(f':FREQuency:CW {frequency}')

        # Set CW power
        if power is not None:
            self._command_wait(f':POWer:POWer {power}')

        # Return actually set values
        mode, dummy = self.get_status()
        actual_freq = self.get_frequency()
        actual_power = self.get_power()
        return actual_freq, actual_power, mode

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

    def list_on(self):
        """
        Switches on the list mode microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        self.log.error('List mode not available for this microwave hardware!')
        return -1

    def set_list(self, frequency=None, power=None):
        """
        Configures the device for list-mode and optionally sets frequencies and/or power

        @param list frequency: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        @return tuple(list, float, str):
            current frequencies in Hz,
            current power in dBm,
            current mode
        """
        self.log.error('List mode not available for this microwave hardware!')
        mode, dummy = self.get_status()
        return self.get_frequency(), self.get_power(), mode

    def reset_listpos(self):
        """
        Reset of MW list mode position to start (first frequency step)

        @return int: error code (0:OK, -1:error)
        """
        self.log.error('List mode not available for this microwave hardware!')
        return -1

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

        if current_mode != 'sweep':
            self._command_wait(':FREQ:MODE SWEEP')

        self._connection.write(':OUTP:STAT ON')
        dummy, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_sweep(self, start=None, stop=None, step=None, power=None):
        """
        Configures the device for sweep-mode and optionally sets frequency start/stop/step
        and/or power

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

        if (start is not None) and (stop is not None) and (step is not None):
            self._connection.write(':SWE:MODE STEP')
            self._connection.write(':SWE:SPAC LIN')
            self._connection.write('*WAI')
            self._connection.write(':FREQ:START {0:f}'.format(start - step))
            self._connection.write(':FREQ:STOP {0:f}'.format(stop))
            self._connection.write(':SWE:STEP:LIN {0:f}'.format(step))
            self._connection.write('*WAI')

        if power is not None:
            self._connection.write(':POW {0:f}'.format(power))
            self._connection.write('*WAI')

        self._command_wait('TRIG:FSW:SOUR EXT')

        actual_power = self.get_power()
        freq_list = self.get_frequency()
        mode, dummy = self.get_status()
        return freq_list[0], freq_list[1], freq_list[2], actual_power, mode

    def reset_sweeppos(self):
        """
        Reset of MW sweep mode position to start (start frequency)

        @return int: error code (0:OK, -1:error)
        """
        self._command_wait(':ABOR:SWE')
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
            edge = 'POSitive'
        elif pol == TriggerEdge.FALLING:
            edge = 'NEGative'
        else:
            self.log.warning('No valid trigger polarity passed to microwave hardware module.')
            edge = None

        if edge is not None:
            self._command_wait(':CONNector:TRIGger:OMODe PETRigger')
            self._command_wait(f':PULM:TRIGger:EXTernal:SLOPe {edge}')

        polarity = self._connection.query(':PULM:TRIGger:EXTernal:SLOPe?')
        if 'NEG' in polarity:
            return TriggerEdge.FALLING, timing
        else:
            return TriggerEdge.RISING, timing

    def trigger(self):
        """ Trigger the next element in the list or sweep mode programmatically.

        @return int: error code (0:OK, -1:error)

        Ensure that the Frequency was set AFTER the function returns, or give
        the function at least a save waiting time.
        """

        # WARNING:
        # The manual trigger functionality was not tested for this device!
        # Might not work well! Please check that!

        self._connection.write('*TRG')
        time.sleep(self._FREQ_SWITCH_SPEED)  # that is the switching speed
        return 0
    
    def unlock(self):
        """
        Unlock the device

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('UNLock 72349234')

        return 0

    def set_ext_pulse_mod(self):
        """
        Set the extneral gated pulse modulation

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('SOUR:PULM:SOUR EXT') # External triggered
        self._connection.write('SOUR:PULM:TRIG:MODE EGAT') # mode = gated trigger
        self._connection.write('SOUR:PULM:TRIG:EXT:IMP G50') # External input impedance
        self._connection.write('SOUR:PULM:STAT 1') # Turn pulse modulation on

        return 0
    
    def set_ext_pulse_mod_off(self):
        """
        Set the extneral gated pulse modulation off

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('SOUR:PULM:STAT 0') # Turn pulse modulation on

        return 0

    def set_IQ_mod(self):
        """
        Set the IQ modulation

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('SOUR:IQ:STAT ON') # IQ mod on

        return 0