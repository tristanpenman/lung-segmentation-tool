"""Interactive viewer for scans and segmented lung volume."""

import ctypes
import math
import pyglet

from euclid3 import Quaternion, Vector3, Matrix4

from pyglet.gl import *
from pyglet.gl.gl_compat import *
from pyglet.window import mouse, Window


def calculate_transverse_size(height):
    return math.ceil(2.0 * height / 3.0)


def draw_line(x1, y1, x2, y2, color, line_width=1.0, viewport_scale=1.0):
    old_line_width = GLfloat(0)
    glGetFloatv(GL_LINE_WIDTH, ctypes.byref(old_line_width))
    glLineWidth(viewport_scale * line_width)
    glColor3f(*color)
    glBegin(GL_LINES)
    glVertex2f(x1, y1)
    glVertex2f(x2, y2)
    glEnd()
    glLineWidth(old_line_width)


def draw_single_textured_quad(texture_id, left, right, top, bottom):
    glEnable(GL_TEXTURE_2D)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(1.0, 1.0, 1.0, 1.0)
    glBegin(GL_QUADS)
    glTexCoord2i(0, 0)
    glVertex2i(left, top)
    glTexCoord2i(1, 0)
    glVertex2i(right, top)
    glTexCoord2i(1, 1)
    glVertex2i(right, bottom)
    glTexCoord2i(0, 1)
    glVertex2i(left, bottom)
    glEnd()
    glDisable(GL_TEXTURE_2D)


def generate_view_matrix(rotation, zoom):
    return Matrix4.new_translate(0.0, 0.0, zoom) * rotation.get_matrix()


def init_texture_params():
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)


