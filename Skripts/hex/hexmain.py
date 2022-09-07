from ast import main
from HexaImp import *
import matplotlib.pyplot as plt
import numpy as np


def tuple_to_array(namedtuple,x_coord,y_coord):
    
    if not (x_coord and y_coord):  
    

        for i in range(int(np.size(namedtuple)/2)):
            x = namedtuple[i].x
            y = namedtuple[i].y

            x_coord.append(x)
            y_coord.append(y)

        return 

    else:
        x_coord =[]
        y_coord =[]
        return tuple_to_array(namedtuple,x_coord,y_coord)
     


def main():
    
    
    """
    Hex1= Hex(0,0,0)
    Hex2 = Hex(1,-1,0)
    Hex3 = Hex(0,-3,3)
    s = Hexsize(1,1)
    origin = Origin(0,0)

    h = math.sqrt(3) * s.size
#    newO = Origin(origin.x + (1.5*s.size) ,0.5*h)
    a = Layout(layout_flat,s,origin)
    test1=polygon_corners(a,Hex1)
    test2 = polygon_corners(a,Hex2)
     
    x_coordinates = []
    y_coordinates = []

    
    for i in range(int(np.size(test1)/2)):
        x2 = test2[i].x
        y2 = test2[i].y
        
        x1 = test1[i].x
        y1 = test1[i].y
        
        x_coordinates.append(x2)
        y_coordinates.append(y2)
        
        x_coordinates.append(x1)
        y_coordinates.append(y1)






    plt.plot(x_coordinates,y_coordinates,'ro')
    #plt.plot(x1_coordinates,y1_coordinates)
    plt.show()



    """

    size = Hexsize(0.1,0.1)
    origin = Origin(0,0)
    layout = Layout(layout_flat,size,origin)
    x_coord =[]
    y_coord =[]
    q_ar =[]
    r_ar =[]
    s_ar =[]
    n = 0
    for q in range(-1,3):
        for r in range(-1,1):
            for s in range(-1,3):
                sum = q+r+s
                if (sum) == 0:
                    if (q == 0 or r == 0 or s == 0): 
                        tempx =[]
                        tempy =[] 

                   #     print(q,r,s)
                        hex = Hex(q,s,r)
                        points = polygon_corners(layout,hex) 
                        tuple_to_array(points,tempx,tempy)

                        q_ar.append(q)
                        r_ar.append(r)
                        s_ar.append(s)


                        x_coord = x_coord+tempx
                        y_coord = y_coord +(tempy)

                        plt.plot(x_coord,y_coord,'o')
                        plt.show()
                    
                else:
                    continue

    
    print('the values of th q array is ',q_ar,'the values of th s array is ',s_ar,'the values of th r array is ',r_ar,) 

    plt.plot(x_coord,y_coord,'ro')
    #plt.plot(x1_coordinates,y1_coordinates)
    plt.show()









if __name__ == "__main__":
    main()
