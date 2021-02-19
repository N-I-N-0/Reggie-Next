#!/usr/bin/python
# -*- coding: latin-1 -*-

# Reggie Next - New Super Mario Bros. Wii Level Editor
# Milestone 4
# Copyright (C) 2009-2020 Treeki, Tempus, angelsl, JasonP27, Kamek64,
# MalStar1000, RoadrunnerWMC, AboodXD, John10v10, TheGrop, CLF78,
# Zementblock, Danster64

# This file is part of Reggie Next.

# Reggie Next is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Reggie Next is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Reggie Next.  If not, see <http://www.gnu.org/licenses/>.


# reggie.py
# This is the main executable for Reggie Next.


################################################################
################################################################

# Python version: sanity check
minimum = 3.5
import sys
import subprocess

currentRunningVersion = sys.version_info.major + (.1 * sys.version_info.minor)
if currentRunningVersion < minimum:
    errormsg = 'Please update your copy of Python to ' + str(minimum) + \
               ' or greater. Currently running on: ' + sys.version[:5]

    raise Exception(errormsg)

# Stdlib imports
import os.path
import time
import traceback
import struct

# PyQt5: import, and error msg if not installed
try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except (ImportError, NameError):
    errormsg = 'PyQt5 is not installed for this Python installation. Go online and download it.'
    raise Exception(errormsg)
Qt = QtCore.Qt

version = map(int, QtCore.QT_VERSION_STR.split('.'))
min_version = "5.4.1"
pqt_min = map(int, min_version.split('.'))
for v, c in zip(version, pqt_min):
    if c > v:
        # lower version
        errormsg = 'Please update your copy of PyQt to ' + min_version \
                 + ' or greater. Currently running on: ' + QtCore.QT_VERSION_STR

        raise Exception(errormsg) from None
    elif c < v:
        # higher version
        break

if not hasattr(QtWidgets.QGraphicsItem, 'ItemSendsGeometryChanges'):
    # enables itemChange being called on QGraphicsItem
    QtWidgets.QGraphicsItem.ItemSendsGeometryChanges = QtWidgets.QGraphicsItem.GraphicsItemFlag(0x800)

################################################################################
################################################################################
################################################################################

# Local imports
import archive
import sprites
import spritelib as SLib

import globals_

################################################################################
################################################################################
################################################################################

from libs import lh
from ui import GetIcon, SetAppStyle, GetDefaultStyle, ListWidgetWithToolTipSignal, LoadNumberFont, LoadTheme
from misc import LoadActionsLists, LoadTilesetNames, LoadBgANames, LoadBgBNames, LoadConstantLists, LoadObjDescriptions, LoadSpriteData, LoadSpriteListData, LoadEntranceNames, LoadTilesetInfo, FilesAreMissing, module_path, IsNSMBLevel, ChooseLevelNameDialog, LoadLevelNames, PreferencesDialog, LoadSpriteCategories, ZoomWidget, ZoomStatusWidget, RecentFilesMenu, SetGamePath, isValidGamePath
from misc2 import LevelScene, LevelViewWidget
from dirty import setting, setSetting, SetDirty
from gamedef import GameDefMenu, LoadGameDef
from levelitems import LocationItem, ZoneItem, ObjectItem, SpriteItem, EntranceItem, ListWidgetItem_SortsByOther, PathItem, CommentItem, PathEditorLineItem
from dialogs import AutoSavedInfoDialog, DiagnosticToolDialog, ScreenCapChoiceDialog, AreaChoiceDialog, ObjectTypeSwapDialog, ObjectTilesetSwapDialog, ObjectShiftDialog, MetaInfoDialog, AboutDialog
from background import BGDialog
from zones import ZonesDialog
from tiles import UnloadTileset, LoadTileset, LoadOverrides
from area import AreaOptionsDialog
from level import Level_NSMBW
from sidelists import Stamp, StampChooserWidget, SpriteList, SpritePickerWidget, ObjectPickerWidget, LevelOverviewWidget
from spriteeditor import SpriteEditorWidget
from editors import LocationEditorWidget, PathNodeEditorWidget, EntranceEditorWidget
from undo import UndoStack
from translation import LoadTranslation

################################################################################
################################################################################
################################################################################

def _excepthook(*exc_info):
    """
    Custom unhandled exceptions handler
    """
    separator = '-' * 80
    logFile = "log.txt"
    notice = \
        """An unhandled exception occurred. Please report the problem """\
        """in the Horizon Discord server.\n"""\
        """A log will be written to "%s"."""\
        """\n\nError information:\n""" % logFile

    timeString = time.strftime("%Y-%m-%d, %H:%M:%S")

    e = "".join(traceback.format_exception(*exc_info))
    sections = [separator, timeString, separator, e]
    msg = '\n'.join(sections)

    globals_.ErrMsg += msg

    try:
        with open(logFile, "w") as f:
            f.write(globals_.ErrMsg)

    except IOError:
        pass

    errorbox = QtWidgets.QMessageBox()
    errorbox.setText(notice + msg)
    errorbox.exec_()

    # global globals_.DirtyOverride
    globals_.DirtyOverride = 0


# Override the exception handler with ours
sys.excepthook = _excepthook

################################################################################
################################################################################
################################################################################

