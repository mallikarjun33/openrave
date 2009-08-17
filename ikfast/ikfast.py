#!/usr/bin/env python
# Software License Agreement (Lesser GPL)
#
# Copyright (C) 2009 Rosen Diankov
#
# ikfast is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option) any later version.
#
# ikfast is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import sys, copy, time
from string import atoi,atof
from sympy import *
from optparse import OptionParser

def xcombinations(items,n):
    if n == 0: yield[]
    else:
        for  i in xrange(len(items)):
            for cc in xcombinations(items[i+1:],n-1):
                yield [items[i]]+cc

import weakref, inspect

class MetaInstanceTracker(type):
    def __init__(cls, name, bases, ns):
        super(MetaInstanceTracker, cls).__init__(name, bases, ns)
        cls.__instance_refs__ = []
    def __instances__(cls):
        instances = []
        validrefs = []
        for ref in cls.__instance_refs__:
            instance = ref()
            if instance is not None:
                instances.append(instance)
                validrefs.append(ref)
        cls.__instance_refs__ = validrefs
        return instances

class InstanceTracker(object):
    __metaclass__ = MetaInstanceTracker
    def __new__(*args, **kwargs):
        cls = args[0]
        self = super(InstanceTracker, cls).__new__(*args, **kwargs)
        cls.__instance_refs__.append(weakref.ref(self))
        return self

    def __reduce_ex__(self, proto):
        return super(InstanceTracker, self).__reduce_ex__(2)

class MetaAutoReloader(MetaInstanceTracker):
    def __init__(cls, name, bases, ns):
        super(MetaAutoReloader, cls).__init__(name, bases, ns)
        f = inspect.currentframe().f_back
        for d in [f.f_locals, f.f_globals]:
            if name in d:
                old_class = d[name]
                for instance in old_class.__instances__():
                    instance.change_class(cls)
                    cls.__instance_refs__.append(weakref.ref(instance))

                for subcls in old_class.__subclasses__():
                    newbases = []
                    for base in subcls.__bases__:
                        if base is old_class:
                            newbases.append(cls)
                        else:
                            newbases.append(base)
                    subcls.__bases__ = tuple(newbases)
                break

class AutoReloader(InstanceTracker):
    __metaclass__ = MetaAutoReloader
    def change_class(self, new_class):
        self.__class__ = new_class


class SolverSolution:
    jointname = None
    jointeval = None
    jointevalcos = None
    jointevalsin = None
    AddPi = False
    def __init__(self, jointname, jointeval=None,jointevalcos=None,jointevalsin=None,AddPi=False):
        self.jointname = jointname
        self.jointeval = jointeval
        self.jointevalcos = jointevalcos
        self.jointevalsin = jointevalsin
        self.AddPi = AddPi
        assert(jointeval is not None or jointevalcos is not None or jointevalsin is not None)

    def generate(self, generator):
        return generator.generateSolution(self)
    def end(self, generator):
        return generator.endSolution(self)

class SolverBranch(AutoReloader):
    jointname = None
    jointeval = None # only used for evaluation, do use these for real solutions
    # list of tuples, first gives expected value of joint, then the code that follows.
    # Last element in list is executed if nothing else is
    jointbranches = None
    def __init__(self, jointname, jointeval, jointbranches):
        self.jointname = jointname
        self.jointeval = jointeval
        self.jointbranches = jointbranches
        assert(jointeval is not None)

    def generate(self, generator):
        return generator.generateBranch(self)
    def end(self, generator):
        return generator.endBranch(self)

class SolverFreeParameter(AutoReloader):
    jointname = None
    jointtree = None
    def __init__(self, jointname, jointtree):
        self.jointname = jointname
        self.jointtree = jointtree

    def generate(self, generator):
        return generator.generateFreeParameter(self)
    def end(self, generator):
        return generator.endFreeParameter(self)

class SolverIKChain(AutoReloader):
    solvejointvars = None
    freejointvars = None
    Tee = None
    jointtree = None
    def __init__(self, solvejointvars, freejointvars, Tee, jointtree):
        self.solvejointvars = solvejointvars
        self.freejointvars = freejointvars
        self.Tee = Tee
        self.jointtree = jointtree

    def generate(self, generator):
        return generator.generateChain(self)
    def end(self, generator):
        return generator.endChain(self)

class SolverRotation(AutoReloader):
    T = None
    jointtree = None
    def __init__(self, T, jointtree):
        self.T = T
        self.jointtree = jointtree

    def generate(self, generator):
        return generator.generateRotation(self)
    def end(self, generator):
        return generator.endRotation(self)

class SolverStoreSolution(AutoReloader):
    alljointvars = None
    def __init__(self, alljointvars):
        self.alljointvars = alljointvars
    def generate(self, generator):
        return generator.generateStoreSolution(self)
    def end(self, generator):
        return generator.endStoreSolution(self)

class SolverSequence(AutoReloader):
    jointtrees = None
    def __init__(self, jointtrees):
        self.jointtrees = jointtrees
    def generate(self, generator):
        return generator.generateSequence(self)
    def end(self, generator):
        return generator.endSequence(self)

class SolverSetJoint(AutoReloader):
    jointname = None
    jointvalue = None
    def __init__(self, jointname,jointvalue):
        self.jointname = jointname
        self.jointvalue = jointvalue
    def generate(self, generator):
        return generator.generateSetJoint(self)
    def end(self, generator):
        return generator.endSetJoint(self)

