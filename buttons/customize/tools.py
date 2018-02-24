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
import copy

# Blender imports
import bpy
from bpy.types import Operator

# Rebrickr imports
from .undo_stack import *
from .functions import *
from ..brickify import *
from ..brickify import *
from ...lib.bricksDict.functions import getDictKey
from ...functions import *


class splitBricks(Operator):
    """Split selected bricks into 1x1 bricks"""
    bl_idname = "rebrickr.split_bricks"
    bl_label = "Split Brick(s)"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        if not bpy.props.rebrickr_initialized:
            return False
        scn = bpy.context.scene
        objs = bpy.context.selected_objects
        # check that at least 1 selected object is a brick
        for obj in objs:
            if obj.isBrick:
                # get cmlist item referred to by object
                cm = getItemByID(scn.cmlist, obj.cmlist_id)
                if cm.lastBrickType != "Custom":
                    return True
        return False

    def execute(self, context):
        self.splitBricks()
        return{"FINISHED"}

    def invoke(self, context, event):
        scn = context.scene
        # invoke props popup if conditions met
        for cm_idx in self.objNamesD.keys():
            cm = scn.cmlist[cm_idx]
            if cm.brickType != "Bricks and Plates":
                continue
            bricksDict = copy.deepcopy(self.bricksDicts[cm_idx])
            for obj_name in self.objNamesD[cm_idx]:
                dictKey, dictLoc = getDictKey(obj_name)
                size = bricksDict[dictKey]["size"]
                if size[2] <= 1:
                    continue
                if size[0] + size[1] > 2:
                    return context.window_manager.invoke_props_popup(self, event)
                else:
                    self.vertical = True
                    self.splitBricks()
                    return {"FINISHED"}
        self.horizontal = True
        self.splitBricks()
        return {"FINISHED"}

    ################################################
    # initialization method

    def __init__(self):
        scn = bpy.context.scene
        self.undo_stack = UndoStack.get_instance()
        self.orig_undo_stack_length = self.undo_stack.getLength()
        self.vertical = False
        self.horizontal = False
        selected_objects = bpy.context.selected_objects
        # initialize objsD (key:cm_idx, val:list of brick objects)
        objsD = createObjsD(selected_objects)
        for cm_idx in objsD.keys():
            self.objNamesD[cm_idx] = [obj.name for obj in objsD[cm_idx]]
        # initialize bricksDicts
        for cm_idx in objsD.keys():
            cm = scn.cmlist[cm_idx]
            # get bricksDict from cache
            bricksDict, _ = getBricksDict(cm=cm)
            # add to bricksDicts
            self.bricksDicts[cm_idx] = bricksDict

    ###################################################
    # class variables

    # variables
    objNamesD = {}
    bricksDicts = {}

    # properties
    vertical = bpy.props.BoolProperty(
        name="Vertical",
        description="Split brick(s) horizontally",
        default=False)
    horizontal = bpy.props.BoolProperty(
        name="Horizontal",
        description="Split brick(s) vertically",
        default=False)

    #############################################
    # class methods

    def splitBricks(self):
        try:
            self.undo_stack.matchPythonToBlenderState()
            if self.orig_undo_stack_length == self.undo_stack.getLength():
                self.undo_stack.undo_push('split')
            scn = bpy.context.scene
            # split all bricks in objNamesD[cm_idx]
            for cm_idx in self.objNamesD.keys():
                cm = scn.cmlist[cm_idx]
                self.undo_stack.iterateStates(cm)
                bricksDict = copy.deepcopy(self.bricksDicts[cm_idx])
                keysToUpdate = []

                for obj_name in self.objNamesD[cm_idx]:
                    # get dict key details of current obj
                    dictKey, dictLoc = getDictKey(obj_name)
                    x0, y0, z0 = dictLoc
                    # get size of current brick (e.g. [2, 4, 1])
                    objSize = bricksDict[dictKey]["size"]
                    bricksDict[dictKey]["type"] = "STANDARD"
                    zStep = getZStep(cm)

                    # skip 1x1 bricks
                    if objSize[0] + objSize[1] + (objSize[2] / zStep) == 3:
                        continue

                    if self.vertical or self.horizontal:
                        # delete the current object
                        delete(bpy.data.objects.get(obj_name))
                        # split the bricks in the matrix and set size of active brick's bricksDict entries to 1x1x[lastZSize]
                        splitKeys = Bricks.split(bricksDict, dictKey, loc=dictLoc, cm=cm, v=self.vertical, h=self.horizontal)
                        # append new splitKeys to keysToUpdate
                        keysToUpdate = [k for k in splitKeys if k not in keysToUpdate]

                # draw modified bricks
                drawUpdatedBricks(cm, bricksDict, keysToUpdate)

                # model is now customized
                cm.customized = True
        except:
            handle_exception()

    #############################################