class ReggieWindow(QtWidgets.QMainWindow):
    """
    Reggie main level editor window
    """

    def CreateAction(self, shortname, function, icon, text, statustext, shortcut, toggle=False):
        """
        Helper function to create an action
        """

        if icon is not None:
            act = QtWidgets.QAction(icon, text, self)
        else:
            act = QtWidgets.QAction(text, self)

        if shortcut is not None: act.setShortcut(shortcut)
        if statustext is not None: act.setStatusTip(statustext)
        if toggle:
            act.setCheckable(True)
        if function is not None: act.triggered.connect(function)

        self.actions[shortname] = act

    def __init__(self):
        """
        Editor window constructor
        """
        # global globals_.Initializing
        globals_.Initializing = True

        # Reggie Version number goes below here. 64 char max (32 if non-ascii).
        self.ReggieInfo = globals_.ReggieID

        self.ZoomLevels = [7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0,
                           85.0, 90.0, 95.0, 100.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 350.0, 400.0]

        # add the undo stack object
        self.undoStack = UndoStack()

        # required variables
        self.UpdateFlag = False
        self.SelectionUpdateFlag = False
        self.selObj = None
        self.CurrentSelection = []

        # set up the window
        QtWidgets.QMainWindow.__init__(self, None)
        self.setWindowTitle('Reggie! Next Level Editor %s' % globals_.ReggieVersionShort)
        self.setWindowIcon(QtGui.QIcon('reggiedata/icon.png'))
        self.setIconSize(QtCore.QSize(16, 16))
        self.setUnifiedTitleAndToolBarOnMac(True)

        # create the level view
        self.scene = LevelScene(0, 0, 1024 * 24, 512 * 24, self)
        self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        self.scene.selectionChanged.connect(self.ChangeSelectionHandler)

        self.view = LevelViewWidget(self.scene, self)
        self.view.centerOn(0, 0)  # this scrolls to the top left
        self.view.PositionHover.connect(self.PositionHovered)
        self.view.XScrollBar.valueChanged.connect(self.XScrollChange)
        self.view.YScrollBar.valueChanged.connect(self.YScrollChange)
        self.view.FrameSize.connect(self.HandleWindowSizeChange)

        # done creating the window!
        self.setCentralWidget(self.view)

        # set up the clipboard stuff
        self.clipboard = None
        self.systemClipboard = QtWidgets.QApplication.clipboard()
        self.systemClipboard.dataChanged.connect(self.TrackClipboardUpdates)

        # we might have something there already, activate Paste if so
        self.TrackClipboardUpdates()

    def __init2__(self):
        """
        Finishes initialization. (fixes bugs with some widgets calling globals_.mainWindow.something before it's init'ed)
        """

        self.AutosaveTimer = QtCore.QTimer()
        self.AutosaveTimer.timeout.connect(self.Autosave)
        self.AutosaveTimer.start(20000)

        # set up actions and menus
        self.SetupActionsAndMenus()

        # set up the status bar
        self.posLabel = QtWidgets.QLabel()
        self.selectionLabel = QtWidgets.QLabel()
        self.hoverLabel = QtWidgets.QLabel()
        self.statusBar().addWidget(self.posLabel)
        self.statusBar().addWidget(self.selectionLabel)
        self.statusBar().addWidget(self.hoverLabel)
        #self.diagnostic = DiagnosticWidget()
        self.ZoomWidget = ZoomWidget()
        self.ZoomStatusWidget = ZoomStatusWidget()
        #self.statusBar().addPermanentWidget(self.diagnostic)
        self.statusBar().addPermanentWidget(self.ZoomWidget)
        self.statusBar().addPermanentWidget(self.ZoomStatusWidget)

        # create the various panels
        self.SetupDocksAndPanels()

        # now get stuff ready
        loaded = False

        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and IsNSMBLevel(sys.argv[1]):
            loaded = self.LoadLevel(None, sys.argv[1], True, 1)
        elif globals_.settings.contains(('LastLevel_' + globals_.gamedef .name) if globals_.gamedef .custom else 'LastLevel'):
            lastlevel = str(globals_.gamedef .GetLastLevel())
            loaded = self.LoadLevel(None, lastlevel, True, 1)

        if not loaded:
            self.LoadLevel(None, '01-01', False, 1)

        QtCore.QTimer.singleShot(100, self.levelOverview.update)

        # call each toggle-button handler to set each feature correctly upon
        # startup
        toggleHandlers = {
            self.HandleSpritesVisibility: globals_.SpritesShown,
            self.HandleSpriteImages: globals_.SpriteImagesShown,
            self.HandleLocationsVisibility: globals_.LocationsShown,
            self.HandleCommentsVisibility: globals_.CommentsShown,
            self.HandlePathsVisibility: globals_.PathsShown,
        }
        for handler in toggleHandlers:
            handler(toggleHandlers[handler])

        # let's restore the state and geometry
        # geometry: determines the main window position
        # state: determines positions of docks
        if globals_.settings.contains('MainWindowGeometry'):
            self.restoreGeometry(setting('MainWindowGeometry'))
        if globals_.settings.contains('MainWindowState'):
            self.restoreState(setting('MainWindowState'), 0)

        # Load the most recently used gamedef
        LoadGameDef(setting('LastGameDef'), False)

        # Aaaaaand... initializing is done!
        # global globals_.Initializing
        globals_.Initializing = False

    def SetupActionsAndMenus(self):
        """
        Sets up Reggie's actions, menus and toolbars
        """
        self.RecentMenu = RecentFilesMenu()
        self.GameDefMenu = GameDefMenu()

        self.createMenubar()

    actions = {}

    def createMenubar(self):
        """
        Create actions, a menubar and a toolbar
        """

        # File
        self.CreateAction(
            'newlevel', self.HandleNewLevel, GetIcon('new'),
            globals_.trans.stringOneLine('MenuItems', 0), globals_.trans.stringOneLine('MenuItems', 1),
            QtGui.QKeySequence.New,
        )

        self.CreateAction(
            'openfromname', self.HandleOpenFromName, GetIcon('open'),
            globals_.trans.stringOneLine('MenuItems', 2), globals_.trans.stringOneLine('MenuItems', 3),
            QtGui.QKeySequence.Open,
        )

        self.CreateAction(
            'openfromfile', self.HandleOpenFromFile, GetIcon('openfromfile'),
            globals_.trans.stringOneLine('MenuItems', 4), globals_.trans.stringOneLine('MenuItems', 5),
            QtGui.QKeySequence('Ctrl+Shift+O'),
        )

        self.CreateAction(
            'openrecent', None, GetIcon('recent'),
            globals_.trans.stringOneLine('MenuItems', 6), globals_.trans.stringOneLine('MenuItems', 7),
            None,
        )

        self.CreateAction(
            'save', self.HandleSave, GetIcon('save'),
            globals_.trans.stringOneLine('MenuItems', 8), globals_.trans.stringOneLine('MenuItems', 9),
            QtGui.QKeySequence.Save,
        )

        self.CreateAction(
            'saveas', self.HandleSaveAs, GetIcon('saveas'),
            globals_.trans.stringOneLine('MenuItems', 10), globals_.trans.stringOneLine('MenuItems', 11),
            QtGui.QKeySequence.SaveAs,
        )

        self.CreateAction(
            'savecopyas', self.HandleSaveCopyAs, GetIcon('savecopyas'),
            globals_.trans.stringOneLine('MenuItems', 128), globals_.trans.stringOneLine('MenuItems', 129),
            None,
        )

        self.CreateAction(
            'metainfo', self.HandleInfo, GetIcon('info'),
            globals_.trans.stringOneLine('MenuItems', 12), globals_.trans.stringOneLine('MenuItems', 13),
            QtGui.QKeySequence('Ctrl+Alt+I'),
        )

        self.CreateAction(
            'changegamedef', None, GetIcon('game'),
            globals_.trans.stringOneLine('MenuItems', 98), globals_.trans.stringOneLine('MenuItems', 99),
            None,
        )

        self.CreateAction(
            'screenshot', self.HandleScreenshot, GetIcon('screenshot'),
            globals_.trans.stringOneLine('MenuItems', 14), globals_.trans.stringOneLine('MenuItems', 15),
            QtGui.QKeySequence('Ctrl+Alt+S'),
        )

        self.CreateAction(
            'changegamepath', self.HandleChangeGamePath, GetIcon('folderpath'),
            globals_.trans.stringOneLine('MenuItems', 16), globals_.trans.stringOneLine('MenuItems', 17),
            QtGui.QKeySequence('Ctrl+Alt+G'),
        )

        self.CreateAction(
            'preferences', self.HandlePreferences, GetIcon('settings'),
            globals_.trans.stringOneLine('MenuItems', 18), globals_.trans.stringOneLine('MenuItems', 19),
            QtGui.QKeySequence('Ctrl+Alt+P'),
        )

        self.CreateAction(
            'exit', self.HandleExit, GetIcon('delete'),
            globals_.trans.stringOneLine('MenuItems', 20), globals_.trans.stringOneLine('MenuItems', 21),
            QtGui.QKeySequence('Ctrl+Q'),
        )

        # Edit
        self.CreateAction(
            'selectall', self.SelectAll, GetIcon('selectall'),
            globals_.trans.stringOneLine('MenuItems', 22), globals_.trans.stringOneLine('MenuItems', 23),
            QtGui.QKeySequence.SelectAll,
        )

        self.CreateAction(
            'deselect', self.Deselect, GetIcon('deselect'),
            globals_.trans.stringOneLine('MenuItems', 24), globals_.trans.stringOneLine('MenuItems', 25),
            QtGui.QKeySequence('Ctrl+D'),
        )

        self.CreateAction(
            'undo', self.Undo, GetIcon('undo'),
            globals_.trans.stringOneLine('MenuItems', 124), globals_.trans.stringOneLine('MenuItems', 125),
            QtGui.QKeySequence.Undo,
        )

        self.CreateAction(
            'redo', self.Redo, GetIcon('redo'),
            globals_.trans.stringOneLine('MenuItems', 126), globals_.trans.stringOneLine('MenuItems', 127),
            QtGui.QKeySequence.Redo,
        )

        self.CreateAction(
            'cut', self.Cut, GetIcon('cut'),
            globals_.trans.stringOneLine('MenuItems', 26), globals_.trans.stringOneLine('MenuItems', 27),
            QtGui.QKeySequence.Cut,
        )

        self.CreateAction(
            'copy', self.Copy, GetIcon('copy'),
            globals_.trans.stringOneLine('MenuItems', 28), globals_.trans.stringOneLine('MenuItems', 29),
            QtGui.QKeySequence.Copy,
        )

        self.CreateAction(
            'paste', self.Paste, GetIcon('paste'),
            globals_.trans.stringOneLine('MenuItems', 30), globals_.trans.stringOneLine('MenuItems', 31),
            QtGui.QKeySequence.Paste,
        )

        self.CreateAction(
            'shiftitems', self.ShiftItems, GetIcon('move'),
            globals_.trans.stringOneLine('MenuItems', 32), globals_.trans.stringOneLine('MenuItems', 33),
            QtGui.QKeySequence('Ctrl+Shift+S'),
        )

        self.CreateAction(
            'mergelocations', self.MergeLocations, GetIcon('merge'),
            globals_.trans.stringOneLine('MenuItems', 34), globals_.trans.stringOneLine('MenuItems', 35),
            QtGui.QKeySequence('Ctrl+Shift+E'),
        )

        self.CreateAction(
            'swapobjectstilesets', self.SwapObjectsTilesets, GetIcon('swap'),
            globals_.trans.stringOneLine('MenuItems', 104), globals_.trans.stringOneLine('MenuItems', 105),
            QtGui.QKeySequence('Ctrl+Shift+L'),
        )

        self.CreateAction(
            'swapobjectstypes', self.SwapObjectsTypes, GetIcon('swap'),
            globals_.trans.stringOneLine('MenuItems', 106), globals_.trans.stringOneLine('MenuItems', 107),
            QtGui.QKeySequence('Ctrl+Shift+Y'),
        )

        self.CreateAction(
            'diagnostic', self.HandleDiagnostics, GetIcon('diagnostics'),
            globals_.trans.stringOneLine('MenuItems', 36), globals_.trans.stringOneLine('MenuItems', 37),
            QtGui.QKeySequence('Ctrl+Shift+D'),
        )

        self.CreateAction(
            'freezeobjects', self.HandleObjectsFreeze, GetIcon('objectsfreeze'),
            globals_.trans.stringOneLine('MenuItems', 38), globals_.trans.stringOneLine('MenuItems', 39),
            QtGui.QKeySequence('Ctrl+Shift+1'), True,
        )

        self.CreateAction(
            'freezesprites', self.HandleSpritesFreeze, GetIcon('spritesfreeze'),
            globals_.trans.stringOneLine('MenuItems', 40), globals_.trans.stringOneLine('MenuItems', 41),
            QtGui.QKeySequence('Ctrl+Shift+2'), True,
        )

        self.CreateAction(
            'freezeentrances', self.HandleEntrancesFreeze, GetIcon('entrancesfreeze'),
            globals_.trans.stringOneLine('MenuItems', 42), globals_.trans.stringOneLine('MenuItems', 43),
            QtGui.QKeySequence('Ctrl+Shift+3'), True,
        )

        self.CreateAction(
            'freezelocations', self.HandleLocationsFreeze, GetIcon('locationsfreeze'),
            globals_.trans.stringOneLine('MenuItems', 44), globals_.trans.stringOneLine('MenuItems', 45),
            QtGui.QKeySequence('Ctrl+Shift+4'), True,
        )

        self.CreateAction(
            'freezepaths', self.HandlePathsFreeze, GetIcon('pathsfreeze'),
            globals_.trans.stringOneLine('MenuItems', 46), globals_.trans.stringOneLine('MenuItems', 47),
            QtGui.QKeySequence('Ctrl+Shift+5'), True,
        )

        self.CreateAction(
            'freezecomments', self.HandleCommentsFreeze, GetIcon('commentsfreeze'),
            globals_.trans.stringOneLine('MenuItems', 114), globals_.trans.stringOneLine('MenuItems', 115),
            QtGui.QKeySequence('Ctrl+Shift+9'), True,
        )

        # View
        self.CreateAction(
            'showlay0', self.HandleUpdateLayer0, GetIcon('layer0'),
            globals_.trans.stringOneLine('MenuItems', 48), globals_.trans.stringOneLine('MenuItems', 49),
            QtGui.QKeySequence('Ctrl+1'), True,
        )

        self.CreateAction(
            'showlay1', self.HandleUpdateLayer1, GetIcon('layer1'),
            globals_.trans.stringOneLine('MenuItems', 50), globals_.trans.stringOneLine('MenuItems', 51),
            QtGui.QKeySequence('Ctrl+2'), True,
        )

        self.CreateAction(
            'showlay2', self.HandleUpdateLayer2, GetIcon('layer2'),
            globals_.trans.stringOneLine('MenuItems', 52), globals_.trans.stringOneLine('MenuItems', 53),
            QtGui.QKeySequence('Ctrl+3'), True,
        )

        self.CreateAction(
            'tileanim', self.HandleTilesetAnimToggle, GetIcon('animation'),
            globals_.trans.stringOneLine('MenuItems', 108), globals_.trans.stringOneLine('MenuItems', 109),
            QtGui.QKeySequence('Ctrl+7'), True,
        )

        self.CreateAction(
            'collisions', self.HandleCollisionsToggle, GetIcon('collisions'),
            globals_.trans.stringOneLine('MenuItems', 110), globals_.trans.stringOneLine('MenuItems', 111),
            QtGui.QKeySequence('Ctrl+8'), True,
        )

        self.CreateAction(
            'realview', self.HandleRealViewToggle, GetIcon('realview'),
            globals_.trans.stringOneLine('MenuItems', 118), globals_.trans.stringOneLine('MenuItems', 119),
            QtGui.QKeySequence('Ctrl+9'), True,
        )

        self.CreateAction(
            'showsprites', self.HandleSpritesVisibility, GetIcon('sprites'),
            globals_.trans.stringOneLine('MenuItems', 54), globals_.trans.stringOneLine('MenuItems', 55),
            QtGui.QKeySequence('Ctrl+4'), True,
        )

        self.CreateAction(
            'showspriteimages', self.HandleSpriteImages, GetIcon('sprites'),
            globals_.trans.stringOneLine('MenuItems', 56), globals_.trans.stringOneLine('MenuItems', 57),
            QtGui.QKeySequence('Ctrl+6'), True,
        )

        self.CreateAction(
            'showlocations', self.HandleLocationsVisibility, GetIcon('locations'),
            globals_.trans.stringOneLine('MenuItems', 58), globals_.trans.stringOneLine('MenuItems', 59),
            QtGui.QKeySequence('Ctrl+5'), True,
        )

        self.CreateAction(
            'showcomments', self.HandleCommentsVisibility, GetIcon('comments'),
            globals_.trans.stringOneLine('MenuItems', 116), globals_.trans.stringOneLine('MenuItems', 117),
            QtGui.QKeySequence('Ctrl+0'), True,
        )

        self.CreateAction(
            'showpaths', self.HandlePathsVisibility, GetIcon('paths'),
            globals_.trans.stringOneLine('MenuItems', 130), globals_.trans.stringOneLine('MenuItems', 131),
            QtGui.QKeySequence('Ctrl+*'), True,
        )

        self.CreateAction(
            'grid', self.HandleSwitchGrid, GetIcon('grid'),
            globals_.trans.stringOneLine('MenuItems', 60), globals_.trans.stringOneLine('MenuItems', 61),
            QtGui.QKeySequence('Ctrl+G'),
        )

        self.CreateAction(
            'zoommax', self.HandleZoomMax, GetIcon('zoommax'),
            globals_.trans.stringOneLine('MenuItems', 62), globals_.trans.stringOneLine('MenuItems', 63),
            QtGui.QKeySequence('Ctrl+PgDown'),
        )

        self.CreateAction(
            'zoomin', self.HandleZoomIn, GetIcon('zoomin'),
            globals_.trans.stringOneLine('MenuItems', 64), globals_.trans.stringOneLine('MenuItems', 65),
            QtGui.QKeySequence.ZoomIn,
        )

        self.CreateAction(
            'zoomactual', self.HandleZoomActual, GetIcon('zoomactual'),
            globals_.trans.stringOneLine('MenuItems', 66), globals_.trans.stringOneLine('MenuItems', 67),
            QtGui.QKeySequence('Ctrl+0'),
        )

        self.CreateAction(
            'zoomout', self.HandleZoomOut, GetIcon('zoomout'),
            globals_.trans.stringOneLine('MenuItems', 68), globals_.trans.stringOneLine('MenuItems', 69),
            QtGui.QKeySequence.ZoomOut,
        )

        self.CreateAction(
            'zoommin', self.HandleZoomMin, GetIcon('zoommin'),
            globals_.trans.stringOneLine('MenuItems', 70), globals_.trans.stringOneLine('MenuItems', 71),
            QtGui.QKeySequence('Ctrl+PgUp'),
        )

        # Show Overview and Show Palette are added later

        # Settings
        self.CreateAction(
            'areaoptions', self.HandleAreaOptions, GetIcon('area'),
            globals_.trans.stringOneLine('MenuItems', 72), globals_.trans.stringOneLine('MenuItems', 73),
            QtGui.QKeySequence('Ctrl+Alt+A'),
        )

        self.CreateAction(
            'zones', self.HandleZones, GetIcon('zones'),
            globals_.trans.stringOneLine('MenuItems', 74), globals_.trans.stringOneLine('MenuItems', 75),
            QtGui.QKeySequence('Ctrl+Alt+Z'),
        )

        self.CreateAction(
            'backgrounds', self.HandleBG, GetIcon('background'),
            globals_.trans.stringOneLine('MenuItems', 76), globals_.trans.stringOneLine('MenuItems', 77),
            QtGui.QKeySequence('Ctrl+Alt+B'),
        )

        self.CreateAction(
            'addarea', self.HandleAddNewArea, GetIcon('add'),
            globals_.trans.stringOneLine('MenuItems', 78), globals_.trans.stringOneLine('MenuItems', 79),
            QtGui.QKeySequence('Ctrl+Alt+N'),
        )

        self.CreateAction(
            'importarea', self.HandleImportArea, GetIcon('import'),
            globals_.trans.stringOneLine('MenuItems', 80), globals_.trans.stringOneLine('MenuItems', 81),
            QtGui.QKeySequence('Ctrl+Alt+O'),
        )

        self.CreateAction(
            'deletearea', self.HandleDeleteArea, GetIcon('delete'),
            globals_.trans.stringOneLine('MenuItems', 82), globals_.trans.stringOneLine('MenuItems', 83),
            QtGui.QKeySequence('Ctrl+Alt+D'),
        )

        self.CreateAction(
            'openpuzzle', self.OpenPuzzle, GetIcon('reload-tilesets'),
            globals_.trans.stringOneLine('MenuItems', 140), globals_.trans.stringOneLine('MenuItems', 141),
            None
        )

        self.CreateAction(
            'reloadgfx', self.ReloadTilesets, GetIcon('reload-tilesets'),
            globals_.trans.stringOneLine('MenuItems', 84), globals_.trans.stringOneLine('MenuItems', 85),
            QtGui.QKeySequence('Ctrl+Shift+R'),
        )

        self.CreateAction(
            'reloaddata', self.ReloadSpritedata, GetIcon('reload-spritedata'),
            globals_.trans.stringOneLine('MenuItems', 138), globals_.trans.stringOneLine('MenuItems', 139),
            # No shortcut for now...
            None
        )

        # Help actions are created later

        # Configure them
        self.actions['openrecent'].setMenu(self.RecentMenu)
        self.actions['changegamedef'].setMenu(self.GameDefMenu)

        self.actions['collisions'].setChecked(globals_.CollisionsShown)
        self.actions['realview'].setChecked(globals_.RealViewEnabled)

        self.actions['showsprites'].setChecked(globals_.SpritesShown)
        self.actions['showspriteimages'].setChecked(globals_.SpriteImagesShown)
        self.actions['showlocations'].setChecked(globals_.LocationsShown)
        self.actions['showcomments'].setChecked(globals_.CommentsShown)
        self.actions['showpaths'].setChecked(globals_.PathsShown)

        self.actions['freezeobjects'].setChecked(globals_.ObjectsFrozen)
        self.actions['freezesprites'].setChecked(globals_.SpritesFrozen)
        self.actions['freezeentrances'].setChecked(globals_.EntrancesFrozen )
        self.actions['freezelocations'].setChecked(globals_.LocationsFrozen)
        self.actions['freezepaths'].setChecked(globals_.PathsFrozen)
        self.actions['freezecomments'].setChecked(globals_.CommentsFrozen)

        self.actions['undo'].setEnabled(False)
        self.actions['redo'].setEnabled(False)
        self.actions['cut'].setEnabled(False)
        self.actions['copy'].setEnabled(False)
        self.actions['paste'].setEnabled(False)
        self.actions['shiftitems'].setEnabled(False)
        self.actions['mergelocations'].setEnabled(False)
        self.actions['deselect'].setEnabled(False)

        ####
        menubar = QtWidgets.QMenuBar()
        self.setMenuBar(menubar)

        fmenu = menubar.addMenu(globals_.trans.string('Menubar', 0))
        fmenu.addAction(self.actions['newlevel'])
        fmenu.addAction(self.actions['openfromname'])
        fmenu.addAction(self.actions['openfromfile'])
        fmenu.addAction(self.actions['openrecent'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['save'])
        fmenu.addAction(self.actions['saveas'])
        fmenu.addAction(self.actions['savecopyas'])
        fmenu.addAction(self.actions['metainfo'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['changegamedef'])
        fmenu.addAction(self.actions['screenshot'])
        fmenu.addAction(self.actions['changegamepath'])
        fmenu.addAction(self.actions['preferences'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['exit'])

        emenu = menubar.addMenu(globals_.trans.string('Menubar', 1))
        emenu.addAction(self.actions['selectall'])
        emenu.addAction(self.actions['deselect'])
        emenu.addSeparator()
        emenu.addAction(self.actions['undo'])
        emenu.addAction(self.actions['redo'])
        emenu.addSeparator()
        emenu.addAction(self.actions['cut'])
        emenu.addAction(self.actions['copy'])
        emenu.addAction(self.actions['paste'])
        emenu.addSeparator()
        emenu.addAction(self.actions['shiftitems'])
        emenu.addAction(self.actions['mergelocations'])
        emenu.addAction(self.actions['swapobjectstilesets'])
        emenu.addAction(self.actions['swapobjectstypes'])
        emenu.addSeparator()
        emenu.addAction(self.actions['diagnostic'])
        emenu.addSeparator()
        emenu.addAction(self.actions['freezeobjects'])
        emenu.addAction(self.actions['freezesprites'])
        emenu.addAction(self.actions['freezeentrances'])
        emenu.addAction(self.actions['freezelocations'])
        emenu.addAction(self.actions['freezepaths'])
        emenu.addAction(self.actions['freezecomments'])

        vmenu = menubar.addMenu(globals_.trans.string('Menubar', 2))
        vmenu.addAction(self.actions['showlay0'])
        vmenu.addAction(self.actions['showlay1'])
        vmenu.addAction(self.actions['showlay2'])
        vmenu.addAction(self.actions['tileanim'])
        vmenu.addAction(self.actions['collisions'])
        vmenu.addAction(self.actions['realview'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['showsprites'])
        vmenu.addAction(self.actions['showspriteimages'])
        vmenu.addAction(self.actions['showlocations'])
        vmenu.addAction(self.actions['showcomments'])
        vmenu.addAction(self.actions['showpaths'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['grid'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['zoommax'])
        vmenu.addAction(self.actions['zoomin'])
        vmenu.addAction(self.actions['zoomactual'])
        vmenu.addAction(self.actions['zoomout'])
        vmenu.addAction(self.actions['zoommin'])
        vmenu.addSeparator()
        # self.levelOverviewDock.toggleViewAction() is added here later
        # so we assign it to self.vmenu
        self.vmenu = vmenu

        lmenu = menubar.addMenu(globals_.trans.string('Menubar', 3))
        lmenu.addAction(self.actions['areaoptions'])
        lmenu.addAction(self.actions['zones'])
        lmenu.addAction(self.actions['backgrounds'])
        lmenu.addSeparator()
        lmenu.addAction(self.actions['addarea'])
        lmenu.addAction(self.actions['importarea'])
        lmenu.addAction(self.actions['deletearea'])
        lmenu.addSeparator()
        lmenu.addAction(self.actions['openpuzzle'])
        lmenu.addAction(self.actions['reloadgfx'])
        lmenu.addAction(self.actions['reloaddata'])

        hmenu = menubar.addMenu(globals_.trans.string('Menubar', 4))
        self.SetupHelpMenu(hmenu)

        # create a toolbar
        self.toolbar = self.addToolBar(globals_.trans.string('Menubar', 5))
        self.toolbar.setObjectName('MainToolbar')

        # Add buttons to the toolbar
        self.addToolbarButtons()

        # Add the area combo box
        self.areaComboBox = QtWidgets.QComboBox()
        self.areaComboBox.activated.connect(self.HandleSwitchArea)
        self.toolbar.addWidget(self.areaComboBox)

    def SetupHelpMenu(self, menu=None):
        """
        Creates the help menu.
        """
        self.CreateAction('infobox', self.AboutBox, GetIcon('reggie'), globals_.trans.stringOneLine('MenuItems', 86),
                          globals_.trans.string('MenuItems', 87), QtGui.QKeySequence('Ctrl+Shift+I'))
        self.CreateAction('helpbox', self.HelpBox, GetIcon('contents'), globals_.trans.stringOneLine('MenuItems', 88),
                          globals_.trans.string('MenuItems', 89), QtGui.QKeySequence('Ctrl+Shift+H'))
        self.CreateAction('tipbox', self.TipBox, GetIcon('tips'), globals_.trans.stringOneLine('MenuItems', 90),
                          globals_.trans.string('MenuItems', 91), QtGui.QKeySequence('Ctrl+Shift+T'))
        self.CreateAction('aboutqt', QtWidgets.qApp.aboutQt, GetIcon('qt'), globals_.trans.stringOneLine('MenuItems', 92),
                          globals_.trans.string('MenuItems', 93), QtGui.QKeySequence('Ctrl+Shift+Q'))

        if menu is None:
            menu = QtWidgets.QMenu(globals_.trans.string('Menubar', 4))
        menu.addAction(self.actions['infobox'])
        menu.addAction(self.actions['helpbox'])
        menu.addAction(self.actions['tipbox'])
        menu.addSeparator()
        menu.addAction(self.actions['aboutqt'])
        return menu

    def addToolbarButtons(self):
        """
        Reads from the Preferences file and adds the appropriate options to the toolbar
        """
        # First, define groups. Each group is isolated by separators.
        Groups = (
            (
                'newlevel',
                'openfromname',
                'openfromfile',
                'openrecent',
                'save',
                'saveas',
                'savecopyas',
                'metainfo',
                'screenshot',
                'changegamepath',
                'preferences',
                'exit',
            ), (
                'selectall',
                'deselect',
            ), (
                'cut',
                'copy',
                'paste',
            ), (
                'shiftitems',
                'mergelocations',
            ), (
                'freezeobjects',
                'freezesprites',
                'freezeentrances',
                'freezelocations',
                'freezepaths',
            ), (
                'diagnostic',
            ), (
                'zoommax',
                'zoomin',
                'zoomactual',
                'zoomout',
                'zoommin',
            ), (
                'grid',
            ), (
                'showlay0',
                'showlay1',
                'showlay2',
            ), (
                'showsprites',
                'showspriteimages',
                'showlocations',
                'showpaths',
            ), (
                'areaoptions',
                'zones',
                'backgrounds',
            ), (
                'addarea',
                'importarea',
                'deletearea',
            ), (
                'openpuzzle',
                'reloadgfx',
                'reloaddata',
            ), (
                'infobox',
                'helpbox',
                'tipbox',
                'aboutqt',
            ),
        )

        # Determine which keys are activated
        if setting('ToolbarActs') in (None, 'None', 'none', '', 0):
            # Get the default settings
            toggled = {}
            for List in (globals_.FileActions, globals_.EditActions, globals_.ViewActions, globals_.SettingsActions, globals_.HelpActions):
                for name, activated, key in List:
                    toggled[key] = activated
        else:
            # Get the settings from the .ini
            toggled = setting('ToolbarActs')
            newToggled = {}  # here, I'm replacing QStrings with python strings
            for key in toggled:
                newToggled[str(key)] = toggled[key]
            toggled = newToggled

        # Add each to the toolbar if toggled[key]
        for group in Groups:
            addedButtons = False
            for key in group:
                if key in toggled and toggled[key]:
                    act = self.actions[key]
                    self.toolbar.addAction(act)
                    addedButtons = True
            if addedButtons:
                self.toolbar.addSeparator()

    def SetupDocksAndPanels(self):
        """
        Sets up the dock widgets and panels
        """
        # level overview
        dock = QtWidgets.QDockWidget(globals_.trans.string('MenuItems', 94), self)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable | QtWidgets.QDockWidget.DockWidgetClosable)
        # dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('leveloverview')  # needed for the state to save/restore correctly

        self.levelOverview = LevelOverviewWidget()
        self.levelOverview.moveIt.connect(self.HandleOverviewClick)
        self.levelOverviewDock = dock
        dock.setWidget(self.levelOverview)

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setVisible(True)
        act = dock.toggleViewAction()
        act.setShortcut(QtGui.QKeySequence('Ctrl+M'))
        act.setIcon(GetIcon('overview'))
        act.setStatusTip(globals_.trans.string('MenuItems', 95))
        self.vmenu.addAction(act)

        # create the sprite editor panel
        dock = QtWidgets.QDockWidget(globals_.trans.string('SpriteDataEditor', 0), self)
        dock.setVisible(False)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('spriteeditor')  # needed for the state to save/restore correctly
        dock.move(100, 100) # offset the dock from the top-left corner

        self.spriteDataEditor = SpriteEditorWidget()
        self.spriteDataEditor.DataUpdate.connect(self.SpriteDataUpdated)
        dock.setWidget(self.spriteDataEditor)
        self.spriteEditorDock = dock

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # create the entrance editor panel
        dock = QtWidgets.QDockWidget(globals_.trans.string('EntranceDataEditor', 24), self)
        dock.setVisible(False)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('entranceeditor')  # needed for the state to save/restore correctly
        dock.move(100, 100) # offset the dock from the top-left corner

        self.entranceEditor = EntranceEditorWidget()
        dock.setWidget(self.entranceEditor)
        self.entranceEditorDock = dock

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # create the path node editor panel
        dock = QtWidgets.QDockWidget(globals_.trans.string('PathDataEditor', 10), self)
        dock.setVisible(False)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('pathnodeeditor')  # needed for the state to save/restore correctly
        dock.move(100, 100) # offset the dock from the top-left corner

        self.pathEditor = PathNodeEditorWidget()
        dock.setWidget(self.pathEditor)
        self.pathEditorDock = dock

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # create the location editor panel
        dock = QtWidgets.QDockWidget(globals_.trans.string('LocationDataEditor', 12), self)
        dock.setVisible(False)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('locationeditor')  # needed for the state to save/restore correctly
        dock.move(100, 100) # offset the dock from the top-left corner

        self.locationEditor = LocationEditorWidget()
        dock.setWidget(self.locationEditor)
        self.locationEditorDock = dock

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # create the palette
        dock = QtWidgets.QDockWidget(globals_.trans.string('MenuItems', 96), self)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable | QtWidgets.QDockWidget.DockWidgetClosable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('palette')  # needed for the state to save/restore correctly

        self.creationDock = dock
        act = dock.toggleViewAction()
        act.setShortcut(QtGui.QKeySequence('Ctrl+P'))
        act.setIcon(GetIcon('palette'))
        act.setStatusTip(globals_.trans.string('MenuItems', 97))
        self.vmenu.addAction(act)

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setVisible(True)

        # add tabs to it
        tabs = QtWidgets.QTabWidget()
        tabs.setIconSize(QtCore.QSize(16, 16))
        tabs.currentChanged.connect(self.CreationTabChanged)
        dock.setWidget(tabs)
        self.creationTabs = tabs

        # object choosing tabs
        tsicon = GetIcon('objects')

        self.objAllTab = QtWidgets.QTabWidget()
        self.objAllTab.currentChanged.connect(self.ObjTabChanged)
        self.objAllTab.tabBarDoubleClicked.connect(self.OpenPuzzle)
        tabs.addTab(self.objAllTab, tsicon, '')
        tabs.setTabToolTip(0, globals_.trans.string('Palette', 13))

        self.objTS0Tab = QtWidgets.QWidget()
        self.objTS1Tab = QtWidgets.QWidget()
        self.objTS2Tab = QtWidgets.QWidget()
        self.objTS3Tab = QtWidgets.QWidget()
        self.objAllTab.addTab(self.objTS0Tab, tsicon, '1')
        self.objAllTab.addTab(self.objTS1Tab, tsicon, '2')
        self.objAllTab.addTab(self.objTS2Tab, tsicon, '3')
        self.objAllTab.addTab(self.objTS3Tab, tsicon, '4')

        oel = QtWidgets.QVBoxLayout(self.objTS0Tab)
        self.createObjectLayout = oel

        ll = QtWidgets.QHBoxLayout()
        self.objUseLayer0 = QtWidgets.QRadioButton('0')
        self.objUseLayer0.setToolTip(globals_.trans.string('Palette', 1))
        self.objUseLayer1 = QtWidgets.QRadioButton('1')
        self.objUseLayer1.setToolTip(globals_.trans.string('Palette', 2))
        self.objUseLayer2 = QtWidgets.QRadioButton('2')
        self.objUseLayer2.setToolTip(globals_.trans.string('Palette', 3))
        ll.addWidget(QtWidgets.QLabel(globals_.trans.string('Palette', 0)))
        ll.addWidget(self.objUseLayer0)
        ll.addWidget(self.objUseLayer1)
        ll.addWidget(self.objUseLayer2)
        ll.addStretch(1)
        oel.addLayout(ll)

        lbg = QtWidgets.QButtonGroup(self)
        lbg.addButton(self.objUseLayer0, 0)
        lbg.addButton(self.objUseLayer1, 1)
        lbg.addButton(self.objUseLayer2, 2)
        lbg.buttonClicked[int].connect(self.LayerChoiceChanged)
        self.LayerButtonGroup = lbg

        self.objPicker = ObjectPickerWidget()
        self.objPicker.ObjChanged.connect(self.ObjectChoiceChanged)
        self.objPicker.ObjReplace.connect(self.ObjectReplace)
        oel.addWidget(self.objPicker, 1)

        # sprite tab
        self.sprAllTab = QtWidgets.QTabWidget()
        self.sprAllTab.currentChanged.connect(self.SprTabChanged)
        tabs.addTab(self.sprAllTab, GetIcon('sprites'), '')
        tabs.setTabToolTip(1, globals_.trans.string('Palette', 14))

        # sprite tab: add
        self.sprPickerTab = QtWidgets.QWidget()
        self.sprAllTab.addTab(self.sprPickerTab, GetIcon('spritesadd'), globals_.trans.string('Palette', 25))

        spl = QtWidgets.QVBoxLayout(self.sprPickerTab)
        self.sprPickerLayout = spl

        svpl = QtWidgets.QHBoxLayout()
        svpl.addWidget(QtWidgets.QLabel(globals_.trans.string('Palette', 4)))

        sspl = QtWidgets.QHBoxLayout()
        sspl.addWidget(QtWidgets.QLabel(globals_.trans.string('Palette', 5)))

        LoadSpriteCategories()
        viewpicker = QtWidgets.QComboBox()
        for view in globals_.SpriteCategories:
            viewpicker.addItem(view[0])
        viewpicker.currentIndexChanged.connect(self.SelectNewSpriteView)

        self.spriteViewPicker = viewpicker
        svpl.addWidget(viewpicker, 1)

        self.spriteSearchTerm = QtWidgets.QLineEdit()
        self.spriteSearchTerm.textChanged.connect(self.NewSearchTerm)
        sspl.addWidget(self.spriteSearchTerm, 1)

        spl.addLayout(svpl)
        spl.addLayout(sspl)

        self.spriteSearchLayout = sspl
        sspl.itemAt(0).widget().setVisible(False)
        sspl.itemAt(1).widget().setVisible(False)

        self.sprPicker = SpritePickerWidget()
        self.sprPicker.SpriteChanged.connect(self.SpriteChoiceChanged)
        self.sprPicker.SpriteReplace.connect(self.SpriteReplace)
        self.sprPicker.SwitchView(globals_.SpriteCategories[0])
        spl.addWidget(self.sprPicker, 1)

        self.defaultPropButton = QtWidgets.QPushButton(globals_.trans.string('Palette', 6))
        self.defaultPropButton.setEnabled(False)
        self.defaultPropButton.clicked.connect(self.ShowDefaultProps)

        sdpl = QtWidgets.QHBoxLayout()
        sdpl.addStretch(1)
        sdpl.addWidget(self.defaultPropButton)
        sdpl.addStretch(1)
        spl.addLayout(sdpl)

        # default sprite data editor
        ddock = QtWidgets.QDockWidget(globals_.trans.string('Palette', 7), self)
        ddock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable | QtWidgets.QDockWidget.DockWidgetClosable)
        ddock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        ddock.setObjectName('defaultprops')  # needed for the state to save/restore correctly
        ddock.move(100, 100) # offset the dock from the top-left corner

        self.defaultDataEditor = SpriteEditorWidget(True)
        self.defaultDataEditor.setVisible(False)
        ddock.setWidget(self.defaultDataEditor)

        self.addDockWidget(Qt.RightDockWidgetArea, ddock)
        ddock.setVisible(False)
        ddock.setFloating(True)
        self.defaultPropDock = ddock

        # sprite tab: current
        self.sprEditorTab = QtWidgets.QWidget()
        self.sprAllTab.addTab(self.sprEditorTab, GetIcon('spritelist'), globals_.trans.string('Palette', 26))

        spel = QtWidgets.QVBoxLayout(self.sprEditorTab)
        self.sprEditorLayout = spel

        slabel = QtWidgets.QLabel(globals_.trans.string('Palette', 11))
        slabel.setWordWrap(True)
        self.spriteList = SpriteList()
        # self.spriteList.list_.itemActivated.connect(self.HandleSpriteSelectByList)
        # self.spriteList.list_.toolTipAboutToShow.connect(self.HandleSpriteToolTipAboutToShow)

        spel.addWidget(slabel)
        spel.addWidget(self.spriteList)

        # entrance tab
        self.entEditorTab = QtWidgets.QWidget()
        tabs.addTab(self.entEditorTab, GetIcon('entrances'), '')
        tabs.setTabToolTip(2, globals_.trans.string('Palette', 15))

        eel = QtWidgets.QVBoxLayout(self.entEditorTab)
        self.entEditorLayout = eel

        elabel = QtWidgets.QLabel(globals_.trans.string('Palette', 8))
        elabel.setWordWrap(True)
        self.entranceList = ListWidgetWithToolTipSignal()
        self.entranceList.itemActivated.connect(self.HandleEntranceSelectByList)
        self.entranceList.toolTipAboutToShow.connect(self.HandleEntranceToolTipAboutToShow)
        self.entranceList.setSortingEnabled(True)

        eel.addWidget(elabel)
        eel.addWidget(self.entranceList)

        # locations tab
        self.locEditorTab = QtWidgets.QWidget()
        tabs.addTab(self.locEditorTab, GetIcon('locations'), '')
        tabs.setTabToolTip(3, globals_.trans.string('Palette', 16))

        locL = QtWidgets.QVBoxLayout(self.locEditorTab)
        self.locEditorLayout = locL

        Llabel = QtWidgets.QLabel(globals_.trans.string('Palette', 12))
        Llabel.setWordWrap(True)
        self.locationList = ListWidgetWithToolTipSignal()
        self.locationList.itemActivated.connect(self.HandleLocationSelectByList)
        self.locationList.toolTipAboutToShow.connect(self.HandleLocationToolTipAboutToShow)
        self.locationList.setSortingEnabled(True)

        locL.addWidget(Llabel)
        locL.addWidget(self.locationList)

        # paths tab
        self.pathEditorTab = QtWidgets.QWidget()
        tabs.addTab(self.pathEditorTab, GetIcon('paths'), '')
        tabs.setTabToolTip(4, globals_.trans.string('Palette', 17))

        pathel = QtWidgets.QVBoxLayout(self.pathEditorTab)
        self.pathEditorLayout = pathel

        pathlabel = QtWidgets.QLabel(globals_.trans.string('Palette', 9))
        pathlabel.setWordWrap(True)
        deselectbtn = QtWidgets.QPushButton(globals_.trans.string('Palette', 10))
        deselectbtn.clicked.connect(self.DeselectPathSelection)
        self.pathList = ListWidgetWithToolTipSignal()
        self.pathList.itemActivated.connect(self.HandlePathSelectByList)
        self.pathList.toolTipAboutToShow.connect(self.HandlePathToolTipAboutToShow)
        self.pathList.setSortingEnabled(True)

        pathel.addWidget(pathlabel)
        pathel.addWidget(deselectbtn)
        pathel.addWidget(self.pathList)

        # events tab
        self.eventEditorTab = QtWidgets.QWidget()
        tabs.addTab(self.eventEditorTab, GetIcon('events'), '')
        tabs.setTabToolTip(5, globals_.trans.string('Palette', 18))

        eventel = QtWidgets.QGridLayout(self.eventEditorTab)
        self.eventEditorLayout = eventel

        eventlabel = QtWidgets.QLabel(globals_.trans.string('Palette', 20))
        eventNotesLabel = QtWidgets.QLabel(globals_.trans.string('Palette', 21))
        self.eventNotesEditor = QtWidgets.QLineEdit()
        self.eventNotesEditor.textEdited.connect(self.handleEventNotesEdit)

        self.eventChooser = QtWidgets.QTreeWidget()
        self.eventChooser.setColumnCount(2)
        self.eventChooser.setHeaderLabels((globals_.trans.string('Palette', 22), globals_.trans.string('Palette', 23)))
        self.eventChooser.itemClicked.connect(self.handleEventTabItemClick)
        self.eventChooserItems = []
        flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled
        for id in range(64):
            itm = QtWidgets.QTreeWidgetItem()
            itm.setFlags(flags)
            itm.setCheckState(0, Qt.Unchecked)
            itm.setText(0, globals_.trans.string('Palette', 24, '[id]', str(id + 1)))
            itm.setText(1, '')
            self.eventChooser.addTopLevelItem(itm)
            self.eventChooserItems.append(itm)
            if id == 0: itm.setSelected(True)

        eventel.addWidget(eventlabel, 0, 0, 1, 2)
        eventel.addWidget(eventNotesLabel, 1, 0)
        eventel.addWidget(self.eventNotesEditor, 1, 1)
        eventel.addWidget(self.eventChooser, 2, 0, 1, 2)

        # stamps tab
        self.stampTab = QtWidgets.QWidget()
        tabs.addTab(self.stampTab, GetIcon('stamp'), '')
        tabs.setTabToolTip(6, globals_.trans.string('Palette', 19))

        stampLabel = QtWidgets.QLabel(globals_.trans.string('Palette', 27))

        stampAddBtn = QtWidgets.QPushButton(globals_.trans.string('Palette', 28))
        stampAddBtn.clicked.connect(self.handleStampsAdd)
        stampAddBtn.setEnabled(False)
        self.stampAddBtn = stampAddBtn  # so we can enable/disable it later
        stampRemoveBtn = QtWidgets.QPushButton(globals_.trans.string('Palette', 29))
        stampRemoveBtn.clicked.connect(self.handleStampsRemove)
        stampRemoveBtn.setEnabled(False)
        self.stampRemoveBtn = stampRemoveBtn  # so we can enable/disable it later

        menu = QtWidgets.QMenu()
        menu.addAction(globals_.trans.string('Palette', 31), self.handleStampsOpen, 0)  # Open Set...
        menu.addAction(globals_.trans.string('Palette', 32), self.handleStampsSave, 0)  # Save Set As...
        stampToolsBtn = QtWidgets.QToolButton()
        stampToolsBtn.setText(globals_.trans.string('Palette', 30))
        stampToolsBtn.setMenu(menu)
        stampToolsBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        stampToolsBtn.setSizePolicy(stampAddBtn.sizePolicy())
        stampToolsBtn.setMinimumHeight(stampAddBtn.height() // 20)

        stampNameLabel = QtWidgets.QLabel(globals_.trans.string('Palette', 35))
        self.stampNameEdit = QtWidgets.QLineEdit()
        self.stampNameEdit.setEnabled(False)
        self.stampNameEdit.textChanged.connect(self.handleStampNameEdited)

        nameLayout = QtWidgets.QHBoxLayout()
        nameLayout.addWidget(stampNameLabel)
        nameLayout.addWidget(self.stampNameEdit)

        self.stampChooser = StampChooserWidget()
        self.stampChooser.selectionChangedSignal.connect(self.handleStampSelectionChanged)

        stampL = QtWidgets.QGridLayout()
        stampL.addWidget(stampLabel, 0, 0, 1, 3)
        stampL.addWidget(stampAddBtn, 1, 0)
        stampL.addWidget(stampRemoveBtn, 1, 1)
        stampL.addWidget(stampToolsBtn, 1, 2)
        stampL.addLayout(nameLayout, 2, 0, 1, 3)
        stampL.addWidget(self.stampChooser, 3, 0, 1, 3)
        self.stampTab.setLayout(stampL)

        # comments tab
        self.commentsTab = QtWidgets.QWidget()
        tabs.addTab(self.commentsTab, GetIcon('comments'), '')
        tabs.setTabToolTip(7, globals_.trans.string('Palette', 33))

        cel = QtWidgets.QVBoxLayout()
        self.commentsTab.setLayout(cel)
        self.entEditorLayout = cel

        clabel = QtWidgets.QLabel(globals_.trans.string('Palette', 34))
        clabel.setWordWrap(True)

        self.commentList = ListWidgetWithToolTipSignal()
        self.commentList.itemActivated.connect(self.HandleCommentSelectByList)
        self.commentList.toolTipAboutToShow.connect(self.HandleCommentToolTipAboutToShow)
        self.commentList.setSortingEnabled(True)

        cel.addWidget(clabel)
        cel.addWidget(self.commentList)

        # Set the current tab to the Object tab
        self.CreationTabChanged(0)

    def DeselectPathSelection(self, checked):
        """
        Deselects selected path nodes in the list
        """
        for selecteditem in self.pathList.selectedItems():
            selecteditem.setSelected(False)

    def Autosave(self):
        """
        Auto saves the level
        """
        # global globals_.AutoSaveDirty
        if not globals_.AutoSaveDirty: return

        data = globals_.Level.save()
        setSetting('AutoSaveFilePath', self.fileSavePath)
        setSetting('AutoSaveFileData', QtCore.QByteArray(data))
        globals_.AutoSaveDirty = False

    def TrackClipboardUpdates(self):
        """
        Catches systemwide clipboard updates
        """
        if globals_.Initializing: return
        clip = self.systemClipboard.text()
        if clip is not None and clip != '':
            clip = str(clip).strip()

            if clip.startswith('ReggieClip|') and clip.endswith('|%'):
                self.clipboard = clip.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')

                self.actions['paste'].setEnabled(True)
            else:
                self.clipboard = None
                self.actions['paste'].setEnabled(False)

    def XScrollChange(self, pos):
        """
        Moves the Overview current position box based on X scroll bar value
        """
        self.levelOverview.Xposlocator = pos
        self.levelOverview.update()

    def YScrollChange(self, pos):
        """
        Moves the Overview current position box based on Y scroll bar value
        """
        self.levelOverview.Yposlocator = pos
        self.levelOverview.update()

    def HandleWindowSizeChange(self, w, h):
        self.levelOverview.Hlocator = h
        self.levelOverview.Wlocator = w
        self.levelOverview.update()

    def UpdateTitle(self):
        """
        Sets the window title accordingly
        """
        # ' - Reggie Next' is added automatically by Qt (see QApplication.setApplicationDisplayName()).
        self.setWindowTitle('%s%s' % (globals_.mainWindow.fileTitle, (' ' + globals_.trans.string('MainWindow', 0)) if globals_.Dirty else ''))

    def CheckDirty(self):
        """
        Checks if the level is unsaved and asks for a confirmation if so - if it returns True, Cancel was picked
        """
        if not globals_.Dirty: return False

        msg = QtWidgets.QMessageBox()
        msg.setText(globals_.trans.string('AutoSaveDlg', 2))
        msg.setInformativeText(globals_.trans.string('AutoSaveDlg', 3))
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        msg.setDefaultButton(QtWidgets.QMessageBox.Save)
        ret = msg.exec_()

        if ret == QtWidgets.QMessageBox.Save:
            if not self.HandleSave():
                # save failed
                return True
            return False
        elif ret == QtWidgets.QMessageBox.Discard:
            return False
        elif ret == QtWidgets.QMessageBox.Cancel:
            return True

    def LoadEventTabFromLevel(self):
        """
        Configures the Events tab from the data in globals_.Area.defEvents
        """
        defEvents = globals_.Area.defEvents
        checked = Qt.Checked
        unchecked = Qt.Unchecked

        data = globals_.Area.Metadata.binData('EventNotes_A%d' % globals_.Area.areanum)
        eventTexts = {}
        if data is not None:
            # Iterate through the data
            idx = 0
            while idx < len(data):
                eventId = data[idx]
                idx += 1
                rawStrLen = data[idx:idx + 4]
                idx += 4
                strLen = (rawStrLen[0] << 24) | (rawStrLen[1] << 16) | (rawStrLen[2] << 8) | rawStrLen[3]
                rawStr = data[idx:idx + strLen]
                idx += strLen
                newStr = ''
                for char in rawStr: newStr += chr(char)
                eventTexts[eventId] = newStr

        for id in range(64):
            item = self.eventChooserItems[id]
            value = 1 << id
            item.setCheckState(0, checked if (defEvents & value) != 0 else unchecked)
            if id in eventTexts:
                item.setText(1, eventTexts[id])
            else:
                item.setText(1, '')
            item.setSelected(False)

        self.eventChooserItems[0].setSelected(True)
        txt0 = ''
        if 0 in eventTexts: txt0 = eventTexts[0]
        self.eventNotesEditor.setText(txt0)

    def handleEventTabItemClick(self, item):
        """
        Handles an item being clicked in the Events tab
        """
        # Write the current note to the event note editor
        noteText = item.text(1)
        self.eventNotesEditor.setText(noteText)

        selIdx = self.eventChooserItems.index(item)
        isOn = (globals_.Area.defEvents & 1 << selIdx) == 1 << selIdx
        if item.checkState(0) == Qt.Checked and not isOn:
            # Turn a bit on
            globals_.Area.defEvents |= 1 << selIdx
            SetDirty()
        elif item.checkState(0) == Qt.Unchecked and isOn:
            # Turn a bit off (mask out 1 bit)
            globals_.Area.defEvents &= ~(1 << selIdx)
            SetDirty()

    def handleEventNotesEdit(self):
        """
        Handles the text within self.eventNotesEditor changing
        """
        newText = self.eventNotesEditor.text()

        # Set the text to the event chooser
        currentItem = self.eventChooser.selectedItems()[0]
        currentItem.setText(1, newText)

        # Save all the events to the metadata
        data = b""
        for id in range(64):
            idtext = str(self.eventChooserItems[id].text(1))
            if idtext == '': continue

            # Add the ID and string length
            data += struct.pack(">2I", id, len(idtext))

            # Add the string
            data += idtext.encode("ascii")

        globals_.Area.Metadata.setBinData('EventNotes_A%d' % globals_.Area.areanum, data)
        SetDirty()

    def handleStampsAdd(self):
        """
        Handles the "Add Stamp" btn being clicked
        """
        # Create a ReggieClip
        selitems = self.scene.selectedItems()
        if len(selitems) == 0: return
        clipboard_o = []
        clipboard_s = []
        ii = isinstance
        type_obj = ObjectItem
        type_spr = SpriteItem
        for obj in selitems:
            if ii(obj, type_obj):
                clipboard_o.append(obj)
            elif ii(obj, type_spr):
                clipboard_s.append(obj)
        RegClp = self.encodeObjects(clipboard_o, clipboard_s)

        # Create a Stamp
        self.stampChooser.addStamp(Stamp(RegClp, 'New Stamp'))

    def handleStampsRemove(self):
        """
        Handles the "Remove Stamp" btn being clicked
        """
        self.stampChooser.removeStamp(self.stampChooser.currentlySelectedStamp())
        self.handleStampSelectionChanged()

    def handleStampsOpen(self):
        """
        Handles the "Open Set..." btn being clicked
        """
        filetypes = ''
        filetypes += globals_.trans.string('FileDlgs', 7) + ' (*.stamps);;'  # *.stamps
        filetypes += globals_.trans.string('FileDlgs', 2) + ' (*)'  # *
        fn = QtWidgets.QFileDialog.getOpenFileName(self, globals_.trans.string('FileDlgs', 6), '', filetypes)[0]
        if fn == '': return

        with open(fn, 'r', encoding='utf-8') as file:
            filedata = file.read()

            if not filedata.startswith('stamps\n------\n'): return

            filesplit = filedata.split('\n')[3:]
            i = 0
            while i < len(filesplit):
                try:
                    # Get data
                    name = filesplit[i]
                    rc = filesplit[i + 1]

                    # Increment the line counter by 3, tp
                    # account for the blank line
                    i += 3

                except IndexError:
                    return

                else:
                    self.stampChooser.addStamp(Stamp(rc, name))

    def handleStampsSave(self):
        """
        Handles the "Save Set As..." btn being clicked
        """
        filetypes = ''
        filetypes += globals_.trans.string('FileDlgs', 7) + ' (*.stamps);;'  # *.stamps
        filetypes += globals_.trans.string('FileDlgs', 2) + ' (*)'  # *
        fn = QtWidgets.QFileDialog.getSaveFileName(self, globals_.trans.string('FileDlgs', 3), '', filetypes)[0]
        if fn == '': return

        newdata = ''
        newdata += 'stamps\n'
        newdata += '------\n'

        for stampobj in self.stampChooser.model.items:
            newdata += '\n'
            newdata += stampobj.Name + '\n'
            newdata += stampobj.ReggieClip + '\n'

        with open(fn, 'w', encoding='utf-8') as f:
            f.write(newdata)

    def handleStampSelectionChanged(self):
        """
        Called when the stamp selection is changed
        """
        newStamp = self.stampChooser.currentlySelectedStamp()
        stampSelected = newStamp is not None
        self.stampRemoveBtn.setEnabled(stampSelected)
        self.stampNameEdit.setEnabled(stampSelected)

        newName = '' if not stampSelected else newStamp.Name
        self.stampNameEdit.setText(newName)

    def handleStampNameEdited(self):
        """
        Called when the user edits the name of the current stamp
        """
        stamp = self.stampChooser.currentlySelectedStamp()
        if not stamp:
            return

        text = self.stampNameEdit.text()
        stamp.Name = text
        stamp.update()

        # Try to get it to update!!! But fail. D:
        for i in range(3):
            self.stampChooser.updateGeometries()
            self.stampChooser.update(self.stampChooser.currentIndex())
            self.stampChooser.update()
            self.stampChooser.repaint()

    def AboutBox(self):
        """
        Shows the about box
        """
        AboutDialog().exec_()

    def HandleInfo(self):
        """
        Records the Level Meta Information
        """
        if globals_.Area.areanum == 1:
            dlg = MetaInfoDialog()
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                globals_.Area.Metadata.setStrData('Title', dlg.levelName.text())
                globals_.Area.Metadata.setStrData('Author', dlg.Author.text())
                globals_.Area.Metadata.setStrData('Group', dlg.Group.text())
                globals_.Area.Metadata.setStrData('Website', dlg.Website.text())

                SetDirty()
                return
        else:
            dlg = QtWidgets.QMessageBox()
            dlg.setText(globals_.trans.string('InfoDlg', 14))
            dlg.exec_()

    def HelpBox(self):
        """
        Shows the help box
        """
        mod_path = module_path()

        file_path = os.path.join('reggiedata', 'help', 'index.html')
        if mod_path is None:
            file_path = os.path.join(os.getcwd(), file_path)
        else:
            file_path = os.path.join(mod_path, file_path)

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))

    def TipBox(self):
        """
        Reggie Next Tips and Commands
        """
        mod_path = module_path()

        file_path = os.path.join('reggiedata', 'help', 'tips.html')
        if mod_path is None:
            file_path = os.path.join(os.getcwd(), file_path)
        else:
            file_path = os.path.join(mod_path, file_path)

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))

    def SelectAll(self):
        """
        Select all objects in the current area
        """
        paintRect = QtGui.QPainterPath()
        paintRect.addRect(float(0), float(0), float(1024 * 24), float(512 * 24))
        self.scene.setSelectionArea(paintRect)

    def Deselect(self):
        """
        Deselect all currently selected items
        """
        items = self.scene.selectedItems()
        for obj in items:
            obj.setSelected(False)

    def Undo(self):
        """
        Undoes something
        """
        self.undoStack.undo()

    def Redo(self):
        """
        Redoes something previously undone
        """
        self.undoStack.redo()

    def Cut(self):
        """
        Cuts the selected items
        """
        self.SelectionUpdateFlag = True
        selitems = self.scene.selectedItems()
        self.scene.clearSelection()

        if len(selitems) > 0:
            clipboard_o = []
            clipboard_s = []
            ii = isinstance
            type_obj = ObjectItem
            type_spr = SpriteItem

            for obj in selitems:
                if ii(obj, type_obj):
                    obj.delete()
                    obj.setSelected(False)
                    self.scene.removeItem(obj)
                    clipboard_o.append(obj)
                elif ii(obj, type_spr):
                    obj.delete()
                    obj.setSelected(False)
                    self.scene.removeItem(obj)
                    clipboard_s.append(obj)

            if len(clipboard_o) > 0 or len(clipboard_s) > 0:
                SetDirty()
                self.actions['cut'].setEnabled(False)
                self.actions['paste'].setEnabled(True)
                self.clipboard = self.encodeObjects(clipboard_o, clipboard_s)
                self.systemClipboard.setText(self.clipboard)

        self.levelOverview.update()
        self.SelectionUpdateFlag = False
        self.ChangeSelectionHandler()

    def Copy(self):
        """
        Copies the selected items
        """
        selitems = self.scene.selectedItems()
        if len(selitems) > 0:
            clipboard_o = []
            clipboard_s = []
            ii = isinstance
            type_obj = ObjectItem
            type_spr = SpriteItem

            for obj in selitems:
                if ii(obj, type_obj):
                    clipboard_o.append(obj)
                elif ii(obj, type_spr):
                    clipboard_s.append(obj)

            if len(clipboard_o) > 0 or len(clipboard_s) > 0:
                self.actions['paste'].setEnabled(True)
                self.clipboard = self.encodeObjects(clipboard_o, clipboard_s)
                self.systemClipboard.setText(self.clipboard)

    def Paste(self):
        """
        Paste the selected items
        """
        if self.clipboard is not None:
            self.placeEncodedObjects(self.clipboard)

    def encodeObjects(self, clipboard_o, clipboard_s):
        """
        Encode a set of objects and sprites into a string
        """
        convclip = ['ReggieClip']

        # get objects
        clipboard_o.sort(key=lambda x: x.zValue())

        for item in clipboard_o:
            convclip.append('0:%d:%d:%d:%d:%d:%d:%d' % (
            item.tileset, item.type, item.layer, item.objx, item.objy, item.width, item.height))

        # get sprites
        for item in clipboard_s:
            data = item.spritedata
            convclip.append('1:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d' % (
            item.type, item.objx, item.objy, data[0], data[1], data[2], data[3], data[4], data[5], data[7]))

        convclip.append('%')
        return '|'.join(convclip)

    def placeEncodedObjects(self, encoded, select=True, xOverride=None, yOverride=None):
        """
        Decode and place a set of objects
        """
        self.SelectionUpdateFlag = True
        self.scene.clearSelection()
        added = []

        x1 = 1024
        x2 = 0
        y1 = 512
        y2 = 0

        # global globals_.OverrideSnapping
        globals_.OverrideSnapping = True

        # Remove leading and trailing whitespace
        encoded = encoded.strip()

        if not (encoded.startswith('ReggieClip|') and encoded.endswith('|%')): return

        clip = encoded.split('|')[1:-1]

        if len(clip) > 300:
            result = QtWidgets.QMessageBox.warning(self, 'Reggie', globals_.trans.string('MainWindow', 1),
                                                   QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.No: return

        layers, sprites = self.getEncodedObjects(encoded)

        # Go through the sprites
        for spr in sprites:
            x = spr.objx / 16
            y = spr.objy / 16
            if x < x1: x1 = x
            if x > x2: x2 = x
            if y < y1: y1 = y
            if y > y2: y2 = y

            globals_.Area.sprites.append(spr)
            added.append(spr)
            self.spriteList.addSprite(spr)
            self.scene.addItem(spr)

        # Go through the objects
        for layer in layers:
            for obj in layer:
                xs = obj.objx
                xe = obj.objx + obj.width - 1
                ys = obj.objy
                ye = obj.objy + obj.height - 1
                if xs < x1: x1 = xs
                if xe > x2: x2 = xe
                if ys < y1: y1 = ys
                if ye > y2: y2 = ye

                added.append(obj)
                self.scene.addItem(obj)

        layer0, layer1, layer2 = layers

        if len(layer0) > 0:
            AreaLayer = globals_.Area.layers[0]
            if len(AreaLayer) > 0:
                z = AreaLayer[-1].zValue() + 1
            else:
                z = 16384
            for obj in layer0:
                AreaLayer.append(obj)
                obj.setZValue(z)
                z += 1

        if len(layer1) > 0:
            AreaLayer = globals_.Area.layers[1]
            if len(AreaLayer) > 0:
                z = AreaLayer[-1].zValue() + 1
            else:
                z = 8192
            for obj in layer1:
                AreaLayer.append(obj)
                obj.setZValue(z)
                z += 1

        if len(layer2) > 0:
            AreaLayer = globals_.Area.layers[2]
            if len(AreaLayer) > 0:
                z = AreaLayer[-1].zValue() + 1
            else:
                z = 0
            for obj in layer2:
                AreaLayer.append(obj)
                obj.setZValue(z)
                z += 1

        # now center everything
        zoomscaler = (self.ZoomLevel / 100.0)
        width = x2 - x1 + 1
        height = y2 - y1 + 1
        viewportx = (self.view.XScrollBar.value() / zoomscaler) / 24
        viewporty = (self.view.YScrollBar.value() / zoomscaler) / 24
        viewportwidth = (self.view.width() / zoomscaler) / 24
        viewportheight = (self.view.height() / zoomscaler) / 24

        # tiles
        if xOverride is None:
            xoffset = int(0 - x1 + viewportx + ((viewportwidth / 2) - (width / 2)))
            xpixeloffset = xoffset * 16
        else:
            xoffset = int(0 - x1 + (xOverride / 16) - (width / 2))
            xpixeloffset = xoffset * 16
        if yOverride is None:
            yoffset = int(0 - y1 + viewporty + ((viewportheight / 2) - (height / 2)))
            ypixeloffset = yoffset * 16
        else:
            yoffset = int(0 - y1 + (yOverride / 16) - (height / 2))
            ypixeloffset = yoffset * 16

        for item in added:
            if isinstance(item, SpriteItem):
                item.setPos(
                    (item.objx + xpixeloffset + item.ImageObj.xOffset) * 1.5,
                    (item.objy + ypixeloffset + item.ImageObj.yOffset) * 1.5,
                )
            elif isinstance(item, ObjectItem):
                item.setPos((item.objx + xoffset) * 24, (item.objy + yoffset) * 24)
            if select: item.setSelected(True)

        globals_.OverrideSnapping = False

        self.levelOverview.update()
        SetDirty()
        self.SelectionUpdateFlag = False
        self.ChangeSelectionHandler()

        return added

    def getEncodedObjects(self, encoded):
        """
        Create the objects from a ReggieClip
        """

        layers = ([], [], [])
        sprites = []

        try:
            if not (encoded.startswith('ReggieClip|') and encoded.endswith('|%')): return

            clip = encoded[11:-2].split('|')

            if len(clip) > 300:
                result = QtWidgets.QMessageBox.warning(self, 'Reggie', globals_.trans.string('MainWindow', 1),
                                                       QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
                if result == QtWidgets.QMessageBox.No:
                    return

            for item in clip:
                # Check to see whether it's an object or sprite
                # and add it to the correct stack
                split = item.split(':')
                if split[0] == '0':
                    # object
                    if len(split) != 8: continue

                    tileset = int(split[1])
                    type = int(split[2])
                    layer = int(split[3])
                    objx = int(split[4])
                    objy = int(split[5])
                    width = int(split[6])
                    height = int(split[7])

                    # basic sanity checks
                    if tileset < 0 or tileset > 3: continue
                    if type < 0 or type > 255: continue
                    if layer < 0 or layer > 2: continue
                    if objx < 0 or objx > 1023: continue
                    if objy < 0 or objy > 511: continue
                    if width < 1 or width > 1023: continue
                    if height < 1 or height > 511: continue

                    newitem = self.CreateObject(tileset, type, layer, objx, objy, width, height, add_to_scene = False)

                    layers[layer].append(newitem)

                elif split[0] == '1':
                    # sprite
                    if len(split) != 11: continue

                    objx = int(split[2])
                    objy = int(split[3])
                    data = bytes(map(int, [split[4], split[5], split[6], split[7], split[8], split[9], '0', split[10]]))

                    newitem = SpriteItem(int(split[1]), objx, objy, data)
                    sprites.append(newitem)

        except ValueError:
            # an int() probably failed somewhere
            pass

        return layers, sprites

    def ShiftItems(self):
        """
        Shifts the selected object(s)
        """
        items = self.scene.selectedItems()
        if len(items) == 0: return

        dlg = ObjectShiftDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            xoffset = dlg.XOffset.value()
            yoffset = dlg.YOffset.value()
            if xoffset == 0 and yoffset == 0: return

            type_obj = ObjectItem
            type_spr = SpriteItem
            type_ent = EntranceItem

            if ((xoffset % 16) != 0) or ((yoffset % 16) != 0):
                # warn if any objects exist
                objectsExist = False
                spritesExist = False
                for obj in items:
                    if isinstance(obj, type_obj):
                        objectsExist = True
                    elif isinstance(obj, type_spr) or isinstance(obj, type_ent):
                        spritesExist = True

                if objectsExist and spritesExist:
                    # no point in warning them if there are only objects
                    # since then, it will just silently reduce the offset and it won't be noticed
                    result = QtWidgets.QMessageBox.information(None, globals_.trans.string('ShftItmDlg', 5),
                                                               globals_.trans.string('ShftItmDlg', 6), QtWidgets.QMessageBox.Yes,
                                                               QtWidgets.QMessageBox.No)
                    if result == QtWidgets.QMessageBox.No:
                        return

            xpoffset = xoffset * 1.5
            ypoffset = yoffset * 1.5

            # global globals_.OverrideSnapping
            globals_.OverrideSnapping = True

            for obj in items:
                obj.setPos(obj.x() + xpoffset, obj.y() + ypoffset)

            globals_.OverrideSnapping = False

            SetDirty()

    def SwapObjectsTilesets(self):
        """
        Swaps objects' tilesets
        """
        # global Area

        dlg = ObjectTilesetSwapDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            for layer in globals_.Area.layers:
                for nsmbobj in layer:
                    if nsmbobj.tileset == (dlg.FromTS.value() - 1):
                        nsmbobj.SetType(dlg.ToTS.value() - 1, nsmbobj.type)
                    elif nsmbobj.tileset == (dlg.ToTS.value() - 1) and dlg.DoExchange.checkState() == Qt.Checked:
                        nsmbobj.SetType(dlg.FromTS.value() - 1, nsmbobj.type)

            SetDirty()

    def SwapObjectsTypes(self):
        """
        Swaps objects' types
        """
        # global Area

        dlg = ObjectTypeSwapDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            for layer in globals_.Area.layers:
                for nsmbobj in layer:
                    if nsmbobj.type == (dlg.FromType.value()) and nsmbobj.tileset == (dlg.FromTileset.value() - 1):
                        nsmbobj.SetType(dlg.ToTileset.value() - 1, dlg.ToType.value())
                    elif nsmbobj.type == (dlg.ToType.value()) and nsmbobj.tileset == (
                        dlg.ToTileset.value() - 1) and dlg.DoExchange.checkState() == Qt.Checked:
                        nsmbobj.SetType(dlg.FromTileset.value() - 1, dlg.FromType.value())

            SetDirty()

    def MergeLocations(self):
        """
        Merges selected sprite locations
        """
        items = self.scene.selectedItems()
        if len(items) == 0: return

        newx = 999999
        newy = 999999
        neww = 0
        newh = 0

        type_loc = LocationItem
        for obj in items:
            if isinstance(obj, type_loc):
                if obj.objx < newx:
                    newx = obj.objx
                if obj.objy < newy:
                    newy = obj.objy
                if obj.width + obj.objx > neww:
                    neww = obj.width + obj.objx
                if obj.height + obj.objy > newh:
                    newh = obj.height + obj.objy
                obj.delete()
                obj.setSelected(False)
                self.scene.removeItem(obj)
                self.levelOverview.update()
                SetDirty()

        if newx != 999999 and newy != 999999:
            loc = self.CreateLocation(newx, newy, neww - newx, newh - newy)
            loc.setSelected(True)

    ###########################################################################
    # Functions that create items
    ###########################################################################
    # Maybe move these as static methods to their respective classes
    def CreateLocation(self, x, y, width = 16, height = 16, id_ = None):
        """
        Creates and returns a new location and makes sure it's added to
        the right lists. If 'id' is None, the next id is calculated. This
        function returns None if there is no free location id available.
        """
        if id_ is None:
            # This can be done more efficiently, but 255 is not that big, so it
            # does not really matter.
            all_ids = set(loc.id for loc in globals_.Area.locations)

            for id_ in range(1, 256):
                if id_ not in all_ids:
                    break
            else:
                print("ReggieWindow#CreateLocation: No free location id")
                return None

        globals_.OverrideSnapping = True
        loc = LocationItem(x, y, width, height, id_)
        globals_.OverrideSnapping = False

        loc.positionChanged = self.HandleObjPosChange
        loc.sizeChanged = self.HandleLocSizeChange
        loc.listitem = ListWidgetItem_SortsByOther(loc)

        self.locationList.addItem(loc.listitem)
        self.scene.addItem(loc)
        globals_.Area.locations.append(loc)
        loc.setSelected(True)

        loc.UpdateListItem()

        # We've changed the level, so set the dirty flag
        SetDirty()

        return loc

    def CreateObject(self, tileset, object_num, layer, x, y, width = 1, height = 1, add_to_scene = True):
        """
        Creates and returns a new object and makes sure it's added to
        the right lists.
        """
        layer_list = globals_.Area.layers[layer]
        if len(layer_list) == 0:
            z = (2 - layer) * 8192
        else:
            z = layer_list[-1].zValue() + 1

        obj = ObjectItem(tileset, object_num, layer, x, y, width, height, z)

        if add_to_scene:
            layer_list.append(obj)
            obj.positionChanged = self.HandleObjPosChange
            self.scene.addItem(obj)

            SetDirty()

        return obj

    def CreateEntrance(self, x, y, id_ = None):
        """
        Creates and returns a new entrance and makes sure it's added to
        the right lists. This function returns None if no further entrances
        can be created.
        """
        if id_ is None:
            # This can be done more efficiently, but 255 is not that big
            # a number so it doesn't really matter
            all_ids = set(ent.entid for ent in globals_.Area.entrances)

            id_ = 0
            while id_ <= 255:
                if id_ not in all_ids:
                    break
                id_ += 1

            if id_ == 256:
                print("ReggieWindow#CreateEntrance: No free entrance id")
                return None
        elif id_ in all_ids:
            print("ReggieWindow#CreateEntrance: Given entrance id (%d) already in use" % id_)
            return None

        ent = EntranceItem(x, y, id_, 0, 0, 0, 0, 0, 0, 0x80, 0)
        ent.positionChanged = self.HandleEntPosChange

        # if it's the first available ID, all the other indices
        # should match, so I can just use the ID to insert
        ent.listitem = ListWidgetItem_SortsByOther(ent)
        self.entranceList.insertItem(id_, ent.listitem)

        globals_.Area.entrances.insert(id_, ent)

        self.scene.addItem(ent)
        ent.UpdateListItem()

        SetDirty()

        return ent


    def HandleAddNewArea(self):
        """
        Adds a new area to the level
        """
        if len(globals_.Level.areas) >= 4:
            QtWidgets.QMessageBox.warning(self, 'Reggie', globals_.trans.string('AreaChoiceDlg', 2))
            return

        if self.CheckDirty():
            return

        newID = len(globals_.Level.areas) + 1

        with open('reggiedata/blankcourse.bin', 'rb') as blank:
            course = blank.read()

        L0 = None
        L1 = None
        L2 = None

        if not self.HandleSaveNewArea(course, L0, L1, L2): return
        self.LoadLevel(None, self.fileSavePath, True, newID)

    def HandleImportArea(self):
        """
        Imports an area from another level
        """
        if len(globals_.Level.areas) >= 4:
            QtWidgets.QMessageBox.warning(self, 'Reggie', globals_.trans.string('AreaChoiceDlg', 2))
            return

        if self.CheckDirty():
            return

        filetypes = ''
        filetypes += globals_.trans.string('FileDlgs', 1) + ' (*' + '.arc' + ');;'  # *.arc
        filetypes += globals_.trans.string('FileDlgs', 5) + ' (*' + '.arc' + '.LH);;'  # *.arc.LH
        filetypes += globals_.trans.string('FileDlgs', 2) + ' (*)'  # *
        fn = QtWidgets.QFileDialog.getOpenFileName(self, globals_.trans.string('FileDlgs', 0), '', filetypes)[0]
        if fn == '': return

        with open(str(fn), 'rb') as fileobj:
            arcdata = fileobj.read()
        if (arcdata[0] & 0xF0) == 0x40:  # If LH-compressed
            try:
                arcdata = lh.UncompressLH(arcdata)
            except IndexError:
                QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Decompress', 0),
                                              globals_.trans.string('Err_Decompress', 1, '[file]', str(fn)))
                return

        arc = archive.U8.load(arcdata)

        # get the area count
        areacount = 0

        for item, val in arc.files:
            if val is not None:
                # it's a file
                fname = item[item.rfind('/') + 1:]
                if fname.startswith('course'):
                    maxarea = int(fname[6])
                    if maxarea > areacount: areacount = maxarea

        # choose one
        dlg = AreaChoiceDialog(areacount)
        if dlg.exec_() == QtWidgets.QDialog.Rejected:
            return

        area = dlg.areaCombo.currentIndex() + 1

        # get the required files
        reqcourse = 'course%d.bin' % area
        reqL0 = 'course%d_bgdatL0.bin' % area
        reqL1 = 'course%d_bgdatL1.bin' % area
        reqL2 = 'course%d_bgdatL2.bin' % area

        course = None
        L0 = None
        L1 = None
        L2 = None

        for item, val in arc.files:
            if val is not None:
                fname = item.split('/')[-1]
                if fname == reqcourse:
                    course = val
                elif fname == reqL0:
                    L0 = val
                elif fname == reqL1:
                    L1 = val
                elif fname == reqL2:
                    L2 = val

        # add them to our level
        newID = len(globals_.Level.areas) + 1

        if not self.HandleSaveNewArea(course, L0, L1, L2): return
        self.LoadLevel(None, self.fileSavePath, True, newID)

    def HandleDeleteArea(self):
        """
        Deletes the current area
        """
        result = QtWidgets.QMessageBox.warning(self, 'Reggie', globals_.trans.string('DeleteArea', 0),
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No: return

        if not self.HandleSave(): return

        globals_.Level.deleteArea(globals_.Area.areanum)

        # no error checking. if it saved last time, it will probably work now
        with open(self.fileSavePath, 'wb') as f:
            f.write(globals_.Level.save())
        self.LoadLevel(None, self.fileSavePath, True, 1)

    def HandleChangeGamePath(self, auto=False):
        """
        Change the game path used by the current game definition
        """
        if self.CheckDirty(): return

        path = None
        while not isValidGamePath(path):
            path = QtWidgets.QFileDialog.getExistingDirectory(None,
                                                              globals_.trans.string('ChangeGamePath', 0, '[game]', globals_.gamedef .name))
            if path == '':
                return False

            path = str(path)

            if (not isValidGamePath(path)) and (not globals_.gamedef .custom):  # custom gamedefs can use incomplete folders
                QtWidgets.QMessageBox.information(None, globals_.trans.string('ChangeGamePath', 1),
                                                  globals_.trans.string('ChangeGamePath', 2))
            else:
                SetGamePath(path)
                break

        if not auto: self.LoadLevel(None, '01-01', False, 1)
        return True

    def HandlePreferences(self):
        """
        Edit Reggie Next preferences
        """
        # Show the dialog
        dlg = PreferencesDialog()
        if dlg.exec_() == QtWidgets.QDialog.Rejected:
            return

        # Get the Menubar setting
        setSetting('Menu', 'Menubar')

        # Get the translation
        name = str(dlg.generalTab.Trans.itemData(dlg.generalTab.Trans.currentIndex(), Qt.UserRole))
        setSetting('Translation', name)

        # Get the Zone Entrance Indicators setting
        globals_.DrawEntIndicators = dlg.generalTab.zEntIndicator.isChecked()
        setSetting('ZoneEntIndicators', globals_.DrawEntIndicators)

        # Get the reset data when hiding setting
        globals_.ResetDataWhenHiding = dlg.generalTab.rdhIndicator.isChecked()
        setSetting('ResetDataWhenHiding', globals_.ResetDataWhenHiding)

        # Get the reset data when hiding setting
        globals_.HideResetSpritedata = dlg.generalTab.erbIndicator.isChecked()
        setSetting('HideResetSpritedata', globals_.HideResetSpritedata)

        globals_.EnablePadding = dlg.generalTab.epbIndicator.isChecked()
        setSetting('EnablePadding', globals_.EnablePadding)

        globals_.PaddingLength = dlg.generalTab.psValue.value()
        setSetting('PaddingLength', globals_.PaddingLength)
        
        globals_.PuzzlePy = dlg.generalTab.puzzlePath.text()
        setSetting('PuzzlePy', globals_.PuzzlePy)


        # Get the Toolbar tab settings
        boxes = (
            dlg.toolbarTab.FileBoxes, dlg.toolbarTab.EditBoxes, dlg.toolbarTab.ViewBoxes, dlg.toolbarTab.SettingsBoxes,
            dlg.toolbarTab.HelpBoxes
        )
        ToolbarSettings = {}
        for boxList in boxes:
            for box in boxList:
                ToolbarSettings[box.InternalName] = box.isChecked()
        setSetting('ToolbarActs', ToolbarSettings)

        # Get the theme settings
        setSetting('Theme', dlg.themesTab.themeBox.currentText())
        setSetting('uiStyle', dlg.themesTab.NonWinStyle.currentText())

        # Warn the user that they may need to restart
        QtWidgets.QMessageBox.warning(None, globals_.trans.string('PrefsDlg', 0), globals_.trans.string('PrefsDlg', 30))

    def HandleNewLevel(self):
        """
        Create a new level
        """
        if self.CheckDirty(): return
        self.LoadLevel(None, None, False, 1)

    def HandleOpenFromName(self):
        """
        Open a level using the level picker
        """
        if self.CheckDirty(): return

        LoadLevelNames()
        dlg = ChooseLevelNameDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.LoadLevel(None, dlg.currentlevel, False, 1)

    def HandleOpenFromFile(self):
        """
        Open a level using the filename
        """
        if self.CheckDirty(): return

        filetypes = ''
        filetypes += globals_.trans.string('FileDlgs', 1) + ' (*' + '.arc' + ');;'  # *.arc
        filetypes += globals_.trans.string('FileDlgs', 5) + ' (*' + '.arc' + '.LH);;'  # *.arc.LH
        filetypes += globals_.trans.string('FileDlgs', 2) + ' (*)'  # *
        fn = QtWidgets.QFileDialog.getOpenFileName(self, globals_.trans.string('FileDlgs', 0), '', filetypes)[0]
        if fn == '': return
        self.LoadLevel(None, str(fn), True, 1)

    def HandleSave(self):
        """
        Save a level back to the archive
        """
        if not self.fileSavePath or self.fileSavePath.endswith('.arc.LH'):
            self.HandleSaveAs()
            return

        # global globals_.Dirty, globals_.AutoSaveDirty
        data = globals_.Level.save()

        # maybe pad with null bytes
        if globals_.EnablePadding:
            pad_length = globals_.PaddingLength - len(data)
            if pad_length < 0:
                # err: orig data is longer than padding data
                QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Save', 0), globals_.trans.string('Err_Save', 2, '[orig-len]', len(data), '[pad-len]', globals_.PaddingLength))
                return False

            data += bytes(pad_length)

        try:
            with open(self.fileSavePath, 'wb') as f:
                f.write(data)
        except IOError as e:
            QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Save', 0),
                                          globals_.trans.string('Err_Save', 1, '[err1]', e.args[0], '[err2]', e.args[1]))
            return False

        globals_.Dirty = False
        globals_.AutoSaveDirty = False
        self.UpdateTitle()

        setSetting('AutoSaveFilePath', self.fileSavePath)
        setSetting('AutoSaveFileData', 'x')
        return True

    def HandleSaveNewArea(self, course, L0, L1, L2):
        """
        Save a level back to the archive
        """
        if not self.fileSavePath or self.fileSavePath.endswith('.arc.LH'):
            self.HandleSaveAs()
            return

        # global globals_.Dirty, globals_.AutoSaveDirty
        data = globals_.Level.saveNewArea(course, L0, L1, L2)
        try:
            with open(self.fileSavePath, 'wb') as f:
                f.write(data)
        except IOError as e:
            QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Save', 0),
                                          globals_.trans.string('Err_Save', 1, '[err1]', e.args[0], '[err2]', e.args[1]))
            return False

        globals_.Dirty = False
        globals_.AutoSaveDirty = False
        self.UpdateTitle()

        setSetting('AutoSaveFilePath', self.fileSavePath)
        setSetting('AutoSaveFileData', 'x')
        return True

    def HandleSaveAs(self, copy = False):
        """
        Save a level back to the archive, with a new filename
        """
        fn = QtWidgets.QFileDialog.getSaveFileName(self, globals_.trans.string('FileDlgs', 8 if copy else 3), '',
                                                   globals_.trans.string('FileDlgs', 1) + ' (*' + '.arc' + ');;' + globals_.trans.string(
                                                       'FileDlgs', 2) + ' (*)')[0]
        if fn == '': return

        if not copy:
            # global globals_.Dirty, globals_.AutoSaveDirty
            globals_.AutoSaveDirty = False
            globals_.Dirty = False

            self.fileSavePath = fn
            self.fileTitle = os.path.basename(fn)

        data = globals_.Level.save()

        # maybe pad with null bytes
        if globals_.EnablePadding:
            pad_length = globals_.PaddingLength - len(data)
            if pad_length < 0:
                # err: orig data is longer than padding data
                QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Save', 0), globals_.trans.string('Err_Save', 2, '[orig-len]', len(data), '[pad-len]', globals_.PaddingLength))
                return False

            data += bytes(pad_length)

        with open(fn, 'wb') as f:
            f.write(data)

        if copy:
            return

        setSetting('AutoSaveFilePath', fn)
        setSetting('AutoSaveFileData', 'x')

        self.UpdateTitle()
        self.RecentMenu.AddToList(self.fileSavePath)

    def HandleSaveCopyAs(self):
        """
        Save a level back to the archive, with a new filename, but does not store this filename
        """
        self.HandleSaveAs(True)

    def HandleExit(self):
        """
        Exit the editor. Why would you want to do this anyway?
        """
        self.close()

    def HandleSwitchArea(self, idx):
        """
        Handle activated signals for areaComboBox
        """
        old_idx = globals_.Area.areanum - 1

        if idx == old_idx:
            return

        if self.CheckDirty():
            self.areaComboBox.setCurrentIndex(old_idx)
            return

        ok = self.LoadLevel(None, self.fileSavePath, True, idx + 1)

        if not ok:
            # loading the new area failed, so reset the combobox
            self.areaComboBox.setCurrentIndex(old_idx)

    def HandleUpdateLayer0(self, checked):
        """
        Handle toggling of layer 0 being shown
        """
        # global globals_.Layer0Shown

        globals_.Layer0Shown = checked

        if globals_.Area is not None:
            for obj in globals_.Area.layers[0]:
                obj.setVisible(globals_.Layer0Shown)

        self.scene.update()

    def HandleUpdateLayer1(self, checked):
        """
        Handle toggling of layer 1 being shown
        """
        # global globals_.Layer1Shown

        globals_.Layer1Shown = checked

        if globals_.Area is not None:
            for obj in globals_.Area.layers[1]:
                obj.setVisible(globals_.Layer1Shown)

        self.scene.update()

    def HandleUpdateLayer2(self, checked):
        """
        Handle toggling of layer 2 being shown
        """
        # global globals_.Layer2Shown

        globals_.Layer2Shown = checked

        if globals_.Area is not None:
            for obj in globals_.Area.layers[2]:
                obj.setVisible(globals_.Layer2Shown)

        self.scene.update()

    def HandleTilesetAnimToggle(self, checked):
        """
        Handle toggling of tileset animations
        """
        globals_.TilesetsAnimating = checked
        for tile in globals_.Tiles:
            if tile is not None: tile.resetAnimation()

        self.scene.update()

    def HandleCollisionsToggle(self, checked):
        """
        Handle toggling of tileset collisions viewing
        """
        globals_.CollisionsShown = checked

        setSetting('ShowCollisions', globals_.CollisionsShown)
        self.scene.update()

    def HandleRealViewToggle(self, checked):
        """
        Handle toggling of Real View
        """
        globals_.RealViewEnabled = checked
        SLib.RealViewEnabled = globals_.RealViewEnabled

        setSetting('RealViewEnabled', globals_.RealViewEnabled)
        self.scene.update()

    def HandleSpritesVisibility(self, checked):
        """
        Handle toggling of sprite visibility
        """
        globals_.SpritesShown = checked

        if globals_.Area is not None:
            for spr in globals_.Area.sprites:
                spr.setVisible(globals_.SpritesShown)

        setSetting('ShowSprites', globals_.SpritesShown)
        self.scene.update()

    def HandleSpriteImages(self, checked):
        """
        Handle toggling of sprite images
        """
        globals_.SpriteImagesShown = checked

        setSetting('ShowSpriteImages', globals_.SpriteImagesShown)

        if globals_.Area is not None:
            globals_.DirtyOverride += 1
            for spr in globals_.Area.sprites:
                spr.UpdateRects()
                if globals_.SpriteImagesShown and not globals_.Initializing:
                    spr.setPos(
                        (spr.objx + spr.ImageObj.xOffset) * 1.5,
                        (spr.objy + spr.ImageObj.yOffset) * 1.5,
                    )
                elif not globals_.Initializing:
                    spr.setPos(
                        spr.objx * 1.5,
                        spr.objy * 1.5,
                    )
            globals_.DirtyOverride -= 1

        self.scene.update()

    def HandleLocationsVisibility(self, checked):
        """
        Handle toggling of location visibility
        """
        globals_.LocationsShown = checked

        if globals_.Area is not None:
            for loc in globals_.Area.locations:
                loc.setVisible(globals_.LocationsShown)

        setSetting('ShowLocations', globals_.LocationsShown)
        self.scene.update()

    def HandleCommentsVisibility(self, checked):
        """
        Handle toggling of comment visibility
        """
        globals_.CommentsShown = checked

        if globals_.Area is not None:
            for com in globals_.Area.comments:
                com.setVisible(globals_.CommentsShown)

        setSetting('ShowComments', globals_.CommentsShown)
        self.scene.update()

    def HandlePathsVisibility(self, checked):
        """
        Handle toggling of path visibility
        """
        globals_.PathsShown = checked

        if globals_.Area is not None:
            for node in globals_.Area.paths:
                node.setVisible(globals_.PathsShown)

            for path in globals_.Area.pathdata:
                path['peline'].setVisible(globals_.PathsShown)

        setSetting('ShowPaths', globals_.PathsShown)
        self.scene.update()

    def HandleObjectsFreeze(self, checked):
        """
        Handle toggling of objects being frozen
        """
        globals_.ObjectsFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for layer in globals_.Area.layers:
                for obj in layer:
                    obj.setFlag(flag1, not globals_.ObjectsFrozen)
                    obj.setFlag(flag2, not globals_.ObjectsFrozen)

        setSetting('FreezeObjects', globals_.ObjectsFrozen)
        self.scene.update()

    def HandleSpritesFreeze(self, checked):
        """
        Handle toggling of sprites being frozen
        """
        globals_.SpritesFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for spr in globals_.Area.sprites:
                spr.setFlag(flag1, not globals_.SpritesFrozen)
                spr.setFlag(flag2, not globals_.SpritesFrozen)

        setSetting('FreezeSprites', globals_.SpritesFrozen)
        self.scene.update()

    def HandleEntrancesFreeze(self, checked):
        """
        Handle toggling of entrances being frozen
        """
        globals_.EntrancesFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for ent in globals_.Area.entrances:
                ent.setFlag(flag1, not globals_.EntrancesFrozen)
                ent.setFlag(flag2, not globals_.EntrancesFrozen)

        setSetting('FreezeEntrances', globals_.EntrancesFrozen)
        self.scene.update()

    def HandleLocationsFreeze(self, checked):
        """
        Handle toggling of locations being frozen
        """
        globals_.LocationsFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for loc in globals_.Area.locations:
                loc.setFlag(flag1, not globals_.LocationsFrozen)
                loc.setFlag(flag2, not globals_.LocationsFrozen)

        setSetting('FreezeLocations', globals_.LocationsFrozen)
        self.scene.update()

    def HandlePathsFreeze(self, checked):
        """
        Handle toggling of path nodes being frozen
        """
        globals_.PathsFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for node in globals_.Area.paths:
                node.setFlag(flag1, not globals_.PathsFrozen)
                node.setFlag(flag2, not globals_.PathsFrozen)

        setSetting('FreezePaths', globals_.PathsFrozen)
        self.scene.update()

    def HandleCommentsFreeze(self, checked):
        """
        Handle toggling of comments being frozen
        """
        globals_.CommentsFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if globals_.Area is not None:
            for com in globals_.Area.comments:
                com.setFlag(flag1, not globals_.CommentsFrozen)
                com.setFlag(flag2, not globals_.CommentsFrozen)

        setSetting('FreezeComments', globals_.CommentsFrozen)
        self.scene.update()

    def HandleSwitchGrid(self):
        """
        Handle switching of the grid view
        """
        if globals_.GridType is None:
            globals_.GridType = 'grid'
        elif globals_.GridType == 'grid':
            globals_.GridType = 'checker'
        else:
            globals_.GridType = None

        setSetting('GridType', globals_.GridType)
        self.scene.update()

    def HandleZoomIn(self):
        """
        Handle zooming in
        """
        z = self.ZoomLevel
        zi = self.ZoomLevels.index(z) + 1
        if zi < len(self.ZoomLevels):
            self.ZoomTo(self.ZoomLevels[zi])

    def HandleZoomOut(self):
        """
        Handle zooming out
        """
        z = self.ZoomLevel
        zi = self.ZoomLevels.index(z) - 1
        if zi >= 0:
            self.ZoomTo(self.ZoomLevels[zi])

    def HandleZoomActual(self):
        """
        Handle zooming to the actual size
        """
        self.ZoomTo(100.0)

    def HandleZoomMin(self):
        """
        Handle zooming to the minimum size
        """
        self.ZoomTo(self.ZoomLevels[0])

    def HandleZoomMax(self):
        """
        Handle zooming to the maximum size
        """
        self.ZoomTo(self.ZoomLevels[-1])

    def ZoomTo(self, z):
        """
        Zoom to a specific level
        """
        tr = QtGui.QTransform()
        tr.scale(z / 100.0, z / 100.0)
        self.ZoomLevel = z
        self.view.setTransform(tr)
        self.levelOverview.mainWindowScale = z / 100.0

        zi = self.ZoomLevels.index(z)
        self.actions['zoommax'].setEnabled(zi < len(self.ZoomLevels) - 1)
        self.actions['zoomin'].setEnabled(zi < len(self.ZoomLevels) - 1)
        self.actions['zoomactual'].setEnabled(z != 100.0)
        self.actions['zoomout'].setEnabled(zi > 0)
        self.actions['zoommin'].setEnabled(zi > 0)

        self.ZoomWidget.setZoomLevel(z)
        self.ZoomStatusWidget.setZoomLevel(z)

        # Update the zone grabber rects, to resize for the new zoom level
        for z in globals_.Area.zones:
            z.UpdateRects()

        self.scene.update()

    def HandleOverviewClick(self, x, y):
        """
        Handle position changes from the level overview
        """
        self.view.centerOn(x, y)
        self.levelOverview.update()

    def SaveComments(self):
        """
        Saves the comments data back to self.Metadata
        """
        b = b""
        for com in globals_.Area.comments:
            tlen = len(com.text)
            b += struct.pack(">3I", com.objx, com.objy, tlen)
            b += com.text.encode("utf-8")

        globals_.Area.Metadata.setBinData('InLevelComments_A%d' % globals_.Area.areanum, b)

    def closeEvent(self, event):
        """
        Handler for the main window close event
        """
        if self.CheckDirty():
            event.ignore()
            return

        # save our state
        self.spriteEditorDock.setVisible(False)
        self.entranceEditorDock.setVisible(False)
        self.pathEditorDock.setVisible(False)
        self.locationEditorDock.setVisible(False)
        self.defaultPropDock.setVisible(False)

        # state: determines positions of docks
        # geometry: determines the main window position
        setSetting('MainWindowState', self.saveState(0))
        setSetting('MainWindowGeometry', self.saveGeometry())

        if hasattr(self, 'HelpBoxInstance'):
            self.HelpBoxInstance.close()

        if hasattr(self, 'TipsBoxInstance'):
            self.TipsBoxInstance.close()

        globals_.gamedef.SetLastLevel(str(self.fileSavePath))

        setSetting('AutoSaveFilePath', None)
        setSetting('AutoSaveFileData', 'x')

        event.accept()

    def LoadLevel(self, game, name, isFullPath, areaNum):
        """
        Load a level from any game into the editor
        """
        new = name is None

        # Get the file path, if possible
        if new:
            # Set the filepath variables
            self.fileSavePath = False
            self.fileTitle = 'untitled'

        else:
            globals_.levName = os.path.basename(name)

            checknames = []
            if isFullPath:
                checknames = [name]
            else:
                for ext in globals_.FileExtentions:
                    checknames.append(os.path.join(globals_.gamedef.GetGamePath(), name + ext))

            found = False
            for checkname in checknames:
                if os.path.isfile(checkname):
                    found = True
                    break
            if not found:
                QtWidgets.QMessageBox.warning(self, 'Reggie!',
                                              globals_.trans.string('Err_CantFindLevel', 0, '[name]', checkname),
                                              QtWidgets.QMessageBox.Ok)
                return False
            if not IsNSMBLevel(checkname):
                QtWidgets.QMessageBox.warning(self, 'Reggie!', globals_.trans.string('Err_InvalidLevel', 0),
                                              QtWidgets.QMessageBox.Ok)
                return False

            name = checkname

            # Get the data
            if not globals_.RestoredFromAutoSave:

                # Check if there is a file by this name
                if not os.path.isfile(name):
                    QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_MissingLevel', 0),
                                                  globals_.trans.string('Err_MissingLevel', 1, '[file]', name))
                    return False

                # Set the filepath variables
                self.fileSavePath = name
                self.fileTitle = os.path.basename(self.fileSavePath)

                # Open the file
                with open(self.fileSavePath, 'rb') as fileobj:
                    levelData = fileobj.read()

                # Decompress, if needed
                if (levelData[0] & 0xF0) == 0x40:  # If LH-compressed
                    try:
                        levelData = lh.UncompressLH(levelData)
                    except IndexError:
                        QtWidgets.QMessageBox.warning(None, globals_.trans.string('Err_Decompress', 0),
                                                      globals_.trans.string('Err_Decompress', 1, '[file]', name))
                        return False

            else:
                # Auto-saved level. Check if there's a path associated with it:

                if globals_.AutoSavePath == 'None':
                    self.fileSavePath = None
                    self.fileTitle = globals_.trans.string('WindowTitle', 0)
                else:
                    self.fileSavePath = globals_.AutoSavePath
                    self.fileTitle = os.path.basename(name)

                # Get the level data
                levelData = globals_.AutoSaveData
                SetDirty(noautosave=True)

                # Turn off the autosave flag
                globals_.RestoredFromAutoSave = False

        # Turn the dirty flag off, and keep it that way
        globals_.Dirty = False
        globals_.DirtyOverride += 1

        # First, clear out the existing level.
        self.scene.clearSelection()
        self.CurrentSelection = []
        self.scene.clear()

        # Clear out all level-thing lists
        for thingList in (self.spriteList, self.entranceList, self.locationList, self.pathList, self.commentList):
            thingList.clear()
            thingList.selectionModel().setCurrentIndex(QtCore.QModelIndex(), QtCore.QItemSelectionModel.Clear)

        # Reset these here, because if they are set after
        # creating the objects, they use the old values.
        globals_.CurrentLayer = 1
        globals_.Layer0Shown = True
        globals_.Layer1Shown = True
        globals_.Layer2Shown = True

        # Also enable things that use 'True' by default
        globals_.SpritesShown = True
        globals_.LocationsShown = True

        # Prevent things from snapping when they're created
        globals_.OverrideSnapping = True

        # Load the actual level
        if new:
            self.newLevel()
        else:
            self.LoadLevel_NSMBW(levelData, areaNum)

        # Set the level overview settings
        globals_.mainWindow.levelOverview.maxX = 100
        globals_.mainWindow.levelOverview.maxY = 40

        # Fill up the area list
        self.areaComboBox.clear()
        for i in range(1, len(globals_.Level.areas) + 1):
            self.areaComboBox.addItem(globals_.trans.string('AreaCombobox', 0, '[num]', i))
        self.areaComboBox.setCurrentIndex(areaNum - 1)

        self.levelOverview.update()

        # Scroll to the initial entrance
        startEntID = globals_.Area.startEntrance
        startEnt = None
        for ent in globals_.Area.entrances:
            if ent.entid == startEntID:
                startEnt = ent
                break

        if startEnt is not None:
            self.view.centerOn(startEnt.objx * 1.5, startEnt.objy * 1.5)
        else:
            self.view.centerOn(0, 0)

        self.ZoomTo(100.0)

        # Reset some editor things
        self.actions['showlay0'].setChecked(True)
        self.actions['showlay1'].setChecked(True)
        self.actions['showlay2'].setChecked(True)
        self.actions['showsprites'].setChecked(True)
        self.actions['showlocations'].setChecked(True)
        self.actions['addarea'].setEnabled(len(globals_.Level.areas) < 4)
        self.actions['importarea'].setEnabled(len(globals_.Level.areas) < 4)
        self.actions['deletearea'].setEnabled(len(globals_.Level.areas) > 1)
        self.actions['backgrounds'].setEnabled(len(globals_.Area.zones) > 0)

        # Turn snapping back on
        globals_.OverrideSnapping = False

        # Turn the dirty flag off
        globals_.DirtyOverride -= 1
        self.UpdateTitle()

        # Update UI things
        self.scene.update(0, 0, self.scene.width(), self.scene.height())

        self.levelOverview.Reset()
        self.levelOverview.update()
        QtCore.QTimer.singleShot(20, self.levelOverview.update)

        if new:
            SetDirty()

        else:
            # Add the path to Recent Files
            self.RecentMenu.AddToList(globals_.mainWindow.fileSavePath)

        # If we got this far, everything worked! Return True.
        return True

    def newLevel(self):
        # Create the new level object
        globals_.Level = Level_NSMBW()

        # Load it
        globals_.Level.new()

        # Prepare the object picker
        self.objUseLayer1.setChecked(True)

        self.objPicker.LoadFromTilesets()

        self.objAllTab.setCurrentIndex(0)
        self.objAllTab.setTabEnabled(0, True)
        self.objAllTab.setTabEnabled(1, False)
        self.objAllTab.setTabEnabled(2, False)
        self.objAllTab.setTabEnabled(3, False)

    def LoadLevel_NSMBW(self, levelData, areaNum):
        """
        Performs all level-loading tasks specific to New Super Mario Bros. Wii levels.
        Do not call this directly - use LoadLevel(NewSuperMarioBrosWii, ...) instead!
        """
        # Create the new level object
        globals_.Level = Level_NSMBW()

        # Load it
        if not globals_.Level.load(levelData, areaNum):
            raise Exception

        # Prepare the object picker
        self.objUseLayer1.setChecked(True)

        self.objPicker.LoadFromTilesets()

        self.objAllTab.setCurrentIndex(0)
        self.objAllTab.setTabEnabled(0, (globals_.Area.tileset0 != ''))
        self.objAllTab.setTabEnabled(1, (globals_.Area.tileset1 != ''))
        self.objAllTab.setTabEnabled(2, (globals_.Area.tileset2 != ''))
        self.objAllTab.setTabEnabled(3, (globals_.Area.tileset3 != ''))

        # Load events
        self.LoadEventTabFromLevel()

        # Add all things to the scene
        pcEvent = self.HandleObjPosChange
        for layer in reversed(globals_.Area.layers):
            for obj in layer:
                obj.positionChanged = pcEvent
                self.scene.addItem(obj)

        pcEvent = self.HandleSprPosChange
        for spr in globals_.Area.sprites:
            spr.positionChanged = pcEvent
            self.spriteList.addSprite(spr)
            self.scene.addItem(spr)
            spr.UpdateListItem()

        pcEvent = self.HandleEntPosChange
        for ent in globals_.Area.entrances:
            ent.positionChanged = pcEvent
            ent.listitem = ListWidgetItem_SortsByOther(ent)
            ent.listitem.entid = ent.entid
            self.entranceList.addItem(ent.listitem)
            self.scene.addItem(ent)
            ent.UpdateListItem()

        for zone in globals_.Area.zones:
            self.scene.addItem(zone)

        pcEvent = self.HandleLocPosChange
        scEvent = self.HandleLocSizeChange
        for location in globals_.Area.locations:
            location.positionChanged = pcEvent
            location.sizeChanged = scEvent
            location.listitem = ListWidgetItem_SortsByOther(location)
            self.locationList.addItem(location.listitem)
            self.scene.addItem(location)
            location.UpdateListItem()

        for path in globals_.Area.paths:
            path.positionChanged = self.HandlePathPosChange
            path.listitem = ListWidgetItem_SortsByOther(path)
            self.pathList.addItem(path.listitem)
            self.scene.addItem(path)
            path.UpdateListItem()

        for path in globals_.Area.pathdata:
            peline = PathEditorLineItem(path['nodes'])
            path['peline'] = peline
            self.scene.addItem(peline)
            peline.loops = path['loops']

        for path in globals_.Area.paths:
            path.UpdateListItem()

        for com in globals_.Area.comments:
            com.positionChanged = self.HandleComPosChange
            com.textChanged = self.HandleComTxtChange
            com.listitem = QtWidgets.QListWidgetItem()
            self.commentList.addItem(com.listitem)
            self.scene.addItem(com)
            com.UpdateListItem()

    def OpenPuzzle(self, tilesetIndex = None):
        if not os.path.isfile(globals_.PuzzlePy):
            return
        
        if type(tilesetIndex) == int:
            if self.objAllTab.isTabEnabled(tilesetIndex):
                tilesets = [globals_.Area.tileset0, globals_.Area.tileset1, globals_.Area.tileset2, globals_.Area.tileset3]
                tilesetDir = " " + os.path.join(globals_.gamedef.GetGamePath(), "Texture/" + tilesets[tilesetIndex] + ".arc")
            else: return
        else:
            tilesetDir = ""
        subprocess.Popen("python " + globals_.PuzzlePy + tilesetDir)


    def ReloadTilesets(self, soft=False):
        """
        Reloads all the tilesets. If soft is True, they will not be reloaded if the filepaths have not changed.
        """
        LoadTilesetInfo(True)

        tilesets = [globals_.Area.tileset0, globals_.Area.tileset1, globals_.Area.tileset2, globals_.Area.tileset3]
        for idx, name in enumerate(tilesets):
            if (name is not None) and (name != ''):
                LoadTileset(idx, name, not soft)

        self.objPicker.LoadFromTilesets()

        for layer in globals_.Area.layers:
            for obj in layer:
                obj.updateObjCache()

        self.scene.update()

    def ReloadSpritedata(self):
        LoadSpriteData()

        # Reload spritedata editor
        cur_sel_sprite = self.spriteDataEditor.spritetype
        self.spriteDataEditor.setSprite(cur_sel_sprite, True)

        # Update list
        self.sprPicker.UpdateSpriteNames()

        # Redo the search if a search was made
        search = self.spriteSearchTerm.text()
        if search != "":
            self.sprPicker.SetSearchString(search)

    def ChangeSelectionHandler(self):
        """
        Update the visible panels whenever the selection changes
        """
        if self.SelectionUpdateFlag: return

        try:
            selitems = self.scene.selectedItems()
        except RuntimeError:
            # must catch this error: if you close the app while something is selected,
            # you get a RuntimeError about the 'underlying C++ object being deleted'
            return

        # do this to avoid flicker
        showSpritePanel = False
        showEntrancePanel = False
        showLocationPanel = False
        showPathPanel = False
        updateModeInfo = False

        # clear our variables
        self.selObj = None
        self.selObjs = None

        self.spriteList.clearSelection()
        self.entranceList.setCurrentItem(None)
        self.locationList.setCurrentItem(None)
        self.pathList.setCurrentItem(None)
        self.commentList.setCurrentItem(None)

        # possibly a small optimization
        func_ii = isinstance
        type_obj = ObjectItem
        type_spr = SpriteItem
        type_ent = EntranceItem
        type_loc = LocationItem
        type_path = PathItem
        type_com = CommentItem

        if len(selitems) == 0:
            # nothing is selected
            self.actions['cut'].setEnabled(False)
            self.actions['copy'].setEnabled(False)
            self.actions['shiftitems'].setEnabled(False)
            self.actions['mergelocations'].setEnabled(False)

        elif len(selitems) == 1:
            # only one item, check the type
            self.actions['cut'].setEnabled(True)
            self.actions['copy'].setEnabled(True)
            self.actions['shiftitems'].setEnabled(True)
            self.actions['mergelocations'].setEnabled(False)

            item = selitems[0]
            self.selObj = item
            if func_ii(item, type_spr):
                showSpritePanel = True
                updateModeInfo = True
            elif func_ii(item, type_ent):
                self.creationTabs.setCurrentIndex(2)
                self.UpdateFlag = True
                self.entranceList.setCurrentItem(item.listitem)
                self.UpdateFlag = False
                showEntrancePanel = True
                updateModeInfo = True
            elif func_ii(item, type_loc):
                self.creationTabs.setCurrentIndex(3)
                self.UpdateFlag = True
                self.locationList.setCurrentItem(item.listitem)
                self.UpdateFlag = False
                showLocationPanel = True
                updateModeInfo = True
            elif func_ii(item, type_path):
                self.creationTabs.setCurrentIndex(4)
                self.UpdateFlag = True
                self.pathList.setCurrentItem(item.listitem)
                self.UpdateFlag = False
                showPathPanel = True
                updateModeInfo = True
            elif func_ii(item, type_com):
                self.creationTabs.setCurrentIndex(7)
                self.UpdateFlag = True
                self.commentList.setCurrentItem(item.listitem)
                self.UpdateFlag = False
                updateModeInfo = True

        else:
            updateModeInfo = True

            # more than one item
            self.actions['cut'].setEnabled(True)
            self.actions['copy'].setEnabled(True)
            self.actions['shiftitems'].setEnabled(True)

        # turn on the Stamp Add btn if applicable
        self.stampAddBtn.setEnabled(len(selitems) > 0)

        # count the # of each type, for the statusbar label
        spr = 0
        ent = 0
        obj = 0
        loc = 0
        path = 0
        com = 0
        for item in selitems:
            if func_ii(item, type_spr): spr += 1
            if func_ii(item, type_ent): ent += 1
            if func_ii(item, type_obj): obj += 1
            if func_ii(item, type_loc): loc += 1
            if func_ii(item, type_path): path += 1
            if func_ii(item, type_com): com += 1

        if loc >= 2:
            self.actions['mergelocations'].setEnabled(True)

        # write the statusbar label text
        text = ''
        if len(selitems) > 0:
            singleitem = len(selitems) == 1
            if singleitem:
                if obj:
                    text = globals_.trans.string('Statusbar', 0)  # 1 object selected
                elif spr:
                    text = globals_.trans.string('Statusbar', 1)  # 1 sprite selected
                elif ent:
                    text = globals_.trans.string('Statusbar', 2)  # 1 entrance selected
                elif loc:
                    text = globals_.trans.string('Statusbar', 3)  # 1 location selected
                elif path:
                    text = globals_.trans.string('Statusbar', 4)  # 1 path node selected
                else:
                    text = globals_.trans.string('Statusbar', 29)  # 1 comment selected
            else:  # multiple things selected; see if they're all the same type
                if not any((spr, ent, loc, path, com)):
                    text = globals_.trans.string('Statusbar', 5, '[x]', obj)  # x objects selected
                elif not any((obj, ent, loc, path, com)):
                    text = globals_.trans.string('Statusbar', 6, '[x]', spr)  # x sprites selected
                elif not any((obj, spr, loc, path, com)):
                    text = globals_.trans.string('Statusbar', 7, '[x]', ent)  # x entrances selected
                elif not any((obj, spr, ent, path, com)):
                    text = globals_.trans.string('Statusbar', 8, '[x]', loc)  # x locations selected
                elif not any((obj, spr, ent, loc, com)):
                    text = globals_.trans.string('Statusbar', 9, '[x]', path)  # x path nodes selected
                elif not any((obj, spr, ent, path, loc)):
                    text = globals_.trans.string('Statusbar', 30, '[x]', com)  # x comments selected
                else:  # different types
                    text = globals_.trans.string('Statusbar', 10, '[x]', len(selitems))  # x items selected
                    types = (
                        (obj, 12, 13),  # variable, translation string ID if var == 1, translation string ID if var > 1
                        (spr, 14, 15),
                        (ent, 16, 17),
                        (loc, 18, 19),
                        (path, 20, 21),
                        (com, 31, 32),
                    )
                    first = True
                    for var, singleCode, multiCode in types:
                        if var > 0:
                            if not first: text += globals_.trans.string('Statusbar', 11)
                            first = False
                            text += globals_.trans.string('Statusbar', (singleCode if var == 1 else multiCode), '[x]', var)
                            # above: '[x]', var) can't hurt if var == 1

                    text += globals_.trans.string('Statusbar', 22)  # ')'
        self.selectionLabel.setText(text)

        self.CurrentSelection = selitems

        for thing in selitems:
            # This helps sync non-objects with objects while dragging
            if not isinstance(thing, ObjectItem):
                thing.dragoffsetx = (((thing.objx // 16) * 16) - thing.objx) * 1.5
                thing.dragoffsety = (((thing.objy // 16) * 16) - thing.objy) * 1.5

        self.spriteEditorDock.setVisible(showSpritePanel)
        self.entranceEditorDock.setVisible(showEntrancePanel)
        self.locationEditorDock.setVisible(showLocationPanel)
        self.pathEditorDock.setVisible(showPathPanel)

        if len(self.CurrentSelection) > 0:
            self.actions['deselect'].setEnabled(True)
        else:
            self.actions['deselect'].setEnabled(False)

        if updateModeInfo:
            globals_.DirtyOverride += 1
            self.UpdateModeInfo()
            globals_.DirtyOverride -= 1

    def HandleObjPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the object being dragged
        """
        if obj == self.selObj:
            if oldx == x and oldy == y: return
            SetDirty()
        self.levelOverview.update()

    def CreationTabChanged(self, nt):
        """
        Handles the selected palette tab changing
        """
        CPT = -1

        if nt == 0:  # objects
            CPT = self.objAllTab.currentIndex()
        elif nt == 1:  # sprites
            # Ensure the user can't paint sprites
            # when the 'current sprites' tab is
            # opened.
            if self.sprAllTab.currentIndex() != 1:
                CPT = 4
        elif nt == 2:
            CPT = 5  # entrances
        elif nt == 3:
            CPT = 7  # locations
        elif nt == 4:
            CPT = 6  # paths
        elif nt == 6:
            CPT = 8  # stamp pad
        elif nt == 7:
            CPT = 9  # comment

        globals_.CurrentPaintType = CPT

    def ObjTabChanged(self, nt):
        """
        Handles the selected slot tab in the object palette changing
        """
        if hasattr(self, 'objPicker'):
            if 0 <= nt <= 3:
                self.objPicker.ShowTileset(nt)
                eval('self.objTS%dTab' % nt).setLayout(self.createObjectLayout)
            self.defaultPropDock.setVisible(False)

        globals_.CurrentPaintType = nt

    def SprTabChanged(self, nt):
        """
        Handles the selected tab in the sprite palette changing
        """
        if nt == 0:
            cpt = 4
        else:
            cpt = -1

        globals_.CurrentPaintType = cpt

    def LayerChoiceChanged(self, nl):
        """
        Handles the selected layer changing
        """
        # global globals_.CurrentLayer
        globals_.CurrentLayer = nl

        # should we replace?
        if QtWidgets.QApplication.keyboardModifiers() == Qt.AltModifier:
            items = self.scene.selectedItems()
            type_obj = ObjectItem
            area = globals_.Area
            change = []

            if nl == 0:
                newLayer = area.layers[0]
            elif nl == 1:
                newLayer = area.layers[1]
            else:
                newLayer = area.layers[2]

            for x in items:
                if isinstance(x, type_obj) and x.layer != nl:
                    change.append(x)

            if len(change) > 0:
                change.sort(key=lambda x: x.zValue())

                if len(newLayer) == 0:
                    z = (2 - nl) * 8192
                else:
                    z = newLayer[-1].zValue() + 1

                if nl == 0:
                    newVisibility = globals_.Layer0Shown
                elif nl == 1:
                    newVisibility = globals_.Layer1Shown
                else:
                    newVisibility = globals_.Layer2Shown

                for item in change:
                    area.RemoveFromLayer(item)
                    item.layer = nl
                    newLayer.append(item)
                    item.setZValue(z)
                    item.setVisible(newVisibility)
                    item.update()
                    item.UpdateTooltip()
                    z += 1

            self.scene.update()
            SetDirty()

    def ObjectChoiceChanged(self, type):
        """
        Handles a new object being chosen
        """
        # global globals_.CurrentObject
        globals_.CurrentObject = type

    def ObjectReplace(self, type):
        """
        Handles a new object being chosen to replace the selected objects
        """
        items = self.scene.selectedItems()
        type_obj = ObjectItem
        tileset = globals_.CurrentPaintType
        changed = False

        for x in items:
            if isinstance(x, type_obj) and (x.tileset != tileset or x.type != type):
                x.SetType(tileset, type)
                x.update()
                changed = True

        if changed:
            SetDirty()

    def SpriteChoiceChanged(self, type):
        """
        Handles a new sprite being chosen
        """
        # global globals_.CurrentSprite
        globals_.CurrentSprite = type
        if type != 1000 and type >= 0:
            self.defaultDataEditor.setSprite(type)
            self.defaultDataEditor.data = b'\0\0\0\0\0\0\0\0\0\0'
            self.defaultDataEditor.update()
            self.defaultPropButton.setEnabled(True)
        else:
            self.defaultPropButton.setEnabled(False)
            self.defaultPropDock.setVisible(False)
            self.defaultDataEditor.update()

    def SpriteReplace(self, type):
        """
        Handles a new sprite type being chosen to replace the selected sprites
        """
        items = self.scene.selectedItems()
        type_spr = SpriteItem
        changed = False

        for x in items:
            if isinstance(x, type_spr):
                x.spritedata = self.defaultDataEditor.data  # change this first or else images get messed up
                x.SetType(type)
                x.update()
                changed = True

        if changed:
            SetDirty()

        self.ChangeSelectionHandler()

    def SelectNewSpriteView(self, type):
        """
        Handles a new sprite view being chosen
        """
        cat = globals_.SpriteCategories[type]
        self.sprPicker.SwitchView(cat)

        isSearch = (type == 0)
        layout = self.spriteSearchLayout
        layout.itemAt(0).widget().setVisible(isSearch)
        layout.itemAt(1).widget().setVisible(isSearch)

    def NewSearchTerm(self, text):
        """
        Handles a new sprite search term being entered
        """
        self.sprPicker.SetSearchString(text)

    def ShowDefaultProps(self):
        """
        Handles the Show Default Properties button being clicked
        """
        self.defaultPropDock.setVisible(True)

    def HandleSprPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the sprite being dragged
        """
        if obj == self.selObj:
            if oldx == x and oldy == y: return
            obj.UpdateListItem()
            SetDirty()

    def SpriteDataUpdated(self, data):
        """
        Handle the current sprite's data being updated
        """
        if self.spriteEditorDock.isVisible():
            obj = self.selObj
            obj.spritedata = data
            obj.UpdateListItem()
            SetDirty()

            obj.UpdateDynamicSizing()

    def HandleEntPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the entrance being dragged
        """
        if oldx == x and oldy == y: return
        obj.UpdateListItem()
        if obj == self.selObj:
            SetDirty()

    def HandlePathPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the path being dragged
        """
        if oldx == x and oldy == y: return
        obj.updatePos()
        obj.pathinfo['peline'].nodePosChanged()
        obj.UpdateListItem()
        if obj == self.selObj:
            SetDirty()

    def HandleComPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the comment being dragged
        """
        if oldx == x and oldy == y: return
        obj.UpdateTooltip()
        obj.handlePosChange(oldx, oldy)
        obj.UpdateListItem()
        if obj == self.selObj:
            self.SaveComments()
            SetDirty()

    def HandleComTxtChange(self, obj):
        """
        Handle the comment's text being changed
        """
        obj.UpdateListItem()
        obj.UpdateTooltip()
        self.SaveComments()
        SetDirty()

    def HandleEntranceSelectByList(self, item):
        """
        Handle an entrance being selected from the list
        """
        if self.UpdateFlag: return

        ent = None
        for check in globals_.Area.entrances:
            if check.listitem == item:
                ent = check
                break
        if ent is None: return

        ent.ensureVisible(QtCore.QRectF(), 192, 192)
        self.scene.clearSelection()
        ent.setSelected(True)

    def HandleEntranceToolTipAboutToShow(self, item):
        """
        Handle an entrance being hovered in the list
        """
        ent = None
        for check in globals_.Area.entrances:
            if check.listitem == item:
                ent = check
                break
        if ent is None: return

        ent.UpdateListItem(True)

    def HandleLocationSelectByList(self, item):
        """
        Handle a location being selected from the list
        """
        if self.UpdateFlag: return

        loc = None
        for check in globals_.Area.locations:
            if check.listitem == item:
                loc = check
                break
        if loc is None: return

        loc.ensureVisible(QtCore.QRectF(), 192, 192)
        self.scene.clearSelection()
        loc.setSelected(True)

    def HandleLocationToolTipAboutToShow(self, item):
        """
        Handle a location being hovered in the list
        """
        loc = None
        for check in globals_.Area.locations:
            if check.listitem == item:
                loc = check
                break
        if loc is None: return

        loc.UpdateListItem(True)

    # def HandleSpriteSelectByList(self, item):
    #     """
    #     Handle a sprite being selected from the list
    #     """
    #     spr = None
    #     for check in globals_.Area.sprites:
    #         if check.listitem == item:
    #             spr = check
    #             break
    #     if spr is None: return

    #     spr.ensureVisible(QtCore.QRectF(), 192, 192)
    #     self.scene.clearSelection()
    #     spr.setSelected(True)

    # def HandleSpriteToolTipAboutToShow(self, item):
    #     """
    #     Handle a sprite being hovered in the list
    #     """
    #     spr = None
    #     for check in globals_.Area.sprites:
    #         if check.listitem == item:
    #             spr = check
    #             break
    #     if spr is None: return

    #     spr.UpdateListItem(True)

    def HandlePathSelectByList(self, item):
        """
        Handle a path node being selected
        """
        path = None
        for check in globals_.Area.paths:
            if check.listitem == item:
                path = check
                break
        if path is None: return

        path.ensureVisible(QtCore.QRectF(), 192, 192)
        self.scene.clearSelection()
        path.setSelected(True)

    def HandlePathToolTipAboutToShow(self, item):
        """
        Handle a path node being hovered in the list
        """
        path = None
        for check in globals_.Area.paths:
            if check.listitem == item:
                path = check
                break
        if path is None: return

        path.UpdateListItem(True)

    def HandleCommentSelectByList(self, item):
        """
        Handle a comment being selected
        """
        comment = None
        for check in globals_.Area.comments:
            if check.listitem == item:
                comment = check
                break
        if comment is None: return

        comment.ensureVisible(QtCore.QRectF(), 192, 192)
        self.scene.clearSelection()
        comment.setSelected(True)

    def HandleCommentToolTipAboutToShow(self, item):
        """
        Handle a comment being hovered in the list
        """
        comment = None
        for check in globals_.Area.comments:
            if check.listitem == item:
                comment = check
                break
        if comment is None: return

        comment.UpdateListItem(True)

    def HandleLocPosChange(self, loc, oldx, oldy, x, y):
        """
        Handle the location being dragged
        """
        if loc == self.selObj:
            if oldx == x and oldy == y: return
            self.locationEditor.setLocation(loc)
            SetDirty()
        loc.UpdateListItem()
        self.levelOverview.update()

    def HandleLocSizeChange(self, loc, width, height):
        """
        Handle the location being resized
        """
        if loc == self.selObj:
            self.locationEditor.setLocation(loc)
            SetDirty()
        loc.UpdateListItem()
        self.levelOverview.update()

    def UpdateModeInfo(self):
        """
        Change the info in the currently visible panel
        """
        self.UpdateFlag = True

        if self.spriteEditorDock.isVisible():
            obj = self.selObj
            self.spriteDataEditor.setSprite(obj.type)
            self.spriteDataEditor.data = obj.spritedata

            self.spriteDataEditor.update()

        elif self.entranceEditorDock.isVisible():
            self.entranceEditor.setEntrance(self.selObj)
        elif self.pathEditorDock.isVisible():
            self.pathEditor.setPath(self.selObj)
        elif self.locationEditorDock.isVisible():
            self.locationEditor.setLocation(self.selObj)

        self.UpdateFlag = False

    def PositionHovered(self, x, y):
        """
        Handle a position being hovered in the view
        """
        info = ''
        hovereditems = self.scene.items(QtCore.QPointF(x, y))
        hovered = None
        type_zone = ZoneItem
        type_peline = PathEditorLineItem
        for item in hovereditems:
            hover = item.hover if hasattr(item, 'hover') else True
            if (not isinstance(item, type_zone)) and (not isinstance(item, type_peline)) and hover:
                hovered = item
                break

        if hovered is not None:
            if isinstance(hovered, ObjectItem):  # Object
                info = globals_.trans.string('Statusbar', 23, '[width]', hovered.width, '[height]', hovered.height, '[xpos]',
                                    hovered.objx, '[ypos]', hovered.objy, '[layer]', hovered.layer, '[type]',
                                    hovered.type, '[tileset]', hovered.tileset + 1)
            elif isinstance(hovered, SpriteItem):  # Sprite
                info = globals_.trans.string('Statusbar', 24, '[name]', hovered.name, '[xpos]', hovered.objx, '[ypos]',
                                    hovered.objy)
            elif isinstance(hovered, SLib.AuxiliaryItem):  # Sprite (auxiliary thing) (treat it like the actual sprite)
                info = globals_.trans.string('Statusbar', 24, '[name]', hovered.parentItem().name, '[xpos]',
                                    hovered.parentItem().objx, '[ypos]', hovered.parentItem().objy)
            elif isinstance(hovered, EntranceItem):  # Entrance
                info = globals_.trans.string('Statusbar', 25, '[name]', hovered.name, '[xpos]', hovered.objx, '[ypos]',
                                    hovered.objy, '[dest]', hovered.destination)
            elif isinstance(hovered, LocationItem):  # Location
                info = globals_.trans.string('Statusbar', 26, '[id]', int(hovered.id), '[xpos]', int(hovered.objx), '[ypos]',
                                    int(hovered.objy), '[width]', int(hovered.width), '[height]', int(hovered.height))
            elif isinstance(hovered, PathItem):  # Path
                info = globals_.trans.string('Statusbar', 27, '[path]', hovered.pathid, '[node]', hovered.nodeid, '[xpos]',
                                    hovered.objx, '[ypos]', hovered.objy)
            elif isinstance(hovered, CommentItem):  # Comment
                info = globals_.trans.string('Statusbar', 33, '[xpos]', hovered.objx, '[ypos]', hovered.objy, '[text]',
                                    hovered.OneLineText())

        self.posLabel.setText(
            globals_.trans.string('Statusbar', 28, '[objx]', int(x / 24), '[objy]', int(y / 24), '[sprx]', int(x / 1.5),
                         '[spry]', int(y / 1.5)))
        self.hoverLabel.setText(info)

    def keyPressEvent(self, event):
        """
        Handles key press events for the main window if needed
        """
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            sel = self.scene.selectedItems()
            if len(sel) > 0:
                self.SelectionUpdateFlag = True
                for obj in sel:
                    obj.delete()
                    obj.setSelected(False)
                    self.scene.removeItem(obj)
                    self.levelOverview.update()
                SetDirty()
                event.accept()
                self.SelectionUpdateFlag = False
                self.ChangeSelectionHandler()
                return
        self.levelOverview.update()

        QtWidgets.QMainWindow.keyPressEvent(self, event)

    def HandleAreaOptions(self):
        """
        Pops up the options for Area Dialogue
        """
        dlg = AreaOptionsDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            SetDirty()

            globals_.Area.timeLimit = dlg.LoadingTab.timer.value() - 200
            globals_.Area.startEntrance = dlg.LoadingTab.entrance.value()
            globals_.Area.toadHouseType = dlg.LoadingTab.toadHouseType.currentIndex()
            globals_.Area.wrapFlag = dlg.LoadingTab.wrap.isChecked()
            globals_.Area.creditsFlag = dlg.LoadingTab.credits.isChecked()
            globals_.Area.ambushFlag = dlg.LoadingTab.ambush.isChecked()
            globals_.Area.unkFlag1 = dlg.LoadingTab.unk1.isChecked()
            globals_.Area.unkFlag2 = dlg.LoadingTab.unk2.isChecked()
            globals_.Area.unkVal1 = dlg.LoadingTab.unk3.value()
            globals_.Area.unkVal2 = dlg.LoadingTab.unk4.value()

            oldnames = [globals_.Area.tileset0, globals_.Area.tileset1, globals_.Area.tileset2, globals_.Area.tileset3]
            assignments = ['globals_.Area.tileset0', 'globals_.Area.tileset1', 'globals_.Area.tileset2', 'globals_.Area.tileset3']
            newnames = dlg.TilesetsTab.values()

            for idx, oldname, assignment, fname in zip(range(4), oldnames, assignments, newnames):

                if fname in ('', None):
                    fname = ''
                elif fname.startswith(globals_.trans.string('AreaDlg', 16)):
                    fname = fname[len(globals_.trans.string('AreaDlg', 17, '[name]', '')):]

                # TODO: Remove this exec
                exec(assignment + ' = fname')

                if fname != '':
                    LoadTileset(idx, fname)
                else:
                    UnloadTileset(idx)

            globals_.mainWindow.objPicker.LoadFromTilesets()
            self.objAllTab.setCurrentIndex(0)
            self.objAllTab.setTabEnabled(0, (globals_.Area.tileset0 != ''))
            self.objAllTab.setTabEnabled(1, (globals_.Area.tileset1 != ''))
            self.objAllTab.setTabEnabled(2, (globals_.Area.tileset2 != ''))
            self.objAllTab.setTabEnabled(3, (globals_.Area.tileset3 != ''))

            for layer in globals_.Area.layers:
                for obj in layer:
                    obj.updateObjCache()

            self.scene.update()

    def HandleZones(self):
        """
        Pops up the options for Zone dialog
        """
        dlg = ZonesDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            SetDirty()
            i = 0

            # resync the zones
            items = self.scene.items()
            func_ii = isinstance
            type_zone = ZoneItem

            for item in items:
                if func_ii(item, type_zone):
                    self.scene.removeItem(item)

            globals_.Area.zones = []

            for tab in dlg.zoneTabs:
                z = tab.zoneObj
                z.id = i
                z.UpdateTitle()
                globals_.Area.zones.append(z)
                self.scene.addItem(z)

                if tab.Zone_xpos.value() < 16:
                    z.objx = 16
                elif tab.Zone_xpos.value() > 24560:
                    z.objx = 24560
                else:
                    z.objx = tab.Zone_xpos.value()

                if tab.Zone_ypos.value() < 16:
                    z.objy = 16
                elif tab.Zone_ypos.value() > 12272:
                    z.objy = 12272
                else:
                    z.objy = tab.Zone_ypos.value()

                if (tab.Zone_width.value() + tab.Zone_xpos.value()) > 24560:
                    z.width = 24560 - tab.Zone_xpos.value()
                else:
                    z.width = tab.Zone_width.value()

                if (tab.Zone_height.value() + tab.Zone_ypos.value()) > 12272:
                    z.height = 12272 - tab.Zone_ypos.value()
                else:
                    z.height = tab.Zone_height.value()

                z.prepareGeometryChange()
                z.UpdateRects()
                z.setPos(z.objx * 1.5, z.objy * 1.5)

                z.modeldark = tab.Zone_modeldark.currentIndex()
                z.terraindark = tab.Zone_terraindark.currentIndex()
                z.cammode = tab.Zone_cammodebuttongroup.checkedId()
                z.camzoom = tab.Zone_screenheights.currentIndex()
                z.camtrack = tab.Zone_direction.currentIndex()

                if tab.Zone_yrestrict.isChecked():
                    z.mpcamzoomadjust = tab.Zone_mpzoomadjust.value()
                else:
                    z.mpcamzoomadjust = 15

                if tab.Zone_vnormal.isChecked():
                    z.visibility = 0
                    z.visibility = z.visibility + tab.Zone_visibility.currentIndex()
                if tab.Zone_vspotlight.isChecked():
                    z.visibility = 16
                    z.visibility = z.visibility + tab.Zone_visibility.currentIndex()
                if tab.Zone_vfulldark.isChecked():
                    z.visibility = 32
                    z.visibility = z.visibility + tab.Zone_visibility.currentIndex()

                z.yupperbound = tab.Zone_yboundup.value()
                z.ylowerbound = tab.Zone_ybounddown.value()
                z.yupperbound2 = tab.Zone_yboundup2.value()
                z.ylowerbound2 = tab.Zone_ybounddown2.value()
                z.yupperbound3 = tab.Zone_yboundup3.value()
                z.ylowerbound3 = tab.Zone_ybounddown3.value()

                z.music = tab.Zone_musicid.value()
                z.sfxmod = tab.Zone_sfx.currentIndex() << 4
                if tab.Zone_boss.isChecked():
                    z.sfxmod |= 1

                i += 1

            self.actions['backgrounds'].setEnabled(len(globals_.Area.zones) > 0)

        self.levelOverview.update()

    # Handles setting the backgrounds
    def HandleBG(self):
        """
        Pops up the Background settings Dialog
        """
        dlg = BGDialog()
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        SetDirty()
        for tab, z in zip(dlg.BGTabs, globals_.Area.zones):
            # first index: BGA/BGB
            # second index: X/Y
            z.XpositionA = tab.pos_boxes[0][0].value()
            z.YpositionA = -tab.pos_boxes[0][1].value()
            z.XpositionB = tab.pos_boxes[1][0].value()
            z.YpositionB = -tab.pos_boxes[1][1].value()

            z.XscrollA = tab.scroll_boxes[0][0].currentIndex()
            z.YscrollA = tab.scroll_boxes[0][1].currentIndex()
            z.XscrollB = tab.scroll_boxes[1][0].currentIndex()
            z.YscrollB = tab.scroll_boxes[1][1].currentIndex()

            z.ZoomA = tab.zoom_boxes[0].currentIndex()
            z.ZoomB = tab.zoom_boxes[1].currentIndex()

            z.bg1A = tab.hex_boxes[0][0].value()
            z.bg2A = tab.hex_boxes[0][1].value()
            z.bg3A = tab.hex_boxes[0][2].value()

            z.bg1B = tab.hex_boxes[1][0].value()
            z.bg2B = tab.hex_boxes[1][1].value()
            z.bg3B = tab.hex_boxes[1][2].value()

    def HandleScreenshot(self):
        """
        Takes a screenshot of the entire level and saves it
        """

        dlg = ScreenCapChoiceDialog()
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            fn = QtWidgets.QFileDialog.getSaveFileName(globals_.mainWindow, globals_.trans.string('FileDlgs', 3), '/untitled.png',
                                                       globals_.trans.string('FileDlgs', 4) + ' (*.png)')[0]
            if fn == '': return
            fn = str(fn)

            if dlg.zoneCombo.currentIndex() == 0:
                ScreenshotImage = QtGui.QImage(globals_.mainWindow.view.width(), globals_.mainWindow.view.height(),
                                               QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                globals_.mainWindow.view.render(RenderPainter,
                                       QtCore.QRectF(0, 0, globals_.mainWindow.view.width(), globals_.mainWindow.view.height()),
                                       QtCore.QRect(QtCore.QPoint(0, 0),
                                                    QtCore.QSize(globals_.mainWindow.view.width(), globals_.mainWindow.view.height())))
                RenderPainter.end()
            elif dlg.zoneCombo.currentIndex() == 1:
                maxX = maxY = 0
                minX = minY = 0x0ddba11
                for z in globals_.Area.zones:
                    if maxX < ((z.objx * 1.5) + (z.width * 1.5)):
                        maxX = ((z.objx * 1.5) + (z.width * 1.5))
                    if maxY < ((z.objy * 1.5) + (z.height * 1.5)):
                        maxY = ((z.objy * 1.5) + (z.height * 1.5))
                    if minX > z.objx * 1.5:
                        minX = z.objx * 1.5
                    if minY > z.objy * 1.5:
                        minY = z.objy * 1.5
                maxX = (1024 * 24 if 1024 * 24 < maxX + 40 else maxX + 40)
                maxY = (512 * 24 if 512 * 24 < maxY + 40 else maxY + 40)
                minX = (0 if 40 > minX else minX - 40)
                minY = (40 if 40 > minY else minY - 40)

                ScreenshotImage = QtGui.QImage(int(maxX - minX), int(maxY - minY), QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                globals_.mainWindow.scene.render(RenderPainter, QtCore.QRectF(0, 0, int(maxX - minX), int(maxY - minY)),
                                        QtCore.QRectF(int(minX), int(minY), int(maxX - minX), int(maxY - minY)))
                RenderPainter.end()

            else:
                i = dlg.zoneCombo.currentIndex() - 2
                ScreenshotImage = QtGui.QImage(globals_.Area.zones[i].width * 1.5, globals_.Area.zones[i].height * 1.5,
                                               QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                globals_.mainWindow.scene.render(RenderPainter,
                                        QtCore.QRectF(0, 0, globals_.Area.zones[i].width * 1.5, globals_.Area.zones[i].height * 1.5),
                                        QtCore.QRectF(int(globals_.Area.zones[i].objx) * 1.5, int(globals_.Area.zones[i].objy) * 1.5,
                                                      globals_.Area.zones[i].width * 1.5, globals_.Area.zones[i].height * 1.5))
                RenderPainter.end()

            ScreenshotImage.save(fn, 'PNG', 50)

    @staticmethod
    def HandleDiagnostics():
        """
        Checks the level for any obvious problems and provides options to autofix them
        """
        dlg = DiagnosticToolDialog()
        dlg.exec_()


def main():
    """
    Main startup function for Reggie
    """
    # Go to the script path
    path = module_path()
    if path is not None:
        os.chdir(path)

    # Create an application
    globals_.app = QtWidgets.QApplication(sys.argv)

    # Load the settings
    globals_.settings = QtCore.QSettings('settings.ini', QtCore.QSettings.IniFormat)

    # Check the version and set the UI style to Fusion by default
    if setting("ReggieVersion") is None:
        setSetting("ReggieVersion", globals_.ReggieVersionFloat)
        setSetting('uiStyle', "Fusion")

    # 4.0 -> oldest version with settings.ini compatible with the current version
    if setting("ReggieVersion") < 4.0 or setting("ReggieVersion") > globals_.ReggieVersionFloat:
        warningBox = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, 'Unsupported settings file', 'Your settings.ini file is unsupported. Please remove it and run Reggie again.')
        warningBox.exec_()
        sys.exit(1)

    # Load the translation (needs to happen first)
    LoadTranslation()

    # Load the style
    GetDefaultStyle()

    # go to the script path
    path = module_path()
    if path is not None:
        os.chdir(module_path())

    # Check if required files are missing
    if FilesAreMissing():
        sys.exit(1)

    # Load required stuff
    # global Sprites
    # global globals_.SpriteListData
    globals_.Sprites = None
    globals_.SpriteListData = None
    LoadGameDef(setting('LastGameDef'))
    LoadActionsLists()
    LoadConstantLists()
    LoadTilesetNames()
    LoadObjDescriptions()
    LoadBgANames()
    LoadBgBNames()
    LoadSpriteData()
    LoadSpriteListData()
    LoadEntranceNames()
    LoadNumberFont()
    LoadTheme()
    SetAppStyle()
    LoadOverrides()
    LoadTilesetInfo()
    SLib.OutlineColor = globals_.theme.color('smi')
    SLib.main()
    sprites.LoadBasics()

    # Set the default window icon (used for random popups and stuff)
    globals_.app.setWindowIcon(GetIcon('reggie'))
    globals_.app.setApplicationDisplayName('Reggie! Next %s' % globals_.ReggieVersionShort)

    gt = setting('GridType')

    if gt == 'checker':
        globals_.GridType = 'checker'

    elif gt == 'grid':
        globals_.GridType = 'grid'

    else:
        globals_.GridType = None

    globals_.CollisionsShown = setting('ShowCollisions', False)
    globals_.RealViewEnabled = setting('RealViewEnabled', True)
    globals_.ObjectsFrozen = setting('FreezeObjects', False)
    globals_.SpritesFrozen = setting('FreezeSprites', False)
    globals_.EntrancesFrozen  = setting('FreezeEntrances', False)
    globals_.LocationsFrozen = setting('FreezeLocations', False)
    globals_.PathsFrozen = setting('FreezePaths', False)
    globals_.CommentsFrozen = setting('FreezeComments', False)
    globals_.SpritesShown = setting('ShowSprites', True)
    globals_.SpriteImagesShown = setting('ShowSpriteImages', True)
    globals_.LocationsShown = setting('ShowLocations', True)
    globals_.CommentsShown = setting('ShowComments', True)
    globals_.PathsShown = setting('ShowPaths', True)
    globals_.DrawEntIndicators = setting('ZoneEntIndicators', False)
    globals_.ResetDataWhenHiding = setting('ResetDataWhenHiding', False)
    globals_.HideResetSpritedata = setting('HideResetSpritedata', False)
    globals_.EnablePadding = setting('EnablePadding', False)
    globals_.PaddingLength = int(setting('PaddingLength', 0))
    globals_.PuzzlePy = setting('PuzzlePy', '')
    SLib.RealViewEnabled = globals_.RealViewEnabled

    # Choose a folder for the game
    # Let the user pick a folder without restarting the editor if they fail
    while not isValidGamePath():
        path = QtWidgets.QFileDialog.getExistingDirectory(None,
                                                          globals_.trans.string('ChangeGamePath', 0, '[game]', globals_.gamedef.name))
        if path == '':
            sys.exit(0)

        SetGamePath(path)
        if not isValidGamePath():
            QtWidgets.QMessageBox.information(None, globals_.trans.string('ChangeGamePath', 1),
                                              globals_.trans.string('ChangeGamePath', 3))
        else:
            setSetting('GamePath', path)
            break

    # Check to see if we have anything saved
    autofile = setting('AutoSaveFilePath')
    autofiledata = setting('AutoSaveFileData', 'x')
    if autofile is not None and autofiledata != 'x':
        result = AutoSavedInfoDialog(autofile).exec_()
        if result == QtWidgets.QDialog.Accepted:
            # global globals_.RestoredFromAutoSave, globals_.AutoSavePath, globals_.AutoSaveData
            globals_.RestoredFromAutoSave = True
            globals_.AutoSavePath = autofile
            globals_.AutoSaveData = bytes(autofiledata)
        else:
            setSetting('AutoSaveFilePath', None)
            setSetting('AutoSaveFileData', 'x')

    # Create and show the main window
    globals_.mainWindow = ReggieWindow()
    globals_.mainWindow.__init2__()  # fixes bugs
    globals_.mainWindow.show()
    if globals_.generateStringsXML:
        globals_.trans.generateXML()

    exitcodesys = globals_.app.exec_()
    globals_.app.deleteLater()
    sys.exit(exitcodesys)


if __name__ == '__main__': main()
