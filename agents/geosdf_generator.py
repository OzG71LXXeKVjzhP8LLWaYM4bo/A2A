"""GeoSDF Generator for precise geometry diagrams using constraint optimization.

Based on arxiv 2506.13492v2 - Uses Signed Distance Fields with PyTorch
for gradient-based constraint optimization.
"""

import asyncio
import io
import json
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, Rectangle
import torch
import torch.optim as optim

from config import config


@dataclass
class GeometryElement:
    """A geometric element with learnable parameters."""
    id: str
    type: str  # "point", "line", "circle", "segment"
    params: torch.Tensor  # learnable parameters
    metadata: dict = field(default_factory=dict)


@dataclass
class Constraint:
    """A geometric constraint between elements."""
    type: str  # "distance", "angle", "incidence", "parallel", "perpendicular"
    elements: list[str]
    value: Optional[float] = None


@dataclass
class Label:
    """A label to display on the diagram."""
    element: str
    text: str
    position: str = "midpoint"


@dataclass
class ImageResult:
    """Result of image generation."""
    success: bool
    image_url: Optional[str] = None
    format: str = "png"
    error: Optional[str] = None
    generation_method: str = "geosdf"
    attempts: int = 0
    metadata: Optional[dict] = None


class GeoSDFGenerator:
    """Generator for precise geometry diagrams using SDF constraint optimization."""

    def __init__(self, gemini_client, upload_fn):
        """Initialize generator.

        Args:
            gemini_client: Gemini client for parsing
            upload_fn: Function to upload image bytes and return URL
        """
        self.gemini_client = gemini_client
        self.upload_fn = upload_fn
        self.canvas_size = 400  # px
        self.scale = 30  # pixels per unit

    async def generate(self, description: str) -> ImageResult:
        """Full pipeline: parse -> optimize -> render -> upload."""
        try:
            # Phase 1: Parse description to symbolic representation
            symbolic = await self._parse_to_symbolic(description)
            if not symbolic or "elements" not in symbolic:
                return ImageResult(
                    success=False,
                    error="Failed to parse description to geometric elements",
                )

            # Phase 2: Create SDF elements (with base anchoring)
            elements = self._create_sdf_elements(symbolic)
            if not elements:
                return ImageResult(
                    success=False,
                    error="No valid elements created from symbolic representation",
                )

            # Phase 3: Create constraints
            constraints = self._create_constraints(symbolic)

            # Auto-add horizontal constraint for base segment
            base_segment = symbolic.get("base_segment")
            if base_segment:
                constraints.append(Constraint(
                    type="horizontal",
                    elements=[base_segment],
                    value=None,
                ))

            # Phase 4: Optimize
            success = self._optimize(elements, constraints)
            if not success:
                return ImageResult(
                    success=False,
                    error="Constraint optimization failed to converge",
                )

            # Phase 5: Post-optimization rotation (ensure base is exactly horizontal)
            self._canonicalize_orientation(elements, base_segment)

            # Phase 6: Render
            labels = [Label(**l) for l in symbolic.get("labels", [])]
            png_bytes = self._render(elements, labels)

            # Phase 7: Upload
            image_url = self.upload_fn(png_bytes, prefix="geosdf")

            return ImageResult(
                success=True,
                image_url=image_url,
                format="png",
                generation_method="geosdf",
            )

        except Exception as e:
            return ImageResult(
                success=False,
                error=f"GeoSDF generation failed: {str(e)}",
            )

    async def _parse_to_symbolic(self, description: str) -> Optional[dict]:
        """Use Gemini to extract elements and constraints from description."""
        prompt = f"""Extract geometric elements and constraints from this description.

DESCRIPTION: {description}

Return JSON with this exact structure:
{{
  "elements": [
    {{"id": "A", "type": "point"}},
    {{"id": "B", "type": "point"}},
    {{"id": "C", "type": "point"}},
    {{"id": "AB", "type": "segment", "endpoints": ["A", "B"]}},
    {{"id": "circle1", "type": "circle", "center": "O", "radius_ref": "A"}}
  ],
  "constraints": [
    {{"type": "distance", "elements": ["A", "B"], "value": 8}},
    {{"type": "angle", "elements": ["A", "B", "C"], "value": 90}},
    {{"type": "incidence", "elements": ["P", "line1"]}},
    {{"type": "parallel", "elements": ["seg1", "seg2"]}},
    {{"type": "perpendicular", "elements": ["seg1", "seg2"]}}
  ],
  "labels": [
    {{"element": "AB", "text": "8 cm", "position": "midpoint"}},
    {{"element": "angle_ABC", "text": "90°", "position": "arc"}}
  ],
  "base_segment": "AB"
}}

RULES:
- Every segment needs its endpoints defined as points
- Angles are specified by 3 points: (ray1_endpoint, vertex, ray2_endpoint)
- Angle values are in degrees
- Distance values are in abstract units (will be scaled)
- Use descriptive IDs (A, B, C for points; AB, BC for segments)
- Include all implicit constraints (e.g., if triangle ABC, include segments AB, BC, CA)

ORIENTATION - base_segment field (REQUIRED):
- For triangles: the bottom edge that should appear horizontal
- For rectangles/squares: the bottom edge
- For parallel lines: the segment that should be horizontal
- Choose the segment that would look most natural as the horizontal base

LABELS (REQUIRED):
- Always include labels for ALL distance constraints (e.g., "3 cm" at midpoint of segment)
- Always include labels for ALL angle constraints (e.g., "90°" at arc position)
- Format angle labels as "angle_XYZ" where Y is the vertex

Return ONLY valid JSON, no explanations."""

        try:
            from google.genai.types import GenerateContentConfig

            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=config.gemini.flash_model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )

            text = response.text.strip()

            # Handle markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())

        except Exception as e:
            print(f"Parse error: {e}")
            return None

    def _create_sdf_elements(self, symbolic: dict) -> dict[str, GeometryElement]:
        """Initialize SDF parameters for each element with base anchoring."""
        elements = {}

        # Find base segment endpoints for anchoring
        base_seg_id = symbolic.get("base_segment")
        base_endpoints = []
        if base_seg_id:
            for elem in symbolic.get("elements", []):
                if elem["id"] == base_seg_id and elem["type"] == "segment":
                    base_endpoints = elem.get("endpoints", [])
                    break

        # First pass: create points
        point_index = 0
        for elem in symbolic.get("elements", []):
            elem_id = elem["id"]
            elem_type = elem["type"]

            if elem_type == "point":
                # Check if this point is part of the base segment
                is_base_p1 = len(base_endpoints) > 0 and elem_id == base_endpoints[0]
                is_base_p2 = len(base_endpoints) > 1 and elem_id == base_endpoints[1]

                # Fallback: if no base specified, use first two points
                if not base_endpoints:
                    is_base_p1 = point_index == 0
                    is_base_p2 = point_index == 1

                if is_base_p1:
                    # First base point: anchor at origin (fixed)
                    params = torch.tensor([0.0, 0.0], requires_grad=False)
                elif is_base_p2:
                    # Second base point: on x-axis, only x is learnable
                    # We use a custom tensor where y=0 is enforced
                    params = torch.tensor([5.0, 0.0], requires_grad=True)
                else:
                    # Other points: fully learnable
                    x = torch.randn(1).item() * 3
                    y = torch.randn(1).item() * 3 + 2  # Bias upward for triangles
                    params = torch.tensor([x, y], requires_grad=True)

                elements[elem_id] = GeometryElement(
                    id=elem_id,
                    type="point",
                    params=params,
                    metadata={"is_base_p1": is_base_p1, "is_base_p2": is_base_p2},
                )
                point_index += 1

            elif elem_type == "circle":
                # Circle: [center_x, center_y, radius]
                cx = torch.randn(1) * 2
                cy = torch.randn(1) * 2
                r = torch.abs(torch.randn(1)) + 1
                params = torch.tensor([cx.item(), cy.item(), r.item()], requires_grad=True)
                elements[elem_id] = GeometryElement(
                    id=elem_id,
                    type="circle",
                    params=params,
                    metadata=elem,
                )

        # Second pass: create segments (reference points)
        for elem in symbolic.get("elements", []):
            elem_id = elem["id"]
            elem_type = elem["type"]

            if elem_type == "segment":
                endpoints = elem.get("endpoints", [])
                elements[elem_id] = GeometryElement(
                    id=elem_id,
                    type="segment",
                    params=torch.empty(0),  # No direct params, references points
                    metadata={"endpoints": endpoints},
                )

        return elements

    def _create_constraints(self, symbolic: dict) -> list[Constraint]:
        """Create constraint objects from symbolic representation."""
        constraints = []
        for c in symbolic.get("constraints", []):
            constraints.append(Constraint(
                type=c["type"],
                elements=c["elements"],
                value=c.get("value"),
            ))
        return constraints

    def _optimize(
        self,
        elements: dict[str, GeometryElement],
        constraints: list[Constraint],
        max_iter: int = 5000,
        tol: float = 1e-4,
    ) -> bool:
        """AdamW optimization with cosine annealing."""
        # Collect learnable parameters
        params = []
        for elem in elements.values():
            if elem.params.requires_grad:
                params.append(elem.params)

        if not params:
            return True  # No optimization needed

        optimizer = optim.AdamW(params, lr=0.1)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_iter)

        best_loss = float('inf')
        patience = 500
        no_improve = 0

        for iteration in range(max_iter):
            optimizer.zero_grad()

            loss = self._compute_constraint_loss(elements, constraints)

            if loss.item() < tol:
                return True

            if loss.item() < best_loss:
                best_loss = loss.item()
                no_improve = 0
            else:
                no_improve += 1

            if no_improve > patience:
                break

            loss.backward()
            optimizer.step()
            scheduler.step()

        return best_loss < 0.1  # Acceptable threshold

    def _compute_constraint_loss(
        self,
        elements: dict[str, GeometryElement],
        constraints: list[Constraint],
    ) -> torch.Tensor:
        """Compute total loss for all constraints."""
        total_loss = torch.tensor(0.0)

        for constraint in constraints:
            loss = self._compute_single_constraint(elements, constraint)
            total_loss = total_loss + loss

        # Add regularization to keep points in reasonable range
        for elem in elements.values():
            if elem.type == "point":
                total_loss = total_loss + 0.001 * (elem.params ** 2).sum()

        return total_loss

    def _compute_single_constraint(
        self,
        elements: dict[str, GeometryElement],
        constraint: Constraint,
    ) -> torch.Tensor:
        """Compute loss for a single constraint."""
        c_type = constraint.type
        c_elems = constraint.elements
        c_value = constraint.value

        if c_type == "distance":
            # Distance between two points
            if len(c_elems) >= 2:
                p1 = elements.get(c_elems[0])
                p2 = elements.get(c_elems[1])
                if p1 and p2 and p1.type == "point" and p2.type == "point":
                    dist = torch.norm(p1.params - p2.params)
                    target = c_value if c_value else 5.0
                    return (dist - target) ** 2

        elif c_type == "angle":
            # Angle at vertex (second element)
            if len(c_elems) >= 3:
                p1 = elements.get(c_elems[0])
                vertex = elements.get(c_elems[1])
                p2 = elements.get(c_elems[2])
                if all(e and e.type == "point" for e in [p1, vertex, p2]):
                    v1 = p1.params - vertex.params
                    v2 = p2.params - vertex.params

                    cos_angle = torch.dot(v1, v2) / (torch.norm(v1) * torch.norm(v2) + 1e-8)
                    cos_angle = torch.clamp(cos_angle, -1, 1)
                    angle_rad = torch.acos(cos_angle)

                    target_rad = math.radians(c_value) if c_value else math.pi / 2
                    return (angle_rad - target_rad) ** 2

        elif c_type == "parallel":
            # Two segments should be parallel
            if len(c_elems) >= 2:
                seg1 = elements.get(c_elems[0])
                seg2 = elements.get(c_elems[1])
                if seg1 and seg2 and seg1.type == "segment" and seg2.type == "segment":
                    ep1 = seg1.metadata.get("endpoints", [])
                    ep2 = seg2.metadata.get("endpoints", [])
                    if len(ep1) >= 2 and len(ep2) >= 2:
                        a1, b1 = elements.get(ep1[0]), elements.get(ep1[1])
                        a2, b2 = elements.get(ep2[0]), elements.get(ep2[1])
                        if all(e and e.type == "point" for e in [a1, b1, a2, b2]):
                            dir1 = b1.params - a1.params
                            dir2 = b2.params - a2.params
                            # Cross product should be 0 for parallel
                            cross = dir1[0] * dir2[1] - dir1[1] * dir2[0]
                            return cross ** 2

        elif c_type == "perpendicular":
            # Two segments should be perpendicular
            if len(c_elems) >= 2:
                seg1 = elements.get(c_elems[0])
                seg2 = elements.get(c_elems[1])
                if seg1 and seg2 and seg1.type == "segment" and seg2.type == "segment":
                    ep1 = seg1.metadata.get("endpoints", [])
                    ep2 = seg2.metadata.get("endpoints", [])
                    if len(ep1) >= 2 and len(ep2) >= 2:
                        a1, b1 = elements.get(ep1[0]), elements.get(ep1[1])
                        a2, b2 = elements.get(ep2[0]), elements.get(ep2[1])
                        if all(e and e.type == "point" for e in [a1, b1, a2, b2]):
                            dir1 = b1.params - a1.params
                            dir2 = b2.params - a2.params
                            # Dot product should be 0 for perpendicular
                            dot = torch.dot(dir1, dir2)
                            return dot ** 2

        elif c_type == "incidence":
            # Point lies on element
            if len(c_elems) >= 2:
                point = elements.get(c_elems[0])
                target = elements.get(c_elems[1])
                if point and point.type == "point":
                    if target and target.type == "circle":
                        # Point on circle boundary
                        center = target.params[:2]
                        radius = target.params[2]
                        dist = torch.norm(point.params - center)
                        return (dist - radius) ** 2
                    elif target and target.type == "segment":
                        # Point on line segment
                        ep = target.metadata.get("endpoints", [])
                        if len(ep) >= 2:
                            a = elements.get(ep[0])
                            b = elements.get(ep[1])
                            if a and b:
                                return self._point_to_line_distance_sq(
                                    point.params, a.params, b.params
                                )

        elif c_type == "horizontal":
            # Segment should be horizontal (y1 == y2)
            if len(c_elems) >= 1:
                seg = elements.get(c_elems[0])
                if seg and seg.type == "segment":
                    ep = seg.metadata.get("endpoints", [])
                    if len(ep) >= 2:
                        p1 = elements.get(ep[0])
                        p2 = elements.get(ep[1])
                        if p1 and p2 and p1.type == "point" and p2.type == "point":
                            # Strong penalty for y-difference
                            return 10.0 * (p1.params[1] - p2.params[1]) ** 2

        return torch.tensor(0.0)

    def _point_to_line_distance_sq(
        self,
        p: torch.Tensor,
        a: torch.Tensor,
        b: torch.Tensor,
    ) -> torch.Tensor:
        """Squared distance from point p to line through a and b."""
        ab = b - a
        ap = p - a
        t = torch.dot(ap, ab) / (torch.dot(ab, ab) + 1e-8)
        closest = a + t * ab
        return torch.sum((p - closest) ** 2)

    def _canonicalize_orientation(
        self,
        elements: dict[str, GeometryElement],
        base_segment: Optional[str],
    ) -> None:
        """Ensure base segment is exactly horizontal after optimization."""
        # Find base segment
        seg = elements.get(base_segment) if base_segment else self._find_longest_segment(elements)
        if not seg or seg.type != "segment":
            return

        ep = seg.metadata.get("endpoints", [])
        if len(ep) < 2:
            return

        p1_elem = elements.get(ep[0])
        p2_elem = elements.get(ep[1])
        if not p1_elem or not p2_elem:
            return

        p1 = p1_elem.params.detach()
        p2 = p2_elem.params.detach()

        # Calculate angle to horizontal
        direction = p2 - p1
        angle = torch.atan2(direction[1], direction[0])

        if abs(angle.item()) < 0.01:  # Already horizontal enough
            return

        # Rotation matrix to make base horizontal
        cos_a = torch.cos(-angle)
        sin_a = torch.sin(-angle)
        R = torch.tensor([[cos_a, -sin_a], [sin_a, cos_a]])

        # Apply rotation to all points
        for elem in elements.values():
            if elem.type == "point":
                rotated = R @ elem.params.detach()
                elem.params = rotated

    def _find_longest_segment(
        self,
        elements: dict[str, GeometryElement],
    ) -> Optional[GeometryElement]:
        """Find the longest segment as fallback base."""
        longest = None
        max_len = 0.0
        for elem in elements.values():
            if elem.type == "segment":
                ep = elem.metadata.get("endpoints", [])
                if len(ep) >= 2:
                    p1 = elements.get(ep[0])
                    p2 = elements.get(ep[1])
                    if p1 and p2 and p1.type == "point" and p2.type == "point":
                        length = torch.norm(p1.params - p2.params).item()
                        if length > max_len:
                            max_len = length
                            longest = elem
        return longest

    def _render(
        self,
        elements: dict[str, GeometryElement],
        labels: list[Label],
    ) -> bytes:
        """Render elements to PNG using matplotlib."""
        fig, ax = plt.subplots(1, 1, figsize=(8, 8), dpi=100)
        ax.set_aspect('equal')
        ax.set_facecolor('white')
        fig.set_facecolor('white')

        # Collect all points to determine bounds and centroid
        all_points = []
        all_point_coords = []
        for elem in elements.values():
            if elem.type == "point":
                p = elem.params.detach().numpy()
                all_points.append((elem.id, p))
                all_point_coords.append(p)

        if all_point_coords:
            xs = [p[0] for p in all_point_coords]
            ys = [p[1] for p in all_point_coords]
            margin = 2
            ax.set_xlim(min(xs) - margin, max(xs) + margin)
            ax.set_ylim(min(ys) - margin, max(ys) + margin)

            # Calculate centroid for smart label positioning
            centroid = (sum(xs) / len(xs), sum(ys) / len(ys))
        else:
            ax.set_xlim(-10, 10)
            ax.set_ylim(-10, 10)
            centroid = (0, 0)

        # Remove axes for clean diagram
        ax.axis('off')

        # Draw segments first (behind points)
        for elem in elements.values():
            if elem.type == "segment":
                ep = elem.metadata.get("endpoints", [])
                if len(ep) >= 2:
                    p1 = elements.get(ep[0])
                    p2 = elements.get(ep[1])
                    if p1 and p2:
                        x1, y1 = p1.params.detach().numpy()
                        x2, y2 = p2.params.detach().numpy()
                        ax.plot([x1, x2], [y1, y2], 'k-', linewidth=2)

        # Draw circles
        for elem in elements.values():
            if elem.type == "circle":
                params = elem.params.detach().numpy()
                cx, cy, r = params[0], params[1], params[2]
                circle = plt.Circle((cx, cy), r, fill=False, color='black', linewidth=2)
                ax.add_patch(circle)

        # Draw points with smart label positioning (away from centroid)
        for elem_id, point in all_points:
            x, y = point
            ax.plot(x, y, 'ko', markersize=6)

            # Position label away from centroid
            dx, dy = x - centroid[0], y - centroid[1]
            dist = math.sqrt(dx**2 + dy**2) + 0.01
            offset = 0.4
            label_x = x + dx / dist * offset
            label_y = y + dy / dist * offset

            ax.text(
                label_x, label_y, elem_id,
                fontsize=12, fontweight='bold',
                ha='center', va='center',
                fontfamily='sans-serif',
            )

        # Draw custom labels (segment lengths, angle markers)
        for label in labels:
            self._draw_label(ax, elements, label, centroid)

        # Save to bytes
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _draw_label(
        self,
        ax: plt.Axes,
        elements: dict[str, GeometryElement],
        label: Label,
        centroid: tuple[float, float],
    ) -> None:
        """Draw a label on the diagram with smart positioning."""
        elem = elements.get(label.element)

        if label.position == "midpoint" and elem and elem.type == "segment":
            # Segment label: perpendicular offset + aligned with line
            ep = elem.metadata.get("endpoints", [])
            if len(ep) >= 2:
                p1 = elements.get(ep[0])
                p2 = elements.get(ep[1])
                if p1 and p2:
                    x1, y1 = p1.params.detach().numpy()
                    x2, y2 = p2.params.detach().numpy()

                    # Midpoint
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2

                    # Line direction and perpendicular
                    dx, dy = x2 - x1, y2 - y1
                    length = math.sqrt(dx**2 + dy**2) + 0.01

                    # Perpendicular unit vector (rotate 90°)
                    perp_x, perp_y = -dy / length, dx / length

                    # Choose perpendicular direction away from centroid
                    to_centroid_x = centroid[0] - mx
                    to_centroid_y = centroid[1] - my
                    dot = perp_x * to_centroid_x + perp_y * to_centroid_y
                    if dot > 0:
                        perp_x, perp_y = -perp_x, -perp_y

                    # Offset label perpendicular to line
                    offset = 0.4
                    label_x = mx + perp_x * offset
                    label_y = my + perp_y * offset

                    # Rotate text to align with segment
                    angle_deg = math.degrees(math.atan2(dy, dx))
                    if angle_deg > 90:
                        angle_deg -= 180
                    if angle_deg < -90:
                        angle_deg += 180

                    ax.text(
                        label_x, label_y, label.text,
                        rotation=angle_deg,
                        ha='center', va='bottom',
                        fontsize=10, fontfamily='sans-serif',
                    )

        elif label.position == "arc" and "angle" in label.element:
            # Angle label: draw arc and position label
            parts = label.element.replace("angle_", "").strip()
            if len(parts) >= 3:
                p1_id, vertex_id, p2_id = parts[0], parts[1], parts[2]
                p1_elem = elements.get(p1_id)
                vertex_elem = elements.get(vertex_id)
                p2_elem = elements.get(p2_id)

                if all(e and e.type == "point" for e in [p1_elem, vertex_elem, p2_elem]):
                    vx, vy = vertex_elem.params.detach().numpy()
                    p1x, p1y = p1_elem.params.detach().numpy()
                    p2x, p2y = p2_elem.params.detach().numpy()

                    # Calculate angles from vertex to each point
                    angle1 = math.degrees(math.atan2(p1y - vy, p1x - vx))
                    angle2 = math.degrees(math.atan2(p2y - vy, p2x - vx))

                    # Ensure angle1 < angle2 for arc drawing
                    if angle1 > angle2:
                        angle1, angle2 = angle2, angle1

                    # Check if it's a right angle (90°)
                    angle_diff = abs(angle2 - angle1)
                    is_right_angle = abs(angle_diff - 90) < 5 or abs(angle_diff - 270) < 5

                    arc_radius = 0.5

                    if is_right_angle:
                        # Draw right angle square
                        # Get unit vectors
                        u1x, u1y = (p1x - vx), (p1y - vy)
                        u2x, u2y = (p2x - vx), (p2y - vy)
                        len1 = math.sqrt(u1x**2 + u1y**2) + 0.01
                        len2 = math.sqrt(u2x**2 + u2y**2) + 0.01
                        u1x, u1y = u1x / len1 * 0.4, u1y / len1 * 0.4
                        u2x, u2y = u2x / len2 * 0.4, u2y / len2 * 0.4

                        # Draw right angle marker
                        square_points = [
                            (vx + u1x, vy + u1y),
                            (vx + u1x + u2x, vy + u1y + u2y),
                            (vx + u2x, vy + u2y),
                        ]
                        ax.plot(
                            [square_points[0][0], square_points[1][0], square_points[2][0]],
                            [square_points[0][1], square_points[1][1], square_points[2][1]],
                            'k-', linewidth=1.5
                        )
                    else:
                        # Draw arc for non-right angles
                        arc = Arc(
                            (vx, vy), arc_radius * 2, arc_radius * 2,
                            angle=0, theta1=angle1, theta2=angle2,
                            color='black', linewidth=1.5
                        )
                        ax.add_patch(arc)

                    # Position label at arc midpoint
                    mid_angle_rad = math.radians((angle1 + angle2) / 2)
                    label_dist = arc_radius * 1.8
                    label_x = vx + label_dist * math.cos(mid_angle_rad)
                    label_y = vy + label_dist * math.sin(mid_angle_rad)

                    ax.text(
                        label_x, label_y, label.text,
                        ha='center', va='center',
                        fontsize=10, fontfamily='sans-serif',
                    )
