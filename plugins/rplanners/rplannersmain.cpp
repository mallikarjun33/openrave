// Copyright (C) 2006-2008 Rosen Diankov (rdiankov@cs.cmu.edu)
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
#include "plugindefs.h"

#include "randomized-astar.h"
#include "rbirrt.h"

// declaring variables with stdcall can be a little complex
#ifdef _MSC_VER

#define PROT_STDCALL(name, paramlist) __stdcall name paramlist
#define DECL_STDCALL(name, paramlist) __stdcall name paramlist

#else

#ifdef __x86_64__
#define DECL_STDCALL(name, paramlist) name paramlist
#else
#define DECL_STDCALL(name, paramlist) __attribute__((stdcall)) name paramlist
#endif

#endif // _MSC_VER

// need c linkage
extern "C" {

// for some reason windows complains when the prototypes are different
InterfaceBase* DECL_STDCALL(ORCreate, (PluginType type, wchar_t* name, EnvironmentBase* penv))
{
    switch(type) {
        case PT_Planner:
            if( wcsicmp(name, L"RA*") == 0 )
                return new RandomizedAStarPlanner(penv);
            else if( wcsicmp(name, L"rBiRRT") == 0 )
                return new BirrtPlanner(penv);

            break;
        default:
            break;
    }

    return NULL;
}

bool DECL_STDCALL(GetPluginAttributes, (PLUGININFO* pinfo, int size))
{
    if( pinfo == NULL ) return false;
    if( size != sizeof(PLUGININFO) ) {
        RAVELOG_ERRORA("bad plugin info sizes %d != %d\n", size, sizeof(PLUGININFO));
        return false;
    }

    pinfo->planners.push_back(L"RA*");
    pinfo->planners.push_back(L"rBiRRT");
    return true;
}

void DECL_STDCALL(DestroyPlugin, ())
{
}

}