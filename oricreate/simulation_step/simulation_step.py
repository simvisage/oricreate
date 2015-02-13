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

from scipy.optimize import \
    fmin_slsqp

from traits.api import \
    Event, Property, cached_property, \
    Int, Float, Bool, \
    Instance

from simulation_config import \
    SimulationConfig

from oricreate.crease_pattern import \
    CreasePatternState

import time

import numpy as np

import platform

if platform.system() == 'Linux':
    sysclock = time.time
elif platform.system() == 'Windows':
    sysclock = time.clock


class SimulationStep(CreasePatternState):

    r"""Class implementing the transition of the crease pattern state
    to the target time :math:`t`.
    """

    source_config_changed = Event
    r'''Notification event for changes in the configuration
    of the optimization problem.
    '''

    opt = Instance(SimulationConfig)
    r'''Configuration of the optimization problem.
    '''

    opt_ = Property(depends_on='sim_config')
    r'''Configuration of the optimization problem including the backward link.
    '''
    @cached_property
    def _get_opt_(self):
        self.opt.sim_step = self
        return self.opt

    t = Float(0.0, auto_set=False, enter_set=True)
    r'''Current time within the step in the range (0,1).
    '''

    show_iter = Bool(False, auto_set=False, enter_set=True)
    r'''Saves the first 10 iteration steps, so they can be analyzed
    '''

    MAX_ITER = Int(100, auto_set=False, enter_set=True)
    r'''Maximum number of iterations.
    '''

    acc = Float(1e-4, auto_set=False, enter_set=True)
    r'''Required accuracy.
    '''

    def _solve_nr(self, t):
        '''Find the solution using the Newton-Raphson procedure.
        '''
        i = 0

        while i <= self.MAX_ITER:
            dR = self.get_G_du(t)
            R = self.get_G(t)
            nR = np.linalg.norm(R)
            if nR < self.acc:
                print '==== converged in ', i, 'iterations ===='
                break
            try:
                d_U = np.linalg.solve(dR, -R)
                self.U += d_U
                i += 1
            except Exception as inst:
                print '=== Problems solving iteration step %d  ====' % i
                print '=== Exception message: ', inst
        else:
            print '==== did not converge in %d iterations ====' % i

        return self.U

    use_G_du = Bool(True, auto_set=False, enter_set=True)

    def _solve_fmin(self):
        '''Solve the problem using the
        Sequential Least Square Quadratic Programming method.
        '''
        print '==== solving with SLSQP optimization ===='
        d0 = self.get_f_t(self.U)
        eps = d0 * 1e-4
        get_G_du_t = None

        self.t = time
        if self.use_G_du:
            get_G_du_t = self.get_G_du_t

        info = fmin_slsqp(self.get_f_t,
                          self.cp_state.U,
                          fprime=self.get_f_du_t,
                          f_Gu=self.get_G_t,
                          fprime_Gu=get_G_du_t,
                          acc=self.acc, iter=self.MAX_ITER,
                          iprint=0,
                          full_output=True,
                          epsilon=eps)
        U, f, n_iter, imode, smode = info
        if imode == 0:
            print '(time: %g, iter: %d, f: %g)' % (time, n_iter, f)
        else:
            print '(time: %g, iter: %d, f: %g, err: %d, %s)' % \
                (time, n_iter, f, imode, smode)
        return U

    # ==========================================================================
    # Goal function
    # ==========================================================================
    def get_f_t(self, U):
        '''Get the goal function value.
        '''
        u = U.reshape(-1, self.n_D)
        f = self.opt.fu.get_f(u, self.t)
        if self.debug_level > 0:
            print 'f:\n', f
        return f

    def get_f_du_t(self, U):
        '''Get the goal function derivatives.
        '''
        u = U.reshape(-1, self.n_D)
        f_du = self.opt.fu.get_f_du(u, self.t)
        if self.debug_level > 1:
            print 'f_du.shape:\n', f_du.shape
            print 'f_du:\n', f_du
        return f_du

    # ==========================================================================
    # Equality constraints
    # ==========================================================================
    def get_g_t(self, U):
        u = U.reshape(-1, self.n_D)
        g = self.get_g(u, self.t)
        if self.debug_level > 0:
            print 'G:\n', [g]
        return g

    def get_g(self, u, t=0):
        g_lst = [gu.get_g(u, t) for gu in self.opt.gu_lst]
        if(g_lst == []):
            return []
        return np.hstack(g_lst)

    def get_g_du_t(self, U):
        u = U.reshape(-1, self.n_D)
        return self.get_g_du(u, self.t)

    def get_g_du(self, u, t=0):
        g_du_lst = [gu.get_G_du(u, t) for gu in self.opt.gu_lst]
        if(g_du_lst == []):
            return []
        g_du = np.vstack(g_du_lst)
        if self.debug_level > 1:
            print 'G_du.shape:\n', g_du.shape
            print 'G_du:\n', [g_du]
        return g_du

    # =========================================================================
    # Output data
    # =========================================================================

    x_0 = Property
    '''Initial position of all nodes.
    '''

    def _get_x_0(self):
        return self.X_0.reshape(-1, self.n_D)

    X_t = Property()
    '''History of nodal positions [time, node*dim]).
    '''

    def _get_X_t(self):
        return self.X_0[np.newaxis, :] + self.U_t

    x_t = Property()
    '''History of nodal positions [time, node, dim].
    '''

    def _get_x_t(self):
        n_t = self.X_t.shape[0]
        return self.X_t.reshape(n_t, -1, self.n_D)

    x_1 = Property
    '''Final position of all nodes.
    '''

    def _get_x_1(self):
        return self.x_t[-1]

    u_t = Property()
    '''History of nodal positions [time, node, dim].
    '''

    def _get_u_t(self):
        n_t = self.U_t.shape[0]
        return self.U_t.reshape(n_t, -1, self.n_D)

    u_1 = Property()
    '''Final nodal positions [node, dim].
    '''

    def _get_u_1(self):
        return self.u_t[-1]

if __name__ == '__main__':
    fs = SimulationStep()
    fs.configure_traits()
