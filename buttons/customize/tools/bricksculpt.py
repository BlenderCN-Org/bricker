"""
    Copyright (C) 2019 Bricks Brought to Life
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
import bmesh
import math

# Blender imports
import bpy
import bgl
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d
from bpy.types import Operator, SpaceView3D, bpy_struct
from bpy.props import *

# Addon imports
from .bricksculpt_framework import *
from .bricksculpt_tools import *
from .bricksculpt_drawing import *
from .drawAdjacent import *
from ..undo_stack import *
from ..functions import *
from ...brickify import *
from ....lib.Brick import *
from ....functions import *
from ....operators.delete_object import OBJECT_OT_delete_override
from ....lib.addon_common.cookiecutter.cookiecutter import CookieCutter
from ....lib.addon_common.common.blender import bversion
from ....lib.addon_common.common.maths import Point, Point2D
from ....lib.addon_common.common.decorators import PersistentOptions


class BRICKER_OT_bricksculpt(bricksculpt_framework, bricksculpt_tools, bricksculpt_drawing, CookieCutter):
    """Run the BrickSculpt editing tool suite"""
    operator_id = "bricker.bricksculpt"
    bl_idname   = "bricker.bricksculpt"
    bl_label    = "BrickSculpt Tools"
    bl_options  = {"REGISTER", "UNDO"}

    ################################################
    # CookieCutter Operator methods

    @classmethod
    def can_start(cls, context):
        """ ensures operator can execute (if not, returns False) """
        if not bpy.props.bricker_initialized:
            return False
        return True

    def start(self):
        """ ExtruCut tool is starting """
        bpy.ops.ed.undo_push()  # push current state to undo

        self.initialize()

        if not self.brickSculptInstalledAndLoaded():
            self.done(cancel=True)
            return

        self.header_text_set("BrickSculpt")
        self.cursor_modal_set("CROSSHAIR")
        self.manipulator_hide()

        self.ui_setup()

        # self.grab_undo_loc = None
        # self.grab_undo_no = None
        # self.mouse = (None, None)
        self.start_post()

    def end_commit(self):
        """ Commit changes to mesh! """
        self.commitChanges()

    def end_cancel(self):
        """ Cancel changes """
        bpy.ops.ed.undo()   # undo geometry hide

    def end(self):
        """ Restore everything, because we're done """
        bpy.props.running_bricksculpt_tool = False
        self.ui_end()
        self.manipulator_restore()
        self.header_text_restore()
        self.cursor_modal_restore()

    def update(self):
        """ Check if we need to update any internal data structures """
        pass

    ################################################
    # initialization method

    def initialize(self):
        scn, cm, n = getActiveContextInfo()
        # push to undo stack
        self.undo_stack = UndoStack.get_instance()
        self.undo_stack.undo_push('bricksculpt_mode', affected_ids=[cm.id])
        # initialize vars
        self.addedBricks = []
        self.addedBricksFromDelete = []
        self.parentKeysToMergeOnRelease = []
        self.keysToMergeOnRelease = []
        self.allUpdatedKeys = []
        self.dimensions = Bricks.get_dimensions(cm.brickHeight, cm.zStep, cm.gap)
        self.obj = None
        self.cm_idx = cm.idx
        self.keysToMergeOnCommit = []
        self.targettedBrickKeys = []
        self.brickType = getBrickType(cm.brickType)
        self.matName = cm.paintbrushMat.name if cm.paintbrushMat is not None else ""  # bpy.data.materials[-1].name if len(bpy.data.materials) > 0 else ""
        self.hiddenBricks = []
        self.releaseTime = 0
        self.vertical = False
        self.horizontal = True
        self.lastMouse = Vector((0, 0))
        self.mouseTravel = 0
        self.junk_bme = bmesh.new()
        self.parent = bpy.data.objects.get("Bricker_%(n)s_parent" % locals())
        deselectAll()
        # initialize properties
        scn, cm, _ = getActiveContextInfo()
        self.undo_stack.iterateStates(cm)
        cm.customized = True
        # get fresh copy of self.bricksDict
        self.bricksDict, _ = getBricksDict(cm=cm)
        # ui properties
        self.left_click = False
        self.double_ctrl = False
        self.ctrlClickTime = -1
        self.runUnSoloLayer = False
        self.layerSolod = None
        self.possibleCtrlDisable = False
        # self.points = [(math.cos(d*math.pi/180.0),math.sin(d*math.pi/180.0)) for d in range(0,361,10)]
        # self.ox = Vector((1,0,0))
        # self.oy = Vector((0,1,0))
        # self.oz = Vector((0,0,1))
        # self.radius = 50.0
        # self.falloff = 1.5
        # self.strength = 0.5
        # self.scale = 0.0
        # self.color = (1,1,1)
        # self.region = bpy.context.region
        # self.r3d = bpy.context.space_data.region_3d
        # self.clear_ui_mouse_pos()

    ###################################################
    # class variables

    # # get items for brickType prop
    # def get_items(self, context):
    #     scn, cm, _ = getActiveContextInfo()
    #     legalBS = bpy.props.Bricker_legal_brick_sizes
    #     items = [itemFromType(typ) for typ in legalBS[cm.zStep]]
    #     if cm.zStep == 1:
    #         items += [itemFromType(typ) for typ in legalBS[3]]
    #     # items = getAvailableTypes(by="ACTIVE", includeSizes="ALL")
    #     return items
    #
    # # define props for popup
    # brickType = bpy.props.EnumProperty(
    #     name="Brick Type",
    #     description="Type of brick to draw adjacent to current brick",
    #     items=get_items,
    #     default=None)

    # define props for popup
    mode = bpy.props.EnumProperty(
        items=[("DRAW", "DRAW", ""),
               ("PAINT", "PAINT", ""),
               ("MERGE/SPLIT", "MERGE/SPLIT", ""),
               ],
    )

    ###################################################
    # class methods

    def brickSculptInstalledAndLoaded(self):
        try:
            # try installing BrickSculpt
            if not self.BrickSculptInstalled:
                status = installBrickSculpt()
                if status:
                    self.BrickSculptInstalled = True
            if self.BrickSculptLoaded:
                if not hasattr(bpy.props, "bricksculpt_module_name"):
                    self.report({"WARNING"}, "Please enable the 'BrickSculpt' addon in User Preferences")
                    return False
                if bpy.props.running_bricksculpt_tool:
                    return False
                else:
                    bpy.props.running_bricksculpt_tool = True
                if self.mode == "DRAW" and self.brickType == "":
                    self.report({"WARNING"}, "Please choose a target brick type")
                    return False
                if self.mode == "PAINT" and self.matName == "":
                    self.report({"WARNING"}, "Please choose a material for the paintbrush")
                    return False
                return True
            elif self.BrickSculptInstalled and not self.BrickSculptLoaded:
                self.report({"WARNING"}, "Please reload Blender to complete the BrickSculpt installation")
                return False
            else:
                self.report({"WARNING"}, "Please install & enable BrickSculpt from the 'User Preferences > Addons' menu")
                return False
        except:
            bricker_handle_exception()
            return {"CANCELLED"}

    def start_post(self):
        pass
