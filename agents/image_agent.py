"""Image Agent for generating SAT-style educational diagrams using Gemini."""

import asyncio
import json
import re
import uuid
from typing import Any, Optional
from dataclasses import dataclass

import boto3
import cairosvg

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from agents.geosdf_generator import GeoSDFGenerator, ImageResult
from agents.spatial_generator import SpatialReasoningGenerator
from config import config


class ImageAgent(BaseAgent):
    """Agent for generating educational diagrams using Gemini + CCJ loop."""

    def __init__(self):
        agent_config = AgentConfig(
            name="ImageAgent",
            description="Generates SAT-style educational diagrams using Gemini AI",
            port=config.ports.image,
            skills=[
                {
                    "id": "generate_diagram",
                    "name": "Generate Diagram",
                    "description": "Generate a diagram from description using Gemini",
                    "tags": ["image", "diagram", "svg", "gemini"],
                },
            ],
        )
        super().__init__(agent_config)
        self._s3_client = None
        self._geosdf = None
        self._spatial = None

    @property
    def geosdf(self) -> GeoSDFGenerator:
        """Lazy initialization of GeoSDF generator."""
        if self._geosdf is None:
            self._geosdf = GeoSDFGenerator(
                gemini_client=self.gemini_client,
                upload_fn=self._upload_to_r2,
            )
        return self._geosdf

    @property
    def spatial(self) -> SpatialReasoningGenerator:
        """Lazy initialization of Spatial Reasoning generator."""
        if self._spatial is None:
            self._spatial = SpatialReasoningGenerator(
                upload_fn=self._upload_to_r2,
            )
        return self._spatial

    async def _route_diagram_type(self, description: str) -> str:
        """Use LLM to determine which generator to use.

        Returns:
            "geosdf" for precise geometry diagrams
            "spatial" for 3D cube stacks with orthographic views
            "ccj" for general diagrams (Venn, flowcharts, patterns)
        """
        prompt = f"""You are a router that decides which diagram generator to use.

DESCRIPTION: {description}

Choose ONE:
- "spatial": For 3D cube/block arrangements asking about top/front/side views. Examples: "stack of cubes", "which is the top view", "3D blocks", "orthographic projection", "spatial reasoning with cubes".
- "geosdf": For precise 2D geometric constructions requiring exact measurements, angles, or spatial relationships. Examples: triangles with specific angles, parallel lines with transversals, circles with tangent lines, geometric proofs.
- "ccj": For conceptual diagrams, illustrations, or visual representations. Examples: Venn diagrams, flowcharts, patterns, sequences, concept maps, any diagram focused on relationships rather than precise geometry.

Reply with ONLY "spatial", "geosdf", or "ccj", nothing else."""

        try:
            response = await self.generate_content(
                prompt,
                model=config.gemini.flash_model,
                temperature=0.0,
                max_tokens=10,
            )
            result = response.strip().lower()
            if "spatial" in result:
                return "spatial"
            if "geosdf" in result:
                return "geosdf"
            return "ccj"
        except Exception:
            return "ccj"

    def _get_s3_client(self):
        """Get or create S3 client for R2."""
        if self._s3_client is None:
            self._s3_client = boto3.client(
                's3',
                endpoint_url=f'https://{config.r2.account_id}.r2.cloudflarestorage.com',
                aws_access_key_id=config.r2.access_key,
                aws_secret_access_key=config.r2.secret_key,
            )
        return self._s3_client

    def _upload_to_r2(self, image_data: bytes, prefix: str = "diagrams") -> str:
        """Upload image to R2 and return public URL."""
        s3 = self._get_s3_client()
        filename = f'{prefix}/{uuid.uuid4().hex}.png'

        s3.put_object(
            Bucket=config.r2.bucket_name,
            Key=filename,
            Body=image_data,
            ContentType='image/png'
        )

        return f'{config.r2.public_url}/{filename}'

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        message = task.status.message
        task_text = ""
        if message and message.parts:
            part = message.parts[0]
            if isinstance(part, dict):
                task_text = part.get("text", "")
            elif hasattr(part, "text"):
                task_text = part.text

        if task_text:
            try:
                task_data = json.loads(task_text)
            except json.JSONDecodeError:
                task_data = {"action": "generate_diagram", "description": task_text}
        else:
            task_data = {"action": "generate_diagram", "description": ""}

        action = task_data.get("action", "generate_diagram")

        if action == "generate_diagram":
            result = await self.generate_diagram(
                description=task_data.get("description", ""),
                difficulty=task_data.get("difficulty", "medium"),
            )
            return result.__dict__
        elif action == "generate_spatial":
            result = await self._generate_spatial(
                difficulty=task_data.get("difficulty", "medium"),
            )
            return result.__dict__
        else:
            return {"error": f"Unknown action: {action}"}

    async def generate_diagram(self, description: str, difficulty: str = "medium") -> ImageResult:
        """Generate a diagram using appropriate method based on description.

        Routes to:
        - Spatial for 3D cube stacks with orthographic views
        - GeoSDF (arxiv 2506.13492v2) for precise geometry diagrams
        - CCJ loop (arxiv 2508.15222) for general diagrams
        """
        diagram_type = await self._route_diagram_type(description)
        print(f"[ImageAgent] Routing to: {diagram_type} for: {description[:50]}...")

        if diagram_type == "spatial":
            return await self._generate_spatial(difficulty)
        elif diagram_type == "geosdf":
            return await self.geosdf.generate(description)
        else:
            return await self._generate_ccj(description)

    async def _generate_spatial(self, difficulty: str = "hard", question_type: str = None) -> ImageResult:
        """Generate a spatial reasoning question with 3D cube stack."""
        try:
            question = self.spatial.generate_question(difficulty="hard", question_type=question_type)
            return ImageResult(
                success=True,
                image_url=question["question_images"][0],
                format="png",
                generation_method="spatial",
                metadata={
                    "question_type": question["question_type"],
                    "question_images": question["question_images"],
                    "view_type": question["view_type"],
                    "options": question["options"],
                    "correct_index": question["correct_index"],
                    "answer": question["answer"],
                },
            )
        except Exception as e:
            return ImageResult(
                success=False,
                error=f"Spatial generation failed: {str(e)}",
            )

    async def _generate_ccj(self, description: str) -> ImageResult:
        """Generate a diagram using Critic-Candidates-Judge loop (arxiv 2508.15222)."""
        try:
            # Phase 1: Generate multiple candidates with different strategies
            candidates = await self._generate_svg_candidates(description)

            if not candidates:
                return ImageResult(
                    success=False,
                    error="No valid SVG candidates generated",
                )

            # Phase 2: Judge - select best candidate
            best_svg = await self._judge_candidates(description, candidates)

            if best_svg:
                # Phase 3: Critic - refine if needed
                refined_svg = await self._critic_refine(description, best_svg)
                final_svg = refined_svg or best_svg

                # Render and upload
                png_bytes = cairosvg.svg2png(bytestring=final_svg.encode())
                image_url = self._upload_to_r2(png_bytes)

                return ImageResult(
                    success=True,
                    image_url=image_url,
                    format="png",
                    generation_method="ccj",
                )

            return ImageResult(
                success=False,
                error="Judge could not select a valid candidate",
            )

        except Exception as e:
            return ImageResult(
                success=False,
                error=f"SVG generation failed: {str(e)}",
            )

    async def _generate_svg_candidates(self, description: str) -> list[str]:
        """Generate multiple SVG candidates with different strategies using Gemini."""
        strategies = [
            ("precise", "Focus on geometric precision and exact positioning. Use calculated coordinates."),
            ("minimal", "Use the simplest possible shapes. Fewer elements, maximum clarity."),
            ("structured", "Organize elements in a clear grid or hierarchical layout."),
        ]

        base_prompt = f"""Generate SVG code for an educational diagram:

DESCRIPTION: {description}

STYLE REQUIREMENTS (SAT-style exam diagram):
- Pure white background (#FFFFFF)
- Black lines and text (#000000), stroke-width: 2px
- Sans-serif font (Arial or Helvetica)
- Clean, precise lines - no gradients, shadows, or 3D effects
- Size: 400x300px viewBox
- Clear labels positioned to avoid overlap

STRATEGY: {{strategy_instruction}}

OUTPUT: Return ONLY valid SVG code starting with <svg and ending with </svg>.
No explanations or markdown."""

        candidates = []
        tasks = []

        for strategy_name, strategy_instruction in strategies:
            prompt = base_prompt.format(strategy_instruction=strategy_instruction)
            tasks.append(self.generate_content(prompt, model=config.gemini.image_model, temperature=0.4))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, str):
                svg = self._extract_svg(result)
                if svg and self._validate_svg(svg):
                    candidates.append(svg)

        return candidates

    def _validate_svg(self, svg: str) -> bool:
        """Validate that SVG is well-formed and renderable."""
        try:
            cairosvg.svg2png(bytestring=svg.encode())
            return True
        except Exception:
            return False

    async def _judge_candidates(self, description: str, candidates: list[str]) -> Optional[str]:
        """Use Gemini to judge which candidate best matches the description."""
        if len(candidates) == 1:
            return candidates[0]

        candidates_text = "\n\n".join([
            f"=== CANDIDATE {i+1} ===\n{svg}"
            for i, svg in enumerate(candidates)
        ])

        prompt = f"""You are judging SVG diagram candidates for this description:

DESCRIPTION: {description}

CANDIDATES:
{candidates_text}

Evaluate each candidate on:
1. Accuracy - Does it correctly represent the description?
2. Clarity - Are elements clearly visible and well-positioned?
3. Completeness - Are all required elements present?

Return ONLY the number of the best candidate (1, 2, or 3). Nothing else."""

        try:
            response = await self.generate_content(prompt, model=config.gemini.image_model, temperature=0.1)
            for char in response.strip():
                if char.isdigit():
                    idx = int(char) - 1
                    if 0 <= idx < len(candidates):
                        return candidates[idx]
            return candidates[0]
        except Exception:
            return candidates[0] if candidates else None

    async def _critic_refine(self, description: str, svg: str) -> Optional[str]:
        """Critic phase: use Gemini to identify issues and refine the SVG."""
        critic_prompt = f"""Analyze this SVG diagram and identify 1-2 specific issues:

DESCRIPTION: {description}

SVG:
{svg}

Identify issues using QUALITATIVE descriptions (not exact coordinates):
- Element positioning: "the circle should be more centered", "labels overlap"
- Missing elements: "needs a label for X"
- Proportions: "the rectangle is too wide relative to height"

If the SVG is already good, respond with "APPROVED".
Otherwise, list 1-2 specific issues to fix."""

        try:
            critique = await self.generate_content(critic_prompt, model=config.gemini.image_model, temperature=0.2)

            if "APPROVED" in critique.upper():
                return svg

            refine_prompt = f"""Improve this SVG based on the following critique:

ORIGINAL SVG:
{svg}

CRITIQUE:
{critique}

DESCRIPTION: {description}

Generate an improved SVG that addresses the critique.
Return ONLY the complete SVG code, no explanations."""

            response = await self.generate_content(refine_prompt, model=config.gemini.image_model, temperature=0.3)
            refined_svg = self._extract_svg(response)

            if refined_svg and self._validate_svg(refined_svg):
                return refined_svg

            return svg

        except Exception:
            return svg

    def _extract_svg(self, text: str) -> Optional[str]:
        """Extract SVG code from text."""
        match = re.search(r'<svg[^>]*>.*?</svg>', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0)

        if "```svg" in text or "```xml" in text:
            parts = text.split("```")
            for part in parts:
                if part.startswith("svg") or part.startswith("xml"):
                    content = part.split("\n", 1)[1] if "\n" in part else part
                    match = re.search(r'<svg[^>]*>.*?</svg>', content, re.DOTALL)
                    if match:
                        return match.group(0)

        return None


async def main():
    """Run the Image Agent."""
    agent = ImageAgent()
    print(f"Starting Image Agent on port {config.ports.image}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
