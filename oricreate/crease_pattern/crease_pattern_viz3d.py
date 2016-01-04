'''
Created on Dec 3, 2015

@author: rch
'''

from traits.api import \
    Array, Tuple, Property, Bool, Float, Color

import numpy as np
from oricreate.viz3d import Viz3D


class CreasePatternViz3D(Viz3D):
    '''Visualize the crease Pattern
    '''
    N_selection = Array(int)
    L_selection = Array(int)
    F_selection = Array(int)

    lines = Bool(True)

    N_L_F = Property(Tuple)
    '''Geometry with applied selection arrays.
    '''

    def _get_N_L_F(self):
        cp = self.vis3d
        x, L, F = cp.x, cp.L, cp.F
        if len(self.N_selection):
            x = x[self.N_selection]
        if len(self.L_selection):
            L = L[self.L_selection]
        if len(self.F_selection):
            F = F[self.F_selection]
        return x, L, F

#    facet_color = Color((0.0, 0.425, 0.683))
    facet_color = Color((0.4, 0.4, 0.7))
    facet_color = Color((0.0 / 255.0, 84.0 / 255.0, 159.0 / 255.0))
#   facet_color = Color((64.0 / 255.0, 127.0 / 255.0, 183.0 / 255.0))
#    facet_color = Color((0.0 / 255.0, 97.0 / 255.0, 101.0 / 255.0))

    def plot(self):

        m = self.ftv.mlab
        N, L, F = self.N_L_F
        x, y, z = N.T
        if len(F) > 0:
            cp_pipe = m.triangular_mesh(x, y, z, F,
                                        line_width=3,
                                        color=self.facet_color)
            if self.lines is True:
                cp_pipe.mlab_source.dataset.lines = L
                tube = m.pipeline.tube(cp_pipe,
                                       tube_radius=self.tube_radius)
                m.pipeline.surface(tube, color=(1.0, 1.0, 1.0))

        else:
            cp_pipe = m.points3d(x, y, z, scale_factor=0.2)
            cp_pipe.mlab_source.dataset.lines = L
        self.cp_pipe = cp_pipe

    def update(self):
        N = self.N_L_F[0]
        self.cp_pipe.mlab_source.set(points=N)

    def _get_bounding_box(self):
        N = self.N_L_F[0]
        return np.min(N, axis=0), np.max(N, axis=0)

    def _get_max_length(self):
        return np.linalg.norm(self._get_bounding_box())

    tube_radius = Float(0.013)

    line_width_factor = Float(0.0024)

    def _get_line_width(self):
        return self._get_max_length() * self.line_width_factor


class CreasePatternThickViz3D(CreasePatternViz3D):
    '''Visualize facets as if they had thickness
    '''
    thickness = Float(0.06)
    lines = False

    plane_offsets = Array(float, value=[0])

    def _get_N_L_F(self):
        x, L, F = super(CreasePatternThickViz3D, self)._get_N_L_F()
        cp = self.vis3d
        F_sel = slice(None)
        if len(self.F_selection):
            F_sel = F[self.F_selection]

        norm_F_normals = cp.norm_F_normals[F_sel]
        offsets = norm_F_normals[None, :, :] * \
            self.plane_offsets[:, None, None]
        F_x = x[F]
        F_x_planes = F_x[None, :, :, :] + offsets[:, :, None, :]
        x_planes = F_x_planes.reshape(-1, 3)
        F = np.arange(x_planes.shape[0]).reshape(-1, 3)
        return x_planes, L, F


class CreasePatternNormalsViz3D(Viz3D):
    '''Visualize the crease Pattern
    '''

    def get_values(self):
        cp = self.vis3d

        Fa_r = cp.Fa_r
        Fa_normals = cp.Fa_normals

        x, y, z = Fa_r.reshape(-1, 3).T
        u, v, w = Fa_normals.reshape(-1, 3).T
        return x, y, z, u, v, w

    def plot(self):

        m = self.ftv.mlab
        x, y, z, u, v, w = self.get_values()
        self.quifer3d_pipe = m.quiver3d(x, y, z, u, v, w)

    def update(self):
        x, y, z, u, v, w = self.get_values()
        self.quifer3d_pipe.mlab_source.set(x=x, y=y, z=z, u=u, v=v, w=w)


class CreasePatternBasesViz3D(Viz3D):
    '''Visualize the crease Pattern
    '''

    def get_values(self):
        cp = self.vis3d

        Fa_r = cp.Fa_r
        F_L_bases = cp.F_L_bases[:, 0, :, :]
        return Fa_r.reshape(-1, 3), F_L_bases.reshape(-1, 3, 3)

    def plot(self):

        m = self.ftv.mlab
        Fa_r, F_L_bases = self.get_values()
        args_red = tuple(Fa_r.T) + tuple(F_L_bases[..., 0, :].T)
        args_gre = tuple(Fa_r.T) + tuple(F_L_bases[..., 1, :].T)
        args_blu = tuple(Fa_r.T) + tuple(F_L_bases[..., 2, :].T)
        self.quifer3d_pipe_red = m.quiver3d(*args_red, color=(1, 0, 0))
        self.quifer3d_pipe_gre = m.quiver3d(*args_gre, color=(0, 1, 0))
        self.quifer3d_pipe_blu = m.quiver3d(*args_blu, color=(0, 0, 1))

    def update(self):
        Fa_r, F_L_bases = self.get_values()
        x, y, z = Fa_r.T
        u, v, w = F_L_bases[..., 0, :].T
        self.quifer3d_pipe_red.mlab_source.set(x=x, y=y, z=z, u=u, v=v, w=w)
        u, v, w = F_L_bases[..., 1, :].T
        self.quifer3d_pipe_gre.mlab_source.set(x=x, y=y, z=z, u=u, v=v, w=w)
        u, v, w = F_L_bases[..., 2, :].T
        self.quifer3d_pipe_blu.mlab_source.set(x=x, y=y, z=z, u=u, v=v, w=w)