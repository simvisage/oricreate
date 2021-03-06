# -------------------------------------------------------------------------
#
# Copyright (c) 2009, IMB, RWTH Aachen.
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD
# license included in oricreate/LICENSE.txt and may be redistributed only
# under the conditions described in the aforementioned license.  The license
# is also available online at http://www.simvisage.com/licenses/BSD.txt
#
# Thanks for using oricreate open source!
#
# Created on Jan 29, 2013 by: rch

import platform
import time

from scipy.optimize import \
    fmin_slsqp
from traits.api import \
    HasStrictTraits, Event, Property, cached_property, \
    Bool, Float, DelegatesTo, List, \
    Instance, WeakRef, Array

import numpy as np
from oricreate.crease_pattern import \
    CreasePatternState
from oricreate.forming_tasks import \
    FormingTask
from .simulation_config import \
    SimulationConfig


if platform.system() == 'Linux':
    sysclock = time.time
elif platform.system() == 'Windows':
    sysclock = time.clock


class SimulationStep(HasStrictTraits):
    r"""Class implementing the transition of the formed object 
    from its initial time to the target time :math:`t`.
    """

    forming_task = WeakRef(FormingTask)
    r'''Backward link to the client forming tasks.
    This may be an incremental time stepping SimulationTask
    of a MappingTaks performed in a single iterative step.
    '''

    source_config_changed = Event
    r'''Notification event for changes in the configuration
    of the optimization problem.
    '''

    config = Instance(SimulationConfig)
    r'''Configuration of the optimization problem.
    '''

    # =====================================================================
    # Cached properties derived from configuration and position in the pipe
    # =====================================================================
    cp_state = Property(Instance(CreasePatternState),
                        depends_on='source_config_changed')
    r'''Crease pattern state.
    '''
    @cached_property
    def _get_cp_state(self):
        return self.forming_task.formed_object

    fu = Property(depends_on='source_config_changed')
    r'''Goal function object.
    '''
    @cached_property
    def _get_fu(self):
        self.config.fu.forming_task = self.forming_task
        return self.config.fu

    gu = Property(depends_on='source_config_changed')
    r'''Goal function object.
    '''
    @cached_property
    def _get_gu(self):
        self.config.gu.forming_task = self.forming_task
        return self.config.gu

    gu_lst = Property(depends_on='source_config_changed')
    r'''Equality constraint object.
    '''
    @cached_property
    def _get_gu_lst(self):
        for gu in self.config.gu_lst:
            gu.forming_task = self.forming_task
        return self.config.gu_lst

    hu_lst = Property(depends_on='source_config_changed')
    r'''Inequality constraint object.
    '''
    @cached_property
    def _get_hu_lst(self):
        for hu in self.config.gu_lst:
            hu.forming_task = self.forming_task
        return self.config.hu_lst

    def __str__(self):
        s = ''
        for gu in self.gu_lst:
            s += str(gu)
        return s

    debug_level = DelegatesTo("config")
    # ===========================================================================
    # Configuration parameters for the iterative solver
    # ===========================================================================
    t = Float(1.0, auto_set=False, enter_set=True)
    r'''Target time within the step in the range (0,1).
    '''

    # =========================================================================
    # Output data
    # =========================================================================

    x_0 = Property
    r'''Initial position of all nodes.
    '''

    def _get_x_0(self):
        return self.X_0.reshape(-1, self.n_D)

    U = Property(Array(float))
    r'''Intermediate displacement vector of the cp_state
    '''

    def _get_U(self):
        return self.cp_state.U

    def _set_U(self, value):
        self.cp_state.U = value

    U_t = Property(depends_on='t')
    r'''Final displacement vector :math:`X` at target time :math:`t`.
    '''
    @cached_property
    def _get_U_t(self):
        U_t = self._solve()
        return U_t

    X_t = Property()
    r'''Vector of node positions :math:`U` at target time :math:`t`.
    '''

    def _get_X_t(self):
        return self.X_0[np.newaxis, :] + self.U_t

    x_t = Property()
    r'''Array of node positions :math:`x_{ij}` at target time :math:`t` - [node, dim].
    '''

    def _get_x_t(self):
        n_t = self.X_t.shape[0]
        return self.X_t.reshape(n_t, -1, self.n_D)

    u_t = Property()
    r'''Array of nodal displaceements :math:`x_{ij}`  [node, dim].
    '''

    def _get_u_t(self):
        n_D = self.cp_state.n_D
        return self.U_t.reshape(-1, n_D)

    # ===========================================================================
    # Iterative solvers
    # ===========================================================================

    def _solve(self):
        '''Decide which solver to take and start it.
        '''
        self.config.validate_input()
        if self.config.goal_function_type_ is not None:
            U_t = self._solve_fmin()
        else:
            # no goal function - switch to an implicit time-stepping algorithm
            print('SOLVING NR')
            U_t = self._solve_nr()

        return U_t

    def _solve_nr(self):
        '''Find the solution using the Newton-Raphson procedure.
        '''
        i = 0
        U_save = np.copy(self.U)
        acc = self.config.acc
        max_iter = self.config.MAX_ITER
        while i <= max_iter:
            dR = self.get_G_du_t(self.U)
            R = self.get_G_t(self.U)
            nR = np.linalg.norm(R)
            if nR < acc:
                print('==== converged in ', i, 'iterations ====')
                break
            try:
                d_U = np.linalg.solve(dR, -R)
                self.U += d_U  # in-place increment
                i += 1
            except Exception as inst:
                print('=== Problems solving iteration step %d  ====' % i)
                print('=== Exception message: ', inst)
                self.U = U_save
                raise inst
        else:
            self.U = U_save
            print('==== did not converge in %d iterations ====' % i)

        # update the state object with the new displacement vector
        return self.U

    def _solve_fmin(self):
        '''Solve the problem using the
        Sequential Least Square Quadratic Programming method.
        '''
        print('==== solving with SLSQP optimization ====')
        U_save = np.copy(self.U)
        d0 = self.get_f_t(self.U)
        eps = d0 * 1e-4
        get_f_du_t = None
        get_G_du_t = None
        get_H_t = None
        get_H_du_t = None
        acc = self.config.acc
        max_iter = self.config.MAX_ITER

        if self.config.use_f_du:
            get_f_du_t = self.get_f_du_t
        if self.config.use_G_du:
            get_G_du_t = self.get_G_du_t
        if self.config.has_H:
            get_H_t = self.get_H_t
            if self.config.use_H_du:
                get_H_du_t = self.get_H_du_t

        info = fmin_slsqp(self.get_f_t,
                          self.U,
                          fprime=get_f_du_t,
                          f_eqcons=self.get_G_t,
                          fprime_eqcons=get_G_du_t,
                          #                           f_ieqcons=get_H_t,
                          #                           fprime_ieqcons=get_H_du_t,
                          acc=acc, iter=max_iter,
                          iprint=2,
                          full_output=True,
                          epsilon=eps)
        U, f, n_iter, imode, smode = info
        if imode == 0:
            print('(time: %g, iter: %d, f: %g)' % (self.t, n_iter, f))
        else:
            # no convergence reached.
            self.U = U_save
            print('(time: %g, iter: %d, f: %g, err: %d, %s)' % \
                (self.t, n_iter, f, imode, smode))
        return U

    def clear_iter(self):
        self.u_it_list = []

    record_iter = Bool(False)
    u_it_list = List
    # ==========================================================================
    # Goal function
    # ==========================================================================

    def get_f_t(self, U):
        '''Get the goal function value.
        '''
        if self.record_iter:
            self.u_it_list.append(np.copy(U.reshape(-1, 3)))
        self.cp_state.U = U
        f = self.get_f()
        if self.debug_level > 0:
            print('f:\n', f)
        return f

    def get_f(self):
        return self.fu.get_f(self.t)

    def get_f_du_t(self, U):
        '''Get the goal function derivatives.
        '''
        self.cp_state.U = U
        f_du = self.get_f_du()
        if self.debug_level > 2:
            print('f_du.shape:\n', f_du.shape)
            print('f_du:\n', f_du)
        return f_du

    def get_f_du(self):
        return self.fu.get_f_du(self.t)

    # ==========================================================================
    # Equality constraints
    # ==========================================================================
    def get_G_t(self, U):
        self.cp_state.U = U
        g = self.get_G(self.t)
        if self.debug_level > 1:
            print('G:\n', [g])
        return g

    def get_G(self, t=0):
        g_lst = [gu.get_G(t) for gu in self.gu_lst]
        if(g_lst == []):
            return []
        return np.hstack(g_lst)

    def get_G_du_t(self, U):
        self.cp_state.U = U
        return self.get_G_du(self.t)

    def get_G_du(self, t=0):
        g_du_lst = [gu.get_G_du(t) for gu in self.gu_lst]
        if(g_du_lst == []):
            return []
        g_du = np.vstack(g_du_lst)
        if self.debug_level > 3:
            print('G_du.shape:\n', g_du.shape)
            print('G_du:\n', [g_du])
        return g_du

    # ==========================================================================
    # Inequality constraints
    # ==========================================================================
    def get_H_t(self, U):
        self.cp_state.U = U
        h = self.get_H(self.t)
        if self.debug_level > 1:
            print('H:\n', [h])
        return h

    def get_H(self, t=0):
        h_lst = [hu.get_H(t) for hu in self.hu_lst]
        if(h_lst == []):
            return []
        return np.hstack(h_lst)

    def get_H_du_t(self, U):
        self.cp_state.U = U
        return self.get_H_du(self.t)

    def get_H_du(self, t=0):
        h_du_lst = [hu.get_H_du(t) for hu in self.hu_lst]
        if(h_du_lst == []):
            return []
        h_du = np.vstack(h_du_lst)
        if self.debug_level > 3:
            print('G_du.shape:\n', h_du.shape)
            print('G_du:\n', [h_du])
        return h_du
