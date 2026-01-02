"""Spatial Reasoning Question Generator for 3D cube stacks and views.

Generates questions where students identify correct top/front/side views
of 3D cube arrangements - a common NSW Selective exam question type.
"""

import io
import random
import copy
from dataclasses import dataclass
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


@dataclass
class CubeStack:
    """Represents a 3D arrangement of unit cubes.

    Grid is indexed as grid[x][y][z] where:
    - x: left-right (columns in top view)
    - y: front-back (rows in top view)
    - z: bottom-top (height)
    """
    grid: list[list[list[bool]]]  # True = cube present

    @property
    def size_x(self) -> int:
        return len(self.grid)

    @property
    def size_y(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    @property
    def size_z(self) -> int:
        return len(self.grid[0][0]) if self.grid and self.grid[0] else 0

    def cube_positions(self) -> list[tuple[int, int, int]]:
        """Return list of (x, y, z) positions where cubes exist."""
        positions = []
        for x in range(self.size_x):
            for y in range(self.size_y):
                for z in range(self.size_z):
                    if self.grid[x][y][z]:
                        positions.append((x, y, z))
        return positions

    def top_view(self) -> list[list[int]]:
        """Return 2D grid showing height at each (x, y) position.

        Returns grid[x][y] = height (number of stacked cubes).
        """
        result = []
        for x in range(self.size_x):
            row = []
            for y in range(self.size_y):
                height = 0
                for z in range(self.size_z):
                    if self.grid[x][y][z]:
                        height = z + 1
                row.append(height)
            result.append(row)
        return result

    def front_view(self) -> list[list[bool]]:
        """Return 2D grid from front (looking along +y axis).

        Returns grid[x][z] = True if any cube visible at that position.
        """
        result = []
        for x in range(self.size_x):
            col = []
            for z in range(self.size_z):
                visible = any(self.grid[x][y][z] for y in range(self.size_y))
                col.append(visible)
            result.append(col)
        return result

    def side_view(self) -> list[list[bool]]:
        """Return 2D grid from right side (looking along -x axis).

        Returns grid[y][z] = True if any cube visible at that position.
        """
        result = []
        for y in range(self.size_y):
            col = []
            for z in range(self.size_z):
                visible = any(self.grid[x][y][z] for x in range(self.size_x))
                col.append(visible)
            result.append(col)
        return result

    def back_view(self) -> list[list[bool]]:
        """Return 2D grid from back (looking along -y axis).

        Returns grid[x][z] = True if any cube visible (mirrored front).
        """
        result = []
        for x in range(self.size_x - 1, -1, -1):  # Reverse x for back view
            col = []
            for z in range(self.size_z):
                visible = any(self.grid[x][y][z] for y in range(self.size_y))
                col.append(visible)
            result.append(col)
        return result

    def left_view(self) -> list[list[bool]]:
        """Return 2D grid from left side (looking along +x axis).

        Returns grid[y][z] = True if any cube visible (mirrored side).
        """
        result = []
        for y in range(self.size_y - 1, -1, -1):  # Reverse y for left view
            col = []
            for z in range(self.size_z):
                visible = any(self.grid[x][y][z] for x in range(self.size_x))
                col.append(visible)
            result.append(col)
        return result

    def copy(self) -> 'CubeStack':
        """Create a deep copy."""
        new_grid = [[[self.grid[x][y][z]
                      for z in range(self.size_z)]
                     for y in range(self.size_y)]
                    for x in range(self.size_x)]
        return CubeStack(grid=new_grid)

    def mirror_x(self) -> 'CubeStack':
        """Return copy mirrored along x-axis."""
        new_grid = [[[self.grid[self.size_x - 1 - x][y][z]
                      for z in range(self.size_z)]
                     for y in range(self.size_y)]
                    for x in range(self.size_x)]
        return CubeStack(grid=new_grid)

    def mirror_y(self) -> 'CubeStack':
        """Return copy mirrored along y-axis."""
        new_grid = [[[self.grid[x][self.size_y - 1 - y][z]
                      for z in range(self.size_z)]
                     for y in range(self.size_y)]
                    for x in range(self.size_x)]
        return CubeStack(grid=new_grid)

    def rotate_90(self) -> 'CubeStack':
        """Return copy rotated 90° clockwise when viewed from top."""
        # After rotation: new_x = old_y, new_y = size_x - 1 - old_x
        new_grid = [[[self.grid[self.size_x - 1 - y][x][z]
                      for z in range(self.size_z)]
                     for y in range(self.size_x)]
                    for x in range(self.size_y)]
        return CubeStack(grid=new_grid)


class SpatialReasoningGenerator:
    """Generates spatial reasoning questions with 3D cube stacks."""

    def __init__(self, upload_fn=None):
        """Initialize generator.

        Args:
            upload_fn: Function to upload image bytes, returns URL
        """
        self.upload_fn = upload_fn

    def generate_question(self, difficulty: str = "medium", question_type: str = None) -> dict:
        """Generate a complete spatial reasoning question.

        Args:
            difficulty: "easy", "medium", or "hard"
            question_type: "find_view" (3D->2D), "find_shape" (2D->3D), or None (random)

        Returns:
            dict with question data
        """
        if question_type is None:
            question_type = random.choice(["find_view", "find_shape"])

        if question_type == "find_shape":
            return self._generate_find_shape_question(difficulty)
        else:
            return self._generate_find_view_question(difficulty)

    def _generate_find_view_question(self, difficulty: str) -> dict:
        """Generate question: Given 3D shape, find the correct 2D view."""
        # 1. Generate cube stack
        stack = self._generate_cube_stack(difficulty)

        # 2. Render two 3D isometric views
        view1, view2 = self._render_both_isometric(stack)

        # 3. Define all 4 view types
        view_types = ["top", "front", "right", "left"]

        # 4. Render all 4 views
        views = {vt: self._render_view(stack, vt) for vt in view_types}

        # 5. Pick one randomly as the correct answer
        view_type = random.choice(view_types)

        # 6. Create options list and shuffle
        options_with_labels = [(vt, views[vt]) for vt in view_types]
        random.shuffle(options_with_labels)

        # Find correct index after shuffle
        correct_index = next(i for i, (vt, _) in enumerate(options_with_labels) if vt == view_type)
        options = [img for _, img in options_with_labels]

        # 7. Upload images if upload_fn provided
        if self.upload_fn:
            view1 = self.upload_fn(view1, prefix="spatial/question")
            view2 = self.upload_fn(view2, prefix="spatial/question")
            options = [self.upload_fn(opt, prefix="spatial/option") for opt in options]

        return {
            "question_type": "find_view",
            "question_images": [view1, view2],
            "view_type": view_type,
            "options": options,
            "correct_index": correct_index,
            "answer": chr(ord('A') + correct_index),
        }

    def _generate_find_shape_question(self, difficulty: str) -> dict:
        """Generate question: Given 2D view(s), find the correct 3D shape."""
        # 1. Generate 4 different cube stacks
        stacks = [self._generate_cube_stack(difficulty) for _ in range(4)]

        # 2. Pick one as correct answer
        correct_idx = random.randint(0, 3)
        correct_stack = stacks[correct_idx]

        # 3. Pick which view type(s) to show as the question
        view_type = random.choice(["top", "front", "right", "left"])

        # 4. Render the 2D view of the correct stack as the question
        question_view = self._render_view(correct_stack, view_type)

        # 5. Render 3D isometric views of all 4 stacks as options
        options = []
        for stack in stacks:
            iso1, iso2 = self._render_both_isometric(stack)
            options.append((iso1, iso2))

        # 6. Shuffle options
        indices = list(range(4))
        random.shuffle(indices)
        options = [options[i] for i in indices]
        correct_index = indices.index(correct_idx)

        # 7. Upload images if upload_fn provided
        if self.upload_fn:
            question_view = self.upload_fn(question_view, prefix="spatial/question")
            uploaded_options = []
            for iso1, iso2 in options:
                uploaded_options.append([
                    self.upload_fn(iso1, prefix="spatial/option"),
                    self.upload_fn(iso2, prefix="spatial/option"),
                ])
            options = uploaded_options

        return {
            "question_type": "find_shape",
            "question_images": [question_view],
            "view_type": view_type,
            "options": options,
            "correct_index": correct_index,
            "answer": chr(ord('A') + correct_index),
        }

    def _generate_cube_stack(self, difficulty: str) -> CubeStack:
        """Generate a random cube stack based on difficulty."""
        if difficulty == "easy":
            size = 2
            max_height = 2
            min_cubes = 3
            max_cubes = 5
        elif difficulty == "hard":
            size = 3
            max_height = 4
            min_cubes = 6
            max_cubes = 12
        else:  # medium
            size = 3
            max_height = 3
            min_cubes = 4
            max_cubes = 8

        # Initialize empty grid
        grid = [[[False for _ in range(max_height)]
                 for _ in range(size)]
                for _ in range(size)]

        # Add cubes (ensuring physical validity - no floating cubes)
        num_cubes = random.randint(min_cubes, max_cubes)
        cubes_placed = 0

        # Start with base layer
        base_positions = [(x, y) for x in range(size) for y in range(size)]
        random.shuffle(base_positions)

        # Place initial cube
        x, y = base_positions[0]
        grid[x][y][0] = True
        cubes_placed += 1
        placed = [(x, y, 0)]

        while cubes_placed < num_cubes:
            # Try to add adjacent cube
            candidates = []

            for px, py, pz in placed:
                # Adjacent on same level
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < size and 0 <= ny < size:
                        # Check if valid (on ground or on top of cube)
                        if pz == 0 or grid[nx][ny][pz - 1]:
                            if not grid[nx][ny][pz]:
                                candidates.append((nx, ny, pz))

                # On top
                if pz + 1 < max_height and not grid[px][py][pz + 1]:
                    candidates.append((px, py, pz + 1))

            if not candidates:
                break

            nx, ny, nz = random.choice(candidates)
            grid[nx][ny][nz] = True
            placed.append((nx, ny, nz))
            cubes_placed += 1

        return CubeStack(grid=grid)

    def _render_isometric(self, stack: CubeStack, azim: int = 45, show_labels: bool = True) -> bytes:
        """Render 3D isometric view of cube stack from given angle with direction labels."""
        fig = plt.figure(figsize=(6, 6), dpi=100)
        ax = fig.add_subplot(111, projection='3d')

        for x, y, z in stack.cube_positions():
            self._draw_cube_3d(ax, x, y, z)

        ax.view_init(elev=25, azim=azim)

        max_size = max(stack.size_x, stack.size_y, stack.size_z)
        ax.set_xlim(0, max_size)
        ax.set_ylim(0, max_size)
        ax.set_zlim(0, max_size)

        # Add direction labels
        if show_labels:
            mid = max_size / 2
            offset = max_size + 0.3
            ax.text(mid, -0.5, 0, 'FRONT', ha='center', va='top', fontsize=10, fontweight='bold')
            ax.text(offset, mid, 0, 'RIGHT', ha='left', va='center', fontsize=10, fontweight='bold')
            ax.text(mid, offset, 0, 'BACK', ha='center', va='bottom', fontsize=10, fontweight='bold')
            ax.text(-0.5, mid, 0, 'LEFT', ha='right', va='center', fontsize=10, fontweight='bold')

        ax.set_axis_off()
        ax.set_facecolor('white')
        fig.set_facecolor('white')

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight',
                    facecolor='white', edgecolor='none', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _render_both_isometric(self, stack: CubeStack) -> tuple[bytes, bytes]:
        """Render two isometric views: front-right (azim=45) and back-left (azim=225)."""
        view1 = self._render_isometric(stack, azim=45)
        view2 = self._render_isometric(stack, azim=225)
        return view1, view2

    def _draw_cube_3d(self, ax, x: int, y: int, z: int):
        """Draw a unit cube at position (x, y, z)."""
        # Define vertices of unit cube
        vertices = [
            [x, y, z], [x+1, y, z], [x+1, y+1, z], [x, y+1, z],  # bottom
            [x, y, z+1], [x+1, y, z+1], [x+1, y+1, z+1], [x, y+1, z+1]  # top
        ]

        # Define faces
        faces = [
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # front
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # back
            [vertices[0], vertices[3], vertices[7], vertices[4]],  # left
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # right
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # bottom
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # top
        ]

        # Draw faces with different shades for depth perception
        colors = ['#DDDDDD', '#AAAAAA', '#CCCCCC', '#BBBBBB', '#999999', '#EEEEEE']

        for face, color in zip(faces, colors):
            poly = Poly3DCollection([face], alpha=1.0)
            poly.set_facecolor(color)
            poly.set_edgecolor('black')
            poly.set_linewidth(1)
            ax.add_collection3d(poly)

    def _render_view(self, stack: CubeStack, view_type: str) -> bytes:
        """Render 2D orthographic view."""
        if view_type == "top":
            return self._render_top_view(stack)
        elif view_type == "front":
            return self._render_front_view(stack)
        elif view_type == "right":
            return self._render_side_view(stack)
        elif view_type == "back":
            return self._render_back_view(stack)
        elif view_type == "left":
            return self._render_left_view(stack)
        else:
            raise ValueError(f"Unknown view type: {view_type}")

    def _render_top_view(self, stack: CubeStack) -> bytes:
        """Render top view as silhouette (no numbers for consistency)."""
        grid = stack.top_view()
        # Convert heights to bool for consistent silhouette style
        bool_grid = [[height > 0 for height in row] for row in grid]
        return self._render_2d_grid_bool(bool_grid)

    def _render_front_view(self, stack: CubeStack) -> bytes:
        """Render front view (silhouette)."""
        grid = stack.front_view()
        return self._render_2d_grid_bool(grid)

    def _render_side_view(self, stack: CubeStack) -> bytes:
        """Render right side view (silhouette)."""
        grid = stack.side_view()
        return self._render_2d_grid_bool(grid)

    def _render_back_view(self, stack: CubeStack) -> bytes:
        """Render back view (silhouette)."""
        grid = stack.back_view()
        return self._render_2d_grid_bool(grid)

    def _render_left_view(self, stack: CubeStack) -> bytes:
        """Render left side view (silhouette)."""
        grid = stack.left_view()
        return self._render_2d_grid_bool(grid)

    def _render_2d_grid(self, grid: list[list[int]], show_numbers: bool = True) -> bytes:
        """Render 2D grid with optional height numbers."""
        size_x = len(grid)
        size_y = len(grid[0]) if grid else 0

        fig, ax = plt.subplots(figsize=(4, 4), dpi=100)
        ax.set_aspect('equal')

        # Draw grid
        for x in range(size_x):
            for y in range(size_y):
                height = grid[x][y]

                # Draw cell
                rect = plt.Rectangle((x, size_y - 1 - y), 1, 1,
                                     fill=height > 0,
                                     facecolor='#DDDDDD' if height > 0 else 'white',
                                     edgecolor='black', linewidth=2)
                ax.add_patch(rect)

                # Add height number
                if show_numbers and height > 0:
                    ax.text(x + 0.5, size_y - 0.5 - y, str(height),
                           ha='center', va='center', fontsize=16, fontweight='bold')

        ax.set_xlim(0, size_x)
        ax.set_ylim(0, size_y)
        ax.axis('off')
        ax.set_facecolor('white')
        fig.set_facecolor('white')

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight',
                    facecolor='white', edgecolor='none', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _render_2d_grid_bool(self, grid: list[list[bool]]) -> bytes:
        """Render 2D boolean grid (filled/empty squares)."""
        size_x = len(grid)
        size_z = len(grid[0]) if grid else 0

        fig, ax = plt.subplots(figsize=(4, 4), dpi=100)
        ax.set_aspect('equal')

        # Draw grid
        for x in range(size_x):
            for z in range(size_z):
                filled = grid[x][z]

                rect = plt.Rectangle((x, z), 1, 1,
                                     fill=filled,
                                     facecolor='#DDDDDD' if filled else 'white',
                                     edgecolor='black', linewidth=2)
                ax.add_patch(rect)

        ax.set_xlim(0, size_x)
        ax.set_ylim(0, size_z)
        ax.axis('off')
        ax.set_facecolor('white')
        fig.set_facecolor('white')

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight',
                    facecolor='white', edgecolor='none', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

# Test function
async def test_spatial_generator():
    """Test the spatial reasoning generator."""
    gen = SpatialReasoningGenerator()

    # Generate a question
    question = gen.generate_question(difficulty="medium")

    print(f"View type: {question['view_type']}")
    print(f"Correct answer: {question['answer']}")
    print(f"Number of options: {len(question['options'])}")

    # Save images to files for inspection
    with open('/tmp/spatial_question.png', 'wb') as f:
        f.write(question['question_image'])

    for i, opt in enumerate(question['options']):
        with open(f'/tmp/spatial_option_{chr(ord("A") + i)}.png', 'wb') as f:
            f.write(opt)

    print("Images saved to /tmp/spatial_*.png")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_spatial_generator())