class CppGenerator(AutoReloader):
    """Generates C++ code from an AST"""

    dictequations = [] # dictionary of symbols already written
    symbolgen = cse_main.numbered_symbols('x')
    strprinter = printing.StrPrinter()
    freevars = None # list of free variables in the solution
    freevardependencies = None # list of variables depending on the free variables

    def generate(self, solvertree):

        code = """/// autogenerated analytical inverse kinematics code from ikfast program
/// \\author Rosen Diankov
///
/// To compile with gcc use: gcc -lstdc++ 
/// To compile without any main function use: gcc -lstdc++ -DIKFAST_NO_MAIN
#include <math.h>
#include <assert.h>
#include <vector>
#include <float.h>

#define IK2PI  6.28318530717959
#define IKPI  3.14159265358979
#define IKPI_2  1.57079632679490

#ifdef _MSC_VER
#ifndef isnan
#define isnan _isnan
#endif
#endif // _MSC_VER

typedef double IKReal;
class IKSolution
{
public:
    /// Gets a solution given its free parameters
    /// \\param pfree The free parameters required, range is in [-pi,pi]
    void GetSolution(IKReal* psolution, const IKReal* pfree) const {
        for(size_t i = 0; i < basesol.size(); ++i) {
            if( basesol[i].freeind < 0 )
                psolution[i] = basesol[i].foffset;
            else {
                assert(pfree != NULL);
                psolution[i] = pfree[basesol[i].freeind]*basesol[i].fmul + basesol[i].foffset;
                if( psolution[i] > IKPI )
                    psolution[i] -= IK2PI;
                else if( psolution[i] < -IKPI )
                    psolution[i] += IK2PI;
            }
        }
    }

    /// Gets the free parameters the solution requires to be set before a full solution can be returned
    /// \\return vector of indices indicating the free parameters
    const std::vector<int>& GetFree() const { return vfree; }

    struct VARIABLE
    {
        VARIABLE() : freeind(-1), fmul(0), foffset(0) {}
        VARIABLE(int freeind, IKReal fmul, IKReal foffset) : freeind(freeind), fmul(fmul), foffset(foffset) {}
        int freeind;
        IKReal fmul, foffset; ///< joint value is fmul*sol[freeind]+foffset
    };

    std::vector<VARIABLE> basesol;       ///< solution and their offsets if joints are mimiced
    std::vector<int> vfree;
};

inline float IKabs(float f) { return fabsf(f); }
inline double IKabs(double f) { return fabs(f); }

inline float IKasin(float f)
{
assert( f > -1.001f && f < 1.001f ); // any more error implies something is wrong with the solver
if( f <= -1 ) return -IKPI_2;
else if( f >= 1 ) return IKPI_2;
return asinf(f);
}
inline double IKasin(double f)
{
assert( f > -1.001 && f < 1.001 ); // any more error implies something is wrong with the solver
if( f <= -1 ) return -IKPI_2;
else if( f >= 1 ) return IKPI_2;
return asin(f);
}

inline float IKacos(float f)
{
assert( f > -1.001f && f < 1.001f ); // any more error implies something is wrong with the solver
if( f <= -1 ) return IKPI;
else if( f >= 1 ) return 0.0f;
return acosf(f);
}
inline double IKacos(double f)
{
assert( f > -1.001 && f < 1.001 ); // any more error implies something is wrong with the solver
if( f <= -1 ) return IKPI;
else if( f >= 1 ) return 0.0;
return acos(f);
}
inline float IKsin(float f) { return sinf(f); }
inline double IKsin(double f) { return sin(f); }
inline float IKcos(float f) { return cosf(f); }
inline double IKcos(double f) { return cos(f); }
inline float IKsqrt(float f) { if( f <= 0.0f ) return 0.0f; return sqrtf(f); }
inline double IKsqrt(double f) { if( f <= 0.0 ) return 0.0; return sqrt(f); }
inline float IKatan2(float fy, float fx) {
    if( isnan(fy) ) {
        assert(!isnan(fx)); // if both are nan, probably wrong value will be returned
        return IKPI_2;
    }
    else if( isnan(fx) )
        return 0;
    return atan2f(fy,fx);
}
inline double IKatan2(double fy, double fx) {
    if( isnan(fy) ) {
        assert(!isnan(fx)); // if both are nan, probably wrong value will be returned
        return IKPI_2;
    }
    else if( isnan(fx) )
        return 0;
    return atan2(fy,fx);
}
"""
        code += solvertree.generate(self)
        code += solvertree.end(self)

        code += """
#ifndef IKFAST_NO_MAIN
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv)
{
    if( argc != 12+getNumFreeParameters()+1 ) {
        printf("\\nUsage: ./ik r00 r01 r02 t0 r10 r11 r12 t1 r20 r21 r22 t2 free0 ...\\n\\n"
               "Returns the ik solutions given the transformation of the end effector specified by\\n"
               "a 3x3 rotation R (rXX), and a 3x1 translation (tX).\\n"
               "There are %d free parameters that have to be specified.\\n\\n",getNumFreeParameters());
        return 1;
    }

    std::vector<IKSolution> vsolutions;
    std::vector<IKReal> vfree(getNumFreeParameters());
    IKReal eerot[9],eetrans[3];
    eerot[0] = atof(argv[1]); eerot[1] = atof(argv[2]); eerot[2] = atof(argv[3]); eetrans[0] = atof(argv[4]);
    eerot[3] = atof(argv[5]); eerot[4] = atof(argv[6]); eerot[5] = atof(argv[7]); eetrans[1] = atof(argv[8]);
    eerot[6] = atof(argv[9]); eerot[7] = atof(argv[10]); eerot[8] = atof(argv[11]); eetrans[2] = atof(argv[12]);
    for(size_t i = 0; i < vfree.size(); ++i)
        vfree[i] = atof(argv[13+i]);
    bool bSuccess = ik(eetrans, eerot, vfree.size() > 0 ? &vfree[0] : NULL, vsolutions);

    if( !bSuccess ) {
        fprintf(stderr,"Failed to get ik solution\\n");
        return -1;
    }

    printf("Found %d ik solutions:\\n", (int)vsolutions.size());
    std::vector<IKReal> sol(getNumJoints());
    for(size_t i = 0; i < vsolutions.size(); ++i) {
        printf("sol%d (free=%d): ", (int)i, (int)vsolutions[i].GetFree().size());
        std::vector<IKReal> vsolfree(vsolutions[i].GetFree().size());
        vsolutions[i].GetSolution(&sol[0],vsolfree.size()>0?&vsolfree[0]:NULL);
        for( size_t j = 0; j < sol.size(); ++j)
            printf("%f, ", (float)sol[j]);
        printf("\\n");
    }
    return 0;
}

#endif
"""
        return code

    def generateChain(self, node):

        self.freevars = []
        self.freevardependencies = []
        self.dictequations = []
        self.symbolgen = cse_main.numbered_symbols('x')

        code = "int getNumFreeParameters() { return %d; }\n"%len(node.freejointvars)
        if len(node.freejointvars) == 0:
            code += "int* getFreeParameters() { return NULL; }\n";
        else:
            code += "int* getFreeParameters() { static int freeparams[] = {";
            for i,freejointvar in enumerate(node.freejointvars):
                code += "%d"%(freejointvar[1])
                if i < len(node.freejointvars)-1:
                    code += ", ";
            code += "}; return freeparams; }\n"
        code += "int getNumJoints() { return %d; }\n\n"%(len(node.freejointvars)+len(node.solvejointvars))
        code += "int getIKRealSize() { return sizeof(IKReal); }\n\n"
        code += "/// solves the inverse kinematics equations.\n"
        code += "/// \\param pfree is an array specifying the free joints of the chain.\n"
        code += "bool ik(const IKReal* eetrans, const IKReal* eerot, const IKReal* pfree, std::vector<IKSolution>& vsolutions) {\n"
        fcode = "vsolutions.resize(0); vsolutions.reserve(8);\n"
        fcode += "IKReal "
        
        for var in node.solvejointvars:
            fcode += "%s, c%s, s%s,\n"%(var[0].name,var[0].name,var[0].name)
        for i in range(len(node.freejointvars)):
            name = node.freejointvars[i][0].name
            fcode += "%s=pfree[%d], c%s=cos(pfree[%d]), s%s=sin(pfree[%d]),\n"%(name,i,name,i,name,i)

        for i in range(3):
            for j in range(3):
                fcode += "_r%d%d, r%d%d = eerot[%d*3+%d],\n"%(i,j,i,j,i,j)
        fcode += "_px, _py, _pz, px = eetrans[0], py = eetrans[1], pz = eetrans[2];\n\n"
        
        rotsubs = [(Symbol("r%d%d"%(i,j)),Symbol("_r%d%d"%(i,j))) for i in range(3) for j in range(3)]
        rotsubs += [(Symbol("px"),Symbol("_px")),(Symbol("py"),Symbol("_py")),(Symbol("pz"),Symbol("_pz"))]

        psymbols = ["_px","_py","_pz"]
        for i in range(3):
            for j in range(3):
                fcode += self.writeEquations(lambda k: "_r%d%d"%(i,j),node.Tee[4*i+j])
            fcode += self.writeEquations(lambda k: psymbols[i],node.Tee[4*i+3])
        for i in range(3):
            for j in range(3):
                fcode += "r%d%d = _r%d%d; "%(i,j,i,j)
        fcode += "px = _px; py = _py; pz = _pz;\n"

        fcode += self.generateTree(node.jointtree)
        code += self.indentCode(fcode,4) + "return vsolutions.size()>0;\n}\n"
        return code
    def endChain(self, node):
        return ""

    def generateSolution(self, node):
        code = ""
        numsolutions = 0
        eqcode = ""
        name = node.jointname
        node.HasFreeVar = False

        if node.jointeval is not None:
            numsolutions = len(node.jointeval)
            equations = []
            names = []
            for i,expr in enumerate(node.jointeval):

                m = None
                for freevar in self.freevars:
                    if expr.has_any_symbols(Symbol(freevar)):
                        # has free variables, so have to look for a*freevar+b form
                        a = Wild("a",exclude=[Symbol(freevar)])
                        b = Wild("b",exclude=[Symbol(freevar)])
                        m = expr.match(a*Symbol(freevar)+b)
                        if m is None:
                            print 'failed to extract free solution'
                            m = dict()
                            m[a] = Real(-1,30)
                            m[b] = Real(0,30)
                        self.freevardependencies.append((freevar,name))
                        
                        assert(len(node.jointeval)==1)
                        code += "IKReal " + self.writeEquations(lambda i: "%smul"%name, m[a])
                        code += self.writeEquations(lambda i: name, m[b])
                        node.HasFreeVar = True
                        return code

                equations.append(expr)
                names.append("%sarray[%d]"%(name,i))
                equations.append(sin(Symbol("%sarray[%d]"%(name,i))))
                names.append("s%sarray[%d]"%(name,i))
                equations.append(cos(Symbol("%sarray[%d]"%(name,i))))
                names.append("c%sarray[%d]"%(name,i))
            eqcode += self.writeEquations(lambda i: names[i], equations)

            if node.AddPi:
                for i in range(numsolutions):
                    eqcode += "%sarray[%d] = %sarray[%d] > 0 ? %sarray[%d]-IKPI : %sarray[%d]+IKPI;\n"%(name,numsolutions+i,name,i,name,i,name,i)
                    eqcode += "s%sarray[%d] = -s%sarray[%d];\n"%(name,numsolutions+i,name,i)
                    eqcode += "c%sarray[%d] = -c%sarray[%d];\n"%(name,numsolutions+i,name,i)
                numsolutions *= 2
            
            for i in range(numsolutions):
                eqcode += "if( %sarray[%d] > IKPI )\n    %sarray[%d]-=IK2PI;\nelse if( %sarray[%d] < -IKPI )\n    %sarray[%d]+=IK2PI;\n"%(name,i,name,i,name,i,name,i)
                eqcode += "%svalid[%d] = true;\n"%(name,i)
        elif node.jointevalcos is not None:
            numsolutions = 2*len(node.jointevalcos)
            eqcode += self.writeEquations(lambda i: "c%sarray[%d]"%(name,2*i),node.jointevalcos)
            for i in range(len(node.jointevalcos)):
                eqcode += "if( c%sarray[%d] >= -1.0001 && c%sarray[%d] <= 1.0001 ) {\n"%(name,2*i,name,2*i)
                eqcode += "    %svalid[%d] = %svalid[%d] = true;\n"%(name,2*i,name,2*i+1)
                eqcode += "    %sarray[%d] = IKacos(c%sarray[%d]);\n"%(name,2*i,name,2*i)
                eqcode += "    s%sarray[%d] = IKsin(%sarray[%d]);\n"%(name,2*i,name,2*i)
                # second solution
                eqcode += "    c%sarray[%d] = c%sarray[%d];\n"%(name,2*i+1,name,2*i)
                eqcode += "    %sarray[%d] = -%sarray[%d];\n"%(name,2*i+1,name,2*i)
                eqcode += "    s%sarray[%d] = -s%sarray[%d];\n"%(name,2*i+1,name,2*i)
                eqcode += "}\n"
                eqcode += "else if( isnan(c%sarray[%d]) ) {\n"%(name,2*i)
                eqcode += "    // probably any value will work\n"
                eqcode += "    %svalid[%d] = true;\n"%(name,2*i)
                eqcode += "    c%sarray[%d] = 1; s%sarray[%d] = 0; %sarray[%d] = 0;\n"%(name,2*i,name,2*i,name,2*i)
                eqcode += "}\n"
        elif node.jointevalsin is not None:
            numsolutions = 2*len(node.jointevalsin)
            eqcode += self.writeEquations(lambda i: "s%sarray[%d]"%(name,2*i),node.jointevalsin)
            for i in range(len(node.jointevalsin)):
                eqcode += "if( s%sarray[%d] >= -1.0001 && s%sarray[%d] <= 1.0001 ) {\n"%(name,2*i,name,2*i)
                eqcode += "    %svalid[%d] = %svalid[%d] = true;\n"%(name,2*i,name,2*i+1)
                eqcode += "    %sarray[%d] = IKasin(s%sarray[%d]);\n"%(name,2*i,name,2*i)
                eqcode += "    c%sarray[%d] = IKcos(%sarray[%d]);\n"%(name,2*i,name,2*i)
                # second solution
                eqcode += "    s%sarray[%d] = s%sarray[%d];\n"%(name,2*i+1,name,2*i)
                eqcode += "    %sarray[%d] = %sarray[%d] > 0 ? (IKPI-%sarray[%d]) : (-IKPI-%sarray[%d]);\n"%(name,2*i+1,name,2*i,name,2*i,name,2*i)
                eqcode += "    c%sarray[%d] = -c%sarray[%d];\n"%(name,2*i+1,name,2*i)
                eqcode += "}\n"
                eqcode += "else if( isnan(s%sarray[%d]) ) {\n"%(name,2*i)
                eqcode += "    // probably any value will work\n"
                eqcode += "    %svalid[%d] = true;\n"%(name,2*i)
                eqcode += "    c%sarray[%d] = 1; s%sarray[%d] = 0; %sarray[%d] = 0;\n"%(name,2*i,name,2*i,name,2*i)
                eqcode += "}\n"

        code += "{\nIKReal %sarray[%d], c%sarray[%d], s%sarray[%d];\n"%(name,numsolutions,name,numsolutions,name,numsolutions)

        code += "bool %svalid[%d]={false};\n"%(name,numsolutions)
        code += eqcode
        for i,j in xcombinations(range(numsolutions),2):
            code += "if( %svalid[%d] && %svalid[%d] && IKabs(c%sarray[%d]-c%sarray[%d]) < 0.0001 && IKabs(s%sarray[%d]-s%sarray[%d]) < 0.0001 )\n    %svalid[%d]=false;\n"%(name,i,name,j,name,i,name,j,name,i,name,j,name,j)
        if numsolutions > 1:
            code += "for(int i%s = 0; i%s < %d; ++i%s) {\n"%(name,name,numsolutions,name)
        else:
            code += "{ int i%s = 0;\n"%(name)
        code += "if( !%svalid[i%s] )\n    continue;\n"%(name,name)

        if numsolutions > 1:
            code += "%s = %sarray[i%s]; c%s = c%sarray[i%s]; s%s = s%sarray[i%s];\n\n"%(name,name,name,name,name,name,name,name,name)
        else:
            code += "%s = %sarray[0]; c%s = c%sarray[0]; s%s = s%sarray[0];\n\n"%(name,name,name,name,name,name)
        return code

    def endSolution(self, node):
        if node.HasFreeVar:
            self.freevardependencies.pop()
            return ""
        return "}\n}\n"

    def generateBranch(self, node):
        name = node.jointname
        code = "IKReal %seval;\n"%name
        code += self.writeEquations(lambda x: "%seval"%name,[node.jointeval]);
        for branch in node.jointbranches:
            branchcode = ""
            for n in branch[1]:
                branchcode += n.generate(self)
            for n in reversed(branch[1]):
                branchcode += n.end(self)
            branchcode = self.indentCode(branchcode,4)
            if branch[0] is None:
                code += "{\n" + branchcode + "}\n"
            else:
                code += "if( %seval >= %f && %seval <= %f ) {\n"%(name,branch[0]-0.0001,name,branch[0]+0.0001)
                code += branchcode + "}\nelse "
        return code
    def endBranch(self, node):
        return ""
    def generateFreeParameter(self, node):
        self.freevars.append(node.jointname)
        self.freevardependencies.append((node.jointname,node.jointname))
        code = "IKReal %smul = 1;\n%s=0;\n"%(node.jointname,node.jointname)
        return code+self.generateTree(node.jointtree)
    def endFreeParameter(self, node):
        self.freevars.pop()
        self.freevardependencies.pop()
        return ""
    def generateSetJoint(self, node):
        code = "{\n%s = %f; s%s = %f; c%s = %f;\n"%(node.jointname,node.jointvalue,node.jointname,sin(node.jointvalue),node.jointname,cos(node.jointvalue))
        return code
    def endSetJoint(self, node):
        return "}\n"
    def generateRotation(self, node):
        code = "";

        listequations = []
        names = []
        for i in range(3):
            for j in range(3):
                listequations.append(node.T[i*4+j])
                names.append(Symbol("_r%d%d"%(i,j)))
        code += self.writeEquations(lambda i: names[i],listequations)
        code += self.generateTree(node.jointtree)
        return code
    def endRotation(self, node):
        return ""
    def generateStoreSolution(self, node):
        code = "vsolutions.push_back(IKSolution()); IKSolution& solution = vsolutions.back();\n"
        code += "solution.basesol.resize(%d);\n"%len(node.alljointvars)
        for i,var in enumerate(node.alljointvars):
            code += "solution.basesol[%d].foffset = %s;\n"%(i,var)
            
            vardeps = [vardep for vardep in self.freevardependencies if vardep[1]==var.name]
            if len(vardeps) > 0:
                freevarname = vardeps[0][0]
                ifreevar = [j for j in range(len(self.freevars)) if freevarname==self.freevars[j]]
                code += "solution.basesol[%d].fmul = %smul;\n"%(i,var.name)
                code += "solution.basesol[%d].freeind = %d;\n"%(i,ifreevar[0])
        code += "solution.vfree.resize(%d);\n"%len(self.freevars)
        for i,varname in enumerate(self.freevars):
            ind = [j for j in range(len(node.alljointvars)) if varname==node.alljointvars[j].name]
            code += "solution.vfree[%d] = %d;\n"%(i,ind[0])
        return code
    def endStoreSolution(self, node):
        return ""
    def generateSequence(self, node):
        code = ""
        for tree in node.jointtrees:
            code += self.generateTree(tree)
        return code
    def endSequence(self, node):
        return ""
    def generateTree(self,tree):
        code = ""
        for n in tree:
            code += n.generate(self)
        for n in reversed(tree):
            code += n.end(self)
        return code
    def writeEquations(self, varnamefn, exprs):
        code = ""
        [replacements,reduced_exprs] = cse(exprs,symbols=self.symbolgen)
        for rep in replacements:                
            eqns = filter(lambda x: rep[1]-x[1]==0, self.dictequations)
            if len(eqns) > 0:
                self.dictequations.append((rep[0],eqns[0][0]))
                code += "IKReal %s=%s;\n"%(rep[0],eqns[0][0])
            else:
                self.dictequations.append(rep)
                code2,sepcode2 = self.writeExprCode(rep[1])
                code += sepcode2+"IKReal %s=%s;\n"%(rep[0],code2)

        for i,rexpr in enumerate(reduced_exprs):
            code2,sepcode2 = self.writeExprCode(rexpr)
            code += sepcode2+"%s=%s;\n"%(varnamefn(i), code2)
        return code

    def writeExprCode(self, expr):
        # go through all arguments and chop them
        code = ""
        sepcode = ""
        if expr.is_Function:
            if expr.func == abs:
                code += "IKabs("
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2
            elif expr.func == acos:
                code += "IKacos("
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2
                sepcode += "if( (%s) < -1.0001 || (%s) > 1.0001 )\n    return false;\n"%(code2,code2)
            elif expr.func == asin:
                code += "IKasin("
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2
                sepcode += "if( (%s) < -1.0001 || (%s) > 1.0001 )\n    return false;\n"%(code2,code2)
            elif expr.func == atan2:
                code += "IKatan2("
                # check for divides by 0 in arguments, this could give two possible solutions?!?
                # if common arguments is nan! solution is lost!
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2+', '
                code3,sepcode2 = self.writeExprCode(expr.args[1])
                code += code3
                sepcode += sepcode2
            elif expr.func == sin:
