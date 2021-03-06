'''
Created on Oct 6, 2014

@author: rch
'''

from traits.api import \
    Property, Array, Instance

from oricreate.crease_pattern import \
    CreasePattern
from oricreate.forming_tasks import \
    IFormingTask


class ISimulationTask(IFormingTask):

    '''Interface for FormingTask process
    simulation step within the origami design process.
    '''

    u_0 = Property(Array)
    '''Method required by subsequent FormingTask steps
    '''

    u_1 = Property(Array)
    '''Method required by subsequent FormingTask steps
    '''

    cp = Instance(CreasePattern)
    '''Crease pattern.
    '''

    u_t = Property(Array)
    '''Method required for visualization.
    '''
