'''
Created on Jan 20, 2016

@author: rch
'''

from traits.api import \
    Float, HasTraits, Property, cached_property, Int, \
    Instance

import numpy as np
from oricreate.api import MappingTask
from oricreate.api import YoshimuraCPFactory, \
    fix, link, r_, s_, t_, MapToSurface,\
    GuConstantLength, GuDofConstraints, SimulationConfig, SimulationTask, \
    FTV, FTA
from oricreate.crease_pattern.crease_pattern_state import CreasePatternState
from oricreate.forming_tasks.forming_task import FormingTask
from oricreate.mapping_tasks.mask_task import MaskTask
import sympy as sp


a_, b_ = sp.symbols('a,b')


def get_fr(var_, L, H):
    fx = a_ * (var_ / L)**2 + b_ * (var_ / L)
    eqns = [fx.subs(var_, L), fx.subs(var_, L / 2) - H]
    ab_subs = sp.solve(eqns, [a_, b_])
    fx = fx.subs(ab_subs)
    return fx


class AddBoundaryTask(MappingTask):
    '''Boundary facet to stiffen the shell
    '''

    def _add_boundary_facet(self, N1, N2, dir_=-1, delta=0.1, N_start_idx=0):
        cp = self.previous_task.formed_object
        x1, x2 = cp.x_0[N1, :], cp.x_0[N2, :]
        dx = x1[:, 0] - x2[:, 0]
        dy = x1[:, 1] - x2[:, 1]
        dz = np.zeros_like(dy)
        # direction vector
        dirvec = np.c_[dx, dy, dz]

        x4 = x2[:, :]
        x4[:, 1] += dir_ * delta
        x3 = np.copy(x4)
        x3[:, :] += dirvec * 0.8

        x_add = np.array([x3[0],
                          x4[0],
                          x3[1]])
        N = N_start_idx + np.arange(len(x_add))

        L_add = np.array([[N1[0], N[0]],
                          [N2[0], N[0]],
                          [N[0], N[1]],
                          [N2[0], N[1]],
                          [N1[1], N[2]],
                          [N2[1], N[2]]
                          ])

        F_add = np.array([[N1[0], N[0], N2[0]],
                          [N[0], N[1], N2[0]],
                          [N1[1], N[2], N2[1]]])

        return x_add, L_add, F_add

    def _get_formed_object(self):
        '''attach additional facets at the boundary
        '''
        cp = self.previous_task.formed_object
        x_0, L, F = cp.x_0, cp.L, cp.F
        n_N = len(x_0)
        n_N_add = 3
        x_br, L_br, F_br = self._add_boundary_facet(
            [8, 37, 15, 43], [37, 15, 43, 20], -1, 0.1, n_N)
        x_bl, L_bl, F_bl = self._add_boundary_facet(
            [8, 31, 3, 27], [31, 3, 27, 0], -1, 0.1, n_N + n_N_add)
        x_tr, L_tr, F_tr = self._add_boundary_facet(
            [14, 42, 19, 46], [42, 19, 46, 22], 1, 0.1, n_N + 2 * n_N_add)
        x_tl, L_tl, F_tl = self._add_boundary_facet(
            [14, 36, 7, 30], [36, 7, 30, 2], 1, 0.1, n_N + 3 * n_N_add)
        x_0 = np.vstack([x_0, x_br, x_bl, x_tr, x_tl])
        L = np.vstack([L, L_br, L_bl, L_tr, L_tl])
        F = np.vstack([F, F_br, F_bl, F_tr, F_tl])
        return CreasePatternState(x_0=x_0,
                                  L=L,
                                  F=F)


class DoublyCurvedYoshiFormingProcess(HasTraits):
    '''
    Define the simulation task prescribing the boundary conditions, 
    target surfaces and configuration of the algorithm itself.
    '''

    L_x = Float(3.0, auto_set=False, enter_set=True, input=True)
    L_y = Float(2.2, auto_set=False, enter_set=True, input=True)
    u_x = Float(0.1, auto_set=False, enter_set=True, input=True)
    n_steps = Int(30, auto_set=False, enter_set=True, input=True)

    ctf = Property(depends_on='+input')
    '''control target surface'''
    @cached_property
    def _get_ctf(self):
        return [r_, s_, - 0.2 * t_ * r_ * (1 - r_ / self.L_x) - 0.000015]

    factory_task = Property(Instance(FormingTask))
    '''Factory task generating the crease pattern.
    '''
    @cached_property
    def _get_factory_task(self):
        return YoshimuraCPFactory(L_x=self.L_x, L_y=self.L_y,
                                  n_x=4, n_y=12)

    mask_task = Property(Instance(MaskTask))
    '''Configure the simulation task.
    '''
    @cached_property
    def _get_mask_task(self):
        return MaskTask(previous_task=self.factory_task,
                        F_mask=[0, 6, 12, 18, 12, 24, 36, 48,
                                96, 78, 90, 102, 54, 42,
                                72, 1, 12, 43, 49, 97, 103, 19,
                                59, 65, 71, 77, 101, 83, 96, 107,
                                47, 29, 41, 53,
                                5, 23, 95,
                                58, 76,
                                100, 106,
                                46, 52],
                        L_mask=[0, 7, 14, 21, 148, 160, 172, 154, 1, 22, 149, 155,
                                152, 158, 5, 26, 153, 165, 177, 159, 6, 13, 20, 27,
                                28, 40, 29, 41, 32, 44, 33, 45, 34, 46, 35, 47, 38, 50, 39, 51,
                                58, 52, 76, 53, 57, 81, 70, 94, 98, 75, 99, 93,
                                124, 100, 128, 129, 105, 135, 112, 142, 118, 119,
                                147, 123],
                        N_mask=[0, 7, 21, 28, 35, 47, 65, 41, 1, 29, 36, 42, 39,
                                45, 5, 33, 40, 52, 70, 46, 6, 13, 27, 34])

    add_boundary_task = Property(Instance(FormingTask))
    '''Initialization to render the desired folding branch. 
    '''
    @cached_property
    def _get_add_boundary_task(self):
        return AddBoundaryTask(previous_task=self.mask_task)

    init_displ_task = Property(Instance(FormingTask))
    '''Initialization to render the desired folding branch. 
    '''
    @cached_property
    def _get_init_displ_task(self):
        cp = self.mask_task.formed_object
        return MapToSurface(previous_task=self.add_boundary_task,
                            target_faces=[(self.ctf, cp.N)])

    fold_task = Property(Instance(FormingTask))
    '''Configure the simulation task.
    '''
    @cached_property
    def _get_fold_task(self):
        x_1 = self.init_displ_task.x_1
