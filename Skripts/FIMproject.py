from fileinput import filename
import importlib

from numpy import product
#import sys
#sys.path.append(r'C:\Users\ne63bic\SharedFiles\CAD\Revit\Dynamo\Scripts')
import BIMproject
importlib.reload(BIMproject)
from BIMproject import BIMdata
import Printer
importlib.reload(Printer)
from Printer import Robot
import FIMlayer
importlib.reload(FIMlayer)
from FIMlayer import Layer
#import ifcopenshell as ifc


import uuid
import time

class Project:
    """
    Project class:
    Represents all necessary information to print the corresponding component.
    """
    count = 0
    unwrap = None
    projects = []

    # IFC definitions
    O = 0., 0., 0.
    X = 1., 0., 0.
    Y = 0., 1., 0.
    Z = 0., 0., 1.
    
    def __init__(self, unwrap):
        self.bimdata = None
        self.printer = Robot() # default position [0, 0, 0]
        self.layers = [] # Layer-wise information (path, speed, etc.)
        
        self.active = False # Flag for partial execution of the script
        Project.unwrap = unwrap # unwrap function passed down from built-in paython
        Project.count += 1
        Project.projects.append(self)
    
    def activate(self):
        """
        Sets active flag to True
        """
        self.active = True
        
    def deactivate(self):
        """
        Sets active flag to False
        """
        self.active = False
        
    def addRobot(self,robot):
        self.printer.defineRobot(robot)
    
    def prepareGeometry(self, inputGeo):
        self.bimdata = BIMdata(inputGeo, self.unwrap)
        #todo: add failsafe
        self.bimdata.extractSolid()
        self.bimdata.extractWidth()
        self.bimdata.extractFaces()
        
    def userDefinitions(self, usrInput):
        self.bimdata.defineInsideOutside(usrInput)
    
    def addLayers(self, usrInput):
        Layer.unwrap = Project.unwrap
        Layer.H = usrInput["LayerH"]
        Layer.D = usrInput["NozzleD"]
        Layer.R = usrInput["Radius"]
        Layer.nop = usrInput["NoP"]
        Layer.pattern = usrInput["Pattern"]
        Layer.patternPar = usrInput["PatternPar"] # TODO: more options here
        reduce = usrInput["reduce"]
        
        if reduce:
            n = usrInput["NoL"]
        else:
            n = int(self.bimdata.height / Layer.H)
        
        for i in range(0,n):
            self.layers.append(Layer())
            
    def initLayers(self):
        surf = self.bimdata.getOffset(0) # edges not important here
        
        for l in self.layers:
            l.defineLsurface(self.bimdata.bb)
            l.setPerimeter(surf, self.bimdata.sides)
            l.determineCurveSE()
    
    def planOuterpath(self):
        #perS, edges = self.bimdata.getOffset(Layer.D/2)
        perSurfs = [self.bimdata.getOffset((n + 0.5)*Layer.D, Layer.R) for n in range(0,Layer.nop + 1)]
        
        for l in self.layers:
            for perS in perSurfs:
                l.addPerimeter(perS)
    
    def continuePath(self):
        for l in self.layers:
            l.addPattern(self.bimdata.getOffset)
    
    def showPath(self) -> list:
        layers = []
        for l in self.layers:
            layers.append(l.path)

        return layers

    def combinePath(self):
        for l in self.layers:
            l.createPolyPath()

    def addAccess(self):
        for l in self.layers:
            pass
        
        pass

