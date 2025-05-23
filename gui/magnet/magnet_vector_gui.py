# -*- coding: utf-8 -*-

"""
This file contains the GUI for magnet control.

QuDi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QuDi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QuDi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import datetime
from hashlib import new
import numpy as np
import os
import pyqtgraph as pg
import pyqtgraph.exporters
from qtpy import uic

import matplotlib as mpl
from matplotlib import cm
import pyqtgraph.opengl as gl
from core.connector import Connector
from core.statusvariable import StatusVar
from gui.colordefs import ColorScaleViridis
from gui.guibase import GUIBase
from gui.guiutils import ColorBar
from qtpy import QtCore, QtGui
from qtpy import QtWidgets
from qtwidgets.scientific_spinbox import ScienDSpinBox
from qtwidgets.scan_plotwidget import ScanImageItem


class CrossLine(pg.InfiniteLine):

    """ Construct one line for the Crosshair in the plot.

    @param float pos: optional parameter to set the position
    @param float angle: optional parameter to set the angle of the line
    @param dict pen: Configure the pen.

    For additional options consider the documentation of pyqtgraph.InfiniteLine
    """

    def __init__(self, **args):
        pg.InfiniteLine.__init__(self, **args)
#        self.setPen(QtGui.QPen(QtGui.QColor(255, 0, 255),0.5))

    def adjust(self, extroi):
        """
        Run this function to adjust the position of the Crosshair-Line

        @param object extroi: external roi object from pyqtgraph
        """
        if self.angle == 0:
            self.setValue(extroi.pos()[1] + extroi.size()[1] * 0.5)
        if self.angle == 90:
            self.setValue(extroi.pos()[0] + extroi.size()[0] * 0.5)

class _3DAlignmentImageItem():
    def __init__(self, rho, thetas, phis, view):
        self.thetas = thetas
        self.phis = phis
        self.d_th = abs(thetas[1]-thetas[0])/2
        self.d_phi = abs(phis[1]-phis[0])/2
        self.rho = rho
        self.parent_view = view
        self.items = []
        
    def del_items(self):
        for item in self.items:
            try:
                self.parent_view.removeItem(item)
            except:
                return
    
    def make_face(self, index):
        theta, phi = self.thetas[index[0]], self.phis[index[1]]
        vertices = []
        for i in [1,-1]:
            for j in [1,-1]:
                _theta = theta + self.d_th*i
                _phi = phi + self.d_phi*j
                x1 = self.rho * np.sin(_theta) * np.cos(_phi)
                y1 = self.rho * np.sin(_theta) * np.sin(_phi)
                z1 = self.rho * np.cos(_theta)
                vertices.append([x1,y1,z1])
        faces = [[0,1,2],
                 [1,2,3]]
        
        return vertices, faces
                
    def setImage(self, matrix, levels):
        self.image = matrix
        cb_min, cb_max = (levels)
        norm = mpl.colors.Normalize(vmin=cb_min, vmax=cb_max)
        cmap = cm.viridis
        m = cm.ScalarMappable(norm=norm, cmap=cmap)
        thet = self.thetas
        ph = self.phis
        mi_vertices = []
        mi_faces = []
        mi_colors = []
        
        n = 0
        for i in range(len(thet)):
            for j in range(len(ph)):
                
                verts, faces = self.make_face((i,j))
                c = m.to_rgba(matrix[i,j])
                colors = np.array([[*c],[*c]])
                
                mi_vertices.extend(verts)
                mi_faces.extend(np.asarray(faces)+4*n)
                mi_colors.extend(colors)
                n += 1
                ## Mesh item will automatically compute face normals.
        m1 = gl.GLMeshItem(vertexes=np.asarray(mi_vertices), faces=np.asarray(mi_faces), faceColors=np.asarray(mi_colors), smooth=False, computeNormals=False)
        m1.translate(0, 0, 0)
        m1.setGLOptions('additive')
        self.parent_view.addItem(m1)
        self.items.append(m1)

class CustomTextItem(gl.GLGraphicsItem.GLGraphicsItem):
    def __init__(self, X, Y, Z, text):
        gl.GLGraphicsItem.GLGraphicsItem.__init__(self)
        self.text = text
        self.X = X
        self.Y = Y
        self.Z = Z

    def setGLViewWidget(self, GLViewWidget):
        self.GLViewWidget = GLViewWidget

    def setText(self, text):
        self.text = text
        self.update()

    def setX(self, X):
        self.X = X
        self.update()

    def setY(self, Y):
        self.Y = Y
        self.update()

    def setZ(self, Z):
        self.Z = Z
        self.update()

    def paint(self):
        self.GLViewWidget.qglColor(QtCore.Qt.white)
        self.GLViewWidget.renderText(self.X, self.Y, self.Z, self.text, QtGui.QFont('Arial', 12, QtGui.QFont.Medium))

class _3DAxisItem():
    def __init__(self, rho, thetas, phis, n_ticks, view, axis=False):
        self.n_ticks = n_ticks
        self.thetas = thetas
        self.phis = phis
        self.rho = rho
        self.parent_view = view
        self.items = []
        if axis:
            self.make_axis()
        self.make_ticks()
    
    def del_items(self):
        for item in self.items:
            try:
                self.parent_view.removeItem(item)
            except:
                return
                
    def make_axis(self):
        thet = np.linspace(self.thetas[0], self.thetas[-1], 50)
        ph = np.linspace(self.phis[0], self.phis[-1], 50)
        v = self.rho
        d_th = abs(self.thetas[0] - self.thetas[1])*0.5
        d_ph = abs(self.phis[0] - self.phis[1])*0.75
        
        thet -= d_th
        ph -=d_ph

        x0 = v * np.sin(thet[0]) * np.cos(ph[0])
        y0 = v * np.sin(thet[0]) * np.sin(ph[0])
        z0 = v * np.cos(thet[0])
        for j in range(len(ph)):
            theta = thet[0]
            phi = ph[j]

            x = v * np.sin(theta) * np.cos(phi)
            y = v * np.sin(theta) * np.sin(phi)
            z = v * np.cos(theta)

            PlotItem = gl.GLLinePlotItem(pos=np.array([[x0,y0,z0],[x,y,z]]), color=pg.glColor((255, 255, 255, 255)), width=5, antialias=True)
            self.parent_view.addItem(PlotItem)
            self.items.append(PlotItem)
            x0,y0,z0 = x,y,z

        x0 = v * np.sin(thet[0]) * np.cos(ph[0])
        y0 = v * np.sin(thet[0]) * np.sin(ph[0])
        z0 = v * np.cos(thet[0])
        for i in range(len(thet)):
            theta = thet[i]
            phi = ph[0]

            x = v * np.sin(theta) * np.cos(phi)
            y = v * np.sin(theta) * np.sin(phi)
            z = v * np.cos(theta)

            PlotItem = gl.GLLinePlotItem(pos=np.array([[x0,y0,z0],[x,y,z]]), color=pg.glColor((255, 255, 255, 255)), width=5, antialias=True)
            self.parent_view.addItem(PlotItem)
            self.items.append(PlotItem)
            x0,y0,z0 = x,y,z
    
    def make_ticks(self):
        thet = np.linspace(self.thetas[0], self.thetas[-1], self.n_ticks)
        ph = np.linspace(self.phis[0], self.phis[-1], self.n_ticks)
        v = self.rho
        d_th = (self.thetas[1] - self.thetas[0])*2
        d_ph = (self.phis[1] - self.phis[0])*2.5
        x0 = v * np.sin(thet[0]) * np.cos(ph[0])
        y0 = v * np.sin(thet[0]) * np.sin(ph[0])
        z0 = v * np.cos(thet[0])
        for j in range(len(ph)):
            theta = thet[0]
            phi = ph[j]

            dx = v * np.sin(theta-d_th) * np.cos(phi)
            dy = v * np.sin(theta-d_th) * np.sin(phi)
            dz = v * np.cos(theta-d_th)

            txt = CustomTextItem(dx,dy,dz,f'{phi/np.pi:.2f}π')
            txt.setGLViewWidget(self.parent_view)
            self.parent_view.addItem(txt)
            self.items.append(txt)

        x0 = v * np.sin(thet[0]) * np.cos(ph[0])
        y0 = v * np.sin(thet[0]) * np.sin(ph[0])
        z0 = v * np.cos(thet[0])
        for i in range(len(thet)):
            theta = thet[i]
            phi = ph[0]

            dx = v * np.sin(theta) * np.cos(phi-d_ph)
            dy = v * np.sin(theta) * np.sin(phi-d_ph)
            dz = v * np.cos(theta)

            txt = CustomTextItem(dx,dy,dz,f'{theta/np.pi:.2f}π')
            txt.setGLViewWidget(self.parent_view)
            self.parent_view.addItem(txt)
            self.items.append(txt)

class MagnetMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_magnet_vector_gui.ui')

        # Load it
        super(MagnetMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()


class MagnetSettingsWindow(QtWidgets.QDialog):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_magnet_settings.ui')

        # Load it
        super(MagnetSettingsWindow, self).__init__()

        uic.loadUi(ui_file, self)


class MagnetGui(GUIBase):
    """ Main GUI for the magnet. """

    # declare connectors
    magnetlogic1 = Connector(interface='MagnetLogic')
    savelogic = Connector(interface='SaveLogic')

    # status var
    _alignment_2d_cb_label = StatusVar('alignment_2d_cb_GraphicsView_text', 'Fluorescence')
    _alignment_2d_cb_units = StatusVar('alignment_2d_cb_GraphicsView_units', 'counts/s')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._continue_2d_fluorescence_alignment = False

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._magnet_logic = self.magnetlogic1()
        self._save_logic = self.savelogic()

        self._mw = MagnetMainWindow()
        self._GLView = None
        self._3D_axis = None
        self._2d_alignment_ImageItem = None
        self.new_vector_item = None
        self.opt_vector_item = None

        # create all the needed control elements. They will manage the
        # connection with each other themselves. Note some buttons are also
        # connected within these functions because they have to be placed at
        # first in the GUI Layout, otherwise the signals will not react.
        self._create_axis_pos_disp()
        self._create_move_rel_control()
        self._create_move_abs_control()
        self.last_pos = {'rho':0.0}

        self._create_meas_type_RadioButtons()

        # Configuring the dock widgets
        # Use the class 'MagnetMainWindow' to create the GUI window

        axis_list = list(self._magnet_logic.get_hardware_constraints())
        self._mw.align_2d_axis0_name_ComboBox.clear()
        self._mw.align_2d_axis0_name_ComboBox.addItems(['theta'])
        self._mw.align_2d_axis0_name_ComboBox.setCurrentIndex(0)

        self._mw.align_2d_axis1_name_ComboBox.clear()
        self._mw.align_2d_axis1_name_ComboBox.addItems(['phi'])
        self._mw.align_2d_axis1_name_ComboBox.setCurrentIndex(0)

        self._mw.align_2d_axis2_name_ComboBox.clear()
        self._mw.align_2d_axis2_name_ComboBox.addItems(['rho'])
        self._mw.align_2d_axis2_name_ComboBox.setCurrentIndex(0)

        # Setup dock widgets
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)
       # self._mw.tabifyDockWidget(self._mw.curr_pos_DockWidget, self._mw.move_rel_DockWidget)
       # self._mw.tabifyDockWidget(self._mw.curr_pos_DockWidget, self._mw.move_abs_DockWidget)
       # self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1), self._mw.curr_pos_DockWidget)
       # self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(2), self._mw.move_rel_DockWidget)
       # self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(3), self._mw.move_abs_DockWidget)
        self.set_default_view_main_window()
        raw_data_2d = self._magnet_logic.get_2d_data_matrix()

        # After a movement command, the device should not block the program, at
        # least on the hardware level. That meant that the dll (or whatever
        # protocol is used to access the hardware) can receive a command during
        # an ongoing action. That is of course controller specific, but in
        # general should it should be possible (unless the controller was
        # written by someone who has no clue what he is doing). Eventually with
        # that you have the possibility of stopping an ongoing movement!
        self._interactive_mode = True
        self._activate_magnet_settings()

        # connect the actions of the toolbar:
        self._mw.magnet_settings_Action.triggered.connect(self.open_magnet_settings)
        self._mw.default_view_Action.triggered.connect(self.set_default_view_main_window)

        curr_pos = self.update_pos()
        # update the values also of the absolute movement display:
        for axis_label in curr_pos:
            if axis_label in ['x','y','z']:
                continue
            dspinbox_move_abs_ref = self.get_ref_move_abs_ScienDSpinBox(axis_label)
            dspinbox_move_abs_ref.setValue(curr_pos[axis_label])
            slider_move_abs_ref = self.get_ref_move_abs_Slider(axis_label)
            slider_move_abs_ref.setValue(curr_pos[axis_label])

        self._magnet_logic.sigPosChanged.connect(self.update_pos)
        self._mw.fitFluorescence_pushButton.clicked.connect(self._magnet_logic._set_optimized_xy_from_fit)
        self._magnet_logic.sigFitFinished.connect(self.give_pos_to_update_GLView_opt_vector)

        # Connect alignment GUI elements:

        self._magnet_logic.sigMeasurementFinished.connect(self._change_display_to_stop_2d_alignment)

        self._mw.align_2d_axis0_name_ComboBox.currentIndexChanged.connect(self._update_limits_axis0)
        self._mw.align_2d_axis1_name_ComboBox.currentIndexChanged.connect(self._update_limits_axis1)

        self._mw.alignment_2d_cb_min_centiles_DSpinBox.valueChanged.connect(self._update_2d_graph_data)
        self._mw.alignment_2d_cb_max_centiles_DSpinBox.valueChanged.connect(self._update_2d_graph_data)
        self._mw.alignment_2d_cb_low_centiles_DSpinBox.valueChanged.connect(self._update_2d_graph_data)
        self._mw.alignment_2d_cb_high_centiles_DSpinBox.valueChanged.connect(self._update_2d_graph_data)

        self._update_limits_axis0()
        self._update_limits_axis1()

        # self._2d_alignment_ImageItem = ScanImageItem(image=self._magnet_logic.get_2d_data_matrix())
        # self._mw.alignment_2d_GraphicsView.addItem(self._2d_alignment_ImageItem)
        # axis0, axis1 = self._magnet_logic.get_2d_axis_arrays()
        # step0 = axis0[1] - axis0[0]
        # step1 = axis1[1] - axis1[0]
        # self._2d_alignment_ImageItem.set_image_extent([[axis0[0]-step0/2, axis0[-1]+step0/2],
        #                                                [axis1[0]-step1/2, axis1[-1]+step1/2]])

        layout = QtWidgets.QGridLayout()
        self._GLView = gl.GLViewWidget()
        layout.addWidget(self._GLView)
        self._mw.frame.setLayout(layout)
        
        my_colors = ColorScaleViridis()
        # self._2d_alignment_ImageItem.setLookupTable(my_colors.lut)

        # Set initial position for the crosshair, default is current magnet position
        # current_position = self._magnet_logic.get_pos()
        # _,current_2d_array = self._magnet_logic.get_2d_axis_arrays()
        # ini_pos_x_crosshair = current_position[self._magnet_logic.align_2d_axis0_name]
        # ini_pos_y_crosshair = current_position[self._magnet_logic.align_2d_axis1_name]

        # ini_width_crosshair = [
        #     (current_2d_array[0][-1] - current_2d_array[0][0]) / len(current_2d_array[0]),
        #     (current_2d_array[1][-1] - current_2d_array[1][0]) / len(current_2d_array[0])]
        # self._mw.alignment_2d_GraphicsView.toggle_crosshair(True, movable=True)
        # self._mw.alignment_2d_GraphicsView.set_crosshair_pos((ini_pos_x_crosshair, ini_pos_y_crosshair))
        # self._mw.alignment_2d_GraphicsView.set_crosshair_size(ini_width_crosshair)
        # self._mw.alignment_2d_GraphicsView.sigCrosshairDraggedPosChanged.connect(
        #     self.update_from_roi_magnet)

        # Configuration of Colorbar:
        self._2d_alignment_cb = ColorBar(my_colors.cmap_normed, 100, 0, 100000)

        self._mw.alignment_2d_cb_GraphicsView.addItem(self._2d_alignment_cb)
        self._mw.alignment_2d_cb_GraphicsView.hideAxis('bottom')
        self._mw.alignment_2d_cb_GraphicsView.hideAxis('left')

        self._mw.alignment_2d_cb_GraphicsView.addItem(self._2d_alignment_cb)

        self._mw.alignment_2d_cb_GraphicsView.setLabel('right',
            self._alignment_2d_cb_label,
            units=self._alignment_2d_cb_units)

        #FIXME: that should be actually set in the logic
        if 'measurement_type' in self._statusVariables:
            self.measurement_type = self._statusVariables['measurement_type']
        else:
            self.measurement_type = 'fluorescence'

        self._magnet_logic.sig2DAxisChanged.connect(self._update_2d_graph_axis)
        self._magnet_logic.sig2DMatrixChanged.connect(self._update_2d_graph_data)

        # Connect the buttons and inputs for the odmr colorbar
        self._mw.alignment_2d_manual_RadioButton.clicked.connect(self._update_2d_graph_data)
        self._mw.alignment_2d_centiles_RadioButton.clicked.connect(self._update_2d_graph_data)

        self._update_2d_graph_data()
        self._update_2d_graph_cb()

        self._3D_axis.del_items()
        self._2d_alignment_ImageItem.del_items()
        self._init_GLView()
        self._mw.alignment_2d_cb_high_centiles_DSpinBox.setValue(100)


        # Add save file tag input box
        self._mw.alignment_2d_nametag_LineEdit = QtWidgets.QLineEdit(self._mw)
        self._mw.alignment_2d_nametag_LineEdit.setMaximumWidth(200)
        self._mw.alignment_2d_nametag_LineEdit.setToolTip('Enter a nametag which will be\n'
                                                          'added to the filename.')

        self._mw.save_ToolBar.addWidget(self._mw.alignment_2d_nametag_LineEdit)
        self._mw.save_Action.triggered.connect(self.save_2d_plots_and_data)

        self._mw.run_stop_2d_alignment_Action.triggered.connect(self.run_stop_2d_alignment)
        self._mw.continue_2d_alignment_Action.triggered.connect(self.continue_stop_2d_alignment)

        # connect the signals:
        # --------------------

        # relative movement:

        constraints=self._magnet_logic.get_hardware_constraints()

        for axis_label in list(constraints):
            if axis_label in ['x','y','z']:
                continue
            self.get_ref_move_rel_ScienDSpinBox(axis_label).setValue(self._magnet_logic.move_rel_dict[axis_label])
            self.get_ref_move_rel_ScienDSpinBox(axis_label).editingFinished.connect(self.move_rel_para_changed)

            dspinbox_move_abs_ref = self.get_ref_move_abs_ScienDSpinBox(axis_label)
            dspinbox_move_abs_ref.editingFinished.connect(self.give_pos_to_update_GLView_new_vector)
            slider_move_abs_ref = self.get_ref_move_abs_Slider(axis_label)
            slider_move_abs_ref.sliderReleased.connect(self.give_pos_to_update_GLView_new_vector)

        # General 2d alignment:
        # index = self._mw.align_2d_axis0_name_ComboBox.findText(self._magnet_logic.align_2d_axis0_name)
        # self._mw.align_2d_axis0_name_ComboBox.setCurrentIndex(index)
        # self._mw.align_2d_axis0_name_ComboBox.currentIndexChanged.connect(self.align_2d_axis0_name_changed)
        self._mw.align_2d_axis0_range_DSpinBox.setValue(self._magnet_logic.align_2d_axis0_range)
        self._mw.align_2d_axis0_range_DSpinBox.editingFinished.connect(self.align_2d_axis0_range_changed)
        self._mw.align_2d_axis2_range_DSpinBox.editingFinished.connect(self.align_2d_axis2_range_changed)
        self._mw.align_2d_axis0_range_DSpinBox.editingFinished.connect(self.update_roi_from_range)
        self._mw.align_2d_axis0_step_DSpinBox.setValue(self._magnet_logic.align_2d_axis0_step)
        self._mw.align_2d_axis0_step_DSpinBox.editingFinished.connect(self.align_2d_axis0_step_changed)

        # index = self._mw.align_2d_axis1_name_ComboBox.findText(self._magnet_logic.align_2d_axis1_name)
        # self._mw.align_2d_axis1_name_ComboBox.setCurrentIndex(index)
        # self._mw.align_2d_axis1_name_ComboBox.currentIndexChanged.connect(self.align_2d_axis1_name_changed)
        self._mw.align_2d_axis1_range_DSpinBox.setValue(self._magnet_logic.align_2d_axis1_range)
        self._mw.align_2d_axis1_range_DSpinBox.editingFinished.connect(self.align_2d_axis1_range_changed)
        self._mw.align_2d_axis1_range_DSpinBox.editingFinished.connect(self.update_roi_from_range)
        self._mw.align_2d_axis1_step_DSpinBox.setValue(self._magnet_logic.align_2d_axis1_step)
        self._mw.align_2d_axis1_step_DSpinBox.editingFinished.connect(self.align_2d_axis1_step_changed)

        # index = self._mw.align_2d_axis2_name_ComboBox.findText(self._magnet_logic.align_2d_axis2_name)
        # self._mw.align_2d_axis2_name_ComboBox.setCurrentIndex(index)
        # self._mw.align_2d_axis2_name_ComboBox.currentIndexChanged.connect(self.align_2d_axis2_name_changed)
        self._mw.align_2d_axis2_range_DSpinBox.setValue(self._magnet_logic.align_2d_axis2_range)
        self._mw.align_2d_axis2_range_DSpinBox.editingFinished.connect(self.align_2d_axis2_range_changed)
        self._mw.align_2d_axis2_range_DSpinBox.editingFinished.connect(self.update_roi_from_range)
        self._mw.align_2d_axis2_step_DSpinBox.setValue(self._magnet_logic.align_2d_axis2_step)
        # self._mw.align_2d_axis2_step_DSpinBox.editingFinished.connect(self.align_2d_axis2_step_changed)

        # for fluorescence alignment:
        self._mw.align_2d_fluorescence_optimize_freq_SpinBox.setValue(self._magnet_logic.get_optimize_pos_freq())
        self._mw.align_2d_fluorescence_integrationtime_DSpinBox.setValue(self._magnet_logic.get_fluorescence_integration_time())
        self._mw.align_2d_fluorescence_optimize_freq_SpinBox.editingFinished.connect(self.optimize_pos_freq_changed)
        self._mw.align_2d_fluorescence_integrationtime_DSpinBox.editingFinished.connect(self.fluorescence_integration_time_changed)

        # process signals from magnet_logic

        self._magnet_logic.sigMoveRelChanged.connect(self.update_move_rel_para)

        self._magnet_logic.sig2DAxis0NameChanged.connect(self.update_align_2d_axis0_name)
        self._magnet_logic.sig2DAxis0RangeChanged.connect(self.update_align_2d_axis0_range)
        self._magnet_logic.sig2DAxis0StepChanged.connect(self.update_align_2d_axis0_step)

        self._magnet_logic.sig2DAxis1NameChanged.connect(self.update_align_2d_axis1_name)
        self._magnet_logic.sig2DAxis1RangeChanged.connect(self.update_align_2d_axis1_range)
        self._magnet_logic.sig2DAxis1StepChanged.connect(self.update_align_2d_axis1_step)

        self._magnet_logic.sigOptPosFreqChanged.connect(self.update_optimize_pos_freq)
        self._magnet_logic.sigFluoIntTimeChanged.connect(self.update_fluorescence_integration_time)

        self.restoreWindowPos(self._mw)
        return 0

    def _activate_magnet_settings(self):
        """ Activate magnet settings.
        """
        self._ms = MagnetSettingsWindow()
        # default config is normal_mode
        self._ms.normal_mode_checkBox.setChecked(True)
        self._ms.z_mode_checkBox.setChecked(False)
        # make sure the buttons are exclusively checked
        self._ms.normal_mode_checkBox.stateChanged.connect(self.trig_wrapper_normal_mode)
        self._ms.z_mode_checkBox.stateChanged.connect(self.trig_wrapper_z_mode)

        #self._ms.z_mode_checkBox.stateChanged.connect(self._ms.normal_mode_checkBox.toggle)
        self._ms.accepted.connect(self.update_magnet_settings)
        self._ms.rejected.connect(self.keep_former_magnet_settings)
        self._ms.ButtonBox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.update_magnet_settings)

        self.keep_former_magnet_settings()
        return

    def trig_wrapper_normal_mode(self):
        if not self._ms.normal_mode_checkBox.isChecked() and not self._ms.z_mode_checkBox.isChecked():
            self._ms.z_mode_checkBox.toggle()
        elif self._ms.normal_mode_checkBox.isChecked() and self._ms.z_mode_checkBox.isChecked():
            self._ms.z_mode_checkBox.toggle()

    def trig_wrapper_z_mode(self):
        if not self._ms.normal_mode_checkBox.isChecked() and not self._ms.z_mode_checkBox.isChecked():
            self._ms.normal_mode_checkBox.toggle()
        elif self._ms.normal_mode_checkBox.isChecked() and self._ms.z_mode_checkBox.isChecked():
            self._ms.normal_mode_checkBox.toggle()

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._statusVariables['measurement_type'] = self.measurement_type
        self._alignment_2d_cb_label =  self._mw.alignment_2d_cb_GraphicsView.plotItem.axes['right']['item'].labelText
        self._alignment_2d_cb_units = self._mw.alignment_2d_cb_GraphicsView.plotItem.axes['right']['item'].labelUnits
        self.saveWindowGeometry(self._mw)
        self._mw.close()

    def show(self):
        """Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def set_default_view_main_window(self):
        """ Establish the default dock Widget configuration. """

        # connect all widgets to the main Window
        self._mw.curr_pos_DockWidget.setFloating(False)
        self._mw.move_rel_DockWidget.setFloating(False)
        self._mw.move_abs_DockWidget.setFloating(False)
        self._mw.alignment_DockWidget.setFloating(False)

        # QtCore.Qt.LeftDockWidgetArea        0x1
        # QtCore.Qt.RightDockWidgetArea       0x2
        # QtCore.Qt.TopDockWidgetArea         0x4
        # QtCore.Qt.BottomDockWidgetArea      0x8
        # QtCore.Qt.AllDockWidgetAreas        DockWidgetArea_Mask
        # QtCore.Qt.NoDockWidgetArea          0

        # align the widget
        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1),
                               self._mw.curr_pos_DockWidget)
        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1),
                               self._mw.move_rel_DockWidget)
        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1),
                               self._mw.move_abs_DockWidget)

        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(2),
                               self._mw.alignment_DockWidget)

    def open_magnet_settings(self):
        """ This method opens the settings menu. """
        self._ms.exec_()

    def update_magnet_settings(self):
        """ Apply the set configuration in the Settings Window. """

        if self._ms.interactive_mode_CheckBox.isChecked():
            self._interactive_mode = True
        else:
            self._interactive_mode = False
        if self._ms.z_mode_checkBox.isChecked() and not self._ms.normal_mode_checkBox.isChecked():
            self.log.warning("dum dum")

        if self._ms.normal_mode_checkBox.isChecked() and not self._ms.z_mode_checkBox.isChecked():
            self.log.warning("dam dam")

        if self._ms.interactive_mode_CheckBox.isChecked():
            self._interactive_mode = True
        else:
            self._interactive_mode = False
        if self._ms.z_mode_checkBox.isChecked():
            self._z_mode = True
            self._magnet_logic._magnet_device.mode = 'z_mode'
        else:
            self._z_mode = False
            self._magnet_logic._magnet_device.mode = 'normal_mode'

        if self._ms.normal_mode_checkBox.isChecked():
            self._normal_mode = True
            self._magnet_logic._magnet_device.mode = 'normal_mode'
        else:
            self._normal_mode = False
            self._magnet_logic._magnet_device.mode = 'z_mode'

    def keep_former_magnet_settings(self):

        self._ms.interactive_mode_CheckBox.setChecked(self._interactive_mode)

    def _create_meas_type_RadioButtons(self):
        """ Create the measurement Buttons for the desired measurements:

        @return:
        """

        self._mw.alignment_2d_ButtonGroup = QtWidgets.QButtonGroup(self._mw)

        self._mw.meas_type_fluorescence_RadioButton = QtWidgets.QRadioButton(parent=self._mw)
        self._mw.alignment_2d_ButtonGroup.addButton(self._mw.meas_type_fluorescence_RadioButton)
        self._mw.alignment_2d_ToolBar.addWidget(self._mw.meas_type_fluorescence_RadioButton)
        self._mw.meas_type_fluorescence_RadioButton.setText('Fluorescence')

        self._mw.meas_type_fluorescence_RadioButton.setChecked(True)

    def _create_axis_pos_disp(self):
        """ Create the axis position display.

        The generic variable name for a created QLable is:
            curr_pos_axis{0}_Label
        The generic variable name for a created ScienDSpinBox is:
            curr_pos_axis{0}_ScienDSpinBox
        where in {0} the name of the axis will be inserted.

        DO NOT CALL THESE VARIABLES DIRECTLY! USE THE DEDICATED METHOD INSTEAD!
        Use the method get_ref_curr_pos_ScienDSpinBox with the appropriated
        label, otherwise you will break the generality.
        """

        constraints = self._magnet_logic.get_hardware_constraints()
        # set the parameters in the curr_pos_DockWidget:
        for index, axis_label in enumerate(constraints):

            # Set the QLabel according to the grid
            # this is the name prototype for the label of current position display
            label_var_name = 'curr_pos_axis{0}_Label'.format(axis_label)
            setattr(self._mw, label_var_name, QtWidgets.QLabel(self._mw.curr_pos_DockWidgetContents))
            label_var = getattr(self._mw, label_var_name)
            label_var.setObjectName(label_var_name)
            label_var.setText('{0}'.format(axis_label))
            self._mw.curr_pos_GridLayout.addWidget(label_var, index, 0, 1, 1)

            # Set the ScienDSpinBox according to the grid
            # this is the name prototype for the current position display
            dspinbox_ref_name = 'curr_pos_axis{0}_ScienDSpinBox'.format(axis_label)

            setattr(self._mw, dspinbox_ref_name, ScienDSpinBox(parent=self._mw.curr_pos_DockWidgetContents))
            dspinbox_ref = getattr(self._mw, dspinbox_ref_name)
            dspinbox_ref.setObjectName(dspinbox_ref_name)
            dspinbox_ref.setReadOnly(True)
            dspinbox_ref.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            dspinbox_ref.setMaximum(np.inf)
            dspinbox_ref.setMinimum(-np.inf)

            # dspinbox_ref.setOpts(minStep=constraints[axis_label]['pos_step'])
            dspinbox_ref.setSingleStep(0.001, dynamic_stepping=False)
            dspinbox_ref.setSuffix(constraints[axis_label]['unit'])

            self._mw.curr_pos_GridLayout.addWidget(dspinbox_ref, index, 1, 1, 1)

        extension = len(constraints)
        self._mw.curr_pos_GridLayout.addWidget(self._mw.curr_pos_get_pos_PushButton, 0, 2, extension, 1)
        self._mw.curr_pos_GridLayout.addWidget(self._mw.curr_pos_stop_PushButton, 0, 3, extension, 1)
        self._mw.curr_pos_get_pos_PushButton.clicked.connect(self.update_pos)
        self._mw.curr_pos_stop_PushButton.clicked.connect(self.stop_movement)

    def _create_move_rel_control(self):
        """ Create all the gui elements to control a relative movement.

        The generic variable name for a created QLable is:
            move_rel_axis_{0}_Label
        The generic variable name for a created ScienDSpinBox is:
            move_rel_axis_{0}_ScienDSpinBox
        The generic variable name for a created QPushButton in negative dir is:
            move_rel_axis_{0}_m_PushButton
        The generic variable name for a created QPushButton in positive dir is:
            move_rel_axis_{0}_p_PushButton

        DO NOT CALL THESE VARIABLES DIRECTLY! USE THE DEDICATED METHOD INSTEAD!
        Use the method get_ref_move_rel_ScienDSpinBox with the appropriated
        label, otherwise you will break the generality.
        """

        constraints = self._magnet_logic.get_hardware_constraints()

        # set the axis_labels in the curr_pos_DockWidget:
        for index, axis_label in enumerate(constraints):
            if axis_label in ['x','y','z']:
                continue
            index-=3
            label_var_name = 'move_rel_axis_{0}_Label'.format(axis_label)
            setattr(self._mw, label_var_name, QtWidgets.QLabel(self._mw.move_rel_DockWidgetContents))
            label_var = getattr(self._mw, label_var_name) # get the reference
            label_var.setObjectName(label_var_name) # set axis_label for the label
            label_var.setText('{0}'.format(axis_label))
            # add the label to the grid:
            self._mw.move_rel_GridLayout.addWidget(label_var, index, 0, 1, 1)

            # Set the ScienDSpinBox according to the grid
            # this is the name prototype for the relative movement display
            dspinbox_ref_name = 'move_rel_axis_{0}_ScienDSpinBox'.format(axis_label)
            setattr(self._mw, dspinbox_ref_name, ScienDSpinBox(parent=self._mw.move_rel_DockWidgetContents))
            dspinbox_ref = getattr(self._mw, dspinbox_ref_name)
            dspinbox_ref.setObjectName(dspinbox_ref_name)