#        cp = self.init_displ_task.formed_object

#        print 'nodes', x_1[(0, 1, 2, 20, 21, 22), 2]

#        cp.u[(26, 25, 24, 23), 2] = -0.01
#        cp.x[(0, 1, 2, 20, 21, 22), 2] = 0.0
        u_max = self.u_x
        fixed_nodes_z = fix(
            [0, 1, 2, 20, 21, 22], (2))
#         fixed_nodes_x = fix(
#             [8, 9, 10, 11, 12, 13, 14], (0))
        fixed_nodes_y = fix(
            [1, 21], (1))  # 5, 11, 17,
        control_left = fix(
            [0, 1, 2], (0),
            lambda t: t * u_max)
        control_right = fix(
            [20, 21, 22], (0),
            lambda t: -t * u_max)

        dof_constraints = fixed_nodes_z + fixed_nodes_y + \
            control_left + control_right
        gu_dof_constraints = GuDofConstraints(dof_constraints=dof_constraints)
        gu_constant_length = GuConstantLength()
        sim_config = SimulationConfig(goal_function_type='potential_energy',
                                      gu={'cl': gu_constant_length,
                                          'dofs': gu_dof_constraints},
                                      acc=1e-5, MAX_ITER=500,
                                      debug_level=0)
        return SimulationTask(previous_task=self.init_displ_task,
                              config=sim_config, n_steps=self.n_steps)


class DoublyCurvedYoshiFormingProcessFTV(FTV):

    model = Instance(DoublyCurvedYoshiFormingProcess)


if __name__ == '__main__':
    bsf_process = DoublyCurvedYoshiFormingProcess(L_x=3.0, L_y=2.41, n_x=4,
                                                  n_y=12, u_x=0.1, n_steps=4)

    fa = bsf_process.factory_task
    mt = bsf_process.mask_task
    ab = bsf_process.add_boundary_task
    it = bsf_process.init_displ_task
    ft = bsf_process.fold_task

#     import pylab as p
#     ax = p.axes()
#     ab.formed_object.plot_mpl(ax)
#     p.show()

    ftv = DoublyCurvedYoshiFormingProcessFTV(model=bsf_process)
#     ftv.add(it.target_faces[0].viz3d)
#     it.formed_object.viz3d.set(tube_radius=0.002)
#     ftv.add(it.formed_object.viz3d)
#     ftv.add(it.formed_object.viz3d_dict['node_numbers'], order=5)
    ft.formed_object.viz3d.set(tube_radius=0.002)
#    ftv.add(ft.formed_object.viz3d_dict['node_numbers'], order=5)
    ftv.add(ft.formed_object.viz3d)
    ft.config.gu['dofs'].viz3d.scale_factor = 0.5
    ftv.add(ft.config.gu['dofs'].viz3d)

#    ftv.add(ft.sim_history.viz3d_dict['node_numbers'], order=5)
#    ft.sim_history.viz3d.set(tube_radius=0.002)

#     ftv.add(ft.sim_history.viz3d)
#     ft.config.gu['dofs'].viz3d.scale_factor = 0.5
#     ftv.add(ft.config.gu['dofs'].viz3d)
#
    it.u_1
    ft.u_1

    ftv.plot()
    ftv.update(vot=1, force=True)
    ftv.show()

    n_cam_move = 40
    fta = FTA(ftv=ftv)
    fta.init_view(a=45, e=60, d=7, f=(0, 0, 0), r=-120)
    fta.add_cam_move(a=60, e=70, n=n_cam_move, d=8, r=-120,
                     duration=10,
                     vot_fn=lambda cmt: np.linspace(0.01, 0.5, n_cam_move),
                     azimuth_move='damped',
                     elevation_move='damped',
                     distance_move='damped')
    fta.add_cam_move(a=80, e=80, d=7, n=n_cam_move, r=-132,
                     duration=10,
                     vot_fn=lambda cmt: np.linspace(0.5, 1.0, n_cam_move),
                     azimuth_move='damped',
                     elevation_move='damped',
                     distance_move='damped')

    fta.plot()
    fta.render()
    fta.configure_traits()