"""Interactive viewer for scans and segmented lung volume."""

import ctypes
import math
import pyglet

from euclid3 import Quaternion, Vector3

from pyglet import gl
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import mouse, Window


MESH_VERTEX_SHADER_SOURCE = """
#version 330 core

uniform mat4 u_projection;
uniform mat4 u_view;
uniform mat4 u_model;

in vec3 position;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(position, 1.0);
}
"""


MESH_FRAGMENT_SHADER_SOURCE = """
#version 330 core

uniform vec4 u_color;

out vec4 frag_color;

void main() {
    frag_color = u_color;
}
"""


SLICE_VERTEX_SHADER_SOURCE = """
#version 330 core

uniform mat4 u_projection;
uniform mat4 u_view;
uniform mat4 u_model;

in vec3 position;
in vec2 tex_coord;

out vec2 v_tex_coord;

void main() {
    v_tex_coord = tex_coord;
    gl_Position = u_projection * u_view * u_model * vec4(position, 1.0);
}
"""


SLICE_FRAGMENT_SHADER_SOURCE = """
#version 330 core

uniform sampler2D u_texture;

in vec2 v_tex_coord;

out vec4 frag_color;

void main() {
    float intensity = texture(u_texture, v_tex_coord).r;
    frag_color = vec4(intensity, intensity, intensity, 1.0);
}
"""


QUAD_INDICES = (0, 1, 2, 0, 2, 3)
QUAD_VERTICES = (
    0.0, 0.0, 0.0,
    1.0, 0.0, 0.0,
    1.0, 1.0, 0.0,
    0.0, 1.0, 0.0,
)
QUAD_TEX_COORDS = (
    0.0, 0.0,
    1.0, 0.0,
    1.0, 1.0,
    0.0, 1.0,
)


def calculate_transverse_size(height):
    return math.ceil(2.0 * height / 3.0)


def euclid_to_mat4(matrix):
    """Convert an ``euclid3.Matrix4`` to ``pyglet.math.Mat4``."""
    values = [float(value) for value in matrix[:16]]
    return Mat4(*values)


def draw_single_textured_quad(program, vertex_list, texture_id, model_matrix, projection_matrix,
                              view_matrix=None):
    view = view_matrix or Mat4()
    program.use()
    program['u_projection'] = projection_matrix
    program['u_view'] = view
    program['u_model'] = model_matrix
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, getattr(texture_id, 'value', texture_id))
    vertex_list.draw(gl.GL_TRIANGLES)
    gl.glUseProgram(0)


def generate_view_matrix(rotation, zoom):
    rotation_matrix = euclid_to_mat4(rotation.get_matrix())
    translation = Mat4.from_translation(Vec3(0.0, 0.0, zoom))
    return translation @ rotation_matrix


def init_texture_params():
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)