#                 if expr.args[0].is_Symbol and expr.args[0].name[0] == 'j':
#                     # probably already have initialized
#                     code += '(s%s'%expr.args[0].name
#                 else:
                code += "IKsin("
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2
            elif expr.func == cos:
#                 if expr.args[0].is_Symbol and expr.args[0].name[0] == 'j':
#                     # probably already have initialized
#                     code += '(c%s'%expr.args[0].name
#                 else:
                code += "IKcos("
                code2,sepcode = self.writeExprCode(expr.args[0])
                code += code2
            else:
                code += expr.func.__name__ + "(";
                for arg in expr.args:
                    code2,sepcode2 = self.writeExprCode(arg)
                    code += code2
                    sepcode += sepcode2
                    if not arg == expr.args[-1]:
                        code += ","
            return code + ")",sepcode
        elif expr.is_Mul:
            code += "("
            for arg in expr.args:
                code2,sepcode2 = self.writeExprCode(arg)
                code += "("+code2+")"
                sepcode += sepcode2
                if not arg == expr.args[-1]:
                    code += "*"
            return code + ")",sepcode
        elif expr.is_Pow:
            exprbase,sepcode = self.writeExprCode(expr.base)
            if expr.exp.is_real:
                if expr.exp.is_integer and expr.exp.evalf() > 0:
                    code += "("+exprbase+")"
                    for i in range(1,expr.exp.evalf()):
                        code += "*("+exprbase+")"
                    return code,sepcode
                elif expr.exp-0.5 == 0:
                    sepcode += "if( (%s) < (IKReal)-0.00001 )\n    return false;\n"%exprbase
                    return "IKsqrt("+exprbase+")",sepcode
                elif expr.exp+1 == 0:
                    return "((IKReal)1/("+exprbase+"))",sepcode
            exprexp,sepcode2 = self.writeExprCode(expr.exp)
            sepcode += sepcode2
            return "pow(" + exprbase + "," + exprexp + ")",sepcode
        elif expr.is_Add:
            code += "("
            for arg in expr.args:
                code2,sepcode2 = self.writeExprCode(arg)
                code += "("+code2+")"
                sepcode += sepcode2
                if not arg == expr.args[-1]:
                    code += "+"
            return code + ")",sepcode

        return self.strprinter.doprint(expr.evalf()),sepcode

    def indentCode(self, code, numspaces):
        lcode = list(code)
        locations = [i for i in range(len(lcode)) if lcode[i]=='\n']
        locations.reverse()
        insertcode = [' ' for i in range(numspaces)]
        for loc in locations:
            lcode[loc+1:0] = insertcode
        lcode[:0] = insertcode
        return ''.join(lcode)

class RobotKinematics(AutoReloader):
    """
    Parses the kinematics from an openrave fk file and generates C++ code for analytical inverse kinematics.
    author: Rosen Diankov

    Generated C++ code structure:

    typedef double IKReal;
    class IKSolution
    {
    public:
        void GetSolution(IKReal* psolution, const IKReal* pfree) const;
    };

    bool ik(const IKReal* eetrans, const IKReal* eerot, const IKReal* pfree, std::vector<SOLUTION>& vsolutions);
    bool fk(const IKReal* joints, IKReal* eetrans, IKReal* eerot);
    
    """
    
    class Joint:
        __slots__ = ['jointtype','axis','Tleft','Tright','jcoeff','linkcur','linkbase','jointindex','isfreejoint','isdummy']

    class Variable:
        __slots__ = ['var','svar','cvar','tvar']
        def __init__(self, var):
            self.var = var
            self.svar = Symbol("s%s"%var.name)
            self.cvar = Symbol("c%s"%var.name)
            self.tvar = Symbol("t%s"%var.name)

    def __init__(self, robotfile):
        self.joints = []
        self.freevarsubs = []
        f=open(robotfile, "r")
        tokens = f.read().split()
        numdof = atoi(tokens[0])
        offset = 1

        self.numlinks = 0
        alljoints = []
        for i in range(numdof):
            joint = RobotKinematics.Joint()
            joint.type = tokens[offset+0]
            joint.linkcur = atoi(tokens[offset+1])
            joint.linkbase = atoi(tokens[offset+2])
            joint.jointindex = atoi(tokens[offset+3])
            joint.axis = Matrix(3,1,[Real(round(atof(x),4),30) for x in tokens[offset+4:offset+7]])
            joint.jcoeff = [round(atof(x),5) for x in tokens[offset+7:offset+9]]
            joint.Tleft = eye(4)
            joint.Tleft[0:3,0:4] = Matrix(3,4,[Real(round(atof(x),5),30) for x in tokens[offset+9:offset+21]])
            joint.Tright = eye(4)
            joint.Tright[0:3,0:4] = Matrix(3,4,[Real(round(atof(x),5),30) for x in tokens[offset+21:offset+33]])
            joint.isfreejoint = False
            joint.isdummy = False
            alljoints.append(joint)
            offset = offset + 33;
            self.numlinks = max(self.numlinks,joint.linkcur)

        # order with respect to joint index
        numjoints = max([joint.jointindex for joint in alljoints])+1
        self.joints = [[] for i in range(numjoints)]
        for joint in alljoints:
            self.joints[joint.jointindex].append(joint)

    def getJointsInChain(self, baselink, eelink):
        # find a path of joints between baselink and eelink using BFS
        linkqueue = [[baselink,[]]]
        alljoints = []
        while len(linkqueue)>0:
            link = linkqueue.pop(0)
            if link[0] == eelink:
                alljoints = link[1]
                break

            attachedjoints = []
            for jointgroup in self.joints:
                attachedjoints += [joint for joint in jointgroup if joint.linkbase == link[0]]
            for joint in attachedjoints:
                path = link[1]+[joint]
                if len(path) > 1 and path[0] == path[-1]:
                    print "discovered circular in joints"
                    return False
                linkqueue.append([joint.linkcur,path])
         
        return alljoints

    def rodrigues(self, axis, angle):
        skewsymmetric = Matrix(3, 3, [0,-axis[2],axis[1],axis[2],0,-axis[0],-axis[1],axis[0],0])
        return eye(3) + sin(angle) * skewsymmetric + (1-cos(angle))*skewsymmetric*skewsymmetric

    # The first and last matrices returned are always numerical
    def forwardKinematics(self, baselink, eelink):
        return self.forwardKinematicsChain(self.getJointsInChain(baselink, eelink))

