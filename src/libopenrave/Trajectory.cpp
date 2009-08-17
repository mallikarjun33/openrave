// Copyright (C) 2006-2008 Carnegie Mellon University (rdiankov@cs.cmu.edu)
//
// This file is part of OpenRAVE.
// OpenRAVE is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
/*! --------------------------------------------------------------------
\file   Trajectory.cpp
\brief  Implements a time-parameterized trajectory of robot configurations
-------------------------------------------------------------------- */
#include "libopenrave.h"

namespace OpenRAVE {

//  convenience inline functions for accessing linear blend params
inline dReal& SEG_OFFSET(Trajectory::TSEGMENT& seg, int d)       { return seg.Get(0, d); }
inline dReal  SEG_OFFSET(const Trajectory::TSEGMENT& seg, int d) { return seg.Get(0, d); }

inline dReal& SEG_SLOPE(Trajectory::TSEGMENT& seg, int d)        { return seg.Get(1, d); }
inline dReal  SEG_SLOPE(const Trajectory::TSEGMENT& seg, int d)  { return seg.Get(1, d); }

inline dReal& START_BLEND_TIME(Trajectory::TSEGMENT& seg, int d) { return seg.Get(2, d); }
inline dReal  START_BLEND_TIME(const Trajectory::TSEGMENT& seg, int d)
{ return seg.Get(2, d); }

inline dReal& END_BLEND_TIME(Trajectory::TSEGMENT& seg, int d)   { return seg.Get(3, d); }
inline dReal  END_BLEND_TIME(const Trajectory::TSEGMENT& seg, int d)
{ return seg.Get(3, d); }

inline dReal& START_A(Trajectory::TSEGMENT& seg, int d)          { return seg.Get(4, d); }
inline dReal  START_A(const Trajectory::TSEGMENT& seg, int d)    { return seg.Get(4, d); }

inline dReal& END_A(Trajectory::TSEGMENT& seg, int d)            { return seg.Get(5, d); }
inline dReal  END_A(const Trajectory::TSEGMENT& seg, int d)      { return seg.Get(5, d); }

Trajectory::Trajectory(EnvironmentBase* penv, int nDOF) : InterfaceBase(PT_Trajectory, penv)
{
    //assert( nDOF > 0 );
    _nDOF = nDOF;
    _interpMethod  = LINEAR;
}

void Trajectory::Reset(int nDOF)
{
    Clear();
    _nDOF = nDOF;
}

void Trajectory::Clear()
{
    _vecpoints.resize(0);
    _lowerJointLimit.resize(0);
    _upperJointLimit.resize(0);
    _maxJointVel.resize(0);
    _maxJointAccel.resize(0);
    _vecsegments.resize(0);
}

bool Trajectory::SetFromRawPathData(const dReal* pPathData, int numFrames)
{
    // error checking
    assert(pPathData != NULL );
    
    _vecpoints.resize(numFrames);

    // set all of the trajectory points
    for (int f = 0; f < numFrames; f++) {
        _vecpoints[f].q.resize(_nDOF);
        memcpy(&_vecpoints[f].q[0], pPathData, sizeof(dReal)*_nDOF);
    }

    return true;
}

//! specify the trajectory timing and interpolation method.
//
//  if the 'bAutoCalTiming' flag is set, then the timing of the
//  trajectory is automatically calculated based on the maximum
//  joint velocities and accelerations.
bool Trajectory::CalcTrajTiming(const RobotBase* pRobot, InterpEnum interpolationMethod, bool bAutoCalcTiming, bool bActiveDOFs, dReal fMaxVelMult)
{
    if( _vecpoints.size() == 0 )
        return false;

    if( pRobot == NULL && bAutoCalcTiming ) {
        RAVELOG(L"need to specify a robot if calculating trajectory timings\n");
        return false;
    }

    if( pRobot != NULL ) {

        if( bActiveDOFs ) {
            if( pRobot->GetActiveDOF() != GetDOF() ) {
                RAVELOG(L"trajectory has different degrees of freedom %d != %d\n", pRobot->GetActiveDOF(), GetDOF());
                return false;
            }
            
            pRobot->GetActiveDOFMaxVel(_maxJointVel);
            pRobot->GetActiveDOFMaxAccel(_maxJointAccel);
            pRobot->GetActiveDOFLimits(_lowerJointLimit, _upperJointLimit);
        }
        else {
            pRobot->GetJointMaxVel(_maxJointVel);
            pRobot->GetJointMaxAccel(_maxJointAccel);
            pRobot->GetJointLimits(_lowerJointLimit, _upperJointLimit);
            _maxAffineTranslationVel = pRobot->GetAffineTranslationMaxVels();
            _maxAffineRotationQuatVel = pRobot->GetAffineRotationQuatMaxVels();
        }
    }

    if( fMaxVelMult > 0 ) {// && fMaxVelMult <= 1 ) {
        FOREACH(it, _maxJointVel)
            *it *= fMaxVelMult;
        _maxAffineTranslationVel *= fMaxVelMult;
        _maxAffineRotationQuatVel *= fMaxVelMult;
    }
    else
        RAVELOG_WARNA("bad multipler set: %f, ignoring...\n", (float)fMaxVelMult);

    // set the trajectory timing using the given interpolation method
    bool bSuccess = false;
    switch (interpolationMethod) {
    case LINEAR:
        // linear interpolation 
        bSuccess = _SetLinear(bAutoCalcTiming, bActiveDOFs);
        break;

        //        case LINEAR_BLEND:
        //        // linear with quadratic blends
        //        return _SetLinearBlend(bAutoCalcTiming);
        //
    case CUBIC:
        bSuccess = _SetCubic(bAutoCalcTiming, bActiveDOFs);
        break;
//    case QUINTIC:
//        bSuccess = _SetQuintic(bAutoCalcTiming);
//        break;
    default:
        RAVELOG_ERRORA("Trajectory:: ERROR - bad interpolation method: %d\n", interpolationMethod);
        break;
    }

    if( bSuccess )
        RAVELOG_VERBOSEA("Total Duration = %f\n", GetTotalDuration());
    return bSuccess;
}

//! sample the trajectory at a given time using the current
//   interpolation  method 
bool Trajectory::SampleTrajectory(dReal time, TPOINT &sample) const
{
    if (_vecpoints.size() < 2) {

        if( _vecpoints.size() == 0 ) {
            RAVELOG_ERRORA("Trajectory:: ERROR unable to sample.  numpoints = %"PRIdS"\n", _vecpoints.size());
            return false;
        }

        sample = _vecpoints.front();
        return true;
    }

    if (time <= 0.0) {
        sample = _vecpoints.front();
        return true;
    }
    else if (time >= GetTotalDuration()) {
        //if (time > GetTotalDuration()) RAVELOG(L"Trajectory::WARNING- sample time > duration: %f\n", time);
        sample = _vecpoints.back();
        return true;
    }

    sample.q.resize(_nDOF);

    // set up interpolation
    int index = _FindActiveInterval(time);
    assert (index < (int)_vecpoints.size() - 1);
    const TPOINT& p0 = _vecpoints[index];
    const TPOINT& p1 = _vecpoints[index+1];
    const TSEGMENT& seg = _vecsegments[index];
    assert (p1.time != p0.time);
    assert (seg._fduration > 0.0);

    // sample using the given method
    switch (_interpMethod) {
        case LINEAR:
          // linear interpolation 
          return _SampleLinear(p0, p1, seg, time, sample);

        case LINEAR_BLEND:
          // linear with quadratic blends
          return _SampleLinearBlend(p0, p1, seg, time, sample);
          break;

        case CUBIC:
          // cubic spline interpolation
          return _SampleCubic(p0, p1, seg, time, sample);
          break;

        case QUINTIC:
          // quintic min-jerk interpolation 
          return _SampleQuintic(p0, p1, seg, time, sample);
          break;

        default:
            assert(0);
    }

    return false;
}

//! perform basic error checking on the trajectory via points.
//
//  checks internal data structures and verifies that all trajectory
//  via points do not violate joint position, velocity, and
//  acceleration limits.
bool Trajectory::IsValid() const
{
    RAVELOG(L"Checking validity of trajectory points...\n");
    bool bResult = true;

    // check joint limits, velocity and acceleration bounds
    vector<TPOINT>::const_iterator it;
    FORIT(it, _vecpoints) {
        for (int d = 0; d < _nDOF; d++) {
            if (it->q[d] < _lowerJointLimit[d]) {
                RAVELOG(L"Trajectory: WARNING! dof %d exceeds lower joint limit (%f)! q = %f\n", d, _lowerJointLimit[d], it->q[d]);
                bResult = false;
            }
            if (it->q[d] > _upperJointLimit[d]) {
                RAVELOG(L"Trajectory: WARNING! dof %d exceeds upper joint limit (%f)! q = %f\n", d, _upperJointLimit[d], it->q[d]);
                bResult = false;
            }
            if (fabs(it->qdot[d]) > _maxJointVel[d]) {
                RAVELOG(L"Trajectory: WARNING! dof %d exceeds max joint velocity (%f)! q = %f\n", d, _lowerJointLimit[d], it->qdot[d]);
                bResult = false;
            }
            //        if (fabs(tp.qaccel[d]) > _maxJointAccel[d]) {
            //            RAVELOG(L"Trajectory: WARNING! dof %d exceeds max joint acceleration (%f)! q = %f\n", d, _lowerJointLimit[d], tp.qaccel[d]);
            //            bResult = false;
            //        }
        }
    }

    return bResult;
}

////////////////
//
// PRIVATE METHODS

//! linear interpolation using the maximum joint velocities for timing
bool Trajectory::_SetLinear(bool bAutoCalcTiming, bool bActiveDOFs)
{
    _vecsegments.resize(_vecpoints.size());

    // if needed, preallocate all velocities, accelerations, and coefficients.
    if (bAutoCalcTiming) {    
        FOREACH(itp, _vecpoints) {
            itp->qdot.resize(_nDOF);
            itp->linearvel = Vector();
            itp->angularvel = Vector();
            memset(&itp->qdot[0], 0, _nDOF*sizeof(dReal));
            //memset(&itp->qaccel[0], 0, _nDOF*sizeof(dReal));
        }
    }

    _vecsegments.resize(_vecpoints.size());

    // initialize 
    RAVELOG_VERBOSEA("Setting linear trajectory...\n");

    _vecpoints[0].time = 0.0;
    dReal timeInterval;

    for (int i = 1; i < (int)_vecpoints.size(); i++) {
        if (bAutoCalcTiming) {
            // compute minimum time interval that does not exceed the maximum joint velocities
            timeInterval = _MinimumTimeLinear(_vecpoints[i-1], _vecpoints[i], bActiveDOFs);
            if( timeInterval < 1e-4f )
                timeInterval= 1e-4f;
            _vecpoints[i].time = _vecpoints[i-1].time + timeInterval;
        }
        else {
            // use time stamps from the points
            timeInterval = _vecpoints[i].time - _vecpoints[i-1].time;
            if( timeInterval < 1e-4f )
                timeInterval = 1e-4f;
        }
    }

    // set up default linear interpolation segments
    for (size_t i = 1; i < _vecpoints.size(); i++) {
        _vecsegments[i-1].SetDimensions(1, _nDOF);
        _vecsegments[i-1]._fduration = _vecpoints[i].time - _vecpoints[i-1].time;

        // set all linear coefficients
        for (int d = 0; d < _nDOF; d++) {
            _vecsegments[i-1].Get(0, d) = _vecpoints[i-1].q[d];
            _vecsegments[i-1].Get(1, d) = (_vecpoints[i].q[d]-_vecpoints[i-1].q[d]) / _vecsegments[i-1]._fduration;
        }
    }

    // set the via point velocities if needed
    if (bAutoCalcTiming) {
        // init the start point velocity and accel
        dReal prevSlope, nextSlope;

        _vecpoints[0].linearvel = _vecsegments[0].linearvel;
        _vecpoints[0].angularvel = _vecsegments[0].angularvel;

        // set the via point velocities to zero for slope direction
        // reversals.  Otherwise, use the average of the slopes of
        // the preceding and subsequent trajectory segments.
        assert(_vecpoints.size()>0);
        for (size_t i = 1; i < _vecpoints.size()-1; i++) {
            
            _vecpoints[i].linearvel = (dReal)0.5f*(_vecsegments[i-1].linearvel+_vecsegments[i].linearvel);
            _vecpoints[i].angularvel = (dReal)0.5f*(_vecsegments[i-1].angularvel+_vecsegments[i].angularvel);

            for (int d = 0; d < _nDOF; d++) {
                prevSlope = _vecsegments[i-1].Get(1, d);
                nextSlope = _vecsegments[i].Get(1, d);

                // check for the same slope directions
                if (( prevSlope > 0 && nextSlope > 0 ) ||
                    ( prevSlope < 0 && nextSlope < 0))
                {
                    // use the slope average velocities
                    _vecpoints[i].qdot[d] = (dReal)0.5 * (prevSlope + nextSlope);
                    //cerr << "i: " << i << "  " << prevSlope << "  " << nextSlope
                    //     << " \t" << _vecpoints[i].qdot[d] << endl;
                    //_vecpoints[i].qdot[d] = 0.0;
                }
                else {
                    // otherwise use a zero velocity
                    _vecpoints[i].qdot[d] = 0.0;
                }
            }
        }
    }

    _interpMethod = LINEAR;
    return true;
}

////! linear interpolation with parabolic blends
//bool Trajectory::_SetLinearBlend(bool bAutoCalcTiming)
//{
//    cerr << "Setting linear blend trajectory..." << endl;
//    _totalDuration = 0.0;
//    if (bAutoCalcTiming)
//        _vecpoints[0].time = 0.0;
//    float timeInterval;
//
//    for (int i = 1; i < _vecpoints.size(); i++)
//    {
//        if (bAutoCalcTiming) {
//            // compute minimum time interval that does not exceed the
//            // maximum joint velocities
//            timeInterval = _MinimumTimeLinearBlend(_vecpoints[i-1], _vecpoints[i]);
//            _vecpoints[i].time = _vecpoints[i-1].time + timeInterval;
//        }
//        else {
//            // use time stamps from the points
//            timeInterval = _vecpoints[i].time - _vecpoints[i-1].time;
//        }
//
//        // make sure the timing interval is valid
//        if (timeInterval <= 0.0) {
//            cerr << "Trajectory: ERROR - bad time interval: " << timeInterval
//                << "  Time stamp " << i << " : " << _vecpoints[i].time
//                << endl;
//            return false;
//        }
//    }
//
//    // update the total duration
//    _totalDuration = _vecpoints[_vecpoints.size()-1].time;
//
//    // set up trajectory segments
//    for (int i = 0; i < _vecpoints.size()-1; i++)
//    {
//        _vecsegments[i].degree = 5;
//        _vecsegments[i].duration = _vecpoints[i+1].time - _vecpoints[i].time;
//
//        // determine the position of the current segment
//        TSEGMENT::Type type;
//        TSEGMENT& prevSeg = _vecsegments[i];
//        if (i == 0) {
//            type = TSEGMENT::START;
//        }
//        else if (i == _vecpoints.size()-2){
//            type = TSEGMENT::END;
//            prevSeg = _vecsegments[i-1];
//        }
//        else {
//            type = TSEGMENT::MIDDLE;
//            prevSeg = _vecsegments[i-1];
//        }
//
//        // set linear blend coefficients for continuous velocities at via points
//        _CalculateLinearBlendCoefficients(type, _vecsegments[i], prevSeg,
//            _vecpoints[i], _vecpoints[i+1],
//            _maxJointAccel);
//    }
//
//    _interpMethod = LINEAR_BLEND;
//    cerr << "  Total Duration = " << _totalDuration << endl;
//
//    return true;
//}
//
////! calculate the coefficients of a the parabolic and linear blends
////  with continuous endpoint positions and velocities for via points.
//inline bool Trajectory::_CalculateLinearBlendCoefficients(TSEGMENT::Type segType,
//                                                          TSEGMENT& seg, TSEGMENT& prev,
//                                                          TPOINT& p0, TPOINT& p1,
//                                                          const float blendAccel[])
//{
//    // extract duration and calculate blend times
//    float duration = p1.time - p0.time;
//    assert ( duration > 0.0 );
//    float posDiff, slopeDiff, accel, halfBlendTime;
//
//    // calculate parabolic and linear blend parameters for all DOFs
//    for (int d = 0; d < _numDOF; d++) 
//    {
//        switch (segType) {
//    case TSEGMENT::START:
//        // slope of interior segment
//        posDiff = p1.q[d] - p0.q[d];
//        SEG_SLOPE(seg,d) = posDiff / duration;
//
//        if (posDiff < 0) accel = -blendAccel[d];
//        else             accel = blendAccel[d];
//        START_A(seg,d) = accel;
//        p0.qaccel[d]   = accel;
//
//        halfBlendTime           = 0.1;
//        START_BLEND_TIME(seg,d) = halfBlendTime;
//
//        SEG_OFFSET(seg,d) = p0.q[d] + SEG_SLOPE(seg,d) * START_BLEND_TIME(seg,d);
//        break;
//
//    case TSEGMENT::MIDDLE:
//        // slope of interior segment
//        SEG_SLOPE(seg,d) = (p1.q[d] - p0.q[d]) / duration;
//
//        slopeDiff = SEG_SLOPE(seg,d) - SEG_SLOPE(prev,d);
//        if (slopeDiff < 0) accel = -blendAccel[d];
//        else               accel = blendAccel[d];
//        START_A(seg,d) = accel;
//        END_A(prev,d)  = accel;
//        p0.qaccel[d]   = accel;
//
//        halfBlendTime           = (slopeDiff / accel) * 0.5;
//        START_BLEND_TIME(seg,d) = halfBlendTime;
//        END_BLEND_TIME(prev,d)  = prev.duration - halfBlendTime;
//
//        SEG_OFFSET(seg,d) = p0.q[d] + SEG_SLOPE(seg,d) * START_BLEND_TIME(seg,d);
//        break;
//
//    case TSEGMENT::END:
//        // slope of interior segment
//        SEG_SLOPE(seg,d) = (p1.q[d] - p0.q[d]) / duration;
//
//        slopeDiff = SEG_SLOPE(seg,d) - SEG_SLOPE(prev,d);
//        if (slopeDiff < 0) accel = -blendAccel[d];
//        else               accel = blendAccel[d];
//        START_A(seg,d) = accel;
//        END_A(prev,d)  = accel;
//        p0.qaccel[d]   = accel;
//
//        halfBlendTime           = (slopeDiff / accel) * 0.5;
//        START_BLEND_TIME(seg,d) = halfBlendTime;
//        END_BLEND_TIME(prev,d)  = prev.duration - halfBlendTime;
//
//        SEG_OFFSET(seg,d) = p0.q[d] + SEG_SLOPE(seg,d) * START_BLEND_TIME(seg,d);
//        break;
//
//    default:
//        cerr << "Trajectory: ERROR - unknown segment type: " << segType << endl;
//        return false;
//        }
//
//    }
//
//
//    return true;
//}
//

/// cubic spline interpolation
bool Trajectory::_SetCubic(bool bAutoCalcTiming, bool bActiveDOFs)
{
    RAVELOG_VERBOSEA("Setting cubic trajectory...\n");
    if (bAutoCalcTiming) {
        _vecpoints[0].time = 0.0;
        FOREACH(itp, _vecpoints) {
            itp->qdot.resize(_nDOF);
            itp->linearvel = Vector();
            itp->angularvel = Vector();
            memset(&itp->qdot[0], 0, _nDOF*sizeof(dReal));
            //memset(&itp->qaccel[0], 0, _nDOF*sizeof(dReal));
        }
    }
                
    dReal timeInterval;
    for (size_t i = 1; i < _vecpoints.size(); i++) {
        if (bAutoCalcTiming) {
            // compute minimum time interval that does not exceed the
            // maximum joint velocities
            timeInterval = _MinimumTimeCubic(_vecpoints[i-1], _vecpoints[i], bActiveDOFs);
            if( timeInterval < 1e-4f )
                timeInterval= 1e-4f;
            _vecpoints[i].time = _vecpoints[i-1].time + timeInterval;
        }
        else {
            // use time stamps from the points
            timeInterval = _vecpoints[i].time - _vecpoints[i-1].time;
            if( timeInterval < 1e-4f )
                timeInterval = 1e-4f;
        }

        _vecsegments[i-1].SetDimensions(3, _nDOF);
        _vecsegments[i-1]._fduration = timeInterval;
    }

    // recalculate via point velocities and accelerations
    _RecalculateViaPointDerivatives();

    // set all cubic coefficients for continuous velocities at via points
    for (size_t i = 1; i < _vecpoints.size(); i++)
        _CalculateCubicCoefficients(_vecsegments[i-1], _vecpoints[i-1], _vecpoints[i]);
    
    _interpMethod = CUBIC;
    return true;
}

/// calculate the coefficients of a smooth cubic spline with
///  continuous endpoint positions and velocities for via points.
void Trajectory::_CalculateCubicCoefficients(Trajectory::TSEGMENT& seg, const TPOINT& tp0, const TPOINT& tp1)
{
    dReal t = tp1.time - tp0.time; // extract duration
    assert ( t > 0.0 );
    dReal t_2 = t*t;
    dReal t_3 = t * t_2;

    // calculate smooth interpolating cubic for all DOFs
    for (int d = 0; d < _nDOF; d++) {
        seg.Get(0,d) = tp0.q[d];
        seg.Get(1,d) = tp0.qdot[d];
        dReal qdiff = tp1.q[d] - tp0.q[d];
        seg.Get(2,d) = (3.0/t_2)*qdiff - (2.0/t)*tp0.qdot[d] - (1.0/t)*tp1.qdot[d];
        seg.Get(3,d) = (-2.0/t_3)*qdiff + (1.0/t_2)*(tp1.qdot[d] + tp0.qdot[d]);
    }
}

////! smooth quintic spline interpolation with minimum jerk criteria
//bool Trajectory::_SetQuintic(bool bAutoCalcTiming)
//{
//    cerr << "Setting minimum-jerk quintic trajectory..." << endl;
//    _totalDuration = 0.0;
//    if (bAutoCalcTiming)
//        _vecpoints[0].time = 0.0;
//    float timeInterval;
//
//    // the points
//    for (int i = 1; i < _vecpoints.size(); i++)
//    {
//        timeInterval = 0.0;
//        if (bAutoCalcTiming) {
//            // compute minimum time interval that does not exceed the
//            // maximum joint velocities
//            timeInterval = _MinimumTimeQuintic(_vecpoints[i-1], _vecpoints[i]);
//            _totalDuration += timeInterval;
//            _vecpoints[i].time = _totalDuration;
//        }
//        else {
//            // use time stamps from the points
//            timeInterval = _vecpoints[i].time - _vecpoints[i-1].time;
//            _totalDuration += timeInterval;
//        }
//
//        // make sure the timing interval is valid
//        if (timeInterval <= 0.0) {
//            cerr << "Trajectory: ERROR - bad time interval: " << timeInterval
//                << "  Time stamp " << i << " : " << _vecpoints[i].time
//                << endl;
//            return false;
//        }
//
//        // set the segments
//        _vecsegments[i-1].duration = timeInterval;
//        _vecsegments[i-1].degree = 5;
//    }
//
//    // recalculate via point velocities and accelerations
//    if (!_RecalculateViaPointDerivatives()) {
//        cerr << "Trajectory: ERROR calculating quintic accelerations" << endl;
//        return false;
//    }
//
//    // calculate all quintic equations
//    for (int i = 1; i < _vecpoints.size(); i++) {
//        // set all cubic coefficients for continuous velocities at via points
//        if (!_CalculateQuinticCoefficients(_vecsegments[i-1].a, _vecpoints[i-1],
//            _vecpoints[i]))
//            cerr << "Trajectory: ERROR calculating quintic coefficients" << endl;
//    }
//
//
//    _interpMethod = QUINTIC;
//    cerr << "  Total Duration = " << _totalDuration << endl;
//
//    return true;
//}

//! recalculate all via point velocities and accelerations
void Trajectory::_RecalculateViaPointDerivatives()
{
    float prevSlope, nextSlope;
    float prevDur, nextDur;

    // set the via point accelerations to max at direction reversals
    for (int i = 1; i < (int)_vecpoints.size()-1; i++) {
        prevDur = _vecsegments[i-1]._fduration;
        nextDur = _vecsegments[i]._fduration;

        for (int d = 0; d < _nDOF; d++)
        {
            prevSlope = (_vecpoints[i].q[d] - _vecpoints[i-1].q[d]) / prevDur;
            nextSlope = (_vecpoints[i+1].q[d] - _vecpoints[i].q[d]) / nextDur;

            // check the slope directions at via points
            if (prevSlope < 0) {
                if (nextSlope > 0) {
                    _vecpoints[i].qdot[d] = 0.0;
                    //_vecpoints[i].qaccel[d] = _maxJointAccel[d];
                }
                else {
                    _vecpoints[i].qdot[d] = 0.5 * (prevSlope + nextSlope);
                    //_vecpoints[i].qaccel[d] = 0.0;
                }
            }
            else {
                if (nextSlope > 0) {
                    _vecpoints[i].qdot[d] = 0.5 * (prevSlope + nextSlope);
                    //_vecpoints[i].qaccel[d] = 0.0;
                }
                else {
                    _vecpoints[i].qdot[d] = 0.0;
                    //_vecpoints[i].qaccel[d] = -_maxJointAccel[d];
                }
            }
        }
    }
}

////! calculate the coefficients of a smooth quintic spline with
////  continuous endpoint positions and velocities for via points
////  using minimum jerk heuristics
//inline bool Trajectory::_CalculateQuinticCoefficients(JointConfig a[],
//                                                      TPOINT& tp0,
//                                                      TPOINT& tp1)
//{
//    // extract duration
//    float t = tp1.time - tp0.time;
//    assert ( t > 0.0 );
//    float t_2 = SQR(t);
//    float t_3 = t * t_2;
//    float t_4 = t * t_3;
//    float t_5 = t * t_4;
//    float qdiff;
//
//    // calculate smooth interpolating quintic for all DOFs
//    for (int d = 0; d < _numDOF; d++) 
//    {
//        a[0][d] = tp0.q[d];
//
//        a[1][d] = tp0.qdot[d];
//
//        a[2][d] = 0.5 * tp0.qaccel[d];
//
//        qdiff = tp1.q[d] - tp0.q[d];
//
//        //a[2][d] = 0.5 * tp0.qaccel[d];
//
//        a[3][d] = 20 * qdiff  -  ( 8 * tp1.qdot[d] + 12 * tp0.qdot[d] ) * t 
//            - ( 3 * tp0.qaccel[d] - tp1.qaccel[d] ) * t_2;
//        a[3][d] /=  2 * t_3;
//
//
//        a[4][d] = -30 * qdiff  +  ( 14 * tp1.qdot[d] + 16 * tp0.qdot[d] ) * t 
//            + ( 3 * tp0.qaccel[d] - 2 * tp1.qaccel[d] ) * t_2;
//        a[4][d] /=  2 * t_4;
//
//
//        a[5][d] = 12 * qdiff  -  ( 6 * tp1.qdot[d] + 6 * tp0.qdot[d] ) * t 
//            - ( tp0.qaccel[d] - tp1.qaccel[d] ) * t_2;
//        a[5][d] /=  2 * t_5;
//    }
//
//    return true;
//}

/// computes minimum time interval for linear interpolation between
///  path points that does not exceed the maximum joint velocities 
inline dReal Trajectory::_MinimumTimeLinear(const TPOINT& tp0, const TPOINT& tp1, bool bActiveDOFs)
{
    dReal minJointTime;
    dReal minPathTime = 0.0;

    // compute minimum time interval that does not exceed the
    // maximum joint velocities
    for (int d = 0; d < _nDOF; d++) {
        if(_maxJointVel[d] > 0.0) {
            minJointTime = fabs(tp1.q[d] - tp0.q[d]) / _maxJointVel[d];
            if (minPathTime < minJointTime)
                minPathTime = minJointTime;
        }
    }

    if( !bActiveDOFs )
        minPathTime = max(_MinimumTimeTransform(tp0.trans, tp1.trans),minPathTime);

#ifndef _WIN32
    assert( !isnan(minPathTime));
#endif

    return minPathTime;
}

/// computes minimum time interval for cubic interpolation between
///  path points that does not exceed the maximum joint velocities 
///  or accelerations
dReal Trajectory::_MinimumTimeCubic(const TPOINT& tp0, const TPOINT& tp1, bool bActiveDOFs)
{
    dReal minJointTime, jointDiff;
    dReal velocityConstraint, accelConstraint;
    dReal minPathTime = 0.0;

    // compute minimum time interval that does not exceed the
    // maximum joint velocities or accelerations
    for (int d = 0; d < _nDOF; d++) {
        if(_maxJointVel[d] > 0.0 && _maxJointAccel[d] > 0 ) {
            jointDiff = fabs(tp1.q[d] - tp0.q[d]);
            velocityConstraint = ((dReal)1.5/_maxJointVel[d]) * jointDiff;
            accelConstraint = RaveSqrt((6.0/_maxJointAccel[d]) * jointDiff);

            minJointTime = max( velocityConstraint, accelConstraint );

            if (minPathTime < minJointTime)
                minPathTime = minJointTime;
        }
    }

    if( !bActiveDOFs )
        minPathTime = max(_MinimumTimeTransform(tp0.trans, tp1.trans),minPathTime);

#ifndef _WIN32
    assert( !isnan(minPathTime));
#endif

    return minPathTime;
}

/// computes minimum time interval for cubic interpolation between
///  path points that does not exceed the maximum joint velocities 
///  or accelerations assuming zero velocities at endpoints
dReal Trajectory::_MinimumTimeCubicZero(const TPOINT& tp0, const TPOINT& tp1, bool bActiveDOFs)
{
    dReal minJointTime, jointDiff;
    dReal velocityConstraint, accelConstraint;
    dReal minPathTime = 0.0;

    // compute minimum time interval that does not exceed the
    // maximum joint velocities or accelerations
    for (int d = 0; d < _nDOF; d++) {
        if(_maxJointVel[d] > 0.0 && _maxJointAccel[d] > 0 ) {
            jointDiff          = fabs(tp1.q[d] - tp0.q[d]);
            velocityConstraint = ((dReal)1.5/_maxJointVel[d]) * jointDiff;
            accelConstraint    = RaveSqrt((6.0/_maxJointAccel[d]) * jointDiff);

            minJointTime = max( velocityConstraint, accelConstraint );

            if (minPathTime < minJointTime)
                minPathTime = minJointTime;
        }
    }
    
    if( !bActiveDOFs )
        minPathTime = max(_MinimumTimeTransform(tp0.trans, tp1.trans),minPathTime);
#ifndef _WIN32
    assert( !isnan(minPathTime));
#endif
    return minPathTime;
}

/// computes minimum time interval for quintic interpolation between
///  path points that does not exceed the maximum joint velocities 
///  or accelerations
dReal Trajectory::_MinimumTimeQuintic(const TPOINT& tp0, const TPOINT& tp1, bool bActiveDOFs)
{
    RAVELOG_ERRORA("Trajectory: ERROR - inaccurate minimum time quintic calculation used.\n");

    dReal minJointTime, jointDiff;
    dReal velocityConstraint, accelConstraint;
    dReal minPathTime = 0.0;

    // compute minimum time interval that does not exceed the
    // maximum joint velocities or accelerations
    for (int d = 0; d < _nDOF; d++)
    {
        if(_maxJointVel[d] > 0.0 && _maxJointAccel[d] > 0.0) {
            jointDiff          = fabs(tp1.q[d] - tp0.q[d]);
            velocityConstraint = ((dReal)1.5/_maxJointVel[d]) * jointDiff;
            accelConstraint    = RaveSqrt((6.0/_maxJointAccel[d]) * jointDiff);

            minJointTime = max( velocityConstraint, accelConstraint );

            if (minPathTime < minJointTime)
                minPathTime = minJointTime;
        }
    }

    if( !bActiveDOFs )
        minPathTime = max(_MinimumTimeTransform(tp0.trans, tp1.trans),minPathTime);
#ifndef _WIN32
    assert( !isnan(minPathTime));
#endif

    return minPathTime;
}

dReal Trajectory::_MinimumTimeTransform(const Transform& t0, const Transform& t1)
{
    //calc time for translation
    dReal x_time = fabs(t1.trans.x - t0.trans.x) / _maxAffineTranslationVel.x;
    dReal y_time = fabs(t1.trans.y - t0.trans.y) / _maxAffineTranslationVel.y;
    dReal z_time = fabs(t1.trans.z - t0.trans.z) / _maxAffineTranslationVel.z;
    dReal rot_dist = sqrtf(min(lengthsqr4(t1.rot-t0.rot), lengthsqr4(t1.rot+t0.rot)))/_maxAffineRotationQuatVel.x;
    return max(max(max(x_time,y_time),z_time),rot_dist);
}

/// find the active trajectory interval covering the given time
///  (returns the index of the start point of the interval)
int Trajectory::_FindActiveInterval(dReal time) const
{
    int index = 0;

    // for now, just do a simple linear search
    while (time > _vecpoints[index+1].time)
        index++;
    assert (index < (int)_vecpoints.size() - 1);

    return index;
}

/// sample the trajectory using linear interpolation.
inline bool Trajectory::_SampleLinear(const TPOINT& p0, const TPOINT& p1,
                                      const TSEGMENT& seg, dReal time,
                                      TPOINT& sample) const
{
    assert (time >= p0.time && time <= p1.time);
    assert (seg._fduration > 0.0);
    assert (fabs((p1.time - p0.time) - seg._fduration) < 1e-4);
    dReal  t = time - p0.time;

    sample.q.resize(_nDOF);
    sample.qdot.resize(_nDOF);
    //sample.qaccel.resize(_nDOF);

    // perform the interpolation
    for (int d = 0; d < _nDOF; d++) {
        sample.q[d]      = seg.Get(0, d) + t * seg.Get(1, d);
        sample.qdot[d]   = seg.Get(1, d);
        //sample.qaccel[d] = 0.0;
    }
    //NEED TO do t/(seg._fduration-step)
    sample.time = time;
    sample.trans.trans = p0.trans.trans + (t/(seg._fduration))*(p1.trans.trans - p0.trans.trans);
    sample.trans.rot = dQSlerp(p0.trans.rot, p1.trans.rot,(t/(seg._fduration)));
    
    return true;
}

/// sample using linear interpolation with parabolic blends.
inline bool Trajectory::_SampleLinearBlend(const TPOINT& p0, const TPOINT& p1,
                                           const TSEGMENT& seg, dReal time,
                                           TPOINT& sample) const
{
    assert (time >= p0.time && time <= p1.time);
    assert (seg._fduration > 0.0);
    //assert (fabs((p1.time - p0.time) - seg.duration) < VERY_SMALL);
    dReal  t = time - p0.time;

    for (int d = 0; d < _nDOF; d++) {
        if (t < START_BLEND_TIME(seg, d) ) {
            // sample in starting parabolic blend region
            sample.q[d]      = p0.q[d]; //+ 0.5 * START_A(seg,d) * SQR(t);
            sample.qdot[d]   = START_A(seg,d) * t;
            //sample.qaccel[d] = START_A(seg,d);
        }
        else if (t > END_BLEND_TIME(seg, d)) {
            // sample in ending parabolic blend region
            t = t - END_BLEND_TIME(seg, d);
            sample.q[d]      = SEG_OFFSET(seg,d) + t * SEG_SLOPE(seg,d);
            sample.qdot[d]   = SEG_SLOPE(seg,d);
            //sample.qaccel[d] = 0.0;
        }
        else {
            // perform linear interpolation in the middle section
            t = t - START_BLEND_TIME(seg, d);
            sample.q[d]      = p1.q[d]; //+ 0.5 * END_A(seg,d) * SQR(t);
            sample.qdot[d]   = END_A(seg,d) * t;
            //sample.qaccel[d] = END_A(seg,d);
        }
    }

    sample.time = time;
    sample.trans.trans = p0.trans.trans + (t/(seg._fduration))*(p1.trans.trans - p0.trans.trans);
    sample.trans.rot = dQSlerp(p0.trans.rot, p1.trans.rot,(t/(seg._fduration)));

    return true;
}

/// sample the trajectory using cubic interpolation.
inline bool Trajectory::_SampleCubic(const TPOINT& p0, const TPOINT& p1,
                                     const TSEGMENT& seg, dReal time,
                                     TPOINT& sample) const
{
    assert (time >= p0.time && time <= p1.time);
    assert (seg._fduration > 0.0);
    assert (fabs((p1.time - p0.time) - seg._fduration) < 1e-4);
    dReal t = time - p0.time;
    dReal t_2 = t*t;
    dReal t_3 = t * t_2;

    // perform the interpolation
    for (int d = 0; d < _nDOF; d++)
    {
        sample.q[d]      = seg.Get(0, d) + t * seg.Get(1, d)
        + t_2 * seg.Get(2, d) + t_3 * seg.Get(3, d);

        sample.qdot[d]   = seg.Get(1, d) + ((dReal)2.0 * t * seg.Get(2, d))
            + ((dReal)3.0 * t_2 * seg.Get(3, d));

//        sample.qaccel[d] = 2.0 * seg.Get(2, d) + (6.0 * t * seg.Get(3, d));
    }
    sample.time = time;
    sample.trans.trans = p0.trans.trans + (t/(seg._fduration))*(p1.trans.trans - p0.trans.trans);
    sample.trans.rot = dQSlerp(p0.trans.rot, p1.trans.rot,(t/(seg._fduration)));

    return true;
}

//! sample the trajectory using quintic interpolation with minimum jerk.
inline bool Trajectory::_SampleQuintic(const TPOINT& p0, const TPOINT& p1,
                                       const TSEGMENT& seg, dReal time,
                                       TPOINT& sample) const
{
    assert (time >= p0.time && time <= p1.time);
    assert (seg._fduration > 0.0);
    assert (fabs((p1.time - p0.time) - seg._fduration) < 1e-4);
    dReal t   = time - p0.time;
    dReal t_2 = t*t;
    dReal t_3 = t * t_2;
    dReal t_4 = t * t_3;
    dReal t_5 = t * t_4;

    // perform the interpolation
    for (int d = 0; d < _nDOF; d++)
    {
        sample.q[d]    = seg.Get(0, d)  +  t * seg.Get(1, d)
        + t_2 * seg.Get(2, d)  +  t_3 * seg.Get(3, d) 
        + t_4 * seg.Get(4, d)  +  t_5 * seg.Get(5, d);

        sample.qdot[d] = seg.Get(1, d)  +  (2 * t * seg.Get(2, d))
            + (3 * t_2 * seg.Get(3, d))  +  (4 * t_3 * seg.Get(4, d)) 
            + (5 * t_4 * seg.Get(5, d));

//        sample.qaccel[d] = (2 * seg.Get(2, d))  +  (6 * t * seg.Get(3, d))
//            + (12 * t_2 * seg.Get(4, d))  +  (20 * t_3 * seg.Get(5, d));
    }
    sample.time = time;
    sample.trans.trans = p0.trans.trans + (t/(seg._fduration))*(p1.trans.trans - p0.trans.trans);
    sample.trans.rot = dQSlerp(p0.trans.rot, p1.trans.rot,(t/(seg._fduration)));

    return true;
}

bool Trajectory::Write(const char* filename, int options) const
{
    assert(filename != NULL);

    ofstream of(filename);
    if( !of ) {
        RAVELOG(L"failed to write to file %s\n", filename);
        return false;
    }

    return Write(of, options);
}

bool Trajectory::Write(FILE* f, int options) const
{
    if( f == NULL ) {
        RAVELOG(L"invalid file handle\n");
        return false;
    }

    stringstream ss;
    if( !Write(ss, options) )
        return false;

    return fwrite(ss.str().c_str(), ss.str().size(), 1, f) != 0;
}

bool Trajectory::Write(std::ostream& f, int options) const
{
    if( !(options&TO_NoHeader) ) {
        if( !(options&TO_OneLine) )
            f << endl;
        else
            f << " ";
        f << _vecpoints.size() << " " << _nDOF << " " << options;
        if( !(options&TO_OneLine) )
            f << endl;
        else
            f << " ";
    }
    
    FOREACHC(it, _vecpoints) {
        if( options & TO_IncludeTimestamps )
            f << it->time << " ";
        FOREACHC(itval, it->q)
            f << *itval << " ";

        if( options & TO_IncludeBaseTransformation )
            f << it->trans << " ";

        if( options & TO_IncludeVelocities ) {
            FOREACHC(itvel, it->qdot)
                f << *itvel << " ";

            if( options & TO_IncludeBaseTransformation )
                f << it->linearvel.x << " " << it->linearvel.y << " " << it->linearvel.z << " "
                  << it->angularvel.x << " " << it->angularvel.y << " " << it->angularvel.z << " ";
        }

        if( !(options&TO_OneLine) )
            f << endl;
        else
            f << " ";
    }

    return !!f;
}

bool Trajectory::Read(const char* filename, RobotBase* robot)
{
    if(filename == NULL)
        return false;

    ifstream fi(filename);
    if( !fi ) {
        RAVELOG(L"failed to read file %s\n", filename);
        return false;
    }

    return Read(fi, robot);
}

bool Trajectory::Read(std::istream& f, RobotBase* robot)
{
    int size, dof, options;
    f >> size >> dof >> options;

    if( dof < 0 )
        return false;

    Reset(dof);
    Transform tbody;
    if( robot != NULL )
        tbody = robot->GetTransform();

    _vecpoints.resize(size);
    FOREACH(it, _vecpoints) {
        it->q.resize(dof);
        it->qdot.resize(dof);

        if( options & TO_IncludeTimestamps )
            f >> it->time;

        FOREACH(itval, it->q)
            f >> *itval;

        if( options & TO_IncludeBaseTransformation )
            f >> it->trans;
        else
            it->trans = tbody;

        if( options & TO_IncludeVelocities ) {
            FOREACH(itvel, it->qdot)
                f >> *itvel;

            if( options & TO_IncludeBaseTransformation )
                f >> it->linearvel.x >> it->linearvel.y >> it->linearvel.z
                  >> it->angularvel.x >> it->angularvel.y >> it->angularvel.z;
        }
    }

    CalcTrajTiming(robot, LINEAR, false, false);

    return true;
}

} // end namespace OpenRAVE