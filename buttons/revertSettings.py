"""
    Copyright (C) 2017 Bricks Brought to Life
    http://bblanimation.com/
    chris@bblanimation.com

    Created by Christopher Gearhart

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>.
    """

# System imports
import time
import os

# Blender imports
import bpy
from bpy.types import Operator

# Rebrickr imports
from ..functions import *

class RebrickrRevertSettings(Operator):
    """Revert Matrix settings to save model customizations"""                   # blender will use this as a tooltip for menu items and buttons.
    bl_idname = "rebrickr.revert_matrix_settings"                               # unique identifier for buttons and menu items to reference.
    bl_label = "Revert Matrix Settings"                                         # display name in the interface.
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        if scn.cmlist_index == -1:
            return False
        cm = scn.cmlist[scn.cmlist_index]
        if matrixReallyIsDirty(cm):
            return True
        return False

    def execute(self, context):
        try:
            revertMatrixSettings()
        except:
            handle_exception()
        return{"FINISHED"}