import json
from typing import Dict, Any
from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def build_tree_from_markdown(
        self,
        content: str
    ) -> Dict[str, Any]:
        """Build PageIndex tree from markdown text."""

        prompt = f"""Analyze this markdown document and create a hierarchical tree structure.

Document Content:
```markdown
{content[:8000]}
```

Return a JSON object with this structure:
{{
  "nodes": [
    {{
      "id": "0001",
      "level": 0,
      "title": "Document Title",
      "content": "Brief summary of this section",
      "page_start": 1,
      "page_end": 1,
      "children": []
    }}
  ]
}}

Requirements:
- id format: 4-digit string, use nesting for children
- level: 0 for root/h1, increases for nested headers
- page_start/page_end: use line numbers approximated as "page" numbers
- Preserve the markdown header hierarchy (#=level 0, ##=level 1, etc.)

Return ONLY the JSON, no other text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content
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

    async def answer_with_text(
        self,
        query: str,
        context: str
    ) -> str:
        """Generate answer from query and text context."""

        prompt = f"""Answer this question based on the provided document context.

Context:
```
{context}
```

Question: {query}

Provide a clear, concise answer based only on the context."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )

        return response.choices[0].message.content