# noinspection PyAbstractClass,PyMethodOverriding
class Viewer(Window):
    # OpenGL handles
    face_buffer_id = GLuint(0)
    coronal_texture_id = GLuint(0)
    sagittal_texture_id = GLuint(0)
    transverse_texture_id = GLuint(0)
    vertex_buffer_id = GLuint(0)

    mouse_down = False
    mouse_down_segmented = False
    mouse_down_transverse = False
    num_faces = 0
    rotation = Quaternion()
    viewport_scale = 1.0
    zoom = -450.0

    def __init__(self, w, h, scan, vertices, faces):
        super().__init__(w, h, caption='Lung Segmentation Tool', resizable=True, visible=False)

        # Derived member variables
        self.scan = scan
        self.coronal_slice = int(scan.shape[1] / 2)
        self.sagittal_slice = int(scan.shape[2] / 2)
        self.transverse_size = calculate_transverse_size(h)
        self.segmented_width = w - self.transverse_size
        self.transverse_slice = int(scan.shape[0] / 2)
        self.view_matrix = generate_view_matrix(self.rotation, self.zoom)
        self.model_matrix = Matrix4.new_rotate_axis(math.pi / -2.0, Vector3(1.0, 0.0, 0.0))

        # Initialise vertex buffer object
        glGenBuffers(1, ctypes.byref(self.vertex_buffer_id))
        self.update_vertex_buffer(vertices)

        # Initialise face buffer object
        glGenBuffers(1, ctypes.byref(self.face_buffer_id))
        self.update_face_buffer(faces)

        # Initialise texture for coronal slice
        glGenTextures(1, ctypes.byref(self.coronal_texture_id))
        self.update_coronal_texture()
        init_texture_params()

        # Initialise texture for coronal slice
        glGenTextures(1, ctypes.byref(self.sagittal_texture_id))
        self.update_sagittal_texture()
        init_texture_params()

        # Initialize texture for transverse slice
        glGenTextures(1, ctypes.byref(self.transverse_texture_id))
        self.update_transverse_texture()
        init_texture_params()

    def draw_coronal(self):
        viewport_size = (self.width, self.height)
        coronal_size = math.ceil(self.transverse_size / 2.0)
        viewport = [viewport_size[0] - math.floor(self.viewport_scale * coronal_size), 0,
                    math.ceil(self.viewport_scale * coronal_size),
                    math.ceil(self.viewport_scale * coronal_size)]

        # Setup viewport and projection matrix for 2D orthogonal view
        glViewport(*viewport)
        glScissor(*viewport)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, coronal_size, 0, coronal_size)

        # Clear canvas
        glClearColor(0.0, 1.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        # Draw single textured quad
        draw_single_textured_quad(self.coronal_texture_id, 0, coronal_size, 0, coronal_size)

        s = (coronal_size - 1.0) / coronal_size

        x = (self.sagittal_slice / self.scan.shape[2] * coronal_size) * s + 1.0
        draw_line(x, 0, x, coronal_size, [0.0, 1.0, 0.0], 2.0, self.viewport_scale)

        y = (self.transverse_slice / self.scan.shape[0] * coronal_size) * s + 1.0
        draw_line(0, y, coronal_size, y, [0.0, 0.0, 1.0], 2.0, self.viewport_scale)

    def draw_mesh(self):
        viewport_size = (self.width, self.height)
        viewport = [0, 0, int(self.segmented_width * self.viewport_scale), viewport_size[1]]

        # Setup viewport and projection matrix for 2D orthogonal view
        glViewport(*viewport)
        glScissor(*viewport)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = (self.segmented_width / float(self.get_size()[1]))
        gluPerspective(60.0, aspect, 0.001, 1000.0)
        glMatrixMode(GL_MODELVIEW)

        # Draw mesh
        glPushClientAttrib(GL_ALL_CLIENT_ATTRIB_BITS)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        glClear(GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        # noinspection PyCallingNonCallable,PyTypeChecker
        glLoadMatrixf((GLfloat * 16)(*(self.view_matrix * self.model_matrix)))
        glColor4f(1.0, 1.0, 1.0, 0.2)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, 0)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, 0, None)
        glDrawElements(GL_TRIANGLES, self.num_faces, GL_UNSIGNED_INT, None)
        glPopMatrix()
        glPopClientAttrib()

    def draw_sagittal(self):
        sagittal_size = math.ceil(self.transverse_size / 2.0)
        viewport = [math.ceil(self.viewport_scale * self.segmented_width), 0,
                    math.ceil(self.viewport_scale * sagittal_size),
                    math.ceil(self.viewport_scale * sagittal_size)]

        # Setup viewport and projection matrix for 2D orthogonal view
        glViewport(*viewport)
        glScissor(*viewport)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, sagittal_size, 0, sagittal_size)

        # Clear canvas
        glClearColor(0.0, 1.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        # Draw single textured quad
        draw_single_textured_quad(self.sagittal_texture_id, 0, int(sagittal_size), 0,
                                  int(sagittal_size))

        s = (sagittal_size - 1.0) / sagittal_size

        x = (self.coronal_slice / self.scan.shape[2] * sagittal_size) * s + 1.0
        draw_line(x, 0, x, sagittal_size, [0.0, 1.0, 0.0], 2.0, self.viewport_scale)

        y = (self.transverse_slice / self.scan.shape[0] * sagittal_size) * s + 1.0
        draw_line(0, y, sagittal_size, y, [1.0, 0.0, 0.0], 2.0, self.viewport_scale)

    def draw_transverse(self):
        scaled_transverse_size = self.viewport_scale * self.transverse_size
        viewport = [int(self.viewport_scale * self.segmented_width),
                    int(scaled_transverse_size / 2.0),
                    int(scaled_transverse_size),
                    int(scaled_transverse_size)]

        # Setup viewport and projection matrix for 2D orthogonal view
        glViewport(*viewport)
        glScissor(*viewport)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, self.transverse_size, self.transverse_size, 0)

        # Clear canvas
        glClearColor(1.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Draw single textured quad
        draw_single_textured_quad(self.transverse_texture_id, 0, self.transverse_size, 0,
                                  self.transverse_size)

        s = (self.transverse_size - 1.0) / self.transverse_size

        x = (self.sagittal_slice / self.scan.shape[2] * self.transverse_size) * s + 1.0
        draw_line(x, 0, x, self.transverse_size, [1.0, 0.0, 0.0], 2.0, self.viewport_scale)

        y = (self.coronal_slice / self.scan.shape[1] * self.transverse_size) * s + 1.0
        draw_line(0, y, self.transverse_size, y, [0.0, 0.0, 1.0], 2.0, self.viewport_scale)

    def on_close(self):
        pyglet.app.exit()

    def on_draw(self):
        glEnable(GL_SCISSOR_TEST)
        self.draw_mesh()
        self.draw_transverse()
        self.draw_sagittal()
        self.draw_coronal()

    def on_mouse_drag(self, x, y, dx, dy, button, modifiers):
        if self.mouse_down_segmented:
            new_rotation = self.rotation
            sensitivity = 0.007
            phi = sensitivity * -dy
            if phi != 0:
                # Rotate phi radians around the X axis of the scene
                axis = new_rotation.get_matrix().inverse() * Vector3(1.0, 0.0, 0.0)
                new_rotation *= Quaternion.new_rotate_axis(phi, axis)
            # Orbital rotation
            phi = sensitivity * dx
            if phi != 0:
                # Rotate phi radians around the original Y axis
                new_rotation *= Quaternion.new_rotate_axis(phi, Vector3(0.0, 1.0, 0.0))
            self.rotation = new_rotation.normalized()
            self.view_matrix = generate_view_matrix(self.rotation, self.zoom)
            self.on_draw()
        elif self.mouse_down_transverse:
            x = x - self.segmented_width
            y = self.transverse_size - (y - self.transverse_size / 2.0)
            self.sagittal_slice = int(max(0, min(x / self.transverse_size * self.scan.shape[2],
                                                 self.scan.shape[2] - 1)))
            self.coronal_slice = int(max(0, min(y / self.transverse_size * self.scan.shape[1],
                                                self.scan.shape[1] - 1)))
            self.update_coronal_texture()
            self.update_sagittal_texture()
            self.on_draw()

    def on_mouse_press(self, x, y, button, modifiers):
        if button & mouse.LEFT:
            if not self.mouse_down_segmented and x < self.segmented_width:
                self.mouse_down_segmented = True
            elif not self.mouse_down_transverse and x >= self.segmented_width and \
                    y > self.transverse_size / 2.0:
                self.mouse_down_transverse = True

    def on_mouse_release(self, x, y, button, modifiers):
        self.mouse_down_segmented = False
        self.mouse_down_transverse = False

    def on_mouse_scroll(self, x, y, _scroll_x, scroll_y):
        if x < self.segmented_width:
            self.zoom -= scroll_y * 3.0
            self.view_matrix = generate_view_matrix(self.rotation, self.zoom)
            self.on_draw()
        elif y > self.get_size()[1] - self.transverse_size:
            self.transverse_slice -= scroll_y
            self.transverse_slice = min(max(0, self.transverse_slice), self.scan.shape[0] - 1)
            self.update_transverse_texture()
            self.on_draw()

    def on_move(self, x, y):
        # HACK: Ensures that change in DPI is handled on Mac; may be required on Linux / Windows
        if pyglet.options['darwin_cocoa']:
            viewport_width = self.width
            width, height = self.get_size()
            if viewport_width / width != self.viewport_scale:
                # Ensure window can be 'resized' without animation
                self.set_visible(False)
                # This will force a resize event to bubble up from Cocoa
                self.set_size(width + 1, height)
                self.set_size(width, height)
                # Make the window visible again
                self.set_visible(True)

    def on_resize(self, width, height):
        if self.visible:
            viewport_size = (self.width, self.height)
            self.viewport_scale = viewport_size[0] / width
            self.transverse_size = math.ceil(2.0 * height / 3.0)
            self.segmented_width = width - self.transverse_size
            self.view_matrix = generate_view_matrix(self.rotation, self.zoom)
            return pyglet.event.EVENT_HANDLED
        else:
            return pyglet.event.EVENT_UNHANDLED

    def update_face_buffer(self, faces):
        self.num_faces = len(faces)
        # noinspection PyCallingNonCallable,PyTypeChecker
        faces_ptr = (GLuint * self.num_faces)(*faces)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.face_buffer_id)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(faces_ptr), faces_ptr, GL_STATIC_DRAW)

    def update_coronal_texture(self):
        shape = self.scan.shape
        image = self.scan[:, self.coronal_slice, :]
        num_pixels = shape[1] * shape[0]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (GLfloat * num_pixels)(*image.flatten())
        glBindTexture(GL_TEXTURE_2D, self.coronal_texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, shape[1], shape[0], 0, GL_RED, GL_FLOAT,
                     image_ptr)

    def update_sagittal_texture(self):
        shape = self.scan.shape
        image = self.scan[:, :, self.sagittal_slice]
        num_pixels = shape[2] * shape[0]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (GLfloat * num_pixels)(*image.flatten())
        glBindTexture(GL_TEXTURE_2D, self.sagittal_texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, shape[2], shape[0], 0, GL_RED, GL_FLOAT,
                     image_ptr)

    def update_transverse_texture(self):
        shape = self.scan.shape
        image = self.scan[self.transverse_slice]
        num_pixels = shape[1] * shape[2]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (GLfloat * num_pixels)(*image.flatten())
        glBindTexture(GL_TEXTURE_2D, self.transverse_texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, shape[1], shape[2], 0, GL_RED, GL_FLOAT,
                     image_ptr)

    def update_vertex_buffer(self, vertices):
        # noinspection PyCallingNonCallable,PyTypeChecker
        vertices_ptr = (GLfloat * len(vertices))(*vertices)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer_id)
        glBufferData(GL_ARRAY_BUFFER, ctypes.sizeof(vertices_ptr), vertices_ptr, GL_STATIC_DRAW)
