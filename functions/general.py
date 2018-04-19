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
import collections
import json
import math
import numpy as np

# Blender imports
import bpy
from mathutils import Vector, Euler, Matrix
from bpy.types import Object

# Addon imports
from .common import *


def getSafeScn():
    safeScn = bpy.data.scenes.get("Bricker_storage (DO NOT MODIFY)")
    if safeScn == None:
        safeScn = bpy.data.scenes.new("Bricker_storage (DO NOT MODIFY)")
    return safeScn


def getActiveContextInfo(cm_idx=None):
    scn = bpy.context.scene
    cm_idx = cm_idx or scn.cmlist_index
    cm = scn.cmlist[cm_idx]
    n = cm.source_name
    return scn, cm, n


def ensureObjNamesUnique(scn, throwError=False):
    cm = getActiveContextInfo()[1]
    # for object in scene
    for obj_name in scn.objects.keys():
        if obj_name != cm.source_name:
            continue
        elif throwError:
            raise Exception("[Bricker] ")
            break
        # rename object if not part of a model or animation
        obj = bpy.data.objects.get(obj_name)
        if obj: obj.name = "%(obj_name)s.001" % locals()


def safeUnlink(obj, hide=True, protect=True):
    scn = bpy.context.scene
    safeScn = getSafeScn()
    try:
        scn.objects.unlink(obj)
    except RuntimeError:
        pass
    safeScn.objects.link(obj)
    obj.protected = protect
    if hide:
        obj.hide = True


def safeLink(obj, unhide=False, protect=False):
    scn = bpy.context.scene
    safeScn = getSafeScn()
    scn.objects.link(obj)
    obj.protected = protect
    if unhide:
        obj.hide = False
    try:
        safeScn.objects.unlink(obj)
    except RuntimeError:
        pass


def getBoundsBF(obj):
    """ brute force method for obtaining object bounding box """
    # initialize min and max
    min = Vector((math.inf, math.inf, math.inf))
    max = Vector((-math.inf, -math.inf, -math.inf))
    # calculate min and max verts
    for v in obj.data.vertices:
        if v.co.x > max.x:
            max.x = v.co.x
        elif v.co.x < min.x:
            min.x = v.co.x
        if v.co.y > max.y:
            max.y = v.co.y
        elif v.co.y < min.y:
            min.y = v.co.y
        if v.co.z > max.z:
            max.z = v.co.z
        elif v.co.z < min.z:
            min.z = v.co.z
    # set up bounding box list of coord lists
    bound_box = [list(min),
                 [min.x, min.y, min.z],
                 [min.x, min.y, max.z],
                 [min.x, max.y, max.z],
                 [min.x, max.y, min.z],
                 [max.x, min.y, min.z],
                 [max.y, min.y, max.z],
                 list(max),
                 [max.x, max.y, min.z]]
    return bound_box


def bounds(obj, local=False, use_adaptive_domain=True):
    """
    returns object details with the following subattribute Vectors:

    .max : maximum value of object
    .min : minimum value of object
    .mid : midpoint value of object
    .dist: distance min to max

    """

    local_coords = getBoundsBF(obj) if is_smoke(obj) and is_adaptive(obj) and not use_adaptive_domain else obj.bound_box[:]
    om = obj.matrix_world

    if not local:
        worldify = lambda p: om * Vector(p[:])
        coords = [worldify(p).to_tuple() for p in local_coords]
    else:
        coords = [p[:] for p in local_coords]

    rotated = zip(*coords[::-1])
    getMax = lambda i: max([co[i] for co in coords])
    getMin = lambda i: min([co[i] for co in coords])

    info = lambda: None
    info.max = Vector((getMax(0), getMax(1), getMax(2)))
    info.min = Vector((getMin(0), getMin(1), getMin(2)))
    info.mid = (info.min + info.max) / 2
    info.dist = info.max - info.min

    return info


def getAnimAdjustedFrame(cm, frame):
    if frame < cm.lastStartFrame:
        curFrame = cm.lastStartFrame
    elif frame > cm.lastStopFrame:
        curFrame = cm.lastStopFrame
    else:
        curFrame = frame
    return curFrame