#     def eye(self,n):
#         tmp = Matrix(n,n,[Real(0,30)]*n*n)
#         for i in range(tmp.lines):
#             tmp[i,i] = Real(1,30)
#         return tmp

    # The first and last matrices returned are always numerical
    def forwardKinematicsChain(self, chain):
        Links = []
        Tright = eye(4)
        jointvars = []
        isolvejointvars = []
        ifreejointvars = []
        jointinds = []
        jointindexmap = dict()
        for i,joint in enumerate(chain):
            if not joint.isdummy:
                if not joint.jointindex in jointindexmap:
                    jointindexmap[joint.jointindex] = len(jointvars)
                    var = Symbol("j%d"%len(jointvars))
                else:
                    var = Symbol("j%d"%jointindexmap[joint.jointindex])
                Tjoint = eye(4)
                if joint.type == 'hinge':
                    Tjoint[0:3,0:3] = self.rodrigues(joint.axis,joint.jcoeff[0]*var+joint.jcoeff[1])
                elif joint.type == 'slider':
                    Tjoint[0:3,3] = joint.axis*(joint.jcoeff[0]*var+joint.jcoeff[1])
                else:
                    raise ValueError('failed to process joint type %s'%joint.type)
                
                if i > 0 and chain[i].jointindex==chain[i-1].jointindex:
                    # the joint is the same as the last joint
                    Links[-1] = self.affineSimplify(Links[-1] * Tright * joint.Tleft * Tjoint)
                    Tright = joint.Tright
                else:
                    # the joints are different, so add regularly
                    if joint.isfreejoint:
                        ifreejointvars.append(len(jointvars))
                    else:
                        isolvejointvars.append(len(jointvars))
                    jointvars.append(var)
                    Links.append(Tright * joint.Tleft)
                    jointinds.append(len(Links))
                    Links.append(Tjoint)
                    Tright = joint.Tright
            else:
                Tright = self.affineSimplify(Tright * joint.Tleft * joint.Tright)
        Links.append(Tright)
        
        # before returning the final links, try to push as much translation components
        # outwards to both ends. Sometimes these components can get in the way of detecting
        # intersecting axes

        if len(jointinds) > 0:
            iright = jointinds[-1]
            Ttrans = eye(4); Ttrans[0:3,3] = Links[iright-1][0:3,0:3].transpose() * Links[iright-1][0:3,3]
            Trot_with_trans = Ttrans * Links[iright]
            separated_trans = Trot_with_trans[0:3,0:3].transpose() * Trot_with_trans[0:3,3]
            if not any([separated_trans[j].has_any_symbols(jointvars[-1]) for j in range(0,3)]):
                Ttrans[0:3,3] = separated_trans
                Links[iright+1] = Ttrans * Links[iright+1]
                Links[iright-1][0:3,3] = Matrix(3,1,[Real(0,30)]*3)
                print "moved translation ",separated_trans.transpose(),"to right end"
        
        if len(jointinds) > 1:
            ileft = jointinds[0]
            separated_trans = Links[ileft][0:3,0:3] * Links[ileft+1][0:3,3]
            if not any([separated_trans[j].has_any_symbols(jointvars[0]) for j in range(0,3)]):
                Ttrans = eye(4); Ttrans[0:3,3] = separated_trans
                Links[ileft-1] = Links[ileft-1] * Ttrans
                Links[ileft+1][0:3,3] = Matrix(3,1,[Real(0,30)]*3)
                print "moved translation ",separated_trans.transpose(),"to left end"

        if len(jointinds) > 3: # last 3 axes always have to be intersecting, move the translation of the first axis to the left
            ileft = jointinds[-3]
            separated_trans = Links[ileft][0:3,0:3] * Links[ileft+1][0:3,3]
            if not any([separated_trans[j].has_any_symbols(jointvars[-3]) for j in range(0,3)]):
                Ttrans = eye(4); Ttrans[0:3,3] = separated_trans
                Links[ileft-1] = Links[ileft-1] * Ttrans
                Links[ileft+1][0:3,3] = Matrix(3,1,[Real(0,30)]*3)
                print "moved translation on intersecting axis ",separated_trans.transpose(),"to left"

        return Links, jointvars, isolvejointvars, ifreejointvars
        
    def generateIkSolver(self, baselink, eelink, solvejoints, freejoints, usedummyjoints,rotation3donly=False):
        alljoints = self.getJointsInChain(baselink, eelink)
        
        # mark the free joints and form the chain
        chain = []
        for joint in alljoints:
            issolvejoint = any([i == joint.jointindex for i in solvejoints])
            joint.isdummy = usedummyjoints and not issolvejoint and not any([i == joint.jointindex for i in freejoints])
            joint.isfreejoint = not issolvejoint and not joint.isdummy
            chain.append(joint)
        
        return self.generateIkSolverChain(chain,rotation3donly=rotation3donly)
        
    def generateIkSolverChain(self, chain, rotation3donly=False):
        Tee = eye(4)
        for i in range(0,3):
            for j in range(0,3):
                Tee[i,j] = Symbol("r%d%d"%(i,j))
        Tee[0,3] = Symbol("px")
        Tee[1,3] = Symbol("py")
        Tee[2,3] = Symbol("pz")
        
        if rotation3donly:
            chaintree = self.solveFullIK_Rotation3D(chain, Tee)
        else:
            chaintree = self.solveFullIK_6D(chain, Tee)
        if chaintree is None:
            print "failed to genreate ik solution"
            return ""

        # parse the solver tree
        return CppGenerator().generate(chaintree)

    def affineInverse(self, affinematrix):
        T = eye(4)
        T[0:3,0:3] = affinematrix[0:3,0:3].transpose()
        T[0:3,3] = -affinematrix[0:3,0:3].transpose() * affinematrix[0:3,3]
        return T

    # deep chopping of tiny numbers due to floating point precision errors
    def chop(self,expr,precision=10):
        # go through all arguments and chop them
        if expr.is_Function:
            return expr.func( self.chop(expr.args[0], precision) )
        elif expr.is_Mul:
            ret = S.One
            for x in expr.args:
                ret *= self.chop(x, precision)
            return ret
        elif expr.is_Pow:
            return Pow(self.chop(expr.base, precision), expr.exp)
        elif expr.is_Add:
            # Scan for the terms we need
            ret = S.Zero
            for term in expr.args:
                term = self.chop(term, precision)
                ret += term

            return ret

        return expr.evalf(precision,chop=True)

    def countVariables(self,expr,var):
        """Counts number of terms variable appears in"""
        if not expr.is_Add:
            if expr.has_any_symbols(var):
                return 1
            return 0
        
        num = 0
        for term in expr.args:
            if term.has_any_symbols(var):
                num += 1

        return num

    def codeComplexity(self,expr):
        complexity = 1
        if expr.is_Add:
            for term in expr.args:
                complexity += self.codeComplexity(term)
        elif expr.is_Mul:
            for term in expr.args:
                complexity += self.codeComplexity(term)
        elif expr.is_Pow:
            complexity += self.codeComplexity(expr.base)+self.codeComplexity(expr.exp)
        elif expr.is_Function:
            complexity += 1
            for term in expr.args:
                complexity += self.codeComplexity(term)
        
        return complexity

    def affineSimplify(self, T, precision=10):
        # yes, it is necessary to call self.trigsimp so many times since it gives up too easily
        return Matrix(4,4,map(lambda x: self.chop(trigsimp(trigsimp(self.chop(trigsimp(x),precision))),precision), T))

    def fk(self, chain, joints):
        Tlinks = [eye(4)]
        for i,joint in enumerate(chain):
            R = eye(4)
            if joint.type == 'hinge':
                R[0:3,0:3] = self.rodrigues(joint.axis,joint.jcoeff[0]*joints[i]+joint.jcoeff[1])
            elif joint.type == 'slider':
                R[0:3,3] = joint.axis*(joint.jcoeff[0]*joints[i]+joint.jcoeff[1])
            else:
                raise ValueError('undefined joint type %s'%joint.type)
            Tlinks.append(Tlinks[-1] * joint.Tleft * R * joint.Tright)
        return Tlinks

    def solveFullIK_Rotation3D(self,chain,Tee):
        Links, jointvars, isolvejointvars, ifreejointvars = self.forwardKinematicsChain(chain)
        Tfirstleft = Links.pop(0)
        Tfirstright = Links.pop()
        LinksInv = [self.affineInverse(link) for link in Links]
        solvejointvars = [jointvars[i] for i in isolvejointvars]
        freejointvars = [jointvars[i] for i in ifreejointvars]

        if not len(solvejointvars) == 3:
            raise ValueError('solve joints needs to be 3')

        # when solving equations, convert all free variables to constants
        self.freevarsubs = []
        for freevar in freejointvars:
            var = self.Variable(freevar)
            self.freevarsubs += [(cos(var.var), var.cvar), (sin(var.var), var.svar)]
        
        #Tee = Tfirstleft.inv() * Tee_in * Tfirstright.inv()
        # LinksAccumLeftInv[x] * Tee = LinksAccumRight[x]
        # LinksAccumLeftInv[x] = InvLinks[x-1] * ... * InvLinks[0]
        # LinksAccumRight[x] = Links[x]*Links[x+1]...*Links[-1]
        LinksAccumLeftAll = [eye(4)]
        LinksAccumLeftInvAll = [eye(4)]
        LinksAccumRightAll = [eye(4)]
        for i in range(len(Links)):
            LinksAccumLeftAll.append(LinksAccumLeftAll[-1]*Links[i])
            LinksAccumLeftInvAll.append(LinksInv[i]*LinksAccumLeftInvAll[-1])
            LinksAccumRightAll.append(Links[len(Links)-i-1]*LinksAccumRightAll[-1])
        LinksAccumRightAll.reverse()
        
        LinksAccumLeftAll = map(lambda T: self.affineSimplify(T), LinksAccumLeftAll)
        LinksAccumLeftInvAll = map(lambda T: self.affineSimplify(T), LinksAccumLeftInvAll)
        LinksAccumRightAll = map(lambda T: self.affineSimplify(T), LinksAccumRightAll)
        
        # create LinksAccumX indexed by joint indices
        assert( len(LinksAccumLeftAll)%2 == 0 )
        LinksAccumLeft = []
        LinksAccumLeftInv = []
        LinksAccumRight = []
        for i in range(0,len(LinksAccumLeftAll),2)+[len(LinksAccumLeftAll)-1]:
            LinksAccumLeft.append(LinksAccumLeftAll[i])
            LinksAccumLeftInv.append(LinksAccumLeftInvAll[i])
            LinksAccumRight.append(LinksAccumRightAll[i])
        assert( len(LinksAccumLeft) == len(jointvars)+1 )
        
        # find a set of joints starting from the last that can solve for a full 3D rotation