""" def export2IFC(self, path):
        if ".ifc" in path.lower():
            fim = ifc.open(path)
        else:
            filename = "AM_Wall.ifc"
            fim = Project.newIfcFile(path, filename)
            path = path + "\\" + filename

        ownerHistory = fim.by_type("IfcOwnerHistory")[0]
        ifcProject = fim.by_type("IfcProject")[0]
        context = fim.by_type("IfcGeometricRepresentationContext")[0]

        componentPlacement = self.create_ifclocalplacement(fim)
        bimGUID = self.bimdata.extractGUID()

        axisRepresentation = None # TODO: extract from BIM
        bodyRepresentation = None # TODO: extract from BIM
        
        #productShape = fim.createIfcProductDefinitionShape(None, None, [ax])
        
        wall = fim.createIfcWall(bimGUID, ownerHistory, "Wall", "printed wall", None, componentPlacement, None, None)

        container_project = fim.createIfcRelAggregates(self.newGUID(), ownerHistory, "Project Container", None, ifcProject, [wall])

        material = fim.createIfcMaterial("wall material")
        material_layer = fim.createIfcMaterialLayer(material, 0.2, None)
        material_layer_set = fim.createIfcMaterialLayerSet([material_layer], None)
        material_layer_set_usage = fim.createIfcMaterialLayerSetUsage(material_layer_set, "AXIS2", "POSITIVE", -0.1)
        fim.createIfcRelAssociatesMaterial(self.newGUID(), ownerHistory, RelatedObjects=[wall], RelatingMaterial=material_layer_set_usage)
        
        ifcLayers = []
        for l in self.layers:
        #    ifcLayers.append(l.createIFCentity(fim))
            layerPlacement = Project.create_ifclocalplacement(fim, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            GUID = self.newGUID()
            lentity = l.createIFCentity(fim, Project.create_ifcaxis2placement, GUID, layerPlacement)
            ifcLayers.append(lentity)

        containerLayer = fim.createIfcRelAggregates(self.newGUID(), ownerHistory, "Layer Container", None, wall, ifcLayers)
         
        print(path)
        fim.write(path)

        return ifc.ifcopenshell_wrapper.schema_by_name("IFC4x2")
  
    @staticmethod
    def newGUID():
        return ifc.guid.compress(uuid.uuid1().hex)

    @classmethod
    def newIfcFile(cls, path, filename):
        timestamp = time.time()
        timestring = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(timestamp))
        creator = "Martin Slepicka"
        organization = "TU Munich"
        application, application_version = "IfcOpenShell", "0.7"
        project_globalid, project_name = Project.newGUID(), "AM Wall"

        temp = '''ISO-10303-21;
        HEADER;
        FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
        FILE_NAME('%(filename)s','%(timestring)s',('%(creator)s'),('%(organization)s'),'%(application)s','%(application)s','');
        FILE_SCHEMA(('IFC4'));
        ENDSEC;
        DATA;
        #1=IFCPERSON($,$,'%(creator)s',$,$,$,$,$);
        #2=IFCORGANIZATION($,'%(organization)s',$,$,$);
        #3=IFCPERSONANDORGANIZATION(#1,#2,$);
        #4=IFCAPPLICATION(#2,'%(application_version)s','%(application)s','');
        #5=IFCOWNERHISTORY(#3,#4,$,.NOCHANGE.,$,#3,#4,%(timestamp)s);
        #6=IFCDIRECTION((1.,0.,0.));
        #7=IFCDIRECTION((0.,0.,1.));
        #8=IFCCARTESIANPOINT((0.,0.,0.));
        #9=IFCAXIS2PLACEMENT3D(#8,$,$);
        #10=IFCDIRECTION((0.,1.));
        #11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#9,#10);
        #12=IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0);
        #13=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
        #14=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);
        #15=IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.);
        #16=IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.);
        #17=IFCMEASUREWITHUNIT(IFCPLANEANGLEMEASURE(0.017453292519943295),#16);
        #18=IFCCONVERSIONBASEDUNIT(#12,.PLANEANGLEUNIT.,'DEGREE',#17);
        #19=IFCUNITASSIGNMENT((#13,#14,#15,#18));
        #20=IFCPROJECT('%(project_globalid)s',#5,'%(project_name)s',$,$,$,$,(#11),#19);
        ENDSEC;
        END-ISO-10303-21;
        ''' % locals()
        
        #temp_handle, temp_filename = tempfile.mkstemp(suffix=".ifc", dir=path, text=True)
        with open(path + "\\" + filename, "w") as f:
            f.write(temp)

        return ifc.open(path + "\\" + filename)
    
    @staticmethod
    def create_ifcaxis2placement(ifcfile, point=O, dir1=Z, dir2=X):
        point = ifcfile.createIfcCartesianPoint(point)
        dir1 = ifcfile.createIfcDirection(dir1)
        dir2 = ifcfile.createIfcDirection(dir2)
        axis2placement = ifcfile.createIfcAxis2Placement3D(point, dir1, dir2)
        return axis2placement

    @staticmethod
    def create_ifclocalplacement(ifcfile, point=O, dir1=Z, dir2=X, relative_to=None):
        axis2placement = Project.create_ifcaxis2placement(ifcfile,point,dir1,dir2)
        ifclocalplacement2 = ifcfile.createIfcLocalPlacement(relative_to,axis2placement)
        return ifclocalplacement2
"""