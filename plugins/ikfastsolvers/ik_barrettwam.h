/// autogenerated analytical inverse kinematics code from ikfast program
/// \author Rosen Diankov
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
    /// \param pfree The free parameters required, range is in [-pi,pi]
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
    /// \return vector of indices indicating the free parameters
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
int getNumFreeParameters() { return 1; }
int* getFreeParameters() { static int freeparams[] = {0}; return freeparams; }
int getNumJoints() { return 7; }

int getIKRealSize() { return sizeof(IKReal); }

/// solves the inverse kinematics equations.
/// \param pfree is an array specifying the free joints of the chain.
bool ik(const IKReal* eetrans, const IKReal* eerot, const IKReal* pfree, std::vector<IKSolution>& vsolutions) {
    vsolutions.resize(0); vsolutions.reserve(8);
    IKReal j1, cj1, sj1,
    j2, cj2, sj2,
    j3, cj3, sj3,
    j4, cj4, sj4,
    j5, cj5, sj5,
    j6, cj6, sj6,
    j0=pfree[0], cj0=cos(pfree[0]), sj0=sin(pfree[0]),
    _r00, r00 = eerot[0*3+0],
    _r01, r01 = eerot[0*3+1],
    _r02, r02 = eerot[0*3+2],
    _r10, r10 = eerot[1*3+0],
    _r11, r11 = eerot[1*3+1],
    _r12, r12 = eerot[1*3+2],
    _r20, r20 = eerot[2*3+0],
    _r21, r21 = eerot[2*3+1],
    _r22, r22 = eerot[2*3+2],
    _px, _py, _pz, px = eetrans[0], py = eetrans[1], pz = eetrans[2];
    
    _r00=r00;
    _r01=((-1.00000000000000)*(r02));
    _r02=r01;
    _px=((-0.220000000000000)+(px));
    _r10=r10;
    _r11=((-1.00000000000000)*(r12));
    _r12=r11;
    _py=((-0.140000000000000)+(py));
    _r20=r20;
    _r21=((-1.00000000000000)*(r22));
    _r22=r21;
    _pz=((-0.346000000000000)+(pz));
    r00 = _r00; r01 = _r01; r02 = _r02; r10 = _r10; r11 = _r11; r12 = _r12; r20 = _r20; r21 = _r21; r22 = _r22; px = _px; py = _py; pz = _pz;
    {
    IKReal j3array[2], cj3array[2], sj3array[2];
    bool j3valid[2]={false};
    IKReal x0=(pz)*(pz);
    IKReal x1=((2.98679637344321)*(x0));
    IKReal x2=(py)*(py);
    IKReal x3=((2.98679637344321)*(x2));
    IKReal x4=(px)*(px);
    IKReal x5=((2.98679637344321)*(x4));
    IKReal x6=((x3)+(x1)+(x5));
    IKReal x7=((1.18441410191008)+(((-1.00000000000000)*(x6))));
    if( (x7) < -1.0001 || (x7) > 1.0001 )
        return false;
    IKReal x8=IKasin(x7);
    j3array[0]=((-1.34027003705316)+(((-1.00000000000000)*(x8))));
    sj3array[0]=IKsin(j3array[0]);
    cj3array[0]=IKcos(j3array[0]);
    j3array[1]=((1.80132261653663)+(x8));
    sj3array[1]=IKsin(j3array[1]);
    cj3array[1]=IKcos(j3array[1]);
    if( j3array[0] > IKPI )
        j3array[0]-=IK2PI;
    else if( j3array[0] < -IKPI )
        j3array[0]+=IK2PI;
    j3valid[0] = true;
    if( j3array[1] > IKPI )
        j3array[1]-=IK2PI;
    else if( j3array[1] < -IKPI )
        j3array[1]+=IK2PI;
    j3valid[1] = true;
    if( j3valid[0] && j3valid[1] && IKabs(cj3array[0]-cj3array[1]) < 0.0001 && IKabs(sj3array[0]-sj3array[1]) < 0.0001 )
        j3valid[1]=false;
    for(int ij3 = 0; ij3 < 2; ++ij3) {
    if( !j3valid[ij3] )
        continue;
    j3 = j3array[ij3]; cj3 = cj3array[ij3]; sj3 = sj3array[ij3];
    
    {
    IKReal j2array[2], cj2array[2], sj2array[2];
    bool j2valid[2]={false};
    sj2array[0]=((((IKReal)1/(((0.0450000000000728)+(((0.299999999999272)*(sj3)))+(((-0.0450000000000728)*(cj3)))))))*(((((cj0)*(py)))+(((-1.00000000000000)*(px)*(sj0))))));
    if( sj2array[0] >= -1.0001 && sj2array[0] <= 1.0001 ) {
        j2valid[0] = j2valid[1] = true;
        j2array[0] = IKasin(sj2array[0]);
        cj2array[0] = IKcos(j2array[0]);
        sj2array[1] = sj2array[0];
        j2array[1] = j2array[0] > 0 ? (IKPI-j2array[0]) : (-IKPI-j2array[0]);
        cj2array[1] = -cj2array[0];
    }
    else if( isnan(sj2array[0]) ) {
        // probably any value will work
        j2valid[0] = true;
        cj2array[0] = 1; sj2array[0] = 0; j2array[0] = 0;
    }
    if( j2valid[0] && j2valid[1] && IKabs(cj2array[0]-cj2array[1]) < 0.0001 && IKabs(sj2array[0]-sj2array[1]) < 0.0001 )
        j2valid[1]=false;
    for(int ij2 = 0; ij2 < 2; ++ij2) {
    if( !j2valid[ij2] )
        continue;
    j2 = j2array[ij2]; cj2 = cj2array[ij2]; sj2 = sj2array[ij2];
    
    {
    IKReal j1array[1], cj1array[1], sj1array[1];
    bool j1valid[1]={false};
    IKReal x9=((py)*(sj0));
    IKReal x10=((cj0)*(px));
    IKReal x11=((x9)+(x10));
    IKReal x12=((-1.00000000000000)*(x11));
    IKReal x13=((0.299999999999272)*(cj3));
    IKReal x14=((0.0450000000000728)*(sj3));
    IKReal x15=((0.550000000002910)+(x13)+(x14));
    IKReal x16=((0.0450000000000728)*(cj2));
    IKReal x17=((148.148148149252)*(x14)*(x16));
    IKReal x18=((x17)+(x16));
    IKReal x19=((3.33333333337214)*(x13)*(x16));
    IKReal x20=((x18)+(((-1.00000000000000)*(x19))));
    IKReal x21=(x12)*(x12);
    IKReal x22=x0;
    IKReal x23=((x21)+(x22));
    IKReal x24=((-1.00000000000000)*(x23));
    IKReal x25=((IKReal)1/(x24));
    j1array[0]=IKatan2(((x25)*(((((x12)*(x15)))+(((pz)*(x20)))))), ((x25)*(((((x12)*(x20)))+(((-1.00000000000000)*(pz)*(x15)))))));
    sj1array[0]=IKsin(j1array[0]);
    cj1array[0]=IKcos(j1array[0]);
    if( j1array[0] > IKPI )
        j1array[0]-=IK2PI;
    else if( j1array[0] < -IKPI )
        j1array[0]+=IK2PI;
    j1valid[0] = true;
    { int ij1 = 0;
    if( !j1valid[ij1] )
        continue;
    j1 = j1array[0]; cj1 = cj1array[0]; sj1 = sj1array[0];
    
    _r00=((((cj0)*(cj1)*(cj2)*(cj3)*(r00)))+(((-1.00000000000000)*(cj3)*(r00)*(sj0)*(sj2)))+(((-1.00000000000000)*(r10)*(sj0)*(sj1)*(sj3)))+(((-1.00000000000000)*(cj0)*(r00)*(sj1)*(sj3)))+(((cj1)*(cj2)*(cj3)*(r10)*(sj0)))+(((-1.00000000000000)*(cj1)*(r20)*(sj3)))+(((cj0)*(cj3)*(r10)*(sj2)))+(((-1.00000000000000)*(cj2)*(cj3)*(r20)*(sj1))));
    _r01=((((-1.00000000000000)*(cj2)*(cj3)*(r21)*(sj1)))+(((-1.00000000000000)*(r11)*(sj0)*(sj1)*(sj3)))+(((cj1)*(cj2)*(cj3)*(r11)*(sj0)))+(((cj0)*(cj1)*(cj2)*(cj3)*(r01)))+(((-1.00000000000000)*(cj1)*(r21)*(sj3)))+(((-1.00000000000000)*(cj3)*(r01)*(sj0)*(sj2)))+(((-1.00000000000000)*(cj0)*(r01)*(sj1)*(sj3)))+(((cj0)*(cj3)*(r11)*(sj2))));
    _r02=((((cj0)*(cj3)*(r12)*(sj2)))+(((cj0)*(cj1)*(cj2)*(cj3)*(r02)))+(((-1.00000000000000)*(r12)*(sj0)*(sj1)*(sj3)))+(((-1.00000000000000)*(cj0)*(r02)*(sj1)*(sj3)))+(((-1.00000000000000)*(cj2)*(cj3)*(r22)*(sj1)))+(((-1.00000000000000)*(cj3)*(r02)*(sj0)*(sj2)))+(((-1.00000000000000)*(cj1)*(r22)*(sj3)))+(((cj1)*(cj2)*(cj3)*(r12)*(sj0))));
    _r10=((((cj2)*(r20)*(sj1)*(sj3)))+(((r00)*(sj0)*(sj2)*(sj3)))+(((-1.00000000000000)*(cj1)*(cj3)*(r20)))+(((-1.00000000000000)*(cj1)*(cj2)*(r10)*(sj0)*(sj3)))+(((-1.00000000000000)*(cj0)*(r10)*(sj2)*(sj3)))+(((-1.00000000000000)*(cj0)*(cj1)*(cj2)*(r00)*(sj3)))+(((-1.00000000000000)*(cj0)*(cj3)*(r00)*(sj1)))+(((-1.00000000000000)*(cj3)*(r10)*(sj0)*(sj1))));
    _r11=((((-1.00000000000000)*(cj1)*(cj2)*(r11)*(sj0)*(sj3)))+(((cj2)*(r21)*(sj1)*(sj3)))+(((-1.00000000000000)*(cj0)*(cj1)*(cj2)*(r01)*(sj3)))+(((r01)*(sj0)*(sj2)*(sj3)))+(((-1.00000000000000)*(cj0)*(r11)*(sj2)*(sj3)))+(((-1.00000000000000)*(cj3)*(r11)*(sj0)*(sj1)))+(((-1.00000000000000)*(cj0)*(cj3)*(r01)*(sj1)))+(((-1.00000000000000)*(cj1)*(cj3)*(r21))));
    _r12=((((-1.00000000000000)*(cj3)*(r12)*(sj0)*(sj1)))+(((-1.00000000000000)*(cj0)*(cj1)*(cj2)*(r02)*(sj3)))+(((r02)*(sj0)*(sj2)*(sj3)))+(((cj2)*(r22)*(sj1)*(sj3)))+(((-1.00000000000000)*(cj1)*(cj3)*(r22)))+(((-1.00000000000000)*(cj0)*(cj3)*(r02)*(sj1)))+(((-1.00000000000000)*(cj0)*(r12)*(sj2)*(sj3)))+(((-1.00000000000000)*(cj1)*(cj2)*(r12)*(sj0)*(sj3))));
    _r20=((((-1.00000000000000)*(cj0)*(cj1)*(r00)*(sj2)))+(((-1.00000000000000)*(cj2)*(r00)*(sj0)))+(((cj0)*(cj2)*(r10)))+(((r20)*(sj1)*(sj2)))+(((-1.00000000000000)*(cj1)*(r10)*(sj0)*(sj2))));
    _r21=((((-1.00000000000000)*(cj2)*(r01)*(sj0)))+(((-1.00000000000000)*(cj0)*(cj1)*(r01)*(sj2)))+(((-1.00000000000000)*(cj1)*(r11)*(sj0)*(sj2)))+(((cj0)*(cj2)*(r11)))+(((r21)*(sj1)*(sj2))));
    _r22=((((cj0)*(cj2)*(r12)))+(((-1.00000000000000)*(cj0)*(cj1)*(r02)*(sj2)))+(((-1.00000000000000)*(cj1)*(r12)*(sj0)*(sj2)))+(((-1.00000000000000)*(cj2)*(r02)*(sj0)))+(((r22)*(sj1)*(sj2))));
    IKReal j5eval;
    j5eval=_r11;
    if( j5eval >= -1.000100 && j5eval <= -0.999900 ) {
        {
        j5 = 3.141593; sj5 = 0.000000; cj5 = -1.000000;
        IKReal j4mul = 1;
        j4=0;
        IKReal j6mul=1.00000000000000;
        j6=((-1.00000000000000)*(IKatan2(((-1.00000000000000)*(_r02)), ((-1.00000000000000)*(_r00)))));
        vsolutions.push_back(IKSolution()); IKSolution& solution = vsolutions.back();
        solution.basesol.resize(7);
        solution.basesol[0].foffset = j0;
        solution.basesol[1].foffset = j1;
        solution.basesol[2].foffset = j2;
        solution.basesol[3].foffset = j3;
        solution.basesol[4].foffset = j4;
        solution.basesol[4].fmul = j4mul;
        solution.basesol[4].freeind = 0;
        solution.basesol[5].foffset = j5;
        solution.basesol[6].foffset = j6;
        solution.basesol[6].fmul = j6mul;
        solution.basesol[6].freeind = 0;
        solution.vfree.resize(1);
        solution.vfree[0] = 4;
        }
        }
    else if( j5eval >= 0.999900 && j5eval <= 1.000100 ) {
        {
        j5 = 0.000000; sj5 = 0.000000; cj5 = 1.000000;
        IKReal j4mul = 1;
        j4=0;
        IKReal j6mul=-1.00000000000000;
        j6=((((-1.00000000000000)*(IKatan2(((-1.00000000000000)*(_r02)), ((-1.00000000000000)*(_r00))))))+(((-1.00000000000000)*(3.14159265358979))));
        vsolutions.push_back(IKSolution()); IKSolution& solution = vsolutions.back();
        solution.basesol.resize(7);
        solution.basesol[0].foffset = j0;
        solution.basesol[1].foffset = j1;
        solution.basesol[2].foffset = j2;
        solution.basesol[3].foffset = j3;
        solution.basesol[4].foffset = j4;
        solution.basesol[4].fmul = j4mul;
        solution.basesol[4].freeind = 0;
        solution.basesol[5].foffset = j5;
        solution.basesol[6].foffset = j6;
        solution.basesol[6].fmul = j6mul;
        solution.basesol[6].freeind = 0;
        solution.vfree.resize(1);
        solution.vfree[0] = 4;
        }
        }
    else {
        {
        IKReal j4array[2], cj4array[2], sj4array[2];
        bool j4valid[2]={false};
        j4array[0]=IKatan2(_r21, _r01);
        sj4array[0]=IKsin(j4array[0]);
        cj4array[0]=IKcos(j4array[0]);
        j4array[1] = j4array[0] > 0 ? j4array[0]-IKPI : j4array[0]+IKPI;
        sj4array[1] = -sj4array[0];
        cj4array[1] = -cj4array[0];
        if( j4array[0] > IKPI )
            j4array[0]-=IK2PI;
        else if( j4array[0] < -IKPI )
            j4array[0]+=IK2PI;
        j4valid[0] = true;
        if( j4array[1] > IKPI )
            j4array[1]-=IK2PI;
        else if( j4array[1] < -IKPI )
            j4array[1]+=IK2PI;
        j4valid[1] = true;
        if( j4valid[0] && j4valid[1] && IKabs(cj4array[0]-cj4array[1]) < 0.0001 && IKabs(sj4array[0]-sj4array[1]) < 0.0001 )
            j4valid[1]=false;
        for(int ij4 = 0; ij4 < 2; ++ij4) {
        if( !j4valid[ij4] )
            continue;
        j4 = j4array[ij4]; cj4 = cj4array[ij4]; sj4 = sj4array[ij4];
        
        {
        IKReal j5array[1], cj5array[1], sj5array[1];
        bool j5valid[1]={false};
        j5array[0]=IKatan2(((-1.00000000000000)*(_r01)*(((IKReal)1/(cj4)))), _r11);
        sj5array[0]=IKsin(j5array[0]);
        cj5array[0]=IKcos(j5array[0]);
        if( j5array[0] > IKPI )
            j5array[0]-=IK2PI;
        else if( j5array[0] < -IKPI )
            j5array[0]+=IK2PI;
        j5valid[0] = true;
        { int ij5 = 0;
        if( !j5valid[ij5] )
            continue;
        j5 = j5array[0]; cj5 = cj5array[0]; sj5 = sj5array[0];
        
        {
        IKReal j6array[1], cj6array[1], sj6array[1];
        bool j6valid[1]={false};
        IKReal x26=((IKReal)1/(sj5));
        j6array[0]=IKatan2(((-1.00000000000000)*(_r12)*(x26)), ((_r10)*(x26)));
        sj6array[0]=IKsin(j6array[0]);
        cj6array[0]=IKcos(j6array[0]);
        if( j6array[0] > IKPI )
            j6array[0]-=IK2PI;
        else if( j6array[0] < -IKPI )
            j6array[0]+=IK2PI;
        j6valid[0] = true;
        { int ij6 = 0;
        if( !j6valid[ij6] )
            continue;
        j6 = j6array[0]; cj6 = cj6array[0]; sj6 = sj6array[0];
        
        vsolutions.push_back(IKSolution()); IKSolution& solution = vsolutions.back();
        solution.basesol.resize(7);
        solution.basesol[0].foffset = j0;
        solution.basesol[1].foffset = j1;
        solution.basesol[2].foffset = j2;
        solution.basesol[3].foffset = j3;
        solution.basesol[4].foffset = j4;
        solution.basesol[5].foffset = j5;
        solution.basesol[6].foffset = j6;
        solution.vfree.resize(0);
        }
        }
        }
        }
        }
        }
        }
    }
    }
    }
    }
    }
    }
    return vsolutions.size()>0;
}

#ifndef IKFAST_NO_MAIN
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv)
{
    if( argc != 12+getNumFreeParameters()+1 ) {
        printf("\nUsage: ./ik r00 r01 r02 t0 r10 r11 r12 t1 r20 r21 r22 t2 free0 ...\n\n"
               "Returns the ik solutions given the transformation of the end effector specified by\n"
               "a 3x3 rotation R (rXX), and a 3x1 translation (tX).\n"
               "There are %d free parameters that have to be specified.\n\n",getNumFreeParameters());
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
        fprintf(stderr,"Failed to get ik solution\n");
        return -1;
    }

    printf("Found %d ik solutions:\n", (int)vsolutions.size());
    std::vector<IKReal> sol(getNumJoints());
    for(size_t i = 0; i < vsolutions.size(); ++i) {
        printf("sol%d (free=%d): ", (int)i, (int)vsolutions[i].GetFree().size());
        std::vector<IKReal> vsolfree(vsolutions[i].GetFree().size());
        vsolutions[i].GetSolution(&sol[0],vsolfree.size()>0?&vsolfree[0]:NULL);
        for( size_t j = 0; j < sol.size(); ++j)
            printf("%f, ", (float)sol[j]);
        printf("\n");
    }
    return 0;
}

#endif