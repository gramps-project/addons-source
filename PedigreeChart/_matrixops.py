#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010       Jakim Friant
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# $Id$

"""
Pure python implementation of matrix addition and multiplication.

This module will only be used by PedigreeChart if the numpy package
cannot be imported.

"""

class DimentionError(Exception):
    """
    Exception raised if the dimentions do not match between two matrices.
    """
    pass

class matrix:
    """
    Store one or two-dimentional arrays and provide the ability to add or
    multiply them as matrices.

    """
    def __init__(self, values):
        """
        Create the class with the values and dimentions.  A 1-dimention list
        will be converted to a matrix.

        A = matrix([[1, 0], [1, 3], [2, 0]])

        A = matrix([1, 1]) -> matrix([[1, 1]])

        """
        self.A = values
        self.m = len(self.A)
        if isinstance(self.A[0], list):
            self.n = len(self.A[0])
        else:
            self.A = [self.A]
            self.n = 1

    def __str__(self):
        """Return a string representation of the arrays"""
        str_out = "[[" + ",".join(["%5.2f " % v for v in self.A[0]]) + "],\n"
        for i in range(1, self.m - 1):
            str_out += " [" + ",".join(["%5.2f " % v for v in self.A[i]]) + "],\n"
        str_out += " [" + ",".join(["%5.2f " % v for v in self.A[self.m - 1]]) + "]]\n"
        return str_out

    def __mul__(self, B):
        """Return the result of simple multiplication between this
        matrix and the other.

        A * B -> matrix()

        """
        if B.m != self.n:
            raise DimentionError()

        p = B.n
        C = []
        for i in range(self.m):
            C.append([0.0 for j in range(p)]) # initialize this row
            for k in range(self.n):
                for j in range(p):
                    C[i][j] += self.A[i][k] * B.A[k][j]
        return matrix(C)

    def __add__(self, B):
        """Return the result of adding another matrix to this one.

        A + B -> matrix()

        Note: adding a 1x2 matrix to this one will result in the other
        matrix being added to each row individually, otherwise the
        matrices must be the same dimentions.

        """
        C = []
        if B.n > 1:
            if B.m != self.m:
                raise DimentionError()
            for i in range(self.m):
                C.append([self.A[i][j] + B.A[i][j] for j in range(B.n)])
        else:
            for i in range(self.m):
                C.append([self.A[i][j] + B.A[0][j] for j in range(B.m)])
        return matrix(C)

    def __getitem__(self, x):
        """Return the requsted row as a list."""
        return self.A[x]

def test():
    """Verify that the matrix operations return the expected results."""
    A = matrix([[-0.5 ,  0.55],
                    [ 0.0 ,  0.55],
                    [ 0.0 ,  0.75],
                    [ 0.5 ,  0.25],
                    [ 0.0 , -0.25],
                    [ 0.0 , -0.05],
                    [-0.5 , -0.05],
                    [-0.5 ,  0.55]])
    B = matrix([[-1, 0], [0, 1]])
    C = matrix([[1, 3], [1, 0], [1, 2]])
    D = matrix([[0, 0], [7, 5], [2, 1]])
    E = matrix([3, 4])
    print "A"
    print A
    print "B"
    print B
    print "A * B"
    print A * B
    print "A + E"
    print A + E
    print "C + D"
    print C + D
    print "__getitem__(0)[1] =", A[0][1]

if __name__ == '__main__':
    test()
