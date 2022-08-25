from ast import main
from HexaImp import *
import matplotlib.pyplot as plt
import numpy as np

class size:
    x = 1
    y = 1

class Origin:
    x = 2
    y = 2



def main():

    a= Hex(0,3,-3)
    s = size()
    origin = Origin()
    test1 = Layout(layout_flat,s,origin)
    test2=polygon_corners(test1,a)
    test2

    

    print(test2)
    points = []

#### Note - look how to convert the test2 output from Point to a np array where we can print

    #plt.plot(test2)
    #plt.show()







if __name__ == "__main__":
    main()
