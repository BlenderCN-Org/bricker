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
# NONE!

# Blender imports
import bpy
from bpy.props import *
from bpy.types import UIList

# Bricker imports
from ..functions import *
from .cmlist_utils import *


# ui list item actions
class Bricker_Uilist_actions(bpy.types.Operator):
    bl_idname = "cmlist.list_action"
    bl_label = "Brick Model List Action"

    action = bpy.props.EnumProperty(
        items=(
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
            ('REMOVE', "Remove", ""),
            ('ADD', "Add", ""),
        )
    )

    # @classmethod
    # def poll(self, context):
    #     """ ensures operator can execute (if not, returns false) """
    #     scn = context.scene
    #     for cm in scn.cmlist:
    #         if cm.animated:
    #             return False
    #     return True

    def execute(self, context):
        try:
            scn = context.scene
            idx = scn.cmlist_index

            try:
                item = scn.cmlist[idx]
            except IndexError:
                pass

            if self.action == 'REMOVE' and len(scn.cmlist) > 0 and scn.cmlist_index >= 0:
                self.removeItem(idx)

            elif self.action == 'ADD':
                self.addItem()

            elif self.action == 'DOWN' and idx < len(scn.cmlist) - 1:
                self.moveDown(item)

            elif self.action == 'UP' and idx >= 1:
                self.moveUp(item)
        except:
            handle_exception()
        return{"FINISHED"}

    def addItem(self):
        scn = bpy.context.scene
        active_object = scn.objects.active
        # if active object isn't on visible layer, don't set it as default source for new model
        if active_object:
            objVisible = False
            for i in range(20):
                if active_object.layers[i] and scn.layers[i]:
                    objVisible = True
            if not objVisible:
                active_object = None
        # if active object already has a model or isn't on visible layer, don't set it as default source for new model
        # NOTE: active object may have been removed, so we need to re-check if none
        if active_object:
            for cm in scn.cmlist:
                if cm.source_name == active_object.name:
                    active_object = None
                    break
        item = scn.cmlist.add()
        last_index = scn.cmlist_index
        scn.cmlist_index = len(scn.cmlist)-1
        if active_object and active_object.type == "MESH" and not active_object.name.startswith("Bricker_"):
            item.source_name = active_object.name
            item.name = active_object.name
            item.version = bpy.props.bricker_version
            # set up default brickHeight values
            source = bpy.data.objects.get(item.source_name)
            if source:
                source_details = bounds(source)
                h = max(source_details.dist)
                # update brick height based on model height
                item.brickHeight = h / 20

        else:
            item.source_name = ""
            item.name = "<New Model>"
        # get all existing IDs
        existingIDs = [cm.id for cm in scn.cmlist]
        i = max(existingIDs) + 1
        # protect against massive item IDs
        if i > 9999:
            i = 1
            while i in existingIDs:
                i += 1
        # set item ID to unique number
        item.id = i
        item.idx = len(scn.cmlist)-1
        item.startFrame = scn.frame_start
        item.stopFrame = scn.frame_end

    def removeItem(self, idx):
        scn, cm, sn = getActiveContextInfo()
        n = cm.name
        if not cm.modelCreated and not cm.animated:
            if len(scn.cmlist) - 1 == scn.cmlist_index:
                scn.cmlist_index -= 1
            scn.cmlist.remove(idx)
            if scn.cmlist_index == -1 and len(scn.cmlist) > 0:
                scn.cmlist_index = 0
        else:
            self.report({"WARNING"}, 'Please delete the Brickified model before attempting to remove this item.' % locals())

    def moveDown(self, item):
        scn = bpy.context.scene
        scn.cmlist.move(scn.cmlist_index, scn.cmlist_index+1)
        scn.cmlist_index += 1
        self.updateIdxs(scn.cmlist)

    def moveUp(self, item):
        scn = bpy.context.scene
        scn.cmlist.move(scn.cmlist_index, scn.cmlist_index-1)
        scn.cmlist_index -= 1
        self.updateIdxs(scn.cmlist)

    def updateIdxs(self, cmlist):
        for i,cm in enumerate(cmlist):
            cm.idx = i


# -------------------------------------------------------------------
# draw
# -------------------------------------------------------------------

class Bricker_UL_items(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Make sure your code supports all 3 layout types
        if self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
        split = layout.split(0.9)
        split.prop(item, "name", text="", emboss=False, translate=False, icon='MOD_REMESH')

    def invoke(self, context, event):
        pass


# copy settings from current index to all other indices
class Bricker_Uilist_copySettingsToOthers(bpy.types.Operator):
    bl_idname = "cmlist.copy_to_others"
    bl_label = "Copy Settings to Other Brick Models"
    bl_description = "Copies the settings from the current model to all other Brick Models"

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns false) """
        scn = context.scene
        if scn.cmlist_index == -1:
            return False
        if len(scn.cmlist) == 1:
            return False
        return True

    def execute(self, context):
        try:
            scn, cm0, _ = getActiveContextInfo()
            for cm1 in scn.cmlist:
                if cm0 != cm1:
                    matchProperties(cm1, cm0, bh=True)
        except:
            handle_exception()
        return{'FINISHED'}


# copy settings from current index to memory
class Bricker_Uilist_copySettings(bpy.types.Operator):
    bl_idname = "cmlist.copy_settings"
    bl_label = "Copy Settings from Current Brick Model"
    bl_description = "Stores the ID of the current model for pasting"

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns false) """
        scn = context.scene
        if scn.cmlist_index == -1:
            return False
        return True

    def execute(self, context):
        try:
            scn, cm, _ = getActiveContextInfo()
            scn.Bricker_copy_from_id = cm.id
        except:
            handle_exception()
        return{'FINISHED'}


# paste settings from index in memory to current index
class Bricker_Uilist_pasteSettings(bpy.types.Operator):
    bl_idname = "cmlist.paste_settings"
    bl_label = "Paste Settings to Current Brick Model"
    bl_description = "Pastes the settings from stored model ID to the current index"

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns false) """
        scn = context.scene
        if scn.cmlist_index == -1:
            return False
        return True

    def execute(self, context):
        try:
            scn, cm0, _ = getActiveContextInfo()
            for cm1 in scn.cmlist:
                if cm0 != cm1 and cm1.id == scn.Bricker_copy_from_id:
                    matchProperties(cm0, cm1)
                    break
        except:
            handle_exception()
        return{'FINISHED'}