class mergeBricks(Operator):
    """Merge selected bricks"""
    bl_idname = "rebrickr.merge_bricks"
    bl_label = "Merge Bricks"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        objs = bpy.context.selected_objects
        i = 0
        # check that at least 2 objects are selected and are bricks
        for obj in objs:
            if obj.isBrick:
                # get cmlist item referred to by object
                cm = getItemByID(scn.cmlist, obj.cmlist_id)
                if cm.lastBrickType != "Custom" and not cm.buildIsDirty:
                    i += 1
                    if i == 2:
                        return True
        return False

    def execute(self, context):
        try:
            scn = bpy.context.scene
            selected_objects = bpy.context.selected_objects

            # initialize objsD (key:cm_idx, val:list of brick objects)
            objsD = createObjsD(selected_objects)

            # iterate through keys in objsD
            for cm_idx in objsD.keys():
                cm = scn.cmlist[cm_idx]
                self.undo_stack.iterateStates(cm)
                # initialize vars
                bricksDict = copy.deepcopy(self.bricksDicts[cm_idx])
                parent_brick = None
                allSplitKeys = []

                # iterate through objects in objsD[cm_idx]
                for obj in objsD[cm_idx]:
                    # initialize vars
                    dictKey, dictLoc = getDictKey(obj.name)
                    x0, y0, z0 = dictLoc
                    objSize = bricksDict[dictKey]["size"]

                    # split brick in matrix
                    splitKeys = Bricks.split(bricksDict, dictKey, cm=cm)
                    allSplitKeys += splitKeys
                    # delete the object that was split
                    delete(obj)

                # run self.mergeBricks
                keysToUpdate = mergeBricks.mergeBricks(bricksDict, allSplitKeys, cm)

                # draw modified bricks
                drawUpdatedBricks(cm, bricksDict, keysToUpdate)

                # model is now customized
                cm.customized = True
        except:
            handle_exception()
        return{"FINISHED"}

    ################################################
    # initialization method

    def __init__(self):
        scn = bpy.context.scene
        self.undo_stack = UndoStack.get_instance()
        self.undo_stack.undo_push('merge')
        selected_objects = bpy.context.selected_objects
        objsD = createObjsD(selected_objects)
        # initialize bricksDicts
        for cm_idx in objsD.keys():
            cm = scn.cmlist[cm_idx]
            # get bricksDict from cache
            bricksDict, _ = getBricksDict(cm=cm)
            # add to bricksDicts
            self.bricksDicts[cm_idx] = bricksDict

    ###################################################
    # class variables

    # variables
    bricksDicts = {}

    #############################################
    # class methods

    @staticmethod
    def getSortedKeys(keys):
        """ sort bricks by (x+y) location for best merge """
        keys.sort(key=lambda k: (strToList(k)[0] * strToList(k)[1] * strToList(k)[2]))
        return keys

    @staticmethod
    def mergeBricks(bricksDict, keys, cm, mergeVertical=True):
        # initialize vars
        updatedKeys = []
        zStep = getZStep(cm)
        randState = np.random.RandomState(cm.mergeSeed)

        keys = mergeBricks.getSortedKeys(keys)

        for key in keys:
            if bricksDict[key]["parent_brick"] in [None, "self"]:
                # attempt to merge current brick with other bricks in keys, according to available brick types
                # TODO: improve originalIsBrick argument (currently hardcoded to False)
                loc = strToList(key)
                brickSize = attemptMerge(cm, bricksDict, key, keys, loc, [bricksDict[key]["size"]], zStep, randState, preferLargest=True, mergeVertical=mergeVertical)
                # bricksDict[key]["size"] = brickSize
                # set exposure of current [merged] brick
                topExposed, botExposed = getBrickExposure(cm, bricksDict, key, loc)
                bricksDict[key]["top_exposed"] = topExposed
                bricksDict[key]["bot_exposed"] = botExposed
                updatedKeys.append(key)
        return updatedKeys

    #############################################