#            dspinbox_ref.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)

            dspinbox_ref.setMaximum(constraints[axis_label]['pos_max'])
            dspinbox_ref.setMinimum(constraints[axis_label]['pos_min'])

            # dspinbox_ref.setOpts(minStep=constraints[axis_label]['pos_step'])
            # dspinbox_ref.setSingleStep(0.001, dynamic_stepping=False)
            dspinbox_ref.setSuffix(constraints[axis_label]['unit'])

            self._mw.move_rel_GridLayout.addWidget(dspinbox_ref, index, 1, 1, 1)

            # this is the name prototype for the relative movement minus button
            func_name = 'move_rel_axis_{0}_m'.format(axis_label)
            # create a method and assign it as attribute:
            setattr(self, func_name, self._function_builder_move_rel(func_name,axis_label,-1) )
            move_rel_m_ref =  getattr(self, func_name)  # get the reference

            # the change of the PushButton is connected to the previous method.
            button_var_name = 'move_rel_axis_{0}_m_PushButton'.format(axis_label)
            setattr(self._mw, button_var_name, QtWidgets.QPushButton(self._mw.move_rel_DockWidgetContents))
            button_var = getattr(self._mw, button_var_name)
            button_var.setObjectName(button_var_name)
            button_var.setText('-')
            button_var.clicked.connect(move_rel_m_ref, type=QtCore.Qt.QueuedConnection)
            self._mw.move_rel_GridLayout.addWidget(button_var, index, 2, 1, 1)

            # this is the name prototype for the relative movement plus button
            func_name = 'move_rel_axis_{0}_p'.format(axis_label)
            setattr(self, func_name, self._function_builder_move_rel(func_name,axis_label,1) )
            move_rel_p_ref = getattr(self, func_name)

            # the change of the PushButton is connected to the previous method.
            button_var_name = 'move_rel_axis_{0}_p_PushButton'.format(axis_label)
            setattr(self._mw, button_var_name, QtWidgets.QPushButton(self._mw.move_rel_DockWidgetContents))
            button_var = getattr(self._mw, button_var_name)
            button_var.setObjectName(button_var_name)
            button_var.setText('+')
            button_var.clicked.connect(move_rel_p_ref, type=QtCore.Qt.QueuedConnection)
            self._mw.move_rel_GridLayout.addWidget(button_var, index, 3, 1, 1)

    def _create_move_abs_control(self):
        """ Create all the GUI elements to control a relative movement.

        The generic variable name for a created QLable is:
            move_abs_axis_{0}_Label
        The generic variable name for a created QLable is:
            move_abs_axis_{0}_Slider
        The generic variable name for a created ScienDSpinBox is:
            move_abs_axis_{0}_ScienDSpinBox
        The generic variable name for a created QPushButton for move is:
            move_abs_PushButton

        These methods should not be called:
        The generic variable name for a update method for the ScienDSpinBox:
            _update_move_abs_{0}_dspinbox
        The generic variable name for a update method for the QSlider:
            _update_move_abs_{0}_slider

        DO NOT CALL THESE VARIABLES DIRECTLY! USE THE DEDICATED METHOD INSTEAD!
        Use the method get_ref_move_abs_ScienDSpinBox with the appropriated
        label, otherwise you will break the generality.
        """

        constraints = self._magnet_logic.get_hardware_constraints()

        for index, axis_label in enumerate(constraints):
            if axis_label in ['x','y','z']:
                continue
            index-=3

            label_var_name = 'move_abs_axis_{0}_Label'.format(axis_label)
            setattr(self._mw, label_var_name, QtWidgets.QLabel(self._mw.move_abs_DockWidgetContents))
            label_var = getattr(self._mw, label_var_name) # get the reference
            # set axis_label for the label:
            label_var.setObjectName(label_var_name)
            label_var.setText(axis_label)

            # make the steps of the splider as a multiple of 10
            # smallest_step_slider = 10**int(np.log10(constraints[axis_label]['pos_step']) -1)
            smallest_step_slider = constraints[axis_label]['pos_step']

            # add the label to the grid:
            self._mw.move_abs_GridLayout.addWidget(label_var, index, 0, 1, 1)

            # Set the ScienDSpinBox according to the grid
            # this is the name prototype for the relative movement display
            slider_obj_name = 'move_abs_axis_{0}_Slider'.format(axis_label)
            setattr(self._mw, slider_obj_name, QtWidgets.QSlider(self._mw.move_abs_DockWidgetContents))
            slider_obj = getattr(self._mw, slider_obj_name)
            slider_obj.setObjectName(slider_obj_name)
            slider_obj.setOrientation(QtCore.Qt.Horizontal)