# noinspection PyAbstractClass,PyMethodOverriding
class Viewer(Window):
    # OpenGL handles
    coronal_texture_id = gl.GLuint(0)
    sagittal_texture_id = gl.GLuint(0)
    transverse_texture_id = gl.GLuint(0)

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
        self.transverse_position = float(self.transverse_slice)
        self.view_matrix = generate_view_matrix(self.rotation, self.zoom)
        self.model_matrix = Mat4.from_rotation(math.pi / -2.0, Vec3(1.0, 0.0, 0.0))

        # Cache supported OpenGL line width range for platforms (macOS core profile)
        line_width_range = (gl.GLfloat * 2)()
        gl.glGetFloatv(gl.GL_ALIASED_LINE_WIDTH_RANGE, line_width_range)
        self._min_line_width = float(line_width_range[0]) if line_width_range[0] > 0 else 1.0
        self._max_line_width = float(line_width_range[1]) if line_width_range[1] > 0 else 1.0
        if self._max_line_width < self._min_line_width:
            self._max_line_width = self._min_line_width

        # Shader programs and vertex lists
        self.mesh_program = ShaderProgram(Shader(MESH_VERTEX_SHADER_SOURCE, 'vertex'),
                                          Shader(MESH_FRAGMENT_SHADER_SOURCE, 'fragment'))
        self.slice_program = ShaderProgram(Shader(SLICE_VERTEX_SHADER_SOURCE, 'vertex'),
                                           Shader(SLICE_FRAGMENT_SHADER_SOURCE, 'fragment'))
        self.slice_program['u_texture'] = 0
        self.slice_vertex_list = self.slice_program.vertex_list_indexed(
            4, gl.GL_TRIANGLES, QUAD_INDICES,
            position=('f', QUAD_VERTICES),
            tex_coord=('f', QUAD_TEX_COORDS))
        vertex_data = list(vertices)
        face_data = list(faces)
        vertex_count = len(vertex_data) // 3
        self.mesh_vertex_list = self.mesh_program.vertex_list_indexed(
            vertex_count, gl.GL_TRIANGLES, face_data,
            position=('f', vertex_data))
        self.mesh_color = (1.0, 1.0, 1.0, 0.2)
        self.num_faces = len(face_data)

        # Initialise textures for slices
        self._coronal_texture_initialized = False
        self._sagittal_texture_initialized = False
        self._transverse_texture_initialized = False

        gl.glGenTextures(1, ctypes.byref(self.coronal_texture_id))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.coronal_texture_id.value)
        init_texture_params()
        self.update_coronal_texture()

        gl.glGenTextures(1, ctypes.byref(self.sagittal_texture_id))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.sagittal_texture_id.value)
        init_texture_params()
        self.update_sagittal_texture()

        gl.glGenTextures(1, ctypes.byref(self.transverse_texture_id))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.transverse_texture_id.value)
        init_texture_params()
        self.update_transverse_texture()

    def _draw_view_line(self, projection, x1, y1, x2, y2, color, line_width=1.0):
        old_line_width = gl.GLfloat(0)
        gl.glGetFloatv(gl.GL_LINE_WIDTH, ctypes.byref(old_line_width))
        desired_width = self.viewport_scale * line_width
        clamped_width = max(self._min_line_width, min(self._max_line_width, desired_width))
        gl.glLineWidth(clamped_width)

        self.mesh_program.use()
        self.mesh_program['u_projection'] = projection
        self.mesh_program['u_view'] = Mat4()
        self.mesh_program['u_model'] = Mat4()
        self.mesh_program['u_color'] = (float(color[0]), float(color[1]), float(color[2]), 1.0)

        line_vertex_list = self.mesh_program.vertex_list(
            2, gl.GL_LINES,
            position=('f', (float(x1), float(y1), 0.0, float(x2), float(y2), 0.0)))
        line_vertex_list.draw(gl.GL_LINES)
        line_vertex_list.delete()
        gl.glUseProgram(0)
        gl.glLineWidth(old_line_width.value)

    def draw_coronal(self):
        viewport_size = (self.width, self.height)
        coronal_size = math.ceil(self.transverse_size / 2.0)
        viewport = [viewport_size[0] - math.floor(self.viewport_scale * coronal_size), 0,
                    math.ceil(self.viewport_scale * coronal_size),
                    math.ceil(self.viewport_scale * coronal_size)]

        # Setup viewport and projection matrix for 2D orthogonal view
        gl.glViewport(*viewport)
        gl.glScissor(*viewport)
        gl.glDisable(gl.GL_DEPTH_TEST)

        # Clear canvas
        gl.glClearColor(0.0, 1.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        # Draw single textured quad
        projection = Mat4.orthogonal_projection(0.0, float(coronal_size), 0.0, float(coronal_size), -1.0, 1.0)
        model = Mat4.from_scale(Vec3(float(coronal_size), float(coronal_size), 1.0))
        draw_single_textured_quad(self.slice_program, self.slice_vertex_list, self.coronal_texture_id,
                                  model, projection)

        s = (coronal_size - 1.0) / coronal_size

        x = (self.sagittal_slice / self.scan.shape[2] * coronal_size) * s + 1.0
        self._draw_view_line(projection, x, 0, x, coronal_size, (0.0, 1.0, 0.0), 2.0)

        y = (self.transverse_slice / self.scan.shape[0] * coronal_size) * s + 1.0
        self._draw_view_line(projection, 0, y, coronal_size, y, (0.0, 0.0, 1.0), 2.0)

    def draw_mesh(self):
        viewport_size = (self.width, self.height)
        viewport = [0, 0, int(self.segmented_width * self.viewport_scale), viewport_size[1]]

        gl.glViewport(*viewport)
        gl.glScissor(*viewport)

        # Draw mesh
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glClearColor(0.2, 0.2, 0.2, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        aspect = self.segmented_width / float(self.get_size()[1])
        projection = Mat4.perspective_projection(aspect, 0.001, 1000.0, 60.0)
        self.mesh_program.use()
        self.mesh_program['u_projection'] = projection
        self.mesh_program['u_view'] = self.view_matrix
        self.mesh_program['u_model'] = self.model_matrix
        self.mesh_program['u_color'] = self.mesh_color
        self.mesh_vertex_list.draw(gl.GL_TRIANGLES)
        gl.glUseProgram(0)

    def draw_sagittal(self):
        sagittal_size = math.ceil(self.transverse_size / 2.0)
        viewport = [math.ceil(self.viewport_scale * self.segmented_width), 0,
                    math.ceil(self.viewport_scale * sagittal_size),
                    math.ceil(self.viewport_scale * sagittal_size)]

        gl.glViewport(*viewport)
        gl.glScissor(*viewport)
        gl.glDisable(gl.GL_DEPTH_TEST)

        # Clear canvas
        gl.glClearColor(0.0, 1.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        # Draw single textured quad
        projection = Mat4.orthogonal_projection(0.0, float(sagittal_size), 0.0, float(sagittal_size), -1.0, 1.0)
        model = Mat4.from_scale(Vec3(float(sagittal_size), float(sagittal_size), 1.0))
        draw_single_textured_quad(self.slice_program, self.slice_vertex_list, self.sagittal_texture_id,
                                  model, projection)

        s = (sagittal_size - 1.0) / sagittal_size

        x = (self.coronal_slice / self.scan.shape[2] * sagittal_size) * s + 1.0
        self._draw_view_line(projection, x, 0, x, sagittal_size, (0.0, 1.0, 0.0), 2.0)

        y = (self.transverse_slice / self.scan.shape[0] * sagittal_size) * s + 1.0
        self._draw_view_line(projection, 0, y, sagittal_size, y, (1.0, 0.0, 0.0), 2.0)

    def draw_transverse(self):
        scaled_transverse_size = self.viewport_scale * self.transverse_size
        viewport = [int(self.viewport_scale * self.segmented_width),
                    int(scaled_transverse_size / 2.0),
                    int(scaled_transverse_size),
                    int(scaled_transverse_size)]

        gl.glViewport(*viewport)
        gl.glScissor(*viewport)
        gl.glDisable(gl.GL_DEPTH_TEST)

        # Clear canvas
        gl.glClearColor(1.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # Draw single textured quad
        projection = Mat4.orthogonal_projection(0.0, float(self.transverse_size), float(self.transverse_size), 0.0,
                                                -1.0, 1.0)
        model = Mat4.from_scale(Vec3(float(self.transverse_size), float(self.transverse_size), 1.0))
        draw_single_textured_quad(self.slice_program, self.slice_vertex_list, self.transverse_texture_id,
                                  model, projection)

        s = (self.transverse_size - 1.0) / self.transverse_size

        x = (self.sagittal_slice / self.scan.shape[2] * self.transverse_size) * s + 1.0
        self._draw_view_line(projection, x, 0, x, self.transverse_size, (1.0, 0.0, 0.0), 2.0)

        y = (self.coronal_slice / self.scan.shape[1] * self.transverse_size) * s + 1.0
        self._draw_view_line(projection, 0, y, self.transverse_size, y, (0.0, 0.0, 1.0), 2.0)

    def on_close(self):
        pyglet.app.exit()

    def on_draw(self):
        gl.glEnable(gl.GL_SCISSOR_TEST)
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
        else:
            self.transverse_position -= scroll_y
            max_index = self.scan.shape[0] - 1
            self.transverse_position = min(max(0.0, self.transverse_position), float(max_index))
            new_slice = int(round(self.transverse_position))
            new_slice = max(0, min(new_slice, max_index))
            if new_slice != self.transverse_slice:
                self.transverse_slice = new_slice
                self.update_transverse_texture()
                self.on_draw()

    def on_move(self, x, y):
        # HACK: Ensures that change in DPI is handled on Mac; may be required on Linux / Windows
        if pyglet.options.get('darwin_cocoa', None):
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
        indices = list(faces)
        self.num_faces = len(indices)
        if self.mesh_vertex_list is not None:
            self.mesh_vertex_list.indices = indices

    def update_coronal_texture(self):
        shape = self.scan.shape
        image = self.scan[:, self.coronal_slice, :]
        num_pixels = shape[1] * shape[0]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (gl.GLfloat * num_pixels)(*image.flatten())
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.coronal_texture_id.value)
        if not self._coronal_texture_initialized:
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RED, shape[1], shape[0], 0, gl.GL_RED, gl.GL_FLOAT,
                            image_ptr)
            self._coronal_texture_initialized = True
        else:
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, shape[1], shape[0], gl.GL_RED, gl.GL_FLOAT, image_ptr)

    def update_sagittal_texture(self):
        shape = self.scan.shape
        image = self.scan[:, :, self.sagittal_slice]
        num_pixels = shape[2] * shape[0]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (gl.GLfloat * num_pixels)(*image.flatten())
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.sagittal_texture_id.value)
        if not self._sagittal_texture_initialized:
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RED, shape[2], shape[0], 0, gl.GL_RED, gl.GL_FLOAT,
                            image_ptr)
            self._sagittal_texture_initialized = True
        else:
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, shape[2], shape[0], gl.GL_RED, gl.GL_FLOAT, image_ptr)

    def update_transverse_texture(self):
        shape = self.scan.shape
        image = self.scan[self.transverse_slice]
        num_pixels = shape[1] * shape[2]
        # noinspection PyCallingNonCallable,PyTypeChecker
        image_ptr = (gl.GLfloat * num_pixels)(*image.flatten())
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.transverse_texture_id.value)
        if not self._transverse_texture_initialized:
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RED, shape[1], shape[2], 0, gl.GL_RED, gl.GL_FLOAT,
                            image_ptr)
            self._transverse_texture_initialized = True
        else:
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, shape[1], shape[2], gl.GL_RED, gl.GL_FLOAT, image_ptr)

    def update_vertex_buffer(self, vertices):
        if self.mesh_vertex_list is not None:
            self.mesh_vertex_list.position[:] = list(vertices)