class setExposure(Operator):
    """Set exposure of bricks"""
    bl_idname = "rebrickr.set_exposure"
    bl_label = "Set Exposure"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        objs = bpy.context.selected_objects
        # check that at least 1 selected object is a brick
        for obj in objs:
            if obj.isBrick:
                # get cmlist item referred to by object
                cm = getItemByID(scn.cmlist, obj.cmlist_id)
                if cm.lastBrickType != "Custom":
                    return True
        return False

    def execute(self, context):
        try:
            scn = bpy.context.scene
            selected_objects = bpy.context.selected_objects
            active_obj = scn.objects.active
            initial_active_obj_name = active_obj.name if active_obj else ""

            # initialize objsD (key:cm_idx, val:list of brick objects)
            objsD = createObjsD(selected_objects)

            # iterate through keys in objsD
            for cm_idx in objsD.keys():
                cm = scn.cmlist[cm_idx]
                self.undo_stack.iterateStates(cm)
                bricksDict = copy.deepcopy(self.bricksDicts[cm_idx])
                keysToUpdate = []

                for obj in objsD[cm_idx]:
                    # get dict key details of current obj
                    dictKey, dictLoc = getDictKey(obj.name)
                    # get size of current brick (e.g. [2, 4, 1])
                    objSize = bricksDict[dictKey]["size"]

                    # delete the current object
                    delete(obj)

                    # set top as exposed
                    if self.side in ["TOP", "BOTH"]:
                        bricksDict[dictKey]["top_exposed"] = not bricksDict[dictKey]["top_exposed"]
                    # set bottom as exposed
                    if self.side in ["BOTTOM", "BOTH"]:
                        bricksDict[dictKey]["bot_exposed"] = not bricksDict[dictKey]["bot_exposed"]
                    # add curKey to simple bricksDict for drawing
                    keysToUpdate.append(dictKey)

                # draw modified bricks
                drawUpdatedBricks(cm, bricksDict, keysToUpdate)

                # model is now customized
                cm.customized = True
            # select original brick
            orig_obj = bpy.data.objects.get(initial_active_obj_name)
            if orig_obj:
                select(orig_obj, active=orig_obj, only=False)
        except:
            handle_exception()
        return {"FINISHED"}

    ################################################
    # initialization method

    def __init__(self):
        scn = bpy.context.scene
        self.undo_stack = UndoStack.get_instance()
        self.undo_stack.undo_push('exposure')
        # initialize bricksDicts
        selected_objects = bpy.context.selected_objects
        objsD = createObjsD(selected_objects)
        for cm_idx in objsD.keys():
            cm = scn.cmlist[cm_idx]
            # get bricksDict from cache
            bricksDict, _ = getBricksDict(cm=cm)
            # add to bricksDicts
            self.bricksDicts[cm_idx] = bricksDict

    ###################################################
    # class variables

    # variables
    bricksDicts = {}

    # properties
    side = bpy.props.EnumProperty(
        items=(("TOP", "Top", ""),
               ("BOTTOM", "Bottom", ""),
               ("BOTH", "Both", ""),),
        default="TOP")

    #############################################

