import logging
import os
import vtk
import slicer
import SampleData
import time
from typing import Annotated
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer import vtkMRMLScalarVolumeNode
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)


class SphereModule(ScriptedLoadableModule):

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("SphereModule")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Examples")]
        self.parent.dependencies = []
        self.parent.contributors = ["Santiramoli - ULPGC"]
        self.parent.helpText = _("""
                                    This is an example of a module for creating a volumetric sphere given two points.
                                    More information: <a href="https://github.com/Santiramoli/SlicerTutorial.git"></a>.
                                """
                                )


# PARAMETERS FOR THE MODULE

@parameterNodeWrapper
class SphereModuleParameterNode:

    """
        The parameters needed by module:

            inputMarkups -  Input node containing the fiducial points selected by the user.
            outputModel -  Output node where the generated 3D model of the sphere will be stored.
            imageThreshold - Opacity value to be applied to the generated model.
            autoUpdate - The model will be automatically updated each time the user modifies an input point.
    """

    inputMarkups: vtkMRMLMarkupsFiducialNode
    outputModel: vtkMRMLModelNode
    imageThreshold: Annotated[float, WithinRange(0, 1)] = 0.5
    autoUpdate: bool = False



# MODULE WIDGET CLASS

class SphereModuleWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

    def __init__(self, parent=None) -> None:
        
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self.observedMarkupNode = None
        self._markupsObserverTag = None

    def setup(self) -> None:
        
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/SphereModule.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = SphereModuleLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.autoUpdateCheckBox.connect("toggled(bool)", self.onEnableAutoUpdate

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

    def cleanup(self) -> None:
        
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        
    """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputMarkups:
            firstaMarkups = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsFiducialNode")
            if firstaMarkups:
                self._parameterNode.inputMarkups = firstaMarkups

        # # If no output model is selected by the user, create a new model node and assign it as the default output
        if not self._parameterNode.outputModel:
            model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "SphereOutput")
            self._parameterNode.outputModel = model

    def setParameterNode(self, inputParameterNode: SphereModuleParameterNode | None) -> None:
        
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

            # Safely check if the UI contains the 'autoUpdateCheckBox' element.
            # If present and checked, activate the auto-update feature for live model updates.
            if hasattr(self.ui, "autoUpdateCheckBox") and self.ui.autoUpdateCheckBox.checked:
                self.onEnableAutoUpdate(True


    def onEnableAutoUpdate(self, enabled: bool) -> None:
        
        """
        Enable or disable automatic updates of the output model when the input markups change.

        If auto-update is enabled, an observer is attached to the input markups node
        to listen for modifications (e.g. when the user moves or adds points).
        If disabled, the observer is removed to stop triggering updates.
        """
        
        # If an observer is already registered, remove it
        if self._markupsObserverTag and self.observedMarkupNode:
            self.observedMarkupNode.RemoveObserver(self._markupsObserverTag)
            self._markupsObserverTag = None
            self.observedMarkupNode = None

        # If enabling auto-update and a valid input markups node exists, add an observer to watch for modifications
        if enabled and self._parameterNode.inputMarkups:
            self.observedMarkupNode = self._parameterNode.inputMarkups
            self._markupsObserverTag = self.observedMarkupNode.AddObserver(
                vtk.vtkCommand.ModifiedEvent, 
                self.onMarkupsUpdated
            )

     def onMarkupsUpdated(self, caller=None, event=None):
        
        """
        Callback function triggered when the input markups node is modified.

        If auto-update is enabled, ensures the output model is valid
        and re-applies the processing logic automatically.
        """

        # Do nothing if auto-update is disabled
        if not self.ui.autoUpdateCheckBox.checked:
            return

        # Ensure the output model node exists before processing
        self.ensureValidOutputModel()

        # Trigger model generation based on updated markups
        self.onApplyButton()



    def _checkCanApply(self, caller=None, event=None) -> None:
        
        """
        Enable or disable the Apply button based on parameter node state.
        The Apply button is enabled only if both input markups and output model are valid.
        """

        if self._parameterNode and self._parameterNode.inputMarkups and self._parameterNode.outputModel:
            self.ui.applyButton.toolTip = _("Create sphere")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input markups and output model")
            self.ui.applyButton.enabled = False


    def ensureValidOutputModel(self):

        """
        Ensure that the output model node is valid.

        If the current outputModel is not a valid vtkMRMLModelNode, it is removed
        from the scene (if possible), and a new model node is created and assigned
        to the parameter node.
        """

        if not isinstance(self._parameterNode.outputModel, vtkMRMLModelNode):
            try:
                slicer.mrmlScene.RemoveNode(self._parameterNode.outputModel)
            except Exception as e:
                pass # Node could not be removed, possibly already deleted
            self._parameterNode.outputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "SphereOutput")

    def onApplyButton(self) -> None:

        """
        Handle Apply button click to generate or update the sphere model.

        Ensures a valid output model exists, then calls the processing logic
        with the current parameter values. If available, updates the UI label
        to show the calculated center of mass. Displays an error message if
        processing fails.
        """

        # Ensure output model node is valid before processing
        self.ensureValidOutputModel()

        try:
            # Call logic to generate the sphere model based on input markups
            self.logic.process(
                self._parameterNode.inputMarkups,
                self._parameterNode.outputModel,
                self._parameterNode.imageThreshold,
            )
            
            # Update center of mass label in the UI (if available)
            if hasattr(self.logic, "centerOfMass") and hasattr(self.ui, "centerOfMassValueLabel"):
                c = self.logic.centerOfMass
                self.ui.centerOfMassValueLabel.setText(f"({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
        except Exception as e:
            slicer.util.errorDisplay(f"Error updating the sphere: {str(e)}")


# MODULE LOGIC CLASS

class SphereModuleLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return SphereModuleParameterNode(super().getParameterNode())

    def getCenterOfMass(self, markupsNode):
        
        """
        Compute the geometric center (center of mass) of all control points in a markups node.

        This function iterates over all fiducial points (control points) in the input
        `vtkMRMLMarkupsFiducialNode`, sums their 3D coordinates, and returns the average
        position as a list of floats [x, y, z].

        Parameters:
            markupsNode (vtkMRMLMarkupsFiducialNode): The input markups node containing points.

        Returns:
            list[float]: A 3-element list representing the center of mass [x, y, z].
                         Returns [0.0, 0.0, 0.0] if no points are defined.
        """

        num = markupsNode.GetNumberOfControlPoints()
        if num == 0:
            return [0.0, 0.0, 0.0]

        sumPos = np.zeros(3)
        for i in range(num):
            pos = markupsNode.GetNthControlPointPositionVector(i)
            sumPos += np.array(pos)

        centerOfMass = sumPos / num
        logging.info(f'Center of mass for {markupsNode.GetName()}: {centerOfMass}')
        return centerOfMass.tolist()


    def process(self,
                inputMarkups: vtkMRMLMarkupsFiducialNode,
                outputModel: vtkMRMLModelNode,
                imageThreshold: float = 0.5) -> None:
        """
        Generate a 3D sphere model based on two fiducial points.

        This method uses the first two control points from a markups node to define
        the diameter of a sphere. The midpoint is used as the center, and the distance
        between the points determines the radius. A new vtkSphere is generated and assigned
        to the output model.

        Parameters:
            inputMarkups (vtkMRMLMarkupsFiducialNode): Fiducial node containing at least two points.
            outputModel (vtkMRMLModelNode): Model node where the generated sphere will be stored.
            imageThreshold (float): Used here as the opacity value for the resulting model.
        """
            
        # Compute and store the center of mass of all control points for later use
        self.centerOfMass = self.getCenterOfMass(inputMarkups)

        # Validate input nodes
        if not inputMarkups or not outputModel:
            raise ValueError("Input markups or output model is invalid")

        # Ensure that there are at least two points to define a sphere
        numPoints = inputMarkups.GetNumberOfControlPoints()
        if numPoints < 2:
            raise ValueError("At least two points are required.")

        # Retrieve positions of the first two points
        p0 = [0.0, 0.0, 0.0]
        p1 = [0.0, 0.0, 0.0]
        inputMarkups.GetNthControlPointPosition(0, p0)
        inputMarkups.GetNthControlPointPosition(1, p1)

        # Compute sphere center (midpoint between p0 and p1) and radius
        center = [(p0[i] + p1[i]) / 2.0 for i in range(3)]
        radius = np.linalg.norm(np.array(p0) - np.array(p1)) / 2.0

        # Create a high-resolution VTK sphere based on calculated center and radius
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(center)
        sphere.SetRadius(radius)
        sphere.SetThetaResolution(64)
        sphere.SetPhiResolution(64)
        sphere.Update()
    
        # Set the generated geometry into the output model node
        outputModel.SetAndObservePolyData(sphere.GetOutput())
        outputModel.CreateDefaultDisplayNodes()

        # Configure display properties for the model node
        displayNode = outputModel.GetDisplayNode()
        displayNode.SetColor(0.1, 0.6, 0.9)
        displayNode.SetOpacity(imageThreshold)
        displayNode.SetSliceIntersectionThickness(2)

        displayNode.SetVisibility2D(True)





# MODULE TEST

class SphereModuleTest(ScriptedLoadableModuleTest):
    
    """Unit test for the SphereModule."""

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_SphereModule1()

    def test_generateSphereFromTwoFiducials(self):
        """Test sphere generation using two fiducial points."""

        self.delayDisplay("Creating test input markups")

        # Create fiducials node with two points
        markupsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "TestFiducials")
        markupsNode.AddControlPoint(0, 0, 0)
        markupsNode.AddControlPoint(10, 0, 0)

        # Create empty model node
        outputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestSphereOutput")

        # Run logic
        logic = SphereModuleLogic()
        logic.process(markupsNode, outputModel, imageThreshold=0.7)

        self.delayDisplay("Verifying output model")

        # Ensure model has geometry
        polyData = outputModel.GetPolyData()
        self.assertIsNotNone(polyData)
        self.assertGreater(polyData.GetNumberOfPoints(), 0)
        self.assertGreater(polyData.GetNumberOfCells(), 0)

        # Check that center of mass is as expected
        expectedCenter = [5.0, 0.0, 0.0]
        centerOfMass = logic.centerOfMass
        for i in range(3):
            self.assertAlmostEqual(centerOfMass[i], expectedCenter[i], places=3)

        self.delayDisplay("SphereModule logic test passed")