#         rotindex = len(jointvars)
#         while rotindex>=0:
#             # check if any entries are constant
#             if all([not LinksAccumRight[rotindex][i,j].is_zero for i in range(3) for j in range(3)]):
#                 break
#             rotindex = rotindex-1
        rotindex = 0

        if rotindex < 0:
            print "Current joints cannot solve for a full 3D rotation"

        storesolutiontree = [SolverStoreSolution (jointvars)]
        rotsubs = [(Symbol("r%d%d"%(i,j)),Symbol("_r%d%d"%(i,j))) for i in range(3) for j in range(3)]
        R = Matrix(3,3, map(lambda x: x.subs(self.freevarsubs), LinksAccumRight[rotindex][0:3,0:3]))
        rotvars = [var for var in jointvars[rotindex:] if any([var==svar for svar in solvejointvars])]
        solvertree = self.solveIKRotation(R=R,Ree = Tee[0:3,0:3].subs(rotsubs),rawvars = rotvars,endbranchtree=storesolutiontree)
        return SolverIKChain([(jointvars[ijoint],ijoint) for ijoint in isolvejointvars], [(jointvars[ijoint],ijoint) for ijoint in ifreejointvars], Tfirstleft.inv() * Tee * Tfirstright.inv(), solvertree)
        
    def solveFullIK_6D(self, chain, Tee):
        Links, jointvars, isolvejointvars, ifreejointvars = self.forwardKinematicsChain(chain)
        Tfirstleft = Links.pop(0)
        Tfirstright = Links.pop()
        LinksInv = [self.affineInverse(link) for link in Links]
        solvejointvars = [jointvars[i] for i in isolvejointvars]
        freejointvars = [jointvars[i] for i in ifreejointvars]
        
        # when solving equations, convert all free variables to constants
        self.freevarsubs = []
        for freevar in freejointvars:
            var = self.Variable(freevar)
            self.freevarsubs += [(cos(var.var), var.cvar), (sin(var.var), var.svar)]
        
        #Tee = Tfirstleft.inv() * Tee_in * Tfirstright.inv()
        # LinksAccumLeftInv[x] * Tee = LinksAccumRight[x]
        # LinksAccumLeftInv[x] = InvLinks[x-1] * ... * InvLinks[0]
        # LinksAccumRight[x] = Links[x]*Links[x+1]...*Links[-1]
        LinksAccumLeftAll = [eye(4)]
        LinksAccumLeftInvAll = [eye(4)]
        LinksAccumRightAll = [eye(4)]
        for i in range(len(Links)):
            LinksAccumLeftAll.append(LinksAccumLeftAll[-1]*Links[i])
            LinksAccumLeftInvAll.append(LinksInv[i]*LinksAccumLeftInvAll[-1])
            LinksAccumRightAll.append(Links[len(Links)-i-1]*LinksAccumRightAll[-1])
        LinksAccumRightAll.reverse()
        
        LinksAccumLeftAll = map(lambda T: self.affineSimplify(T), LinksAccumLeftAll)
        LinksAccumLeftInvAll = map(lambda T: self.affineSimplify(T), LinksAccumLeftInvAll)
        LinksAccumRightAll = map(lambda T: self.affineSimplify(T), LinksAccumRightAll)
        
        # create LinksAccumX indexed by joint indices
        assert( len(LinksAccumLeftAll)%2 == 0 )
        LinksAccumLeft = []
        LinksAccumLeftInv = []
        LinksAccumRight = []
        for i in range(0,len(LinksAccumLeftAll),2)+[len(LinksAccumLeftAll)-1]:
            LinksAccumLeft.append(LinksAccumLeftAll[i])
            LinksAccumLeftInv.append(LinksAccumLeftInvAll[i])
            LinksAccumRight.append(LinksAccumRightAll[i])
        assert( len(LinksAccumLeft) == len(jointvars)+1 )
        
        # find last point that separates translation and rotation
        lastsepindex = -1
        for i in isolvejointvars:
            testjoints = [j for j in jointvars[i:] if not any([j==jfree for jfree in freejointvars])]
            if not any([LinksAccumRight[i][j,3].has_any_symbols(*testjoints) for j in range(0,3)]):
                lastsepindex = i
                break
        
        if lastsepindex < 0:
            print "failed to find joint index to separate translation and rotation"
            return None
        
        # find a set of joints starting from the last that can solve for a full 3D rotation
        rotindex = min(len(jointvars)-3,lastsepindex)
        while rotindex>=0:
            # check if any entries are constant
            if all([not LinksAccumRight[rotindex][i,j].is_zero for i in range(3) for j in range(3)]):
                break
            rotindex = rotindex-1

        if rotindex < 0:
            print "Current joints cannot solve for a full 3D rotation"

        # add all but first 3 vars to free parameters
        rotvars = []
        transvars = []
        for svar in solvejointvars:
            if any([LinksAccumRight[rotindex][i,j].has_any_symbols(svar) for i in range(3) for j in range(3)]):
                rotvars.append(svar)
            else:
                transvars.append(svar)
        #transvars = solvejointvars[0:min(3,lastsepindex)]

        solvertree = []

        Positions = [self.affineSimplify(LinksAccumRightAll[i])[0:3,3] for i in range(0,1+lastsepindex*2)]
        Positionsee = [(LinksAccumLeftInvAll[i]*Tee)[0:3,3] for i in range(0,1+lastsepindex*2)]
        
        # try to shift all the constants of each Position expression to one side
        for i in range(len(Positions)):
            for j in range(3):
                p = Positions[i][j]
                pee = Positionsee[i][j]
                
                pconstterm = None
                peeconstterm = None
                if p.is_Add:
                    pconstterm = [term for term in p.args if term.is_number]
                elif p.is_number:
                    pconstterm = [p]
                else:
                    continue
                
                if pee.is_Add:
                    peeconstterm = [term for term in pee.args if term.is_number]
                elif pee.is_number:
                    peeconstterm = [pee]
                else:
                    continue
                
                if len(pconstterm) > 0 and len(peeconstterm) > 0:
                    # shift it to the one that has the least terms
                    for term in peeconstterm if len(p.args) < len(pee.args) else pconstterm:
                        Positions[i][j] -= term
                        Positionsee[i][j] -= term
        
        transtree = []
        transvarsubs = []
        solvedvars = self.solveIKTranslationLength(Positions, Positionsee, rawvars = transvars)
        if len(solvedvars) > 0:
            bestindex = min([(1000*len(solvedvar[2])+reduce(lambda x,y:x+y,solvedvar[2]),i) for i,solvedvar in enumerate(solvedvars)])[1]
            solvedvar = solvedvars[bestindex]
            var = solvedvar[0]
            subvars = [(cos(var),self.Variable(var).cvar),(sin(var),self.Variable(var).svar)]
            transvarsubs += subvars
            transvars.remove(var)
            transtree += [solvedvar[1]]
            Positions = map(lambda x: x.subs(subvars), Positions)
            Positionsee = map(lambda x: x.subs(subvars), Positionsee)
        else:
            print "Could not solve variable from length of translation"
        
        while len(transvars)>0:
            solvedvars = self.solveIKTranslation(Positions,Positionsee,rawvars = transvars)
            if len(solvedvars) == 0:
                break
            
            # pick only one solution, and let that be the smallest one
            bestindex = min([(1000*len(solvedvar[2])+reduce(lambda x,y:x+y,solvedvar[2]),i) for i,solvedvar in enumerate(solvedvars)])[1]
            
            var = solvedvars[bestindex][0]
            subvars = [(cos(var),self.Variable(var).cvar),(sin(var),self.Variable(var).svar)]
            transvarsubs += subvars
            transvars.remove(var)
            Positions = map(lambda x: x.subs(subvars), Positions)
            Positionsee = map(lambda x: x.subs(subvars), Positionsee)
            transtree += [solvedvars[bestindex][1]]
        
        if len(transvars) > 0:
            print "error, cannot solve anymore variables"
            return None
        
