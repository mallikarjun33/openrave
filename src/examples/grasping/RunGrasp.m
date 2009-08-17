% data = RunGrasp(robot, grasp, Target, get_clutter, noise, mu, affinedof)
%

% Copyright (C) 2008 Rosen Diankov (rdiankov@cs.cmu.edu), Dmitry Berenson
% This program is free software: you can redistribute it and/or modify
% it under the terms of the GNU General Public License as published by
% the Free Software Foundation, either version 3 of the License, or
% (at your option) any later version.
%
% This program is distributed in the hope that it will be useful,
% but WITHOUT ANY WARRANTY; without even the implied warranty of
% MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
% GNU General Public License for more details.
%
% You should have received a copy of the GNU General Public License
% along with this program.  If not, see <http://www.gnu.org/licenses/>.
function [data,Thand] = RunGrasp(robot, grasp, Target, get_clutter, noise, mu, affinedof)

global probs

data = [];

if( ~exist('affinedof','var') )
    affinedof = 7; % X,Y,Z
end

orBodySetJointValues(robot.id,grasp(robot.grasp.joints));
orRobotSetActiveDOFs(robot.id, robot.handjoints, affinedof);

command_string = ['direction ', sprintf('%f ', grasp(robot.grasp.direction)), ...
                  ' body ' Target.name ' robot ', num2str(robot.id), ' ',];

if( exist('noise','var') && noise )
    command_string =  [command_string, ' noise 0.1 0.005 '];
end
if( exist('get_clutter','var') && get_clutter )
    command_string = [command_string, ' getclutter'];
end

if( exist('mu', 'var') && mu > 0 )
    command_string = [command_string, ' friction ', num2str(mu)];
end

T = orBodyGetTransform(Target.id);
targtrans = transpose(T(10:12,1));

command_string = [command_string, ' roll ' num2str(grasp(robot.grasp.roll))];
command_string = [command_string, ' standoff ' num2str(grasp(robot.grasp.standoff))];
command_string = [command_string, ' centeroffset ' sprintf('%f ', grasp(robot.grasp.center)-targtrans)];
command_string = [command_string, ' palmdir ' sprintf('%f ', robot.palmdir)];
%command_string = [command_string, ' collision pqp ' ];

data = orProblemSendCommand(['exec ', command_string], probs.grasp);
orEnvWait(robot.id);
Thand = reshape(orBodyGetTransform(robot.id),[3 4]);