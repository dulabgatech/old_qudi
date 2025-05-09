# -*- coding: utf-8 -*-

"""
This file contains the dummy for a magnet interface.

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

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from collections import OrderedDict

from core.module import Base
from interface.magnet_interface import MagnetInterface
import numpy as np
from core.configoption import ConfigOption


class MagnetAxisDummy:
    """ Generic dummy magnet representing one axis. """
    def __init__(self, label):
        self.label = label
        self.pos = 0.0
        self.status = 0, {0: 'MagnetDummy Idle'}


class MagnetDummy(Base, MagnetInterface):
    """ This is the Interface class to define the controls for the simple
        magnet hardware.

    Example config for copy-paste:

    magnet_dummy:
        module.Class: 'magnet.magnet_dummy.MagnetDummy'

    """
    x_constr = ConfigOption('magnet_x_constr', 1e-3)
    y_constr = ConfigOption('magnet_y_constr', 1e-3)
    z_constr = ConfigOption('magnet_z_constr', 1e-3)
    rho_constr = ConfigOption('magnet_rho_constr', 1e-3)
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        #these label should be actually set by the config.
        self._x_axis = MagnetAxisDummy('x')
        self._y_axis = MagnetAxisDummy('y')
        self._z_axis = MagnetAxisDummy('z')
        self._phi_axis = MagnetAxisDummy('phi')
        self._rho_axis = MagnetAxisDummy('rho')
        self._theta_axis = MagnetAxisDummy('theta')
    

    #TODO: Checks if configuration is set and is reasonable

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        pass

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        pass

    def get_constraints(self):
        """ Retrieve the hardware constrains from the motor device.

        @return dict: dict with constraints for the magnet hardware. These
                      constraints will be passed via the logic to the GUI so
                      that proper display elements with boundary conditions
                      could be made.

        Provides all the constraints for each axis of a motorized stage
        (like total travel distance, velocity, ...)
        Each axis has its own dictionary, where the label is used as the
        identifier throughout the whole module. The dictionaries for each axis
        are again grouped together in a constraints dictionary in the form

            {'<label_axis0>': axis0 }

        where axis0 is again a dict with the possible values defined below. The
        possible keys in the constraint are defined here in the interface file.
        If the hardware does not support the values for the constraints, then
        insert just None. If you are not sure about the meaning, look in other
        hardware files to get an impression.
        """
        constraints = OrderedDict()

        # get the constraints for the x axis:
        axis0 = {'label': 'x',
                 'unit': 'T',
                 'ramp': ['Linear'],
                 'pos_min': -self.x_constr,
                 'pos_max': self.x_constr,
                 'pos_step': 0.001e-3,
                 'vel_min': 0,
                 'vel_max': 1e-3,
                 'vel_step': 0.01e-3,
                 'acc_min': 0.1e-3,
                 'acc_max': 0.0,
                 'acc_step': 0.0}

        axis1 = {'label': 'y',
                 'unit': 'T',
                 'ramp': ['Linear'],
                 'pos_min': -self.y_constr,
                 'pos_max': self.y_constr,
                 'pos_step': 0.001e-3,
                 'vel_min': 0,
                 'vel_max': 1e-3,
                 'vel_step': 0.01e-3,
                 'acc_min': 0.1e-3,
                 'acc_max': 0.0,
                 'acc_step': 0.0}

        axis2 = {'label': 'z',
                 'unit': 'T',
                 'ramp': ['Linear'],
                 'pos_min': -self.z_constr,
                 'pos_max': self.z_constr,
                 'pos_step': 0.001e-3,
                 'vel_min': 0,
                 'vel_max': 1e-3,
                 'vel_step': 0.01e-3,
                 'acc_min': 0.1e-3,
                 'acc_max': 0.0,
                 'acc_step': 0.0}
        
        axis3 = {'label': 'rho', 'unit': 'T', 'pos_min': 0, 'pos_max': self.rho_constr, 'pos_step': 1e-6,
                 'vel_min': 0, 'vel_max': 1, 'vel_step': 1e-6}


        axis4 = {'label': 'theta', 'unit': ' rad', 'pos_min': 0, 'pos_max': 2*np.pi, 'pos_step': 2*np.pi/1000, 'vel_min': 0,
                 'vel_max': 1, 'vel_step': 1e-6}

        axis5 = {'label': 'phi',
                 'unit': ' rad',
                 'ramp': ['Sinus'],
                 'pos_min': 0,
                 'pos_max': 2*np.pi,
                 'pos_step': 2*np.pi/1000,
                 'vel_min': 0,
                 'vel_max': 1,
                 'vel_step': 1e-6,
                 'acc_min': None,
                 'acc_max': None,
                 'acc_step': None}
        
        

        # assign the parameter container for x to a name which will identify it

        # assign the parameter container for x to a name which will identify it
        constraints[axis0['label']] = axis0
        constraints[axis1['label']] = axis1
        constraints[axis2['label']] = axis2
        constraints[axis3['label']] = axis3
        constraints[axis4['label']] = axis4
        constraints[axis5['label']] = axis5

        return constraints


    def move_rel(self,  param_dict):
        """ Moves magnet in given direction (relative movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed.
                                With get_constraints() you can obtain all
                                possible parameters of that stage. According to
                                this parameter set you have to pass a dictionary
                                with keys that are called like the parameters
                                from get_constraints() and assign a SI value to
                                that. For a movement in x the dict should e.g.
                                have the form:
                                    dict = { 'x' : 23 }
                                where the label 'x' corresponds to the chosen
                                axis label.

        A smart idea would be to ask the position after the movement.
        """
        curr_pos_dict = self.get_pos()
        constraints = self.get_constraints()

        if param_dict.get(self._phi_axis.label) is not None:
            move_phi = param_dict[self._phi_axis.label]
            curr_pos_phi = curr_pos_dict[self._phi_axis.label]

            if  (curr_pos_phi + move_phi > constraints[self._phi_axis.label]['pos_max'] ) or\
                (curr_pos_phi + move_phi < constraints[self._phi_axis.label]['pos_min']):

                self.log.warning('Cannot make further movement of the axis '
                        '"{0}" with the step {1}, since the border [{2},{3}] '
                        ' of the magnet was reached! Ignore '
                        'command!'.format(
                            self._phi_axis.label,
                            move_phi,
                            constraints[self._phi_axis.label]['pos_min'],
                            constraints[self._phi_axis.label]['pos_max']))
            else:
                self._phi_axis.pos = self._phi_axis.pos + move_phi
        
        if param_dict.get(self._rho_axis.label) is not None:
            move_rho = param_dict[self._rho_axis.label]
            curr_pos_rho = curr_pos_dict[self._rho_axis.label]

            if  (curr_pos_rho + move_rho > constraints[self._rho_axis.label]['pos_max'] ) or\
                (curr_pos_rho + move_rho < constraints[self._rho_axis.label]['pos_min']):

                self.log.warning('Cannot make further movement of the axis '
                        '"{0}" with the step {1}, since the border [{2},{3}] '
                        ' of the magnet was reached! Ignore '
                        'command!'.format(
                            self._rho_axis.label,
                            move_rho,
                            constraints[self._rho_axis.label]['pos_min'],
                            constraints[self._rho_axis.label]['pos_max']))
            else:
                self._rho_axis.pos = self._rho_axis.pos + move_rho
        
        if param_dict.get(self._theta_axis.label) is not None:
            move_theta = param_dict[self._theta_axis.label]
            curr_pos_theta = curr_pos_dict[self._theta_axis.label]

            if  (curr_pos_theta + move_theta > constraints[self._theta_axis.label]['pos_max'] ) or\
                (curr_pos_theta + move_theta < constraints[self._theta_axis.label]['pos_min']):

                self.log.warning('Cannot make further movement of the axis '
                        '"{0}" with the step {1}, since the border [{2},{3}] '
                        ' of the magnet was reached! Ignore '
                        'command!'.format(
                            self._theta_axis.label,
                            move_theta,
                            constraints[self._theta_axis.label]['pos_min'],
                            constraints[self._theta_axis.label]['pos_max']))
            else:
                self._theta_axis.pos = self._theta_axis.pos + move_theta
        
        self.move_abs({self._theta_axis.label:self._theta_axis.pos, self._rho_axis.label:self._rho_axis.pos, self._phi_axis.label:self._phi_axis.pos})

    def move_abs(self, param_dict):
        """ Moves magnet to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <a-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        A smart idea would be to ask the position after the movement.
        """
        constraints = self.get_constraints()

        if param_dict.get(self._phi_axis.label) is not None:
            desired_pos = param_dict[self._phi_axis.label]
            constr = constraints[self._phi_axis.label]

            if not(constr['pos_min'] <= desired_pos <= constr['pos_max']):
                self.log.warning('Cannot make absolute movement of the axis '
                        '"{0}" to possition {1}, since it exceeds the limits '
                        '[{2},{3}] of the magnet! Command is ignored!'.format(
                            self._phi_axis.label,
                            desired_pos,
                            constr['pos_min'],
                            constr['pos_max']))
            else:
                self._phi_axis.pos = desired_pos
        
        if param_dict.get(self._theta_axis.label) is not None:
            desired_pos = param_dict[self._theta_axis.label]
            constr = constraints[self._theta_axis.label]

            if not(constr['pos_min'] <= desired_pos <= constr['pos_max']):
                self.log.warning('Cannot make absolute movement of the axis '
                        '"{0}" to possition {1}, since it exceeds the limits '
                        '[{2},{3}] of the magnet! Command is ignored!'.format(
                            self._theta_axis.label,
                            desired_pos,
                            constr['pos_min'],
                            constr['pos_max']))
            else:
                self._theta_axis.pos = desired_pos
        
        if param_dict.get(self._rho_axis.label) is not None:
            desired_pos = param_dict[self._rho_axis.label]
            constr = constraints[self._rho_axis.label]

            if not(constr['pos_min'] <= desired_pos <= constr['pos_max']):
                self.log.warning('Cannot make absolute movement of the axis '
                        '"{0}" to possition {1}, since it exceeds the limits '
                        '[{2},{3}] of the magnet! Command is ignored!'.format(
                            self._rho_axis.label,
                            desired_pos,
                            constr['pos_min'],
                            constr['pos_max']))
            else:
                self._rho_axis.pos = desired_pos
        
        self._x_axis.pos = self._rho_axis.pos * np.sin(self._theta_axis.pos) * np.cos(self._phi_axis.pos)
        self._y_axis.pos = self._rho_axis.pos * np.sin(self._theta_axis.pos) * np.sin(self._phi_axis.pos)
        self._z_axis.pos = self._rho_axis.pos * np.cos(self._theta_axis.pos)

    def abort(self):
        """ Stops movement of the stage

        @return int: error code (0:OK, -1:error)
        """
        self.log.info('MagnetDummy: Movement stopped!')
        return 0

    def get_pos(self, param_list=None):
        """ Gets current position of the magnet stage arms

        @param list param_list: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """
        pos = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                pos[self._x_axis.label] = self._x_axis.pos

            if self._y_axis.label in param_list:
                pos[self._y_axis.label] = self._y_axis.pos

            if self._z_axis.label in param_list:
                pos[self._z_axis.label] = self._z_axis.pos

            if self._phi_axis.label in param_list:
                pos[self._phi_axis.label] = self._phi_axis.pos
            
            if self._rho_axis.label in param_list:
                pos[self._rho_axis.label] = self._rho_axis.pos
            
            if self._theta_axis.label in param_list:
                pos[self._theta_axis.label] = self._theta_axis.pos

        else:
            pos[self._x_axis.label] = self._x_axis.pos
            pos[self._y_axis.label] = self._y_axis.pos
            pos[self._z_axis.label] = self._z_axis.pos
            pos[self._phi_axis.label] = self._phi_axis.pos
            pos[self._theta_axis.label] = self._theta_axis.pos
            pos[self._rho_axis.label] = self._rho_axis.pos

        # return {'x':np.random.random(),'y':np.random.random(),'z':np.random.random(),'rho':np.random.random(),'theta':np.random.random(),'phi':np.random.random()}
        return pos

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and the status number as item.
        """

        status = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                status[self._x_axis.label] = self._x_axis.status

            if self._y_axis.label in param_list:
                status[self._y_axis.label] = self._y_axis.status

            if self._z_axis.label in param_list:
                status[self._z_axis.label] = self._z_axis.status

            if self._phi_axis.label in param_list:
                status[self._phi_axis.label] = self._phi_axis.status
            
            if self._theta_axis.label in param_list:
                status[self._theta_axis.label] = self._theta_axis.status
            
            if self._rho_axis.label in param_list:
                status[self._rho_axis.label] = self._rho_axis.status

        else:
            status[self._x_axis.label] = self._x_axis.status
            status[self._y_axis.label] = self._y_axis.status
            status[self._z_axis.label] = self._z_axis.status
            status[self._phi_axis.label] = self._phi_axis.status
            status[self._rho_axis.label] = self._rho_axis.status
            status[self._theta_axis.label] = self._theta_axis.status

        return status

    def calibrate(self, param_list=None):
        """ Calibrates the magnet stage.

        @param dict param_list: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        if param_list is not None:
            if self._x_axis.label in param_list:
                self._x_axis.pos = 0.0

            if self._y_axis.label in param_list:
                self._y_axis.pos = 0.0

            if self._z_axis.label in param_list:
                self._z_axis.pos = 0.0

            if self._phi_axis.label in param_list:
                self._phi_axis.pos = 0.0
            
            if self._rho_axis.label in param_list:
                self._rho_axis.pos = 0.0
            
            if self._theta_axis.label in param_list:
                self._theta_axis.pos = 0.0

        else:
            self._x_axis.pos = 0.0
            self._y_axis.pos = 0.0
            self._z_axis.pos = 0.0
            self._phi_axis.pos = 0.0
            self._theta_axis.pos = 0.0
            self._rho_axis.pos = 0.0

        return 0

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.

        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        vel = {}
        if param_list is not None:
            if self._x_axis.label in param_list:
                vel[self._x_axis.label] = self._x_axis.vel
            if self._y_axis.label in param_list:
                vel[self._x_axis.label] = self._y_axis.vel
            if self._z_axis.label in param_list:
                vel[self._x_axis.label] = self._z_axis.vel
            if self._phi_axis.label in param_list:
                vel[self._phi_axis.label] = self._phi_axis.vel
            if self._rho_axis.label in param_list:
                vel[self._rho_axis.label] = self._rho_axis.vel
            if self._theta_axis.label in param_list:
                vel[self._theta_axis.label] = self._theta_axis.vel

        else:
            vel[self._x_axis.label] = self._x_axis.get_vel
            vel[self._y_axis.label] = self._y_axis.get_vel
            vel[self._z_axis.label] = self._z_axis.get_vel
            vel[self._phi_axis.label] = self._phi_axis.vel
            vel[self._rho_axis.label] = self._rho_axis.vel
            vel[self._theta_axis.label] = self._theta_axis.vel

        return vel

    def set_velocity(self, param_dict=None):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        """
        # constraints = self.get_constraints()

        # if param_dict.get(self._x_axis.label) is not None:
        #     desired_vel = param_dict[self._x_axis.label]
        #     constr = constraints[self._x_axis.label]

        #     if not(constr['vel_min'] <= desired_vel <= constr['vel_max']):
        #         self.log.warning('Cannot make absolute movement of the axis '
        #                 '"{0}" to possition {1}, since it exceeds the limits '
        #                 '[{2},{3}] ! Command is ignored!'.format(
        #                     self._x_axis.label,
        #                     desired_vel,
        #                     constr['vel_min'],
        #                     constr['vel_max']))
        #     else:
        #         self._x_axis.vel = desired_vel

        # if param_dict.get(self._y_axis.label) is not None:
        #     desired_vel = param_dict[self._y_axis.label]
        #     constr = constraints[self._y_axis.label]

        #     if not(constr['vel_min'] <= desired_vel <= constr['vel_max']):
        #         self.log.warning('Cannot make absolute movement of the axis '
        #                 '"{0}" to possition {1}, since it exceeds the limits '
        #                 '[{2},{3}] ! Command is ignored!'.format(
        #                     self._y_axis.label,
        #                     desired_vel,
        #                     constr['vel_min'],
        #                     constr['vel_max']))
        #     else:
        #         self._y_axis.vel = desired_vel

        # if param_dict.get(self._z_axis.label) is not None:
        #     desired_vel = param_dict[self._z_axis.label]
        #     constr = constraints[self._z_axis.label]

        #     if not(constr['vel_min'] <= desired_vel <= constr['vel_max']):
        #         self.log.warning('Cannot make absolute movement of the axis '
        #                 '"{0}" to possition {1}, since it exceeds the limits '
        #                 '[{2},{3}] ! Command is ignored!'.format(
        #                     self._z_axis.label,
        #                     desired_vel,
        #                     constr['vel_min'],
        #                     constr['vel_max']))
        #     else:
        #         self._z_axis.vel = desired_vel

        # if param_dict.get(self._phi_axis.label) is not None:
        #     desired_vel = param_dict[self._phi_axis.label]
        #     constr = constraints[self._phi_axis.label]

        #     if not(constr['vel_min'] <= desired_vel <= constr['vel_max']):
        #         self.log.warning('Cannot make absolute movement of the axis '
        #                 '"{0}" to possition {1}, since it exceeds the limits '
        #                 '[{2},{3}] ! Command is ignored!'.format(
        #                     self._phi_axis.label,
        #                     desired_vel,
        #                     constr['vel_min'],
        #                     constr['vel_max']))
        #     else:
        #         self._phi_axis.vel = desired_vel
        pass

    def tell(self, param_dict=None):
        """ Send a command to the magnet.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the command string>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        self.log.info('You can tell the magnet dummy as much as you want, it '
                'has always an open ear for you. But do not expect an '
                'answer, it is very shy!')

        return 0

    def ask(self, param_dict=None):
        """ Ask the magnet a question.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the question string>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return string: contains the answer coming from the magnet
        """
        self.log.info('Dude, I am a dummy! Your question(s) "{0}" to the '
                'axis "{1}" is/are way to complicated for me :D ! If you '
                'want to talk to someone, ask Siri, maybe she will listen to '
                'you and answer your questions :P.'.format(
                    list(param_dict.values()), list(param_dict)))

        return_val = {}
        for entry in param_dict:
            return_val[entry] = 'Nothing to say, Motor is quite.'

        return return_val

    def set_magnet_idle_state(self, magnet_idle=True):
        """ Set the magnet to couple/decouple to/from the control.

        @param bool magnet_idle: if True then magnet will be set to idle and
                                 each movement command will be ignored from the
                                 hardware file. If False the magnet will react
                                 on movement changes of any kind.

        @return bool: the actual state which was set in the magnet hardware.
                        True = idle, decoupled from control
                        False = Not Idle, coupled to control
        """

        self._idle_state = magnet_idle
        return self._idle_state

    def get_magnet_idle_state(self):
        """ Retrieve the current state of the magnet, whether it is idle or not.

        @return bool: the actual state which was set in the magnet hardware.
                        True = idle, decoupled from control
                        False = Not Idle, coupled to control
        """

        return self._idle_state

    def initialize(self):
        """
        Acts as a switch. When all coils of the superconducting magnet are
        heated it cools them, else the coils get heated.
        @return int: (0: Ok, -1:error)
        """
        return -1
