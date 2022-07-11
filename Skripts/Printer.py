import clr
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import PolySurface
clr.AddReference('DSCoreNodes')
import DSCore
from DSCore import List

class Robot:
    def __init__(self):
        self.robot = None
        self.rLCS = [0, 0, 0]
       
    def defineRobot(self, robot):
        """
        Stores Robot information and retrieves location
        """
        self.robot = robot
        
        loc = robot.GetLocation()
        self.rLCS = [loc.X, loc.Y, loc.Z]
        self.rLCS = [round(c,6) for c in self.rLCS]
    
    def go2point(self, pose: list):
        """
        Moves robot to pose
        """
        # TODO: finish method and add inverse kinematics to control robot
        self.robot.SetParameterByName("Theta_1", 45)