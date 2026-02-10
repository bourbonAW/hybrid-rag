import json
import base64
from typing import List, Dict, Any
from openai import AsyncOpenAI


class VLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def build_tree_from_images(
        self,
        image_paths: List[str],
        total_pages: int
    ) -> Dict[str, Any]:
        """Build PageIndex tree from page images."""

        # Build message with images
        content = [
            {"type": "text", "text": f"""Analyze this {total_pages}-page document and create a hierarchical tree structure.

Return a JSON object with this structure:
{{
  "nodes": [
    {{
      "id": "0001",
      "level": 0,
      "title": "Document Title",
      "content": "Brief summary",
      "page_start": 1,
      "page_end": 5,
      "children": []
    }}
  ]
}}

Requirements:
- id format: 4-digit string, use nesting for children (e.g., "0001.0001")
- level: 0 for root, increases for nesting
- page_start/page_end: 1-indexed page numbers
- Include all significant sections"""}
        ]

        # Add up to 10 sample images (to save tokens)
        for img_path in image_paths[:10]:
            with open(img_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content
        # Extract JSON from markdown code blocks if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        return json.loads(result_text.strip())

    async def search_tree(
        self,
        tree: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """Search tree for relevant nodes."""

        prompt = f"""Given this document tree structure and a question, find the most relevant nodes.

Document Tree:
{json.dumps(tree, indent=2)}

Question: {query}

Return JSON:
{{
  "thinking": "Your reasoning about which nodes are relevant",
  "node_list": ["0001", "0002.0001"]
}}

Return ONLY the JSON, no other text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        return json.loads(result_text.strip())

    async def answer_with_images(
        self,
        query: str,
        image_paths: List[str]
    ) -> str:
        """Generate answer from query and page images."""

        content = [{"type": "text", "text": f"Answer this question based on the provided document pages:\n\n{query}"}]

        for img_path in image_paths:
            with open(img_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=2000
        )

        return response.choices[0].message.content
