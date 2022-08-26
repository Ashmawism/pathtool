from ast import main
from HexaImp import *
import matplotlib.pyplot as plt
import numpy as np

class size:
    x = 1
    y = 1

class Origin:
    x = 0
    y = 0



def main():

    a= Hex(0,1,-1)
    s = size()
    origin = Origin()
    test1 = Layout(layout_pointy,s,origin)
    test2=polygon_corners(test1,a)
    test2
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
    for i in list(range(6)):
        x2 = test2[i].x
        y2 = test2[i].y
        x_coordinates.append(x2)
        y_coordinates.append(y2)


    x_coordinates.append(x_coordinates[0])
    y_coordinates.append(y_coordinates[0])


       #print ('the value of x is ',x2,' and the value of y is ', y2)
    print('the current value for the xs is ',x_coordinates)
    print('the current value for the ys is ',y_coordinates)

#### Note - look how to convert the test2 output from Point to a np array where we can print

    plt.plot(x_coordinates,y_coordinates)
    plt.show()







if __name__ == "__main__":
    main()