class drawAdjacent(Operator):
    """Draw brick to one side of active brick"""
    bl_idname = "rebrickr.draw_adjacent"
    bl_label = "Draw Adjacent Bricks"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        active_obj = scn.objects.active
        # check active object is not None
        if active_obj is None:
            return False
        # check that active_object is brick
        if not active_obj.isBrick:
            return False
        return True

    def execute(self, context):
        try:
            # store enabled/disabled values
            createAdjBricks = [self.xPos, self.xNeg, self.yPos, self.yNeg, self.zPos, self.zNeg]
            # if no sides were and are selected, don't execute (i.e. if only brick type changed)
            shouldRun = False
            for i in range(6):
                if createAdjBricks[i] or self.adjBricksCreated[i][0]:
                    shouldRun = True
            if not shouldRun:
                return {"CANCELLED"}
            # push to undo stack
            self.undo_stack.matchPythonToBlenderState()
            if self.orig_undo_stack_length == self.undo_stack.getLength():
                self.undo_stack.undo_push('draw_adjacent')
            # initialize variables
            scn = bpy.context.scene
            scn.update()
            cm = scn.cmlist[scn.cmlist_index]
            self.undo_stack.iterateStates(cm)
            obj = scn.objects.active
            initial_active_obj_name = obj.name
            keysToMerge = []

            # get dict key details of current obj
            dictKey, dictLoc = getDictKey(obj.name)
            x0,y0,z0 = dictLoc
            # get size of current brick (e.g. [2, 4, 1])
            objSize = self.bricksDict[dictKey]["size"]

            zStep = getZStep(cm)
            decriment = 0
            dimensions = Bricks.get_dimensions(cm.brickHeight, zStep, cm.gap)
            # check all 6 directions for action to be executed
            for i in range(6):
                # if checking beneath obj in 'Bricks and Plates', check 3 keys below instead of 1 key below
                if i == 5 and cm.brickType == "Bricks and Plates":
                    newBrickHeight = self.getNewBrickHeight()
                    decriment = newBrickHeight - 1
                # if action should be executed (value changed in direction prop)
                if (createAdjBricks[i] or (not createAdjBricks[i] and self.adjBricksCreated[i][0])):
                    # add or remove bricks in all adjacent locations in current direction
                    for j,adjDictLoc in enumerate(self.adjDKLs[i]):
                        if decriment != 0:
                            adjDictLoc = adjDictLoc.copy()
                            adjDictLoc[2] -= decriment
                        self.toggleBrick(cm, dimensions, adjDictLoc, dictKey, objSize, i, j, keysToMerge, addBrick=createAdjBricks[i])
                    # after ALL bricks toggled, check exposure of bricks above and below new ones
                    for j,adjDictLoc in enumerate(self.adjDKLs[i]):
                        self.bricksDict = verifyBrickExposureAboveAndBelow(adjDictLoc.copy(), self.bricksDict, decriment=decriment, zNeg=self.zNeg, zPos=self.zPos)

            # recalculate val for each bricksDict key in original brick
            for x in range(x0, x0 + objSize[0]):
                for y in range(y0, y0 + objSize[1]):
                    for z in range(z0, z0 + objSize[2], zStep):
                        curKeyLoc = [x, y, z]
                        setCurBrickVal(self.bricksDict, curKeyLoc)

            # attempt to merge created bricks
            keysToUpdate = mergeBricks.mergeBricks(self.bricksDict, keysToMerge, cm, mergeVertical=self.brickType == "BRICK")

            # if bricks created on top, set top_exposed of original brick to False
            if self.zPos:
                self.bricksDict[dictKey]["top_exposed"] = False
                keysToUpdate.append(dictKey)
                delete(obj)
            # if bricks created on bottom, set top_exposed of original brick to False
            if self.zNeg:
                self.bricksDict[dictKey]["bot_exposed"] = False
                if not self.zPos:
                    keysToUpdate.append(dictKey)
                    delete(obj)

            # draw created bricks
            drawUpdatedBricks(cm, self.bricksDict, keysToUpdate, selectCreated=False)

            # select original brick
            orig_obj = bpy.data.objects.get(initial_active_obj_name)
            if orig_obj: select(orig_obj, active=orig_obj)

            # model is now customized
            cm.customized = True
        except:
            handle_exception()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)

    ################################################
    # initialization method

    def __init__(self):
        try:
            self.undo_stack = UndoStack.get_instance()
            self.orig_undo_stack_length = self.undo_stack.getLength()
            scn = bpy.context.scene
            cm = scn.cmlist[scn.cmlist_index]
            obj = scn.objects.active

            # initialize self.bricksDict
            self.bricksDict, _ = getBricksDict(cm=cm)

            # initialize direction bools
            self.zPos = False
            self.zNeg = False
            self.yPos = False
            self.yNeg = False
            self.xPos = False
            self.xNeg = False

            # initialize vars for self.adjDKLs setup
            dictKey, dictLoc = getDictKey(obj.name)
            x,y,z = dictLoc
            objSize = self.bricksDict[dictKey]["size"]
            zStep = getZStep(cm)
            self.adjDKLs = [[],[],[],[],[],[]]
            # set up self.adjDKLs
            for y0 in range(y, y + objSize[1]):
                for z0 in range(z, z + (objSize[2]//zStep)):
                    dkl = [x + objSize[0], y0, z0]
                    self.adjDKLs[0].append(dkl)
            for y0 in range(y, y + objSize[1]):
                for z0 in range(z, z + (objSize[2]//zStep)):
                    dkl = [x - 1, y0, z0]
                    self.adjDKLs[1].append(dkl)
            for x0 in range(x, x + objSize[0]):
                for z0 in range(z, z + (objSize[2]//zStep)):
                    dkl = [x0, y + objSize[1], z0]
                    self.adjDKLs[2].append(dkl)
            for x0 in range(x, x + objSize[0]):
                for z0 in range(z, z + (objSize[2]//zStep)):
                    dkl = [x0, y - 1, z0]
                    self.adjDKLs[3].append(dkl)
            for x0 in range(x, x + objSize[0]):
                for y0 in range(y, y + objSize[1]):
                    if cm.brickType == "Bricks and Plates":
                        dkl = [x0, y0, z + objSize[2]]
                    else:
                        dkl = [x0, y0, z + 1]
                    self.adjDKLs[4].append(dkl)
            for x0 in range(x, x + objSize[0]):
                for y0 in range(y, y + objSize[1]):
                    dkl = [x0, y0, z - 1]
                    self.adjDKLs[5].append(dkl)

            # initialize self.adjBricksCreated
            self.adjBricksCreated = []
            for i in range(6):
                self.adjBricksCreated.append([False]*len(self.adjDKLs[i]))
        except:
            handle_exception()

    ###################################################
    # class variables

    # vars
    bricksDict = {}
    adjDKLs = []

    # get items for brickType prop
    def get_items1(self, context):
        scn = bpy.context.scene
        obj = scn.objects.active
        if obj is None: return [("NULL", "Null", "")]
        cm = scn.cmlist[scn.cmlist_index]
        bricksDict, _ = getBricksDict(cm=cm)
        dictKey,_ = getDictKey(obj.name)
        # build items
        if bricksDict[dictKey]["size"][2] == 3:
            items = [("BRICK", "Brick", "")]
            if "Plates" in cm.brickType:
                items.append(("PLATE", "Plate", ""))
        elif bricksDict[dictKey]["size"][2] == 1:
            items = [("PLATE", "Plate", "")]
            if "Bricks" in cm.brickType and "BRICK" not in items:
                items.append(("BRICK", "Brick", ""))
        return items

    # define props for popup
    brickType = bpy.props.EnumProperty(
        name="Brick Type",
        description="Type of brick to draw adjacent to current brick",
        items=get_items1,
        default=None)
    zPos = bpy.props.BoolProperty(name="+Z (Top)", default=False)
    zNeg = bpy.props.BoolProperty(name="-Z (Bottom)", default=False)
    xPos = bpy.props.BoolProperty(name="+X (Front)", default=False)
    xNeg = bpy.props.BoolProperty(name="-X (Back)", default=False)
    yPos = bpy.props.BoolProperty(name="+Y (Right)", default=False)
    yNeg = bpy.props.BoolProperty(name="-Y (Left)", default=False)

    #############################################
    # class methods

    def setDirBool(self, idx, val):
        if idx == 0: self.xPos = val
        elif idx == 1: self.xNeg = val
        elif idx == 2: self.yPos = val
        elif idx == 3: self.yNeg = val
        elif idx == 4: self.zPos = val
        elif idx == 5: self.zNeg = val

    def getBrickD(self, dkl):
        """ set up adjBrickD """
        adjacent_key = listToStr(dkl)
        try:
            brickD = self.bricksDict[adjacent_key]
            return adjacent_key, brickD
        except:
            return adjacent_key, False

    def getNewBrickHeight(self):
        newBrickHeight = 1 if self.brickType == "PLATE" else 3
        return newBrickHeight

    def getNewCoord(self, co, dimensions, side):
        co = list(co)
        if side == 0:
            co[0] += dimensions["width"]
        if side == 1:
            co[0] -= dimensions["width"]
        if side == 2:
            co[1] += dimensions["width"]
        if side == 3:
            co[1] -= dimensions["width"]
        if side == 4:
            co[2] += dimensions["height"]
        if side == 5:
            co[2] -= dimensions["height"]
        return co

    def isBrickAlreadyCreated(self, brickNum, side):
        return not (brickNum == len(self.adjDKLs[side]) - 1 and
                    not any(self.adjBricksCreated[side])) # evaluates True if all values in this list are False

    def toggleBrick(self, cm, dimensions, adjDictLoc, dictKey, objSize, side, brickNum, keysToMerge, addBrick=True):
        # if brick height is 3 and 'Bricks and Plates'
        newBrickHeight = self.getNewBrickHeight()
        if cm.brickType == "Bricks and Plates" and newBrickHeight == 3:
            checkTwoMoreAbove = True
        else:
            checkTwoMoreAbove = False

        adjacent_key, adjBrickD = self.getBrickD(adjDictLoc)

        # if key doesn't exist in bricksDict, create it
        if not adjBrickD:
            n = cm.source_name
            cm.numBricksGenerated += 1
            j = cm.numBricksGenerated
            zStep = getZStep(cm)
            newDictLoc = adjDictLoc.copy()
            if side == 0:
                newDictLoc[0] = newDictLoc[0] - 1
            elif side == 1:
                newDictLoc[0] = newDictLoc[0] + 1
            elif side == 2:
                newDictLoc[1] = newDictLoc[1] - 1
            elif side == 3:
                newDictLoc[1] = newDictLoc[1] + 1
            elif side == 4:
                newDictLoc[2] = newDictLoc[2] - 1
            elif side == 5:
                newDictLoc[2] = newDictLoc[2] + 1
            theKey = listToStr(newDictLoc)
            co = self.bricksDict[theKey]["co"]
            co = self.getNewCoord(co, dimensions, side)
            self.bricksDict[adjacent_key] = createBricksDictEntry(
                name=         'Rebrickr_%(n)s_brick_%(j)s__%(adjacent_key)s' % locals(),
                co=           co,
                nearest_face= self.bricksDict[dictKey]["nearest_face"],
                mat_name=     self.bricksDict[dictKey]["mat_name"],
            )
            adjBrickD = self.bricksDict[adjacent_key]
            # self.report({"WARNING"}, "Matrix not available at the following location: %(adjacent_key)s" % locals())
            # self.setDirBool(side, False)
            # return False

        # if brick exists there
        if adjBrickD["draw"] and not (addBrick and self.adjBricksCreated[side][brickNum]):
            # if attempting to add brick
            if addBrick:
                # reset direction bool if no bricks could be added
                if not self.isBrickAlreadyCreated(brickNum, side):
                    self.setDirBool(side, False)
                self.report({"INFO"}, "Brick already exists in the following location: %(adjacent_key)s" % locals())
                return False
            # if attempting to remove brick
            else:
                adjBrickD["draw"] = False
                adjBrickD["val"] = 0 # TODO: set val to 0 only if adjacent to another outside brick (else set to inside (-1?))
                adjBrickD["size"] = None
                adjBrickD["parent_brick"] = None
                adjBrickD["bot_exposed"] = None
                adjBrickD["top_exposed"] = None
                brick = bpy.data.objects.get(adjBrickD["name"])
                if brick: delete(brick)
                self.adjBricksCreated[side][brickNum] = False
                return True
        # if brick doesn't exist there
        else:
            # if attempting to add brick
            if addBrick:
                if checkTwoMoreAbove:
                    # verify two more locs available above current
                    adjDictLoc0 = adjDictLoc.copy()
                    for i in range(1, 3):
                        adjDictLoc0[2] += 1
                        nextKey,nextBrickD = self.getBrickD(adjDictLoc0)
                        if not nextBrickD:
                            self.setDirBool(side, False)
                        # if brick drawn in next loc and not just rerunning based on new direction selection
                        elif (nextBrickD["draw"] and
                              (not self.isBrickAlreadyCreated(brickNum, side) or
                               self.adjBricksCreated[side][brickNum] != self.brickType)):
                            self.report({"INFO"}, "Brick already exists in the following location: %(nextKey)s" % locals())
                            self.setDirBool(side, False)
                        else:
                            continue
                        # reset values at failed location, in case brick was previously drawn there
                        self.adjBricksCreated[side][brickNum] = False
                        adjBrickD["draw"] = False
                        return False

                adjBrickD["draw"] = True
                setCurBrickVal(self.bricksDict, strToList(adjacent_key))
                adjBrickD["mat_name"] = self.bricksDict[dictKey]["mat_name"]
                adjBrickD["size"] = [1, 1, newBrickHeight]
                adjBrickD["parent_brick"] = "self"
                topExposed, botExposed = getBrickExposure(cm, self.bricksDict, adjacent_key)
                adjBrickD["top_exposed"] = topExposed
                adjBrickD["bot_exposed"] = botExposed
                keysToMerge.append(adjacent_key)
                self.adjBricksCreated[side][brickNum] = self.brickType
                if checkTwoMoreAbove:
                    # update matrix for two locations above adjacent_key
                    adjDictLoc0 = adjDictLoc.copy()
                    for i in range(1, 3):
                        adjDictLoc0[2] += 1
                        nextKey,nextBrickD = self.getBrickD(adjDictLoc0)
                        nextBrickD["draw"] = True
                        setCurBrickVal(self.bricksDict, strToList(nextKey))
                        nextBrickD["mat_name"] = self.bricksDict[dictKey]["mat_name"]
                        nextBrickD["parent_brick"] = adjacent_key
                        keysToMerge.append(nextKey)

                return True
            # if attempting to remove brick
            else:
                self.report({"INFO"}, "Brick does not exist in the following location: %(adjacent_key)s" % locals())
                return False

    #############################################

class changeBrickType(Operator):
    """change brick type of active brick"""
    bl_idname = "rebrickr.change_brick_type"
    bl_label = "Change Brick Type"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        active_obj = scn.objects.active
        # check active object is not None
        if active_obj is None:
            return False
        # check that active_object is brick
        if not active_obj.isBrick:
            return False
        # get cmlist item referred to by object
        cm = getItemByID(scn.cmlist, active_obj.cmlist_id)
        # confirm that active_obj brickType is not CUSTOM
        if cm.lastBrickType == "Custom":
            return False
        return True

    def execute(self, context):
        try:
            self.undo_stack.matchPythonToBlenderState()
            if self.orig_undo_stack_length == self.undo_stack.getLength():
                self.undo_stack.undo_push('change_type')
            scn = bpy.context.scene
            cm = scn.cmlist[self.cm_idx]
            self.undo_stack.iterateStates(cm)
            obj = scn.objects.active
            initial_active_obj_name = obj.name if obj else ""

            # get dict key details of current obj
            dictKey, dictLoc = getDictKey(obj.name)
            x0,y0,z0 = dictLoc
            # get size of current brick (e.g. [2, 4, 1])
            objSize = self.bricksDict[dictKey]["size"]

            # skip bricks that are already of type self.brickType
            if (self.bricksDict[dictKey]["type"] == self.brickType and
                self.bricksDict[dictKey]["flipped"] == self.flipBrick and
                self.bricksDict[dictKey]["rotated"] == self.rotateBrick):
                return {"CANCELLED"}

            # turn 1x1 & 1x2 plates into slopes
            if (self.brickType == "SLOPE" and
               objSize[2] == 1 and
               objSize[0] + objSize[1] in [2, 3]):
                self.report({"INFO"}, "turn 1x1 & 1x2 plates into slopes")
            # turn 1x2 & 1x3 bricks into inverted slopes
            elif (self.brickType == "SLOPE_INVERTED" and
                 objSize[2] == 3 and
                 ((objSize[0] == 1 and objSize[1] in [2, 3]) or
                  (objSize[1] == 1 and objSize[0] in [2, 3]))):
                self.report({"INFO"}, "turn 1x2 & 1x3 bricks into inverted slopes")
            # turn 1x2 & 1x3 bricks into slopes
            elif (self.brickType == "SLOPE" and
                  objSize[2] == 3 and
                  (sum(objSize[:2]) in range(3,8))):
                self.report({"INFO"}, "turn 1x2, 1x3, 1x4, 1x6, 2x2, 2x3, 2x4, and 3x4 bricks into slopes")
            # turn plates into tiles
            elif (self.brickType == "TILE" and
                  objSize[2] == 1):
                self.report({"INFO"}, "turn plates into tiles")
            # turn 1x1 plates into studs
            elif ("STUD" in self.brickType and
                  objSize[0] + objSize[1] == 2 and
                  objSize[2] == 1):
                self.report({"INFO"}, "turn 1x1 plates into studs")
            # turn 1x1 bricks into cylinders/cones
            elif (self.brickType in ["CYLINDER", "CONE"] and
                  objSize[0] + objSize[1] == 2 and
                  objSize[2] == 3):
                self.report({"INFO"}, "turn 1x1 bricks into " + self.brickType.lower() + "s")
            # skip anything else
            else:
                return {"CANCELLED"}

            # set type of parent_brick to self.brickType
            self.bricksDict[dictKey]["type"] = self.brickType
            self.bricksDict[dictKey]["flipped"] = self.flipBrick
            self.bricksDict[dictKey]["rotated"] = self.rotateBrick
            brickSize = self.bricksDict[dictKey]["size"]
            keysToUpdate = [dictKey]
            for x in range(brickSize[0]):
                for y in range(brickSize[1]):
                    curLoc = [x0 + x, y0 + y, z0]
                    self.bricksDict = verifyBrickExposureAboveAndBelow(curLoc, self.bricksDict)
                    for i in [1, -1]:
                        k0 = listToStr([curLoc[0], curLoc[1], z0 + i])
                        if k0 not in self.bricksDict:
                            continue
                        parent_key = k0 if self.bricksDict[k0]["parent_brick"] == "self" else self.bricksDict[k0]["parent_brick"]
                        if parent_key not in keysToUpdate and parent_key is not None:
                            keysToUpdate.append(parent_key)

            # delete objects to be updated
            for k1 in keysToUpdate:
                obj0 = bpy.data.objects.get(self.bricksDict[k1]["name"])
                if obj0 is not None:
                    delete(obj0)
            # draw updated brick
            drawUpdatedBricks(cm, self.bricksDict, keysToUpdate, selectCreated=False)
            # select original brick
            orig_obj = bpy.data.objects.get(initial_active_obj_name)
            if orig_obj: select(orig_obj, active=orig_obj, only=False)
            # model is now customized
            cm.customized = True
        except:
            handle_exception()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)

    ################################################
    # initialization method

    def __init__(self):
        try:
            self.undo_stack = UndoStack.get_instance()
            scn = bpy.context.scene
            self.orig_undo_stack_length = self.undo_stack.getLength()
            obj = scn.objects.active
            cm = scn.cmlist[scn.cmlist_index]
            # get cmlist item referred to by object
            cm = getItemByID(scn.cmlist, obj.cmlist_id)
            # get bricksDict from cache
            self.bricksDict, _ = getBricksDict(cm=cm)
            dictKey, dictLoc = getDictKey(obj.name)
            self.cm_idx = cm.idx
            curBrickType = self.bricksDict[dictKey]["type"]
            self.brickType = curBrickType if curBrickType is not None else "STANDARD"
            self.flipBrick = self.bricksDict[dictKey]["flipped"]
            self.rotateBrick = self.bricksDict[dictKey]["rotated"]
        except:
            handle_exception()

    ###################################################
    # class variables

    # vars
    bricksDict = {}
    cm_idx = -1

    # get items for brickType prop
    def get_items(self, context):
        scn = bpy.context.scene
        obj = scn.objects.active
        if obj is None: return []
        cm = scn.cmlist[scn.cmlist_index]
        items = [("STANDARD", "Standard", "")]

        dictKey, dictLoc = getDictKey(obj.name)
        bricksDict, _ = getBricksDict(cm=cm)
        objSize = bricksDict[dictKey]["size"]
        # Bricks
        if objSize[2] == 3:
            if (objSize[2] == 3 and (sum(objSize[:2]) in range(3,8))):
                items.append(("SLOPE", "Slope", ""))
            # if sum(objSize[:2]) in range(3,6):
            #     items.append(("SLOPE_INVERTED", "Slope Inverted", ""))
            if sum(objSize[:2]) == 2:
                items.append(("CYLINDER", "Cylinder", ""))
                items.append(("CONE", "Cone", ""))
            #     items.append(("BRICK_STUD_ON_ONE_SIDE", "Brick Stud on One Side", ""))
            #     items.append(("BRICK_INSET_STUD_ON_ONE_SIDE", "Brick Stud on One Side", ""))
            #     items.append(("BRICK_STUD_ON_TWO_SIDES", "Brick Stud on Two Sides", ""))
            #     items.append(("BRICK_STUD_ON_ALL_SIDES", "Brick Stud on All Sides", ""))
            # if sum(objSize[:2]) == 3:
            #     items.append(("TILE_WITH_HANDLE", "Tile with Handle", ""))
            #     items.append(("BRICK_PATTERN", "Brick Pattern", ""))
            # if objSize[0] == 2 and objSize[1] == 2:
            #     items.append(("DOME", "Dome", ""))
            #     items.append(("DOME_INVERTED", "Dome Inverted", ""))
        # # Plates
        elif objSize[2] == 1:
            if objSize[2] == 1:
                items.append(("STUD", "Stud", ""))
                items.append(("STUD_HOLLOW", "Stud (hollow)", ""))
        #         items.append(("ROUNDED_TILE", "Rounded Tile", ""))
        #     if objSize[:2] in bpy.props.Rebrickr_legal_brick_sizes[0.9]:
        #         items.append(("TILE", "Tile", ""))
        #     if sum(objSize[:2]) == 3:
        #         items.append(("TILE_GRILL", "Tile Grill", ""))
        #     if objSize[0] == 2 and objSize[1] == 2:
        #         items.append(("TILE_ROUNDED", "Tile Rounded", ""))
        #         items.append(("PLATE_ROUNDED", "Plate Rounded", ""))
        #         items.append(("DOME", "Dome", ""))
        #     if ((objSize[0] == 2 and objSize[1] in [3,4]) or
        #        (objSize[1] == 2 and objSize[0] in [3,4]) or
        #        (objSize[0] == 3 and objSize[1] in [6,8,12]) or
        #        (objSize[1] == 3 and objSize[0] in [6,8,12]) or
        #        (objSize[0] == 4 and objSize[1] == 4) or
        #        (objSize[0] == 6 and objSize[1] == 12) or
        #        (objSize[1] == 6 and objSize[0] == 12) or
        #        (objSize[0] == 7 and objSize[1] == 12) or
        #        (objSize[1] == 7 and objSize[0] == 12)):
        #         items.append(("WING", "Wing", ""))
        # 1x2 brick pattern Brick
        return items


    # properties
    brickType = bpy.props.EnumProperty(
        name="Brick Type",
        description="Choose what type of brick should be drawn at this location",
        items=get_items,
        default=None)
    flipBrick = bpy.props.BoolProperty(
        name="Flip Brick Orientation",
        description="Flip the brick about the non-mirrored axis",
        default=False)
    rotateBrick = bpy.props.BoolProperty(
        name="Rotate 90 Degrees",
        description="Rotate the brick about the Z axis (brick width & depth must be equivalent)",
        default=False)

    #############################################

class redrawBricks(Operator):
    """redraw selected bricks from bricksDict"""
    bl_idname = "rebrickr.redraw_bricks"
    bl_label = "Redraw Bricks"
    bl_options = {"REGISTER", "UNDO"}

    ################################################
    # Blender Operator methods

    @classmethod
    def poll(self, context):
        """ ensures operator can execute (if not, returns False) """
        scn = bpy.context.scene
        objs = bpy.context.selected_objects
        # check that at least 1 selected object is a brick
        for obj in objs:
            if obj.isBrick:
                return True
        return False

    def execute(self, context):
        try:
            scn = bpy.context.scene
            selected_objects = bpy.context.selected_objects
            active_obj = scn.objects.active
            initial_active_obj_name = active_obj.name if active_obj else ""

            # initialize objsD (key:cm_idx, val:list of brick objects)
            objsD = createObjsD(selected_objects)

            # iterate through keys in objsD
            for cm_idx in objsD.keys():
                cm = scn.cmlist[cm_idx]
                # get bricksDict from cache
                bricksDict, _ = getBricksDict(cm=cm)
                keysToUpdate = []

                # delete objects to be updated
                for obj in objsD[cm_idx]:
                    delete(obj)

                # add keys for updated objects to simple bricksDict for drawing
                keysToUpdate = [getDictKey(obj.name)[0] for obj in objsD[cm_idx]]

                # draw modified bricks
                drawUpdatedBricks(cm, bricksDict, keysToUpdate)

            # select original brick
            orig_obj = bpy.data.objects.get(initial_active_obj_name)
            if orig_obj: select(orig_obj, active=orig_obj, only=False)
        except:
            handle_exception()
        return {"FINISHED"}

    ################################################
    # initialization method

    def __init__(self):
        pass

    #############################################