def setObjOrigin(obj, loc):
    # TODO: Speed up this function by not using the ops call
    # for v in obj.data.vertices:
    #     v.co += obj.location - loc
    # obj.location = loc
    scn = bpy.context.scene
    old_loc = tuple(scn.cursor_location)
    scn.cursor_location = loc
    select(obj, active=True, only=True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    scn.cursor_location = old_loc


def setOriginToObjOrigin(toObj, fromObj=None, fromLoc=None, deleteFromObj=False):
    assert fromObj or fromLoc
    setObjOrigin(toObj, fromObj.matrix_world.to_translation().to_tuple() if fromObj else fromLoc)
    if fromObj:
        if deleteFromObj:
            m = fromObj.data
            bpy.data.objects.remove(fromObj, True)
            bpy.data.meshes.remove(m)


def getBricks(cm=None, typ=None):
    """ get bricks in 'cm' model """
    cm = cm or getActiveContextInfo()[1]
    typ = typ or ("MODEL" if cm.modelCreated else "ANIM")
    n = cm.source_name
    if typ == "MODEL":
        gn = "Bricker_%(n)s_bricks" % locals()
        bGroup = bpy.data.groups[gn]
        bricks = list(bGroup.objects)
    elif typ == "ANIM":
        bricks = []
        for cf in range(cm.lastStartFrame, cm.lastStopFrame+1):
            gn = "Bricker_%(n)s_bricks_f_%(cf)s" % locals()
            bGroup = bpy.data.groups.get(gn)
            if bGroup:
                bricks += list(bGroup.objects)
    return bricks


def getMatObject(cm=None, typ="RANDOM"):
    cm = cm or getActiveContextInfo()[1]
    n = cm.id
    Bricker_mat_on = "Bricker_%(n)s_%(typ)s_mats" % locals()
    matObj = bpy.data.objects.get(Bricker_mat_on)
    return matObj


def getBrickTypes(height):
    return bpy.props.Bricker_legal_brick_sizes[height].keys()


def flatBrickType(cm):
    return "PLATE" in cm.brickType or "STUD" in cm.brickType


def mergableBrickType(cm=None, typ=None, up=False):
    if typ is not None:
        return typ in ["PLATE", "BRICK", "SLOPE"] or (up and typ == "CYLINDER")
    elif cm is not None:
        return "PLATE" in cm.brickType or "BRICK" in cm.brickType or "SLOPE" in cm.brickType or (up and ("CYLINDER" in cm.brickType))
    else:
        return False


def getTallType(cm, brickD, targetType=None):
    return targetType if targetType in getBrickTypes(height=3) else (brickD["type"] if brickD["type"] in getBrickTypes(height=3) else "BRICK")


def getShortType(cm, brickD, targetType=None):
    return targetType if targetType in getBrickTypes(height=1) else (brickD["type"] if brickD["type"] in getBrickTypes(height=1) else "PLATE")


def brick_materials_installed():
    scn = bpy.context.scene
    return hasattr(scn, "isBrickMaterialsInstalled") and scn.isBrickMaterialsInstalled


def brick_materials_loaded():
    scn = bpy.context.scene
    # make sure abs_plastic_materials addon is installed
    brick_mats_installed = hasattr(scn, "isBrickMaterialsInstalled") and scn.isBrickMaterialsInstalled
    if not brick_mats_installed:
        return False
    # check if any of the colors haven't been loaded
    mats = bpy.data.materials.keys()
    for color in bpy.props.abs_plastic_materials:
        if color not in mats:
            return False
    return True


def getMatrixSettings(cm=None):
    cm = cm or getActiveContextInfo()[1]
    # TODO: Maybe remove custom object names from this?
    return listToStr([cm.brickHeight, cm.gap, cm.brickType, cm.distOffset, cm.customObjectName1, cm.customObjectName2, cm.customObjectName3, cm.useNormals, cm.insidenessRayCastDir, cm.castDoubleCheckRays, cm.brickShell, cm.calculationAxes])


def matrixReallyIsDirty(cm):
    return (cm.matrixIsDirty and cm.lastMatrixSettings != getMatrixSettings()) or cm.matrixLost


def vecToStr(vec, separate_by=","):
    return listToStr(list(vec), separate_by=separate_by)


def listToStr(lst, separate_by=","):
    assert type(lst) in [list, tuple]
    return separate_by.join(map(str, lst))



def strToList(string, item_type=int, split_on=","):
    lst = string.split(split_on)
    assert type(string) is str and type(split_on) is str
    lst = list(map(item_type, lst))
    return lst


def strToTuple(string, item_type=int, split_on=","):
    tup = tuple(strToList(string, item_type, split_on))
    return tup


def isUnique(lst):
    return np.unique(lst).size == len(lst)


def getZStep(cm):
    return 1 if flatBrickType(cm) else 3


def gammaCorrect(rgba, val):
    r, g, b, a = rgba
    r = math.pow(r, val)
    g = math.pow(g, val)
    b = math.pow(b, val)
    return [r, g, b, a]


def getParentKey(bricksDict, key):
    if key not in bricksDict:
        return None
    parent_key = key if bricksDict[key]["parent"] in ["self", None] else bricksDict[key]["parent"]
    return parent_key


def createdWithUnsupportedVersion(cm):
    return cm.version[:3] != bpy.props.bricker_version[:3]


def getLocsInBrick(cm, size, key, loc=None, zStep=None):
    zStep = zStep or getZStep(cm)
    x0, y0, z0 = loc or strToList(key)
    return [[x0 + x, y0 + y, z0 + z] for z in range(0, size[2], zStep) for y in range(size[1]) for x in range(size[0])]


def getKeysInBrick(cm, size, key, loc=None, zStep=None):
    zStep = zStep or getZStep(cm)
    x0, y0, z0 = loc or strToList(key)
    return ["{x},{y},{z}".format(x=x0 + x, y=y0 + y, z=z0 + z) for z in range(0, size[2], zStep) for y in range(size[1]) for x in range(size[0])]


def isOnShell(cm, bricksDict, key, loc=None, zStep=None, shellDepth=1):
    """ check if any locations in brick are on the shell """
    size = bricksDict[key]["size"]
    brickKeys = getKeysInBrick(cm, size=size, key=key, loc=loc, zStep=zStep)
    for k in brickKeys:
        if bricksDict[k]["val"] >= 1 - (shellDepth - 1) / 100:
            return True
    return False


def getDictKey(name):
    """ get dict key details of obj """
    dictKey = name.split("__")[-1]
    return dictKey

def getDictLoc(dictKey):
    return strToList(dictKey)


def getBrickCenter(cm, bricksDict, key, loc=None, zStep=None):
    brickKeys = getKeysInBrick(cm, size=bricksDict[key]["size"], key=key, loc=loc, zStep=zStep)
    coords = [bricksDict[k0]["co"] for k0 in brickKeys]
    coord_ave = Vector((mean([co[0] for co in coords]), mean([co[1] for co in coords]), mean([co[2] for co in coords])))
    return coord_ave


def getNormalDirection(normal, maxDist=0.77):
    # initialize vars
    minDist = maxDist
    minDir = None
    # skip normals that aren't within 0.3 of the z values
    if normal is None or ((normal.z > -0.2 and normal.z < 0.2) or normal.z > 0.8 or normal.z < -0.8):
        return minDir
    # set Vectors for perfect normal directions
    normDirs = {"^X+":Vector((1, 0, 0.5)),
                "^Y+":Vector((0, 1, 0.5)),
                "^X-":Vector((-1, 0, 0.5)),
                "^Y-":Vector((0, -1, 0.5)),
                "vX+":Vector((1, 0, -0.5)),
                "vY+":Vector((0, 1, -0.5)),
                "vX-":Vector((-1, 0, -0.5)),
                "vY-":Vector((0, -1, -0.5))}
    # calculate nearest
    for dir,v in normDirs.items():
        dist = (v - normal).length
        if dist < minDist:
            minDist = dist
            minDir = dir
    return minDir


def getFlipRot(dir):
    flip = False
    rot = False
    if dir == "X-":
        flip = True
    elif dir == "Y+":
        rot = True
    elif dir == "Y-":
        flip = True
        rot = True
    return flip, rot


def legalBrickSize(s, t):
     return s[:2] in bpy.props.Bricker_legal_brick_sizes[s[2]][t]


def get_override(area_type, region_type):
    for area in bpy.context.screen.areas:
        if area.type == area_type:
            for region in area.regions:
                if region.type == region_type:
                    override = {'area': area, 'region': region}
                    return override
    #error message if the area or region wasn't found
    raise RuntimeError("Wasn't able to find", region_type," in area ", area_type,
                        "\n Make sure it's open while executing script.")


def getSpace():
    scr = bpy.context.window.screen
    v3d = [area for area in scr.areas if area.type == 'VIEW_3D'][0]
    return v3d.spaces[0]


def getExportPath(cm, fn, ext):
    cm = getActiveContextInfo()[1]
    path = cm.exportPath
    lastSlash = path.rfind("/")
    path = path[:len(path) if lastSlash == -1 else lastSlash + 1]
    blendPath = bpy.path.abspath("//") or "/tmp/"
    blendPathSplit = blendPath[:-1].split("/")
    # if relative path, construct path from user input
    if path.startswith("//"):
        splitPath = path[2:].split("/")
        while len(splitPath) > 0 and splitPath[0] == "..":
            splitPath.pop(0)
            blendPathSplit.pop()
        newPath = "/".join(splitPath)
        fullBlendPath = "/".join(blendPathSplit) if len(blendPathSplit) > 1 else "/"
        path = os.path.join(fullBlendPath, newPath)
    # if path is blank at this point, use default render location
    if path == "":
        path = blendPath
    # check to make sure path exists on local machine
    if not os.path.exists(path):
        return path, "Blender could not find the following path: '%(path)s'" % locals()
    # create full path from path and filename
    fn0 = "" if lastSlash == -1 else cm.exportPath[lastSlash + 1:len(cm.exportPath)]
    fullPath = os.path.join(path, (fn if fn0 == "" else fn0) + ext)
    # ensure target folder has write permissions
    try:
        f = open(fullPath, "w")
        f.close()
    except PermissionError:
        return path, "Blender does not have write permissions for the following path: '%(path)s'" % locals()
    return fullPath, None


def shortenName(string:str, max_len:int=30):
    """shortens string while maintaining uniqueness"""
    if len(string) <= max_len:
        return string
    else:
        return string[:math.ceil(max_len * 0.65)] + str(hash_str(string))[:math.floor(max_len * 0.35)]


def is_smoke(ob):
    if ob is None:
        return False
    for mod in ob.modifiers:
        if mod.type == "SMOKE" and mod.domain_settings and mod.show_viewport:
            return True
    return False


def is_adaptive(ob):
    if ob is None:
        return False
    for mod in ob.modifiers:
        if mod.type == "SMOKE" and mod.domain_settings and mod.domain_settings.use_adaptive_domain:
            return True
    return False

def customValidObject(cm, targetType="Custom 0", idx=None):
    for i, customInfo in enumerate([[cm.hasCustomObj1, cm.customObjectName1], [cm.hasCustomObj2, cm.customObjectName2], [cm.hasCustomObj3, cm.customObjectName3]]):
        hasCustomObj = customInfo[0]
        if idx is not None and idx != i:
            continue
        elif not hasCustomObj and not (i == 0 and cm.brickType == "CUSTOM") and int(targetType.split(" ")[-1]) != i + 1:
            continue
        customObjName = customInfo[1]
        if customObjName == "":
            warningMsg = "Custom object {} not specified.".format(i + 1)
            return warningMsg
        customObj = bpy.data.objects.get(customObjName)
        if customObj is None:
            n = customObjName
            warningMsg = "Custom brick type object '%(n)s' could not be found" % locals()
            return warningMsg
        if customObjName == cm.source_name and (not (cm.animated or cm.modelCreated) or customObj.protected):
            warningMsg = "Source object cannot be its own custom brick."
            return warningMsg
        if customObj.type != "MESH":
            warningMsg = "Custom object {} is not of type 'MESH'. Please select another object (or press 'ALT-C to convert object to mesh).".format(i + 1)
            return warningMsg
        custom_details = bounds(customObj)
        zeroDistAxes = ""
        if custom_details.dist.x < 0.00001:
            zeroDistAxes += "X"
        if custom_details.dist.y < 0.00001:
            zeroDistAxes += "Y"
        if custom_details.dist.z < 0.00001:
            zeroDistAxes += "Z"
        if zeroDistAxes != "":
            axisStr = "axis" if len(zeroDistAxes) == 1 else "axes"
            warningMsg = "Custom brick type object is to small along the '%(zeroDistAxes)s' %(axisStr)s (<0.00001). Please select another object or extrude it along the '%(zeroDistAxes)s' %(axisStr)s." % locals()
            return warningMsg
    return None


def updateHasCustomObjs(cm, typ):
    # update hasCustomObj
    if typ == "CUSTOM 1":
        cm.hasCustomObj1 = True
    if typ == "CUSTOM 2":
        cm.hasCustomObj2 = True
    if typ == "CUSTOM 3":
        cm.hasCustomObj3 = True