#         for i in range(3,lastsepindex): 3 should be number of solved vars
#             transtree = [SolverFreeParameter(solvejointvars[i].name, transtree)]
        solvertree += transtree
        
        # substitute all known variables
        storesolutiontree = [SolverStoreSolution (jointvars)]
        rotsubs = [(Symbol("r%d%d"%(i,j)),Symbol("_r%d%d"%(i,j))) for i in range(3) for j in range(3)]
        R = Matrix(3,3, map(lambda x: x.subs(self.freevarsubs+transvarsubs), LinksAccumRight[rotindex][0:3,0:3]))
        #rotvars = [var for var in jointvars[rotindex:] if any([var==svar for svar in solvejointvars])]
        tree = self.solveIKRotation(R=R,Ree = Tee[0:3,0:3].subs(rotsubs),rawvars = rotvars,endbranchtree=storesolutiontree)
        
        if len(tree) == 0:
            print "could not solve for all rotation variables"
            return None
        
        solvertree.append(SolverRotation(LinksAccumLeftInv[rotindex].subs(self.freevarsubs+transvarsubs)*Tee, tree))
        
        if not rotindex == lastsepindex:
            print "TODO: did not separate translation and rotation cleanly"
            return None
        
        return SolverIKChain([(jointvars[ijoint],ijoint) for ijoint in isolvejointvars], [(jointvars[ijoint],ijoint) for ijoint in ifreejointvars], Tfirstleft.inv() * Tee * Tfirstright.inv(), solvertree)

    def isExpressionUnique(self, exprs, expr):
        for exprtest in exprs:
            e = expr-exprtest
            if e.is_number and abs(e) < 1e-10:
                return False
        return True

    # solve for just the translation component
    def solveIKTranslationLength(self, Positions, Positionsee, rawvars):
        vars = map(lambda rawvar: self.Variable(rawvar), rawvars)
        
        # try to get an equation from the lengths
        Lengths = map(lambda x: self.chop(self.customtrigsimp(self.customtrigsimp(self.customtrigsimp((x[0]**2+x[1]**2+x[2]**2).expand())).expand())), Positions)
        Lengthsee = map(lambda x: self.chop(self.customtrigsimp(self.customtrigsimp(self.customtrigsimp((x[0]**2+x[1]**2+x[2]**2).expand())).expand())), Positionsee)
        LengthEq = map(lambda i: Lengths[i]-Lengthsee[i], range(len(Lengths)))
        solvedvars = []
        
        for eq in LengthEq:
            for var in vars:
                othervars = [v.var for v in vars if not v == var]
                if eq.has_any_symbols(var.var) and (len(othervars) == 0 or not eq.has_any_symbols(*othervars)):
                    
                    symbolgen = cse_main.numbered_symbols('const')
                    eqnew, symbols = self.removeConstants(eq.subs(self.freevarsubs+[(sin(var.var),var.svar),(cos(var.var),var.cvar)]),[var.cvar,var.svar], symbolgen)
                    eqnew2,symbols2 = self.factorLinearTerms(eqnew,[var.svar,var.cvar],symbolgen)
                    symbols += [(s[0],s[1].subs(symbols)) for s in symbols2]
                    if self.countVariables(eqnew2,var.cvar) == 1 and self.countVariables(eqnew2,var.svar) == 1:
                        a = Wild('a',exclude=[var.svar,var.cvar])
                        b = Wild('b',exclude=[var.svar,var.cvar])
                        c = Wild('c',exclude=[var.svar,var.cvar])
                        m = eqnew2.match(a*var.cvar+b*var.svar+c)
                        if m is not None:
                            symbols += [(var.svar,sin(var.var)),(var.cvar,cos(var.var))]
                            asinsol = asin(-m[c]/sqrt(m[a]*m[a]+m[b]*m[b])).subs(symbols)
                            constsol = -atan2(m[a],m[b]).subs(symbols).evalf()
                            jointsolutions = [constsol+asinsol,constsol+pi.evalf()-asinsol]
                            solvedvars.append((var.var,SolverSolution(var.var.name,jointeval=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
                            continue
                    
                    try:
                        # substitute sin                        
                        if self.countVariables(eq.subs(cos(var.var),var.cvar),var.cvar) <= 1: # anything more than 1 implies quartic equation
                            eqnew = eq.subs(self.freevarsubs+[(cos(var.var),sqrt(Real(1,30)-var.svar**2)),(sin(var.var),var.svar)])
                            eqnew,symbols = self.factorLinearTerms(eqnew,[var.svar])
                            solutions = self.customtsolve(eqnew,var.svar)
                            jointsolutions = [s.subs(symbols+[(var.svar,sin(var.var))]) for s in solutions]
                            solvedvars.append((var.var,SolverSolution(var.var.name, jointevalsin=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
                    except (ValueError, AttributeError):
                        pass

                    # substite cos
                    try:
                        if self.countVariables(eq.subs(sin(var.var),var.svar),var.svar) <= 1: # anything more than 1 implies quartic equation
                            eqnew = eq.subs(self.freevarsubs+[(sin(var.var),sqrt(Real(1,30)-var.cvar**2)),(cos(var.var),var.cvar)])
                            eqnew,symbols = self.factorLinearTerms(eqnew,[var.cvar])
                            solutions = self.customtsolve(eqnew,var.cvar)
                            jointsolutions = [s.subs(symbols+[(var.cvar,cos(var.var))]) for s in solutions]
                            solvedvars.append((var.var,SolverSolution(var.var.name, jointevalcos=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
                    except (ValueError, AttributeError):
                        pass
        return solvedvars

    # solve for just the translation component
    def solveIKTranslation(self, Positions, Positionsee, rawvars):
        vars = map(lambda rawvar: self.Variable(rawvar), rawvars)
        solvedvars = []

        P = map(lambda i: Positions[i] - Positionsee[i], range(len(Positions)))
        for var in vars:
            othervars = [v.var for v in vars if not v == var and not v.var==solvedvars]
            eqns = []
            for p in P:
                for j in range(3):
                    if p[j].has_any_symbols(var.var) and (len(othervars)==0 or not p[j].has_any_symbols(*othervars)):
                        if self.isExpressionUnique(eqns,p[j]) and self.isExpressionUnique(eqns,-p[j]):
                            eqns.append(p[j])
            
            if len(eqns) == 0:
                continue
            
            if len(eqns) > 1:
                neweqns = []
                listsymbols = []
                symbolgen = cse_main.numbered_symbols('const')
                for e in eqns:
                    enew, symbols = self.removeConstants(e.subs(self.freevarsubs+[(sin(var.var),var.svar),(cos(var.var),var.cvar)]),[var.cvar,var.svar], symbolgen)
                    enew2,symbols2 = self.factorLinearTerms(enew,[var.svar,var.cvar],symbolgen)
                    symbols += [(s[0],s[1].subs(symbols)) for s in symbols2]
                    rank = self.codeComplexity(enew2)+reduce(lambda x,y: x+self.codeComplexity(y[1]),symbols,0)
                    neweqns.append((rank,enew2))
                    listsymbols += symbols
                
                # since we're solving for two variables, we only want to use two equations, so
                # start trying all the equations starting from the least complicated ones to the most until a solution is found
                eqcombinations = []
                for eqs in xcombinations(neweqns,2):
                    eqcombinations.append((eqs[0][0]+eqs[1][0],[Eq(e[1],0) for e in eqs]))
                eqcombinations.sort(lambda x, y: x[0]-y[0])
                
                solution = None
                for comb in eqcombinations:
                    # try to solve for both sin and cos terms
                    s = solve(comb[1],[var.svar,var.cvar])
                    if s is not None and s.has_key(var.svar) and s.has_key(var.cvar):
                        solution = s
                        break
                if solution is not None:
                    jointsolution = [self.customtrigsimp(atan2(solution[var.svar],solution[var.cvar]).subs(listsymbols), deep=True)]
                    solvedvars.append((var.var,SolverSolution(var.var.name,jointsolution), [self.codeComplexity(s) for s in jointsolution]))
                    continue
            
            # solve one equation
            eq = eqns[0]
            symbolgen = cse_main.numbered_symbols('const')
            eqnew, symbols = self.removeConstants(eq.subs(self.freevarsubs+[(sin(var.var),var.svar),(cos(var.var),var.cvar)]), [var.cvar,var.svar], symbolgen)
            eqnew2,symbols2 = self.factorLinearTerms(eqnew,[var.cvar,var.svar], symbolgen)
            symbols += [(s[0],s[1].subs(symbols)) for s in symbols2]

            if self.countVariables(eqnew2,var.cvar) == 1 and self.countVariables(eqnew2,var.svar) == 1:
                a = Wild('a',exclude=[var.svar,var.cvar])
                b = Wild('b',exclude=[var.svar,var.cvar])
                c = Wild('c',exclude=[var.svar,var.cvar])
                m = eqnew2.match(a*var.cvar+b*var.svar+c)
                if m is not None:
                    symbols += [(var.svar,sin(var.var)),(var.cvar,cos(var.var))]
                    asinsol = asin(-m[c]/sqrt(m[a]*m[a]+m[b]*m[b])).subs(symbols)
                    constsol = -atan2(m[a],m[b]).subs(symbols).evalf()
                    jointsolutions = [constsol+asinsol,constsol+pi.evalf()-asinsol]
                    solvedvars.append((var.var,SolverSolution(var.var.name,jointeval=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
                    continue

            try:
                # substitute cos
                if self.countVariables(eqnew2,var.svar) <= 1: # anything more than 1 implies quartic equation
                    solutions = self.customtsolve(eqnew2.subs(var.svar,sqrt(1-var.cvar**2)),var.cvar)
                    jointsolutions = [s.subs(symbols+[(var.cvar,cos(var.var))]) for s in solutions]
                    solvedvars.append((var.var,SolverSolution(var.var.name, jointevalcos=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
            except (ValueError):
                pass
            
            # substitute sin
            try:
                if self.countVariables(eqnew2,var.svar) <= 1: # anything more than 1 implies quartic equation
                    solutions = self.customtsolve(eqnew2.subs(var.cvar,sqrt(1-var.svar**2)),var.svar)
                    jointsolutions = [trigsimp(s.subs(symbols+[(var.svar,sin(var.var))])) for s in solutions]
                    solvedvars.append((var.var,SolverSolution(var.var.name, jointevalsin=jointsolutions), [self.codeComplexity(s) for s in jointsolutions]))
            except (ValueError):
                pass
        return solvedvars

    # solve for just the rotation component
    def solveIKRotation(self, R, Ree, rawvars,endbranchtree=None):
        vars = map(lambda rawvar: self.Variable(rawvar), rawvars)
        subreal = [(cos(var.var),var.cvar) for var in vars]+[(sin(var.var),var.svar) for var in vars]
        Rsolve = R.subs(subreal)
        roottree = []
        curtree = roottree
        
        while len(vars)>0:
            solvedvars, checkzerovars = self.checkStandaloneVariables(R, Rsolve, Ree, vars)
            solvedvars2 = self.checkQuotientVariables(R, Rsolve, Ree, vars)

            solutiontrees = dict()
            # for every solved variable in solvedvars, check that there isn't a cleaner solution in solvedvars2
            for var,solutions in solvedvars.iteritems():
                if solvedvars2.has_key(var) and not solvedvars2[var][1]:
                    divisor = solvedvars2[var][2]
                    if divisor.has_any_symbols(*rawvars):
                        # can solve for divisor ahead of time and branch out to better solution
                        solutiontrees[var] = SolverBranch('%squot'%(var.name),divisor,[(0,[SolverSolution(var.name, jointeval=solutions)]),(None,[SolverSolution(var.name,solvedvars2[var][0])])])
                    elif self.codeComplexity(solutions[0]) > self.codeComplexity(solvedvars2[var][0][0]):
                        solvedvars[var] = solvedvars2[var][0] # replace

            vars = filter(lambda var: not solvedvars.has_key(var.var), vars)
            
            for var,solutions in solvedvars.iteritems():
                if solutiontrees.has_key(var):
                    curtree.append(solutiontrees[var])
                else:
                    curtree.append(SolverSolution(var.name, jointeval=solutions))
            
            if len(vars) == 0:
                break

            solvedvars2 = self.checkQuotientVariables(R, Rsolve, Ree, vars)
            if len(solvedvars2) == 0:
                newrawvars = [var.var for var in vars]
                print "picking free parameter for potential degenerate case: ",newrawvars[0]
                print "R = "
                pprint(R)
                tree = self.solveIKRotation(R,Ree,newrawvars[1:],endbranchtree)
                curtree.append(SolverFreeParameter(newrawvars[0].name,tree))
                return roottree

            nextvars = vars[:]
            nexttree = []
            for var,solutions in solvedvars2.iteritems():
                if not solutions[1]:
                    nexttree.append(SolverSolution(var.name, jointeval=solutions[0]))
                    nextvars = filter(lambda x: not x.var == var, nextvars)
            if len(nexttree) == 0:
                for var,solutions in solvedvars2.iteritems():
                    if solutions[1]:
                        nexttree.append(SolverSolution(var.name, jointeval=solutions[0], AddPi=True))
                        nextvars = filter(lambda x: not x.var == var, nextvars)
                        break

            # if checkzerovars1 are 0 or pi/2, substitute with new R2 and resolve
            if len(checkzerovars) > 0:
                checkvar = checkzerovars[0][0]
                checkeq = checkzerovars[0][1]
                if checkeq.is_Function and checkeq.func == asin:
                    checkeq = checkeq.args[0]
                    valuestotest = [(-1,[-pi/2]),(1,[pi/2])]
                elif checkeq.is_Function and checkeq.func == acos:
                    checkeq = checkeq.args[0]
                    valuestotest = [(-1,[pi]),(1,[0])]
                elif checkeq.is_Mul and len(checkeq.args)>1 and checkeq.args[0].is_number:
                    if checkeq.args[1].is_Function and checkeq.args[1].func == asin:
                        c = checkeq.args[0].evalf()
                        checkeq = checkeq.args[1].args[0]
                        valuestotest = [(-c,[-pi/2]),(c,[pi/2])]
                    elif checkeq.args[1].is_Function and checkeq.args[1].func == acos:
                        c = checkeq.args[0].evalf()
                        checkeq = checkeq.args[1].args[0]
                        valuestotest = [(-c,[pi]),(c,[0])]
                else:
                    print "unknown function when checking for 0s",checkeq
                    valuestotest = [(0,[checkeq.subs(checkvar,0)])]

                newrawvars = [var.var for var in vars if not var.var == checkvar]
                subtrees = []
                for checkvalue in valuestotest:
                    subtree = []
                    for value in checkvalue[1]:
                        subtree += [[SolverSetJoint(checkvar,value)]+self.solveIKRotation(R.subs(checkvar,value), Ree, newrawvars,endbranchtree)]
                    subtrees.append((checkvalue[0],[SolverSequence(subtree)]))
                branchtree = SolverBranch(checkvar, checkeq, subtrees+[(None,nexttree)])
                curtree.append(branchtree)
                curtree = nexttree
            else:
                curtree += nexttree
            vars = nextvars

        if endbranchtree is not None:
            curtree += endbranchtree
        return roottree
            
    # look for individual elements that have only one symbol
    def checkStandaloneVariables(self, R, Rsolve, Ree, vars):
        solvedvars = dict()
        checkzerovars = []
        
        for var in vars:
            othervars = [v.var for v in vars if not v == var]
            inds = [i for i in range(9) if R[i].has_any_symbols(var.var) and (len(othervars) == 0 or not R[i].has_any_symbols(*othervars))]
            if len(inds) == 0:
                continue
            
            if len(inds) > 2:
                inds = inds[0:2]

            solution = solve([Eq(Rsolve[i],Ree[i]) for i in inds],[var.svar,var.cvar])
            if solution is None:
                continue
            if solution.has_key(var.svar) and solution.has_key(var.cvar):
                solvedvars[var.var] = [self.customtrigsimp(atan2(self.customtrigsimp(solution[var.svar]), self.customtrigsimp(solution[var.cvar])), deep=True)]
            else:
                # although variable cannot be solved completely,
                # can check for multiples of pi/2 and eliminate possible 0s
                if solution.has_key(var.svar):
                    checkzerovars.append((var.var, asin(solution[var.svar])))
                elif solution.has_key(var.cvar):
                    checkzerovars.append((var.var, acos(solution[var.cvar])))
        
        return solvedvars, checkzerovars

    def checkQuotientVariables(self, R, Rsolve, Ree, vars):
        # look for quotient of two elements that has only one element
        solvedvars = dict()

        for var in vars:
            othervars = [v.var for v in vars if not v == var]
            
            taninds = None
            for i in range(9):
                if not R[i].has_any_symbols(var.var):
                    continue
                
                for j in range(i+1,9):
                    if not R[j].has_any_symbols(var.var):
                        continue
                    
                    Q = R[i]/R[j]
                    if Q.has_any_symbols(var.var) and (len(othervars)==0 or not Q.has_any_symbols(*othervars)):
                        ## found something, check if tan or cotan or variable
                        Qsub = Q.subs(sin(var.var)/cos(var.var),var.tvar)
                        if not Q == Qsub: # if substitution was successful
                            divisor = R[i]/fraction(Q)[0]
                            taninds = (Qsub,i,j,True if len(othervars)>0 and divisor.has_any_symbols(*othervars) else False,divisor)
                        else:
                            Q = R[j]/R[i]
                            Qsub = Q.subs(sin(var.var)/cos(var.var),var.tvar)
                            if not Q == Qsub: # if substitution was successful
                                divisor = R[j]/fraction(Q)[0]
                                taninds = (Qsub,j,i,True if len(othervars)>0 and divisor.has_any_symbols(*othervars) else False,divisor)
                            #else:
                            #    print "There is no tangent in division expression? ",Q
                    if not taninds is None:
                        break
                if not taninds is None:
                    break
            if taninds is None:
                continue
            
            if taninds[3]:
                solutions = solve(Eq(taninds[0],Ree[taninds[1]]/Ree[taninds[2]]),var.tvar)
                solvedvars[var.var] = ([self.customtrigsimp(atan2(*fraction(self.customtrigsimp(solution))), deep=True) for solution in solutions], taninds[3],taninds[4])
            else:
                sinvarsols = solve(Eq(Rsolve[taninds[1]],Ree[taninds[1]]),var.svar)
                cosvarsols = solve(Eq(Rsolve[taninds[2]],Ree[taninds[2]]),var.cvar)

                solutions = []
                for sinvarsol in sinvarsols:
                    for cosvarsol in cosvarsols:
                        solutions.append(self.customtrigsimp(atan2(self.customtrigsimp(sinvarsol),self.customtrigsimp(cosvarsol)),deep=True))
                solvedvars[var.var] = (solutions,taninds[3],taninds[4])
        
        return solvedvars

    ## SymPy helper routines

    # factors linear terms together
    def factorLinearTerms(self,expr,vars,symbolgen = None):
        if not expr.is_Add:
            return expr,[]
        
        if symbolgen is None:
            symbolgen = cse_main.numbered_symbols('const')
        
        cexprs = dict()
        newexpr = S.Zero
        symbols = []
        for term in expr.args:
            if term.is_Mul:
                termconst = []
                termlinear = []
                termquad = []
                termother = []
                for x in term.args:
                    haslinear = any([x - var == 0 for var in vars])
                    hasquad = any([x - var*var == 0 for var in vars])
                    if haslinear and not hasquad:
                        termquad.append(x)
                    elif not haslinear and hasquad:
                        termquad.append(x)
                    elif x.has_any_symbols(*vars):
                        termother.append(x)
                        break
                    else:
                        termconst.append(x)
                
                if len(termother) == 0 and len(termlinear) == 1 and len(termquad) == 0:
                    if cexprs.has_key(termlinear[0]):
                        cexprs[termlinear[0]] += term/termlinear[0]
                    else:
                        cexprs[termlinear[0]] = term/termlinear[0]
                elif len(termother) == 0 and len(termlinear) == 0 and len(termquad) == 1:
                    if cexprs.has_key(termquad[0]):
                        cexprs[termquad[0]] += term/termquad[0]
                    else:
                        cexprs[termquad[0]] = term/termquad[0]
                else:
                    newexpr += term
            elif any([term - var == 0 for var in vars]) or any([term - var*var == 0 for var in vars]):
                if cexprs.has_key(term):
                    cexprs[term] += S.One
                else:
                    cexprs[term] = S.One
            else:
                newexpr += term
        
        for var,cexpr in cexprs.iteritems():
            c = symbolgen.next();
            newexpr += c*var
            symbols.append((c,cexpr))
        return newexpr,symbols

    def removeConstants(self,expr,vars,symbolgen = None):
        """Separates all terms that do have var in them"""
        if symbolgen is None:
            symbolgen = cse_main.numbered_symbols('const')
        if expr.is_Add:
            newexpr = S.Zero
            cexpr = S.Zero
            symbols = []
            for term in expr.args:
                if term.has_any_symbols(*vars):
                    expr2, symbols2 = self.removeConstants(term,vars,symbolgen)
                    newexpr += expr2
                    symbols += symbols2
                else:
                    cexpr += term

            if not cexpr == 0:
                c = symbolgen.next();
                newexpr += c
                symbols.append((c,cexpr))
            return newexpr,symbols
        elif expr.is_Mul:
            newexpr = S.One
            cexpr = S.One
            symbols = []
            for term in expr.args:
                if term.has_any_symbols(*vars):
                    expr2, symbols2 = self.removeConstants(term,vars,symbolgen)
                    newexpr *= expr2
                    symbols += symbols2
                else:
                    cexpr *= term

            if not cexpr == 0:
                c = symbolgen.next();
                newexpr *= c
                symbols.append((c,cexpr))
            return newexpr,symbols
        return expr,[]

    def customtrigsimp(self,expr, deep=False):
        """
        Usage
        =====
        trig(expr) -> reduces expression by using known trig identities

        Notes
        =====


        Examples
        ========
        >>> from sympy import *
        >>> x = Symbol('x')
        >>> y = Symbol('y')
        >>> e = 2*sin(x)**2 + 2*cos(x)**2
        >>> trigsimp(e)
        2
        >>> trigsimp(log(e))
        log(2*cos(x)**2 + 2*sin(x)**2)
        >>> trigsimp(log(e), deep=True)
        log(2)
        """
        from sympy.core.basic import S
        sin, cos, tan, cot, atan2 = C.sin, C.cos, C.tan, C.cot, C.atan2
        
        #XXX this stopped working:
        if expr == 1/cos(Symbol("x"))**2 - 1:
            return tan(Symbol("x"))**2
        
        if expr.is_Function:
            if deep:
                newargs = [self.customtrigsimp(a, deep) for a in expr.args]

                if expr.func == atan2:
                    # check special simplification
                    a,b,c = map(Wild, 'abc')
                    patterns = [
                        (a*sin(b)+c*cos(b),c*sin(b)-a*cos(b),-b-atan2(c,a)-pi),
                        (a*sin(b)-c*cos(b),c*sin(b)+a*cos(b),b-atan2(c,a)),
                        (a*sin(b)+c*cos(b),-c*sin(b)+a*cos(b),b+atan2(c,a)),
                        (a*sin(b)-c*cos(b),-c*sin(b)-a*cos(b),-b+atan2(c,a)-pi),
                        (-a*sin(b)-c*cos(b),c*sin(b)-a*cos(b),b+atan2(c,a)+pi),
                        (-a*sin(b)+c*cos(b),c*sin(b)+a*cos(b),-b+atan2(c,a)),
                        (-a*sin(b)-c*cos(b),a*cos(b)-c*sin(b),-b-atan2(c,a)),
                        (-a*sin(b)+c*cos(b),-c*sin(b)-a*cos(b),b-atan2(c,a)+pi),
                        ]

                    for pattern in patterns:
                        m0 = newargs[0].match(pattern[0])
                        m1 = newargs[1].match(pattern[1])
                        if m0 is not None and m1 is not None and m0[a]-m1[a]==0 and m0[b]-m1[b]==0 and m0[c]-m1[c]==0:
                            return pattern[2].subs(m0)

                newexpr = expr.func(*newargs)
                return newexpr
        elif expr.is_Mul:
            ret = S.One
            for x in expr.args:
                ret *= self.customtrigsimp(x, deep)
            return ret
        elif expr.is_Pow:
            return Pow(self.customtrigsimp(expr.base, deep), self.customtrigsimp(expr.exp, deep))
        elif expr.is_Add:
            # TODO this needs to be faster
            # The types of trig functions we are looking for
            a,b,c = map(Wild, 'abc')
            matchers = (
                (a*sin(b)**2, a - a*cos(b)**2),
                (a*tan(b)**2, a*(1/cos(b))**2 - a),
                (a*cot(b)**2, a*(1/sin(b))**2 - a),
                )
            
            # Scan for the terms we need
            ret = S.Zero
            for term in expr.args:
                term = self.customtrigsimp(term, deep)
                res = None
                for pattern, result in matchers:
                    res = term.match(pattern)
                    if res is not None:
                        ret += result.subs(res)
                        break
                if res is None:
                    ret += term
            
            # Reduce any lingering artifacts, such as sin(x)**2 changing
            # to 1-cos(x)**2 when sin(x)**2 was "simpler"
            artifacts = (
                (a - a*cos(b)**2 + c, a*sin(b)**2 + c, []),
                (a*cos(b)**2 - a*cos(b)**4 + c, a*cos(b)**2*sin(b)**2 + c, []),
                (a*sin(b)**2 - a*sin(b)**4 + c, a*cos(b)**2*sin(b)**2 + c, []),
                (a*sin(b)**2 + c*sin(b)**2, sin(b)**2*(a+c), []),
                (a*sin(b)**2 + a*cos(b)**2, a, []),
                # tangets should go after all identities with cos/sin (otherwise infinite looping)!!
                #(a - a*(1/cos(b))**2 + c, -a*tan(b)**2 + c, [cos]),
                #(a - a*(1/sin(b))**2 + c, -a*cot(b)**2 + c, [sin]),
                #(a*cos(b)**2*tan(b)**2 + c, a*sin(b)**2+c, [sin,cos,tan]),
                #(a*sin(b)**2/tan(b)**2 + c, a*cos(b)**2+c, [sin,cos,tan]),
                )
            
            expr = ret
            Changed = True
            while Changed:
                Changed = False
                prevexpr = expr
                
                for pattern, result, ex in artifacts:
                    # Substitute a new wild that excludes some function(s)
                    # to help influence a better match. This is because
                    # sometimes, for example, 'a' would match sec(x)**2
                    a_t = Wild('a', exclude=ex)
                    pattern = pattern.subs(a, a_t)
                    result = result.subs(a, a_t)
                    
                    if expr.is_number:
                        return expr
                    
                    try:
                        m = expr.match(pattern)
                    except TypeError:
                        break
                    
                    while m is not None:
                        if not m.has_key(c):
                            break
                        if m[a_t] == 0 or -m[a_t] in m[c].args or m[a_t] + m[c] == 0:
                            break
                        exprnew = result.subs(m)
                        if len(exprnew.args) > len(expr.args):
                            break
                        expr = exprnew
                        Changed = True
                        if not expr.is_Add:
                            break # exhausted everything
                        if len(exprnew.args) == len(expr.args):
                            break
                        
                        try:
                            m = expr.match(pattern)
                        except TypeError:
                            break
                    
                    if not expr.is_Add:
                        break # exhausted everything
                
                if not expr.is_Add:
                    break # exhausted everything
                if expr.is_Add and len(expr.args) >= len(prevexpr.args):
                    break # new expression hasn't helped, so stop
            
            return expr
        return expr

    def customtsolve(self,eq, sym):
        """
        Solves a transcendental equation with respect to the given
        symbol. Various equations containing mixed linear terms, powers,
        and logarithms, can be solved.

        Only a single solution is returned. This solution is generally
        not unique. In some cases, a complex solution may be returned
        even though a real solution exists.

            >>> from sympy import *
            >>> x = Symbol('x')

            >>> tsolve(3**(2*x+5)-4, x)
            (-5*log(3) + log(4))/(2*log(3))

            >>> tsolve(log(x) + 2*x, x)
            1/2*LambertW(2)

        """
        if solvers.patterns is None:
            solvers._generate_patterns()
        eq = sympify(eq)
        if isinstance(eq, Equality):
            eq = eq.lhs - eq.rhs
        sym = sympify(sym)
        
        eq2 = eq.subs(sym, solvers.x)
        # First see if the equation has a linear factor
        # In that case, the other factor can contain x in any way (as long as it
        # is finite), and we have a direct solution
        r = Wild('r')
        m = eq2.match((solvers.a*solvers.x+solvers.b)*r)
        if m and m[solvers.a]:
            return [(-solvers.b/solvers.a).subs(m).subs(solvers.x, sym)]
        for p, sol in solvers.patterns:
            m = eq2.match(p)
            if m:
                return [sol.subs(m).subs(solvers.x, sym)]
        
        # let's also try to inverse the equation
        lhs = eq
        rhs = S.Zero
        while True:
            indep, dep = lhs.as_independent(sym)

            # dep + indep == rhs
            if lhs.is_Add:
                # this indicates we have done it all
                if indep is S.Zero:
                    break

                lhs = dep
                rhs-= indep
        
            # dep * indep == rhs
            else:
                # this indicates we have done it all
                if indep is S.One:
                    break

                lhs = dep
                rhs/= indep
        
        #                    -1
        # f(x) = g  ->  x = f  (g)
        if lhs.is_Function and lhs.nargs==1 and hasattr(lhs, 'inverse'):
            rhs = lhs.inverse() (rhs)
            lhs = lhs.args[0]
            
            sol = solve(lhs-rhs, sym)
            return sol
        elif lhs.is_Pow:
            rhs = pow(rhs,1/lhs.exp)
            lhs = lhs.base

            sol = self.customtsolve(lhs-rhs, sym)
            return sol
        elif lhs.is_Add:
            # just a simple case - we do variable substitution for first function,
            # and if it removes all functions - let's call solve.
            #      x    -x                   -1
            # UC: e  + e   = y      ->  t + t   = y
            t = Symbol('t', dummy=True)
            terms = lhs.args
            
            # find first term which is Function
            IsPow = False
            for f1 in lhs.args:
                if f1.is_Function:
                    break
                elif f1.is_Pow and f1.exp.evalf() < 1:
                    IsPow = True
                    break
                elif f1.is_Mul:
                    if len(filter(lambda f2: f2.is_Pow and f2.exp.evalf() < 1, f1.args)) == 1:
                        IsPow = True
                        break
                    elif len(filter(lambda f2: f2.is_Function, f1.args)) == 1:
                        break
            else:
                return solve(lhs-rhs,sym)

            # perform the substitution
            lhs_ = lhs.subs(f1, t)
            
            # if no Functions left, we can proceed with usual solve
            if not (lhs_.is_Function or
                    any(term.is_Function for term in lhs_.args)):
                cv_sols = solve(lhs_ - rhs, t)
                if IsPow:
                    cv_inv = self.customtsolve( t - f1, sym )[0]
                else:
                    cv_inv = solve( t - f1, sym )[0]
                
                sols = list()
                if cv_inv.is_Pow:
                    for sol in cv_sols:
                        neweq = (pow(sym,1/cv_inv.exp)-cv_inv.base.subs(t, sol)).expand()
                        symbolgen = cse_main.numbered_symbols('tsolveconst')
                        neweq2,symbols = self.factorLinearTerms(neweq,[sym],symbolgen)
                        neweq3,symbols2 = self.removeConstants(neweq2,[sym],symbolgen)
                        symbols += [(s[0],s[1].subs(symbols)) for s in symbols2]
                        newsols = solve(neweq3,sym)
                        sols = sols + [simplify(sol.subs(symbols)) for sol in newsols]
                else:
                    for sol in cv_sols:
                        newsol = cv_inv.subs(t, sol)
                        if newsol.has_any_symbols(sym):
                            sols = sols + solve(newsol,sym)
                        else:
                            sols.append(newsol)
                return sols
        
        raise ValueError("unable to solve the equation")

if __name__ == "__main__":

    parser = OptionParser(usage='usage: %prog [options] [solve joint indices]',
                          description="""
Software License Agreement (Lesser GPL v3)
Copyright (C) 2009 Rosen Diankov
ikfast is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

ikfast generates an analytical inverse kinematics solver in C++ for a set of 2, 3, or 6 joint values.
It takes as input an OpenRAVE robot file, the base link to specify all end effector transformations
again, the end effector link, and 6 joints in the chain from the base to the end effector to solve
the analytical inverse kinematics for. Extra joints between the base-end effector chain that are
not part of the 6 chosen joints need to be given inside the inverse kinematics call. For now, only
supports hinge joints.

Example usage for 7 DOF Barrett WAM where 1st joint is a free parameter:

ikfast.py --fkfile=fk_WAM7.txt --baselink=0 --eelink=7 --savefile=ik.cpp 1 2 3 4 5 6

""")
    parser.add_option('--fkfile', action='store', type='string', dest='fkfile',
                      help='forward kinematics file usually a text based representation outputed by OpenRAVE on load of the robot')
    parser.add_option('--savefile', action='store', type='string', dest='savefile',default='ik.cpp',
                      help='filename where to store the generated c++ code')
    parser.add_option('--baselink', action='store', type='int', dest='baselink',
                      help='base link index to start extraction of ik chain')
    parser.add_option('--eelink', action='store', type='int', dest='eelink',
                      help='end effector link index to end extraction of ik chain')
    parser.add_option('--freeparam', action='append', type='int', dest='freeparams',default=[],
                      help='Optional joint index specifying a free parameter of the manipulator. If not specified, assumes all joints not solving for are free parameters. Can be specified multiple times for multiple free parameters.')
    parser.add_option('--rotation3donly', action='store_true', dest='rotation3donly',default=False,
                      help='If true, need to specify only 3 solve joints and will solve for a target rotation')
#     parser.add_option('--rotation2donly', action='store_true', dest='rotation2donly',default=False,
#                       help='If true, need to specify only 2 solve joints and will solve for a target direction')
    parser.add_option('--usedummyjoints', action="store_true",dest='usedummyjoints',default=False,
                      help='Treat the unspecified joints in the kinematic chain as dummy and set them to 0. If not specified, treats all unspecified joints as free parameters.')

    (options, args) = parser.parse_args()
    if options.fkfile is None or options.baselink is None or options.eelink is None:
        print('Error: Not all arguments specified')
        sys.exit(1)

    solvejoints = [atoi(joint) for joint in args]
    numexpected = 6
    if options.rotation3donly:
        numexpected = 3

    if not len(solvejoints) == numexpected:
        print 'Need ',numexpected, 'solve joints, got: ', solvejoints
        sys.exit(1)

    tstart = time.time()
    kinematics = RobotKinematics(options.fkfile)
    code = kinematics.generateIkSolver(options.baselink,options.eelink,solvejoints,options.freeparams,options.usedummyjoints)

    success = True if len(code) > 0 else False

    print "total time for ik generation of %s is %fs"%(options.savefile,time.time()-tstart)
    if success:
        open(options.savefile,'w').write(code)

    sys.exit(0 if success else 1)