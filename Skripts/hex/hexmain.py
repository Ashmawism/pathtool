from ast import main
from HexaImp import *
import matplotlib.pyplot as plt
import numpy as np

class Hexsize:
    def __init__(self, x1,y1):
        self.x = x1
        self.y = y1

class Origin:
    def __init__(self, x1,y1):
        self.x = x1
        self.y = y1




def main():

    Hex1= Hex(0,0,0)
    Hex2 = Hex(0,1,-1)
    s = Hexsize(1,1)
    origin = Origin(0,0)

    #h = math.sqrt(3) * 
    
    a = Layout(layout_flat,s,origin)
    b = Layout(layout_flat,s, Origin(origin.x + (1.5*s.x) ,origin.y+s.y) )
    
    test1=polygon_corners(a,Hex1)
    test2 = polygon_corners(b,Hex2)
    '''
    print(test2[1])
    print(test2[2])
    print(test2[3])
    print(test2[4])
    print(test2[5])
    print(test2[0])
    '''
    x_coordinates = []
    y_coordinates = []

    x1_coordinates = []
    y1_coordinates = []
    for i in list(range(6)):
        x2 = test2[i].x
        y2 = test2[i].y
        
        x1 = test1[i].x
        y1 = test1[i].y
        
        x_coordinates.append(x2)
        y_coordinates.append(y2)
        
        x1_coordinates.append(x1)
        y1_coordinates.append(y1)


    x_coordinates.append(x_coordinates[0])
    y_coordinates.append(y_coordinates[0])

    x1_coordinates.append(x1_coordinates[0])
    y1_coordinates.append(y1_coordinates[0])



       #print ('the value of x is ',x2,' and the value of y is ', y2)


#### Note - look how to convert the test2 output from Point to a np array where we can print

    plt.plot(x_coordinates,y_coordinates)
    plt.plot(x1_coordinates,y1_coordinates)
    plt.show()







if __name__ == "__main__":
    main()
