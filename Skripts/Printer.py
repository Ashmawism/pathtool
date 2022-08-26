# pyright: reportMissingImports=false
import clr
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import Vector
from Autodesk.DesignScript.Geometry import CoordinateSystem
from Autodesk.DesignScript.Geometry import Point

class Robot:
    def __init__(self):
        self.robot = None
        self.rLCS = [0, 0, 0]
       
    def defineRobot(self, robot, unwrap):
        """
        Stores Robot information and retrieves location
        """
        self.robot = robot
        
        loc = robot.GetLocation()
        tf = unwrap(robot).GetTotalTransform()
        xVec = Vector.ByCoordinates(-tf.BasisY[0],-tf.BasisY[1],-tf.BasisY[2])
        yVec = Vector.ByCoordinates(tf.BasisX[0],tf.BasisX[1],tf.BasisX[2])
        
        self.rLCS = CoordinateSystem.ByOriginVectors(loc, xVec, yVec)
    
    def transformPath(self, polypath):
        GCS = CoordinateSystem.ByOrigin(Point.ByCoordinates(0,0,0))
        polypath = polypath.Transform(self.rLCS, GCS)
        return polypath

    def go2point(self, pose: list):
        """
        Moves robot to pose
        """
        # [ ]: finish method and add inverse kinematics to control robot
        self.robot.SetParameterByName("Theta_1", 45)