#            dspinbox_ref.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)

            max_val = abs(constraints[axis_label]['pos_max'] - constraints[axis_label]['pos_min'])

            # set the step size of the slider to a fixed resolution, that
            # prevents really ugly rounding error behaviours in display.
            # Set precision to nanometer scale, which is actually never reached.
            max_steps = int(max_val/smallest_step_slider)

            slider_obj.setMaximum(max_steps)
            slider_obj.setMinimum(0)
            #TODO: set the decimals also from the constraints!
#            slider_obj.setDecimals(3)
            slider_obj.setSingleStep(1)
            # slider_obj.setEnabled(False)

            self._mw.move_abs_GridLayout.addWidget(slider_obj, index, 1, 1, 1)

            # Set the ScienDSpinBox according to the grid
            # this is the name prototype for the relative movement display
            dspinbox_ref_name = 'move_abs_axis_{0}_ScienDSpinBox'.format(axis_label)
            setattr(self._mw, dspinbox_ref_name, ScienDSpinBox(parent=self._mw.move_abs_DockWidgetContents))
            dspinbox_ref = getattr(self._mw, dspinbox_ref_name)
            dspinbox_ref.setObjectName(dspinbox_ref_name)
#            dspinbox_ref.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)

            dspinbox_ref.setMaximum(constraints[axis_label]['pos_max'])
            dspinbox_ref.setMinimum(constraints[axis_label]['pos_min'])

            # dspinbox_ref.setOpts(minStep=constraints[axis_label]['pos_step'])
            # dspinbox_ref.setSingleStep(0.001, dynamic_stepping=False)
            dspinbox_ref.setSuffix(constraints[axis_label]['unit'])

            # set the horizontal size to 100 pixel:
            dspinbox_ref.setMinimumSize(QtCore.QSize(80, 16777215))

            self._mw.move_abs_GridLayout.addWidget(dspinbox_ref, index, 2, 1, 1)

            # build a function to change the dspinbox value and connect a
            # slidermove event to it:
            func_name = '_update_move_abs_{0}_dspinbox'.format(axis_label)
            setattr(self, func_name, self._function_builder_update_viewbox(func_name, axis_label, dspinbox_ref))
            update_func_dspinbox_ref = getattr(self, func_name)
            slider_obj.valueChanged.connect(update_func_dspinbox_ref)

            # build a function to change the slider value and connect a
            # spinbox value change event to it:
            func_name = '_update_move_abs_{0}_slider'.format(axis_label)
            setattr(self, func_name, self._function_builder_update_slider(func_name, axis_label, slider_obj))
            update_func_slider_ref = getattr(self, func_name)
            # dspinbox_ref.valueChanged.connect(update_func_slider_ref)

            # the editingFinished idea has to be implemented properly at first:
            dspinbox_ref.editingFinished.connect(update_func_slider_ref)

        extension = len(constraints)-3
        self._mw.move_abs_GridLayout.addWidget(self._mw.move_abs_PushButton, 0, 3, extension, 1)
        self._mw.move_abs_PushButton.clicked.connect(self.move_abs)
        self._mw.move_abs_PushButton.clicked.connect(self.update_roi_from_abs_movement)

    def _function_builder_move_rel(self, func_name, axis_label, direction):
        """ Create a function/method, which gets executed for pressing move_rel.

        @param str func_name: name how the function should be called.
        @param str axis_label: label of the axis you want to create a control
                               function for.
        @param int direction: either 1 or -1 depending on the relative movement.
        @return: function with name func_name

        A routine to construct a method on the fly and attach it as attribute
        to the object, so that it can be used or so that other signals can be
        connected to it. That means the return value is already fixed for a
        function name.
        """

        def func_dummy_name():
            self.move_rel(axis_label, direction)

        func_dummy_name.__name__ = func_name
        return func_dummy_name

        # create the signals for the push buttons and connect them to the move
        # rel method in the Logic

    def _function_builder_update_viewbox(self, func_name, axis_label,
                                         ref_dspinbox):
        """ Create a function/method, which gets executed for pressing move_rel.

        @param str func_name: name how the function should be called.
        @param str axis_label: label of the axis you want to create a control
                               function for.
        @param object ref_dspinbox: a reference to the dspinbox object, which
                                    will actually apply the changed within the
                                    created method.

        @return: function with name func_name

        A routine to construct a method on the fly and attach it as attribute
        to the object, so that it can be used or so that other signals can be
        connected to it. The connection of a signal to this method must appear
        outside of the present function.
        """

        def func_dummy_name(slider_val):
            """
            @param int slider_val: The current value of the slider, will be an
                                   integer value between
                                       [0,(pos_max - pos_min)/pos_step]
                                   of the corresponding axis label.
                                   Now convert this value back to a viewbox
                                   value like:
                                       pos_min + slider_step*pos_step
            """

            constraints = self._magnet_logic.get_hardware_constraints()
            # set the resolution of the slider to nanometer precision, that is
            # better for the display behaviour. In the end, that will just make
            # everything smoother but not actually affect the displayed number:

            # max_step_slider = 10**int(np.log10(constraints[axis_label]['pos_step']) -1)
            max_step_slider = constraints[axis_label]['pos_step']

            actual_pos = (constraints[axis_label]['pos_min'] + slider_val * max_step_slider)
            ref_dspinbox.setValue(actual_pos)

        func_dummy_name.__name__ = func_name
        return func_dummy_name

    def _function_builder_update_slider(self, func_name, axis_label, ref_slider):
        """ Create a function/method, which gets executed for pressing move_rel.

        Create a function/method, which gets executed for pressing move_rel.

        @param str func_name: name how the function should be called.
        @param str axis_label: label of the axis you want to create a control
                               function for.
        @param object ref_slider: a reference to the slider object, which
                                  will actually apply the changed within the
                                  created method.

        @return: function with name func_name

        A routine to construct a method on the fly and attach it as attribute
        to the object, so that it can be used or so that other signals can be
        connected to it. The connection of a signal to this method must appear
        outside of the present function.
        """

        def func_dummy_name():
            """
            @param int slider_step: The current value of the slider, will be an
                                    integer value between
                                        [0,(pos_max - pos_min)/pos_step]
                                    of the corresponding axis label.
                                    Now convert this value back to a viewbox
                                    value like:
                                        pos_min + slider_step*pos_step
            """

            dspinbox_obj = self.get_ref_move_abs_ScienDSpinBox(axis_label)
            viewbox_val = dspinbox_obj.value()

            constraints = self._magnet_logic.get_hardware_constraints()
            # set the resolution of the slider to nanometer precision, that is
            # better for the display behaviour. In the end, that will just make
            # everything smoother but not actually affect the displayed number:

            # max_step_slider = 10**int(np.log10(constraints[axis_label]['pos_step']) -1)
            max_step_slider = constraints[axis_label]['pos_step']

            slider_val = abs(viewbox_val - constraints[axis_label]['pos_min'])/max_step_slider
            ref_slider.setValue(slider_val)

        func_dummy_name.__name__ = func_name
        return func_dummy_name

        # create the signals for the push buttons and connect them to the move
        # rel method in the Logic

    def move_rel(self, axis_label, direction):
        """ Move relative by the axis with given label an direction.

        @param str axis_label: tells which axis should move.
        @param int direction: either 1 or -1 depending on the relative movement.

        That method get called from methods, which are created on the fly at
        runtime during the activation of that module (basically from the
        methods with the generic name move_rel_axis_{0}_p or
        move_rel_axis_{0}_m with the appropriate label).
        """
        #constraints = self._magnet_logic.get_hardware_constraints()
        dspinbox = self.get_ref_move_rel_ScienDSpinBox(axis_label)

        movement = dspinbox.value() * direction

        self._magnet_logic.move_rel({axis_label: movement})
        if self._interactive_mode:
            self.update_pos()
        return axis_label, direction

    def move_abs(self, param_dict=None):
        """ Perform an absolute movement.

        @param param_dict: with {<axis_label>:<position>}, can of course
                           contain many entries of the same kind.

        Basically all the axis can be controlled at the same time.
        """

        if (param_dict is not None) and (type(param_dict) is not bool):
            self._magnet_logic.move_abs(param_dict)
        else:
            constraints = self._magnet_logic.get_hardware_constraints()

            # create the move_abs dict
            move_abs = {}
            for label in constraints:
                if label in ['x','y','z']:
                    continue
                move_abs[label] = self.get_ref_move_abs_ScienDSpinBox(label).value()

            self._magnet_logic.move_abs(move_abs)

        if self._interactive_mode:
            self.update_pos()
            return param_dict

    def get_ref_curr_pos_ScienDSpinBox(self, label):
        """ Get the reference to the double spin box for the passed label. """

        dspinbox_name = 'curr_pos_axis{0}_ScienDSpinBox'.format(label)
        dspinbox_ref = getattr(self._mw, dspinbox_name)
        return dspinbox_ref

    def get_ref_move_rel_ScienDSpinBox(self, label):
        """ Get the reference to the double spin box for the passed label. """

        dspinbox_name = 'move_rel_axis_{0}_ScienDSpinBox'.format(label)
        dspinbox_ref = getattr(self._mw, dspinbox_name)
        return dspinbox_ref

    def get_ref_move_abs_ScienDSpinBox(self, label):
        """ Get the reference to the double spin box for the passed label. """

        dspinbox_name = 'move_abs_axis_{0}_ScienDSpinBox'.format(label)
        dspinbox_ref = getattr(self._mw, dspinbox_name)
        return dspinbox_ref

    def get_ref_move_abs_Slider(self, label):
        """ Get the reference to the slider for the passed label. """

        slider_name = 'move_abs_axis_{0}_Slider'.format(label)
        slider_ref = getattr(self._mw, slider_name)
        return slider_ref

    def move_rel_para_changed(self):
        """ Pass the current GUI value to the logic

        @return dict: Passed move relative parameter
        """
        return_dict = dict()
        axes = list(self._magnet_logic.get_hardware_constraints())
        for axis_label in axes:
            if axis_label in ['x','y','z']:
                continue
            dspinbox = self.get_ref_move_rel_ScienDSpinBox(axis_label)
            return_dict[axis_label]=dspinbox.value()
        self._magnet_logic.set_move_rel_para(return_dict)
        return return_dict

    def align_2d_axis0_name_changed(self):
        """ Pass the current GUI value to the logic

        @return str: Passed axis name
        """
        axisname = self._mw.align_2d_axis0_name_ComboBox.currentText()
        self._magnet_logic.set_align_2d_axis0_name(axisname)
        return axisname

    def align_2d_axis0_range_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed range
        """
        axis_range = self._mw.align_2d_axis0_range_DSpinBox.value()
        self._magnet_logic.set_align_2d_axis0_range(axis_range)
        return axis_range

    def align_2d_axis2_range_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed range
        """
        axis_range = self._mw.align_2d_axis2_range_DSpinBox.value()
        # self._magnet_logic.set_align_2d_axis2_range(axis_range)
        self.make_new_sphere(radius=axis_range)
        return axis_range

    def align_2d_axis0_step_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed step
        """
        step = self._mw.align_2d_axis0_step_DSpinBox.value()
        self._magnet_logic.set_align_2d_axis0_step(step)
        return step


    def align_2d_axis1_name_changed(self):
        """ Pass the current GUI value to the logic

        @return str: Passed axis name
        """
        axisname = self._mw.align_2d_axis1_name_ComboBox.currentText()
        self._magnet_logic.set_align_2d_axis1_name(axisname)
        return axisname

    def align_2d_axis1_range_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed range
        """
        axis_range = self._mw.align_2d_axis1_range_DSpinBox.value()
        self._magnet_logic.set_align_2d_axis1_range(axis_range)
        return axis_range

    def align_2d_axis1_step_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed step size
        """
        step = self._mw.align_2d_axis1_step_DSpinBox.value()
        self._magnet_logic.set_align_2d_axis1_step(step)
        return step


    def optimize_pos_freq_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed frequency
         """
        freq = self._mw.align_2d_fluorescence_optimize_freq_SpinBox.value()
        self._magnet_logic.set_optimize_pos_freq(freq)
        return freq

    def fluorescence_integration_time_changed(self):
        """ Pass the current GUI value to the logic

        @return float: Passed integration time
         """
        time = self._mw.align_2d_fluorescence_integrationtime_DSpinBox.value()
        self._magnet_logic.set_fluorescence_integration_time(time)
        return time

    def stop_movement(self):
        """ Invokes an immediate stop of the hardware.

        MAKE SURE THAT THE HARDWARE CAN BE CALLED DURING AN ACTION!
        If the parameter _interactive_mode is set to False no stop can be done
        since the device would anyway not respond to a method call.
        """

        if self._interactive_mode:
            self._magnet_logic.stop_movement()
        else:
            self.log.warning('Movement cannot be stopped during a movement '
                    'anyway! Set the interactive mode to True in the Magnet '
                    'Settings! Otherwise this method is useless.')

    def update_pos(self, param_list=None):
        """ Update the current position.

        @param list param_list: optional, if specific positions needed to be
                                updated.

        If no value is passed, the current position is retrieved from the
        logic and the display is changed.
        """
        constraints = self._magnet_logic.get_hardware_constraints()
        curr_pos = self._magnet_logic.get_pos(list(constraints.keys()))
        self.last_pos = curr_pos
        if (param_list is not None) and (type(param_list) is not bool):
            param_list = list(param_list)
            # param_list =list(param_list) # convert for safety to a list
            curr_pos =  self._magnet_logic.get_pos(param_list)

        for axis_label in curr_pos:
            # update the values of the current position viewboxes:
            dspinbox_pos_ref = self.get_ref_curr_pos_ScienDSpinBox(axis_label)

            dspinbox_pos_ref.setValue(curr_pos[axis_label])
            

            # update the values also of the absolute movement display:
            # if axis_label not in ['x','y','z']:
            #     dspinbox_move_abs_ref = self.get_ref_move_abs_ScienDSpinBox(axis_label)
            #     dspinbox_move_abs_ref.setValue(curr_pos[axis_label])
                # slider_move_abs_ref = self.get_ref_move_abs_Slider(axis_label)
                # slider_move_abs_ref.setValue(curr_pos[axis_label])
        
        self.update_GLView_vector(curr_pos)
        self.make_new_sphere(radius=curr_pos['rho'])
        return curr_pos

    def run_stop_2d_alignment(self, is_checked):
        """ Manage what happens if 2d magnet scan is started/stopped

        @param bool is_checked: state if the current scan, True = started,
                                False = stopped
        """

        if is_checked:
            self.start_2d_alignment_clicked()

        else:
            self.abort_2d_alignment_clicked()

    def _change_display_to_stop_2d_alignment(self):
        """ Changes every display component back to the stopped state. """

        self._mw.run_stop_2d_alignment_Action.blockSignals(True)
        self._mw.run_stop_2d_alignment_Action.setChecked(False)

        self._mw.continue_2d_alignment_Action.blockSignals(True)
        self._mw.continue_2d_alignment_Action.setChecked(False)

        self._mw.run_stop_2d_alignment_Action.blockSignals(False)
        self._mw.continue_2d_alignment_Action.blockSignals(False)

    def start_2d_alignment_clicked(self):
        """ Start the 2d alignment. """

        if self.measurement_type == '2d_fluorescence':
            self._magnet_logic.curr_alignment_method = self.measurement_type

            self._magnet_logic.fluorescence_integration_time = self._mw.align_2d_fluorescence_integrationtime_DSpinBox.value()
            self._mw.alignment_2d_cb_GraphicsView.setLabel('right', 'Fluorescence', units='c/s')

        self._magnet_logic.start_2d_alignment(continue_meas=self._continue_2d_fluorescence_alignment)

        self._continue_2d_fluorescence_alignment = False

    def continue_stop_2d_alignment(self, is_checked):
        """ Manage what happens if 2d magnet scan is continued/stopped

        @param bool is_checked: state if the current scan, True = continue,
                                False = stopped
        """

        if is_checked:
            self.continue_2d_alignment_clicked()
        else:
            self.abort_2d_alignment_clicked()

    def continue_2d_alignment_clicked(self):

        self._continue_2d_fluorescence_alignment = True
        self.start_2d_alignment_clicked()

    def abort_2d_alignment_clicked(self):
        """ Stops the current Fluorescence alignment. """

        self._change_display_to_stop_2d_alignment()
        self._magnet_logic.stop_alignment()

    def _update_limits_axis0(self):
        """ Whenever a new axis name was chosen in axis0 config, the limits of the
            viewboxes will be adjusted.
        """

        constraints = self._magnet_logic.get_hardware_constraints()
        axis0_name = self._mw.align_2d_axis0_name_ComboBox.currentText()

        # set the range constraints:
        self._mw.align_2d_axis0_range_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis0_range_DSpinBox.setMaximum(constraints[axis0_name]['pos_max'])
        # self._mw.align_2d_axis0_range_DSpinBox.setSingleStep(constraints[axis0_name]['pos_step'],
        #                                                      dynamic_stepping=False)
        self._mw.align_2d_axis0_range_DSpinBox.setSuffix(constraints[axis0_name]['unit'])

        # set the step constraints:
        self._mw.align_2d_axis0_step_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis0_step_DSpinBox.setMaximum(constraints[axis0_name]['pos_max'])
        # self._mw.align_2d_axis0_step_DSpinBox.setSingleStep(constraints[axis0_name]['pos_step'],
        #                                                     dynamic_stepping=False)
        self._mw.align_2d_axis0_step_DSpinBox.setSuffix(constraints[axis0_name]['unit'])


    def _update_limits_axis1(self):
        """ Whenever a new axis name was chosen in axis0 config, the limits of the
            viewboxes will be adjusted.
        """

        constraints = self._magnet_logic.get_hardware_constraints()
        axis1_name = self._mw.align_2d_axis1_name_ComboBox.currentText()

        self._mw.align_2d_axis1_range_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis1_range_DSpinBox.setMaximum(constraints[axis1_name]['pos_max'])
        # self._mw.align_2d_axis1_range_DSpinBox.setSingleStep(constraints[axis1_name]['pos_step'],
        #                                                      dynamic_stepping=False)
        self._mw.align_2d_axis1_range_DSpinBox.setSuffix(constraints[axis1_name]['unit'])

        self._mw.align_2d_axis1_step_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis1_step_DSpinBox.setMaximum(constraints[axis1_name]['pos_max'])
        # self._mw.align_2d_axis1_step_DSpinBox.setSingleStep(constraints[axis1_name]['pos_step'],
        #                                                     dynamic_stepping=False)
        self._mw.align_2d_axis1_step_DSpinBox.setSuffix(constraints[axis1_name]['unit'])

    def _update_limits_axis2(self):
        """ Whenever a new axis name was chosen in axis0 config, the limits of the
            viewboxes will be adjusted.
        """

        constraints = self._magnet_logic.get_hardware_constraints()
        axis2_name = self._mw.align_2d_axis2_name_ComboBox.currentText()

        self._mw.align_2d_axis2_range_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis2_range_DSpinBox.setMaximum(constraints[axis2_name]['pos_max'])
        # self._mw.align_2d_axis2_range_DSpinBox.setSingleStep(constraints[axis2_name]['pos_step'],
        #                                                      dynamic_stepping=False)
        self._mw.align_2d_axis2_range_DSpinBox.setSuffix(constraints[axis2_name]['unit'])

        self._mw.align_2d_axis2_step_DSpinBox.setMinimum(0)
        self._mw.align_2d_axis2_step_DSpinBox.setMaximum(constraints[axis2_name]['pos_max'])
        # self._mw.align_2d_axis2_step_DSpinBox.setSingleStep(constraints[axis2_name]['pos_step'],
        #                                                     dynamic_stepping=False)
        self._mw.align_2d_axis2_step_DSpinBox.setSuffix(constraints[axis2_name]['unit'])

    def _update_2d_graph_axis(self):

        constraints = self._magnet_logic.get_hardware_constraints()

        axis0_name = self._mw.align_2d_axis0_name_ComboBox.currentText()
        axis0_unit = constraints[axis0_name]['unit']
        axis1_name = self._mw.align_2d_axis1_name_ComboBox.currentText()
        axis1_unit = constraints[axis1_name]['unit']

        axis0_array, axis1_array = self._magnet_logic.get_2d_axis_arrays()

        step0 = axis0_array[1] - axis0_array[0]
        step1 = axis1_array[1] - axis1_array[0]

        if self._3D_axis:
            self._3D_axis.del_items()

        # self._3D_axis = _3DAxisItem(rho=self._magnet_logic.get_pos(['rho'])['rho'], thetas=axis0_array, phis=axis1_array, n_ticks=5, view=self._GLView, axis=False)
        self._3D_axis = _3DAxisItem(rho=self.last_pos['rho'], thetas=axis0_array, phis=axis1_array, n_ticks=5, view=self._GLView, axis=False)
        # self._2d_alignment_ImageItem.set_image_extent([[axis0_array[0]-step0/2, axis0_array[-1]+step0/2],
        #                                                [axis1_array[0]-step1/2, axis1_array[-1]+step1/2]])

        # self._mw.alignment_2d_GraphicsView.setLabel('bottom', 'Absolute Position, Axis0: ' + axis0_name, units=axis0_unit)
        # self._mw.alignment_2d_GraphicsView.setLabel('left', 'Absolute Position, Axis1: '+ axis1_name, units=axis1_unit)

    def _update_2d_graph_cb(self):
        """ Update the colorbar to a new scaling.

        That function alters the color scaling of the colorbar next to the main
        picture.
        """

        # If "Centiles" is checked, adjust colour scaling automatically to
        # centiles. Otherwise, take user-defined values.

        if self._mw.alignment_2d_centiles_RadioButton.isChecked():

            low_centile = self._mw.alignment_2d_cb_low_centiles_DSpinBox.value()
            high_centile = self._mw.alignment_2d_cb_high_centiles_DSpinBox.value()

            if np.isclose(low_centile, 0.0):
                low_centile = 0.0

            # mask the array such that the arrays will be
            masked_image = np.ma.masked_equal(self._2d_alignment_ImageItem.image, 0.0)

            if len(masked_image.compressed()) == 0:
                cb_min = np.percentile(self._2d_alignment_ImageItem.image, low_centile)
                cb_max = np.percentile(self._2d_alignment_ImageItem.image, high_centile)
            else:
                cb_min = np.percentile(masked_image.compressed(), low_centile)
                cb_max = np.percentile(masked_image.compressed(), high_centile)

        else:
            cb_min = self._mw.alignment_2d_cb_min_centiles_DSpinBox.value()
            cb_max = self._mw.alignment_2d_cb_max_centiles_DSpinBox.value()
        
        cb_min = 0 if cb_min>cb_max else cb_min

        self._2d_alignment_cb.refresh_colorbar(cb_min, cb_max)
        self._mw.alignment_2d_cb_GraphicsView.update()

    def _update_2d_graph_data(self):
        """ Refresh the 2D-matrix image. """
        matrix_data = self._magnet_logic.get_2d_data_matrix()
        axis0_array, axis1_array = self._magnet_logic.get_2d_axis_arrays()

        if self._mw.alignment_2d_centiles_RadioButton.isChecked():

            low_centile = self._mw.alignment_2d_cb_low_centiles_DSpinBox.value()
            high_centile = self._mw.alignment_2d_cb_high_centiles_DSpinBox.value()

            if np.isclose(low_centile, 0.0):
                low_centile = 0.0

            # mask the array in order to mark the values which are zeros with
            # True, the rest with False:
            masked_image = np.ma.masked_equal(matrix_data, 0.0)

            # compress the 2D masked array to a 1D array where the zero values
            # are excluded:
            if len(masked_image.compressed()) == 0:
                cb_min = np.percentile(matrix_data, low_centile)
                cb_max = np.percentile(matrix_data, high_centile)
            else:
                cb_min = np.percentile(masked_image.compressed(), low_centile)
                cb_max = np.percentile(masked_image.compressed(), high_centile)
        else:
            cb_min = self._mw.alignment_2d_cb_min_centiles_DSpinBox.value()
            cb_max = self._mw.alignment_2d_cb_max_centiles_DSpinBox.value()

        if self._2d_alignment_ImageItem:
            self._2d_alignment_ImageItem.del_items()

        cb_min = 0 if cb_min>cb_max else cb_min
            
        # self._3d_alignment_ImageItem = _3DAlignmentImageItem(rho=self._magnet_logic.get_pos(['rho'])['rho'], thetas=axis0_array, phis=axis1_array, view=self._GLView)
        self._2d_alignment_ImageItem = _3DAlignmentImageItem(rho=self.last_pos['rho'], thetas=axis0_array, phis=axis1_array, view=self._GLView)
        self._2d_alignment_ImageItem.setImage(matrix=matrix_data, levels=(cb_min, cb_max))
        self._update_2d_graph_axis()

        self._update_2d_graph_cb()

        # get data from logic

    def save_2d_plots_and_data(self):
        """ Save the sum plot, the scan marix plot and the scan data """
        timestamp = datetime.datetime.now()
        filetag = self._mw.alignment_2d_nametag_LineEdit.text()
        filepath = self._save_logic.get_path_for_module(module_name='Magnet')

        if len(filetag) > 0:
            filename = os.path.join(filepath, '{0}_{1}_Magnet'.format(timestamp.strftime('%Y%m%d-%H%M-%S'), filetag))
        else:
            filename = os.path.join(filepath, '{0}_Magnet'.format(timestamp.strftime('%Y%m%d-%H%M-%S'),))

        # exporter_graph = pyqtgraph.exporters.SVGExporter(self._mw.alignment_2d_GraphicsView.plotItem.scene())
        # #exporter_graph = pg.exporters.ImageExporter(self._mw.odmr_PlotWidget.plotItem)
        # exporter_graph.export(filename  + '.svg')

        # self._save_logic.
        self._magnet_logic.save_2d_data(filetag, timestamp)

    def set_measurement_type(self):
        """ According to the selected Radiobox a measurement type will be chosen."""

        #FIXME: the measurement type should actually be set and saved in the logic

        if self._mw.meas_type_fluorescence_RadioButton.isChecked():
            self.measurement_type = '2d_fluorescence'
        else:
            self.log.error('No measurement type specified in Magnet GUI!')

    def update_from_roi_magnet(self, pos):
        """The user manually moved the XY ROI, adjust all other GUI elements accordingly

        @params object roi: PyQtGraph ROI object
        """
        x_pos = pos.x()
        y_pos = pos.y()

        if hasattr(self._magnet_logic, '_axis0_name') and hasattr(self._magnet_logic, '_axis1_name'):
            axis0_name = self._magnet_logic._axis0_name
            axis1_name = self._magnet_logic._axis1_name
        else:
            axis0_name = 'axis0'
            axis1_name = 'axis1'

        self._mw.pos_label.setText('({0}, {1})'.format(axis0_name, axis1_name))
        self._mw.pos_show.setText('({0:.6f}, {1:.6f})'.format(x_pos, y_pos))
        # I only need to update my label here.
        # which I would like to create in the QtDesigner

    def update_roi_from_abs_movement(self):
        """
        User changed magnetic field through absolute movement, therefore the roi has to be adjusted.
        @return:
        """
        axis0_name = self._mw.align_2d_axis0_name_ComboBox.currentText()
        axis1_name = self._mw.align_2d_axis1_name_ComboBox.currentText()
        self.log.debug('get the axis0_name: {0}'.format(axis0_name))
        self.log.debug('get the axis0_name: {0}'.format(axis1_name))
        axis0_value = self.get_ref_move_abs_ScienDSpinBox(axis0_name).value()
        axis1_value = self.get_ref_move_abs_ScienDSpinBox(axis1_name).value()
        # self._mw.alignment_2d_GraphicsView.set_crosshair_pos([axis0_value, axis1_value])
        return 0

    def update_move_rel_para(self, parameters):
        """ The GUT is updated taking dict into account. Thereby no signal is triggered!

        @params dictionary: Dictionary containing the values to update

        @return dictionary: Dictionary containing the values to update
         """
        for axis_label in parameters:
            dspinbox = self.get_ref_move_rel_ScienDSpinBox(axis_label)
            dspinbox.blockSignals(True)
            dspinbox.setValue(parameters[axis_label])
            dspinbox.blockSignals(False)
        return parameters

    def update_roi_from_range(self):
        """
        User changed scan range and therefore the rectangular should be adjusted
        @return:
        """
        # first get the size of axis0 and axis1 range
        x_range = self._mw.align_2d_axis0_range_DSpinBox.value()
        y_range = self._mw.align_2d_axis0_range_DSpinBox.value()
        # self._mw.alignment_2d_GraphicsView.set_crosshair_size([x_range/100, y_range/100])

    def update_align_2d_axis0_name(self,axisname):
        """ The GUT is updated taking axisname into account. Thereby no signal is triggered!

        @params str: Axis name to update

        @return str: Axis name to update
         """
        self._mw.align_2d_axis0_name_ComboBox.blockSignals(True)
        index = self._mw.align_2d_axis0_name_ComboBox.findText(axisname)
        self._mw.align_2d_axis0_name_ComboBox.setCurrentIndex(index)
        self._mw.align_2d_axis0_name_ComboBox.blockSignals(False)
        return axisname

    def update_align_2d_axis0_range(self, axis_range):
        """ The GUT is updated taking range into account. Thereby no signal is triggered!

        @params float: Range to update

        @return float: Range to update
         """
        self._mw.align_2d_axis0_range_DSpinBox.blockSignals(True)
        self._mw.align_2d_axis0_range_DSpinBox.setValue(axis_range)
        self._mw.align_2d_axis0_range_DSpinBox.blockSignals(False)
        return axis_range

    def update_align_2d_axis0_step(self, step):
        """ The GUT is updated taking step into account. Thereby no signal is triggered!

        @params float: Step to update in m

        @return float: Step to update in m
         """
        self._mw.align_2d_axis0_step_DSpinBox.blockSignals(True)
        self._mw.align_2d_axis0_step_DSpinBox.setValue(step)
        self._mw.align_2d_axis0_step_DSpinBox.blockSignals(False)
        return step

    def update_align_2d_axis1_name(self, axisname):
        """ The GUT is updated taking axisname into account. Thereby no signal is triggered!

        @params str: Axis name to update

        @return str: Axis name to update
         """
        self._mw.align_2d_axis1_name_ComboBox.blockSignals(True)
        index = self._mw.align_2d_axis1_name_ComboBox.findText(axisname)
        self._mw.align_2d_axis1_name_ComboBox.setCurrentIndex(index)
        self._mw.align_2d_axis1_name_ComboBox.blockSignals(False)
        return index

    def update_align_2d_axis1_range(self, axis_range):
        """ The GUT is updated taking range into account. Thereby no signal is triggered!

        @params float: Range to update

        @return float: Range to update
         """
        self._mw.align_2d_axis1_range_DSpinBox.blockSignals(True)
        self._mw.align_2d_axis1_range_DSpinBox.setValue(axis_range)
        self._mw.align_2d_axis1_range_DSpinBox.blockSignals(False)
        return axis_range

    def update_align_2d_axis1_step(self, step):
        """ The GUT is updated taking step into account. Thereby no signal is triggered!

        @params float: Step to update in m

        @return float: Step to update in m
         """
        self._mw.align_2d_axis1_step_DSpinBox.blockSignals(True)
        self._mw.align_2d_axis1_step_DSpinBox.setValue(step)
        self._mw.align_2d_axis1_step_DSpinBox.blockSignals(False)
        return step


    def update_optimize_pos_freq(self, freq):
        """ The GUT is updated taking freq into account. Thereby no signal is triggered!

        @params float: Frequency to update

        @return float: Frequency to update
         """
        self._mw.align_2d_fluorescence_optimize_freq_SpinBox.blockSignals(True)
        self._mw.align_2d_fluorescence_optimize_freq_SpinBox.setValue(freq)
        self._mw.align_2d_fluorescence_optimize_freq_SpinBox.blockSignals(False)
        return freq

    def update_fluorescence_integration_time(self, time):
        """ The GUT is updated taking time into account. Thereby no signal is triggered!

        @params float: Integration time to update

        @return float: Integration time to update
         """
        self._mw.align_2d_fluorescence_integrationtime_DSpinBox.blockSignals(True)
        self._mw.align_2d_fluorescence_integrationtime_DSpinBox.setValue(time)
        self._mw.align_2d_fluorescence_integrationtime_DSpinBox.blockSignals(False)
        return time
    
    def _init_GLView(self):

        view = self._GLView

        xgrid = gl.GLGridItem()
        ygrid = gl.GLGridItem()
        zgrid = gl.GLGridItem()

        view.addItem(xgrid)
        view.addItem(ygrid)
        view.addItem(zgrid)

        ## rotate x and y grids to face the correct direction
        xgrid.rotate(90, 0, 1, 0)
        ygrid.rotate(90, 1, 0, 0)

        ## scale each grid differently
        xgrid.scale(0.2, 0.1, 0.1)
        ygrid.scale(0.2, 0.1, 0.1)
        zgrid.scale(0.1, 0.2, 0.1)

        PlotItem = gl.GLLinePlotItem(pos=np.array([[0,0,0],[1,0,0]]), color=pg.glColor((255, 140, 140, 255)), width=5, antialias=True)
        view.addItem(PlotItem)
        PlotItem = gl.GLLinePlotItem(pos=np.array([[0,0,0],[0,1,0]]), color=pg.glColor((140, 255, 140, 255)), width=5, antialias=True)
        view.addItem(PlotItem)
        PlotItem = gl.GLLinePlotItem(pos=np.array([[0,0,0],[0,0,1]]), color=pg.glColor((140, 140, 255, 255)), width=5, antialias=True)
        view.addItem(PlotItem)

        md = gl.MeshData.sphere(rows=20, cols=20)
        m4 = gl.GLMeshItem(meshdata=md, smooth=True, drawFaces=False, drawEdges=True, edgeColor=(0.3,0.3,0.3,1))
        m4.translate(0,0,0)
        self.sphere = m4
        view.addItem(self.sphere)
        self.vector_item = gl.GLLinePlotItem(pos=np.array([[0,0,0],[0,0,0]]), color=pg.glColor((255, 255, 255, 255)), width=5, antialias=True)
        self._GLView.addItem(self.vector_item)
        
        def makeGaussian(size, fwhm = 3, center=None):
            """ Make a square gaussian kernel.

            size is the length of a side of the square
            fwhm is full-width-half-maximum, which
            can be thought of as an effective radius.
            """

            x = np.arange(0, size, 1, float)
            y = x[:,np.newaxis]

            if center is None:
                x0 = y0 = size // 2
            else:
                x0 = center[0]
                y0 = center[1]

            return np.exp(-4*np.log(2) * ((x-x0)**2 + (y-y0)**2) / fwhm**2)

        # size = 30
        # thet = np.linspace(np.pi/4,3*np.pi/4,size)
        # ph = np.linspace(0,0.5*np.pi,size)
        # matrix = np.random.random((size,size))
        # matrix = makeGaussian(size, size/3)
        # rho = 0.7

        # self._3D_axis = _3DAxisItem(rho, thet, ph, 5, self._GLView, False)
        # self._2d_alignment_ImageItem = _3DAlignmentImageItem(rho, thet, ph, self._GLView)
        # self._2d_alignment_ImageItem.setImage(matrix, (0,1))
        # self._GLView.update()
    
    def make_new_sphere(self, radius=1):
        if self._GLView:
            self._GLView.removeItem(self.sphere)
            md = gl.MeshData.sphere(rows=20, cols=20, radius=radius)
            m4 = gl.GLMeshItem(meshdata=md, smooth=True, drawFaces=False, drawEdges=True, edgeColor=(0.3,0.3,0.3,1))
            m4.translate(0,0,0)
            self.sphere = m4
            self._GLView.addItem(self.sphere)
            self._GLView.update()
    
    def update_GLView_vector(self, curr_pos):
        if self._GLView:
            self._GLView.removeItem(self.vector_item)
            self.vector_item = gl.GLLinePlotItem(pos=np.array([[0,0,0],[curr_pos['x'],curr_pos['y'],curr_pos['z']]]), color=pg.glColor((255, 255, 255, 255)), width=5, antialias=True)
            self._GLView.addItem(self.vector_item)
    
    def update_GLView_new_vector(self, new_pos):
        if self._GLView:
            if self.new_vector_item:
                self._GLView.removeItem(self.new_vector_item)
            self.new_vector_item = gl.GLLinePlotItem(pos=np.array([[0,0,0],[new_pos['x'],new_pos['y'],new_pos['z']]]), color=pg.glColor((142, 199, 210, 255)), width=5, antialias=True)
            self._GLView.addItem(self.new_vector_item)
    
    def update_GLView_opt_vector(self, new_pos):
        if self._GLView:
            if self.opt_vector_item:
                self._GLView.removeItem(self.opt_vector_item)
            self.opt_vector_item = gl.GLLinePlotItem(pos=np.array([[0,0,0],[new_pos['x'],new_pos['y'],new_pos['z']]]), color=pg.glColor((255, 195, 0, 255)), width=5, antialias=True)
            self._GLView.addItem(self.opt_vector_item)
    
    def give_pos_to_update_GLView_new_vector(self):
        constraints=self._magnet_logic.get_hardware_constraints()
        new_pos_dict = {}
        for axis_label in list(constraints):
            if axis_label in ['x','y','z']:
                continue
            dspinbox_move_abs_ref = self.get_ref_move_abs_ScienDSpinBox(axis_label)
            new_pos_dict[axis_label] = dspinbox_move_abs_ref.value()
        new_pos = {}
        new_pos['x'] = new_pos_dict['rho'] * np.sin(new_pos_dict['theta']) * np.cos(new_pos_dict['phi'])
        new_pos['y'] = new_pos_dict['rho'] * np.sin(new_pos_dict['theta']) * np.sin(new_pos_dict['phi'])
        new_pos['z'] = new_pos_dict['rho'] * np.cos(new_pos_dict['theta'])
        self.update_GLView_new_vector(new_pos)
    
    def give_pos_to_update_GLView_opt_vector(self, new_pos_dict):
        new_pos = {}
        new_pos['x'] = new_pos_dict['rho'] * np.sin(new_pos_dict['theta']) * np.cos(new_pos_dict['phi'])
        new_pos['y'] = new_pos_dict['rho'] * np.sin(new_pos_dict['theta']) * np.sin(new_pos_dict['phi'])
        new_pos['z'] = new_pos_dict['rho'] * np.cos(new_pos_dict['theta'])
        self._mw.fitResult_textBrowser.setText(new_pos_dict['fit_result'])
        self.update_GLView_opt_vector(new_pos)