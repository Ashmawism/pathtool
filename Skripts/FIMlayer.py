# pyright: reportMissingImports=false
import clr
from typing import Any, Union, Tuple
from collections import Counter

clr.AddReference('ProtoGeometry')

from Autodesk.DesignScript.Geometry import PolySurface
from Autodesk.DesignScript.Geometry import Plane
from Autodesk.DesignScript.Geometry import Vector
from Autodesk.DesignScript.Geometry import Point
from Autodesk.DesignScript.Geometry import PolyCurve
from Autodesk.DesignScript.Geometry import Curve
from Autodesk.DesignScript.Geometry import NurbsCurve
from Autodesk.DesignScript.Geometry import BoundingBox
from Autodesk.DesignScript.Geometry import Surface
from Autodesk.DesignScript.Geometry import NurbsSurface
from Autodesk.DesignScript.Geometry import Line
from Autodesk.DesignScript.Geometry import Arc
import numpy as np
import ifcopenshell as ifc

class Layer:
    """
    Layer class:
    Stores layer surfaces, print path and speed profile.
    Class attributes store general data applicable for all layers.
    """
    unwrap = None # unwrap function passed from built-in python
    Pattern = None # stores Pattern object (handles pattern generation)
    count = 0 # amount of layers
    inst = [] # registered layers (layers can access other layers)
    offsets = {} # stores offsets of perimeter surfaces
    
    def __init__(self):
        self.path = [] # tool path for print
        self.polyPath = None
        self.speed = None # speed profile
        self.surface = None # contains slicing surface (Plane for planar layers, NURBS surface for non-planar)
        self.slice = None # contains layer slice
        self.perimeter = None # stores outer perimeter as list of Curve
        self.PolyPerimeter = None # stores outer perimeter as PolyCurve
        self.sides = [] # list for sides
        self.corners = [] # list for corner types
        self.origin = None # origin of layer surface
        self.redir = False # reverse direction of intersection.
        self.test = None # just for testing
        
        self.count = Layer.count # layer ID
        Layer.inst.append(self) # registering self
        Layer.count += 1 # counting Layers
        self.height = Layer.count * Layer.Pattern.H # Sets layer height for individual layers
        # for non-planar layers height will refer to the max Z of its bounding box.
    
    def get_noc(self) -> int: 
        return len(self.path)

    @classmethod
    def changeRef(cls, newRef: Point):
        """changes reference Point, to change start curve."""
        cls.ref = newRef 

    @classmethod
    def addOffset(cls, surf, dist):
        cls.offsets[f"{dist}"] = surf
    
    def defineLsurface(self, bb: BoundingBox, surf: Union[Surface, PolySurface, NurbsSurface]=None, nV: Vector=None):
        """
        defines slicing surface from input.
        if surf != None -> non-planar 
        else -> planar
        nV: sets normal vector if different than vertical axis.
        bb: Bounding Box of the BIM component.
        """
        if nV == None:
            nV = Vector.ZAxis() # vertical axis
        
        if surf:
            pass # placeholder for non-planar layer definition.
        else:
            minP = bb.MinPoint
            maxP = bb.MaxPoint
            x = (minP.X + maxP.X)/2 # center x-coordinate
            y = (minP.Y + maxP.Y)/2 # center y-coordinate
            self.origin = Point.ByCoordinates(x, y, self.height) # defines origin in xy-center of the component
            self.surface = Plane.ByOriginNormal(self.origin, nV) # sets Plane at Origin with normal nV
    
    def setPerimeter(self, surf: Surface, sides: Curve):
        """
        Intersects boundary surfaces of component with layer surface to get perimeter curves for reference.
        Also determines which of the perimeter curves are sides.
        surf: boundary surface of component
        sides: side surfaces of the component
        """
        per = Layer.unwrap(self.surface.Intersect(surf))
        self.perimeter = per
        self.PolyPerimeter = per[0] # initialize Join
        
        alt = 0
        try:
            for p in per[1:]:
                self.PolyPerimeter = self.PolyPerimeter.Join(p) # Join to PolyCurve
        except:
            self.PolyPerimeter = None
            print("PolyPerimeter failed")

        # determine sides
        for p in per:
            for s in sides:
                t = Layer.unwrap(p.Intersect(s))
                
                if t and isinstance(t[0], type(p)): # intersection with side surface should reveil same type of curve.
                    self.sides.append(p)
        
        # determine side closest to reference point Layer.ref
        minD = 10000 # some large value
        for n,s in enumerate(self.sides):
            if s.DistanceTo(Layer.Pattern.ref) < minD: # overwrite minD if smaller.
                minD = n
        
        self.sides = self.Pattern.rotate(self.sides, minD) # rotate to closest side

    def planLayerPath(self):
        Layer.Pattern.doPathPlanning(self)
        self.createPolyPath()

    def interlayerAccess(self):
        aC = self.path[0]
        newAC = [Layer.unwrap(c.Explode()[0]) for c in aC.TrimInteriorByParameter(0.25,0.75)]
    
        newAC.extend(self.path)
        newAC = self.rotate(newAC, 1)
        
        self.test = newAC

    def determineCurveSE(self):
        """
        Determines the Start End (SE) connection type of curves.
        """
        idx = [self.perimeter.index(s) for s in self.sides]
        parts = [pC for pC in self.perimeter[min(idx)+1:max(idx)] if not(isinstance(pC,Arc) and pC.Radius - Layer.Pattern.R < 0.001)]
        parts = iter(parts)
        
        curveT = [-1]
        
        prevC = next(parts, -1)
        nextC = next(parts, -1)
        
        while nextC != -1:
            angle = prevC.TangentAtParameter(1).AngleAboutAxis(nextC.TangentAtParameter(0), Vector.ZAxis())
            
            if (angle < 0.001) or (abs(angle - 360) < 0.01):
                t = 0
            elif angle > 180:
                t = 1
            else:
                t = 2
            
            curveT.append(t)
            prevC = nextC
            nextC = next(parts, -1)
        
        curveT.append(-1)
        
        self.corners = curveT

    def createIFCentity(self, fim: ifc.file, createAxis2Placement, GUID, lPlacement):
        o = self.origin
        ownerHistory = fim.by_id(5)
        context = fim.by_id(11)
        pOrigin = fim.createIfcCartesianPoint((0.0, 0.0, o.Z))
            
        surfacePlacement = fim.createIfcAxis2Placement3D(pOrigin, None, None)
        surface = fim.createIfcPlane(surfacePlacement)
        segments = []
        for p in self.PolyPerimeter.Explode():
            segments.append(self.createIfcCurveSegment(fim, p, createAxis2Placement))
        Ccurve = fim.createIfcCompositeCurve(segments, False)
        lSurface = fim.createIfcCurveBoundedPlane(surface, Ccurve, [])
        # [ ]: create composite curve on surface
        path = self.polyPath.Explode()
        pathsegments = []
        for n, c in enumerate(path):
            #if n != len(path)-1:
            pathsegments.append(self.createIfcCurveSegment(fim, c, createAxis2Placement))
            #else:
            #    segments.append(self.createIfcCurveSegment(fim, p, createAxis2Placement, 'DISCONTINUOUS'))

        pcurve = fim.createIfcCompositeCurve(pathsegments, False)

        axisRepresentation = fim.createIfcShapeRepresentation(context, "Axis", "Curve3D", [pcurve])
        bodyRepresentation = fim.createIfcShapeRepresentation(context, "Surface", "Surface3D", [lSurface])
        productShape = fim.createIfcProductDefinitionShape(None, None, [axisRepresentation, bodyRepresentation])

        return fim.createIfcBuildingElementProxy(GUID, ownerHistory, f"Layer_{self.count}", "a print layer", None, lPlacement, productShape, None, 'ELEMENT')

    def createPolyPath(self):
        self.polyPath = PolyCurve.ByJoinedCurves(self.path, 0.0005)

    @staticmethod
    def createIfcCurveSegment(fim, curve, createAxis2Placement, transition='CONTINUOUS'):
        sP = curve.StartPoint
        eP = curve.EndPoint
        sP = fim.createIfcCartesianPoint((sP.X, sP.Y, sP.Z))
        eP = fim.createIfcCartesianPoint((eP.X, eP.Y, eP.Z))

        if isinstance(curve, Line):
            segment = fim.createIfcPolyLine([sP, eP])
        elif isinstance(curve, Arc):
            cP = curve.CenterPoint
            n = curve.Normal
            r = curve.Radius
            placement = createAxis2Placement(fim, (cP.X, cP.Y, cP.Z), (n.X, n.Y, n.Z))
            circle = fim.createIfcCircle(placement, r)
            segment = fim.createIfcTrimmedCurve(circle, [sP], [eP], True, 'CARTESIAN')
        elif isinstance(curve, NurbsCurve):
            d = curve.Degree
            cP = Layer.unwrap(curve.ControlPoints())
            ifcCP = []
            for p in cP:
                ifcP = fim.createIfcCartesianPoint((p.X, p.Y, p.Z))
                ifcCP.append(ifcP)

            form = 'UNSPECIFIED'
            closed = curve.IsClosed
            si = False
            
            knots = Layer.unwrap(curve.Knots())
            kV = list(Counter(knots).keys())
            if min(kV) < 0:
                aV = min(kV)
                kV = [val - aV for val in kV]
            kM = list(Counter(knots).values())
            kT = 'UNSPECIFIED'
            w = Layer.unwrap(curve.Weights())

            segment = fim.createIfcRationalBSplineCurveWithKnots(d, ifcCP, form, closed, si, kM, kV, kT, w)
        else:
            print("something went wrong")
            segment = None

        CCsegment = fim.createIfcCompositeCurveSegment(transition, True, segment)
        
        return CCsegment
