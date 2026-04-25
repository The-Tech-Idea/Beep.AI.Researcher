"""
AI Service - LLM Integration
Handles communication with Beep.AI.Server for AI generation
Supports tool calling, vision, and streaming responses.
"""

import json
from typing import Generator, Dict, Any, List, Optional

import requests

from . import beep_ai_client


class AIService:
    """Service for AI generation via the token-authenticated Beep.AI.Server OpenAI API."""

    def __init__(self):
        self.api_path = '/v1/chat/completions'

    def _endpoint(self) -> str:
        server_root = beep_ai_client._server_root()
        if not server_root:
            raise RuntimeError('Beep.AI.Server URL not configured')
        return f"{server_root}{self.api_path}"

    def _headers(self) -> Dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        headers.update(beep_ai_client._headers())
        if 'Authorization' not in headers:
            raise RuntimeError('Beep.AI.Server token not configured')
        return headers

    def generate(
        self,
        prompt: str,
        creativity: float = 0.7,
        max_tokens: int = 1000,
        model: str = 'gpt-4',
        stream: bool = False,
    ) -> Generator[Dict[str, Any], None, None]:
        """Generate content using the server OpenAI-compatible API."""

        payload = {
            'model': model,
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are an expert academic research assistant. Provide well-structured, properly cited, and academically rigorous content.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': creativity,
            'max_tokens': max_tokens,
            'stream': stream
        }

        if stream:
            response = requests.post(
                self._endpoint(),
                json=payload,
                stream=True,
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if not line.startswith('data: '):
                    continue

                data_str = line[6:]
                if data_str.strip() == '[DONE]':
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if 'choices' not in data or not data['choices']:
                    continue

                delta = data['choices'][0].get('delta', {})
                content = delta.get('content', '')
                if content:
                    yield {'token': content}
            return

        response = requests.post(
            self._endpoint(),
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        if 'choices' in data and data['choices']:
            content = data['choices'][0]['message']['content']
            yield {'token': content}


# Singleton instance
_ai_service = None


def get_ai_service():
    """Get AI service singleton"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


def generate_with_llm(prompt: str, 
                      creativity: float = 0.7,
                      max_tokens: int = 1000,
                      stream: bool = False) -> Generator[Dict[str, Any], None, None]:
    """
    Convenience function for LLM generation
    
    Usage:
        # Streaming
        for chunk in generate_with_llm(prompt, stream=True):
            print(chunk['token'], end='', flush=True)
        
        # Non-streaming
        result = next(generate_with_llm(prompt, stream=False))
        print(result['token'])
    """
    service = get_ai_service()
    return service.generate(
        prompt=prompt,
        creativity=creativity,
        max_tokens=max_tokens,
        stream=stream
    )


# Mock implementation for testing without Beep.AI.Server
class MockAIService(AIService):
    """Mock AI service for testing"""
    
    def generate(self, prompt, creativity=0.7, max_tokens=1000, model='gpt-4', stream=False):
        """Generate mock response"""
        
        mock_response = f"""
# Literature Review

Based on the provided research question and sources, here is a comprehensive literature review:

## Introduction

The field of {prompt[:50]}... has seen significant development in recent years. This review synthesizes current research and identifies key themes.

## Theoretical Framework

Several theoretical perspectives inform this domain:

1. **First Perspective**: Description of theoretical foundation
2. **Second Perspective**: Alternative theoretical approach
3. **Third Perspective**: Emerging framework

## Current Research

Recent studies have demonstrated:

- Finding 1 from the literature
- Finding 2 from the literature  
- Finding 3 from the literature

## Research Gap

Despite advances, several areas require further investigation:

- Gap 1
- Gap 2
- Gap 3

## Conclusion

This review highlights the current state of knowledge and points to future research directions.

## References

[Generated based on provided sources]
        """.strip()
        
        if stream:
            # Simulate streaming by yielding word by word
            words = mock_response.split()
            for word in words:
                yield {'token': word + ' '}
        else:
            yield {'token': mock_response}


# Use mock service for development
def use_mock_service():
    """Switch to mock AI service for testing"""
    global _ai_service
    _ai_service = MockAIService()


# =====================
# Tool-Enhanced Generation (NEW)
# =====================

def generate_with_tools(prompt: str,
                        system_prompt: Optional[str] = None,
                        tools: Optional[List] = None,
                        tool_choice: str = "auto",
                        creativity: float = 0.7,
                        max_tokens: int = 2000) -> Dict[str, Any]:
    """
    Generate LLM response with optional tool calling.
    
    Args:
        prompt: User prompt
        system_prompt: System instruction (defaults to research assistant)
        tools: Specific tools to enable (None = auto-load all)
        tool_choice: "auto", "required", or "none"
        creativity: Temperature
        max_tokens: Max tokens to generate
    
    Returns:
        Dict with 'content', 'tool_calls', 'tokens_used'
    """
    messages = []
    
    if system_prompt:
        messages.append({
            'role': 'system',
            'content': system_prompt
        })
    else:
        messages.append({
            'role': 'system',
            'content': 'You are an expert academic research assistant. Use available tools when they can help answer the user\'s question. Provide well-structured, properly cited, and academically rigorous content.'
        })
    
    messages.append({
        'role': 'user',
        'content': prompt
    })
    
    ok, result = beep_ai_client.chat_with_tools(
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        auto_execute_tools=True,
        temperature=creativity,
        max_tokens=max_tokens
    )
    
    if not ok:
        return {'error': result, 'content': None, 'tool_calls': []}
    
    # Extract response
    try:
        choice = result.get('choices', [{}])[0]
        message = choice.get('message', {})
        return {
            'content': message.get('content', ''),
            'tool_calls': message.get('tool_calls', []),
            'tokens_used': result.get('usage', {})
        }
    except (KeyError, IndexError):
        return {'error': 'Unexpected response format', 'content': None, 'tool_calls': []}


def analyze_research_document(image_url: str = None,
                               text_content: str = None,
                               analysis_prompt: str = None) -> Dict[str, Any]:
    """
    Analyze a research document using vision and text analysis.
    
    Args:
        image_url: URL or base64 of scanned document/figure
        text_content: Document text content
        analysis_prompt: Custom analysis instructions
    
    Returns:
        Dict with 'insights', 'extracted_text', 'classification'
    """
    result = {
        'insights': None,
        'extracted_text': None,
        'classification': None,
        'summary': None
    }
    
    # If we have an image, extract insights
    if image_url:
        ok, insights = beep_ai_client.extract_document_insights(
            image_url=image_url,
            text_content=text_content
        )
        if ok:
            result['extracted_text'] = insights.get('extracted_text')
            result['classification'] = insights.get('document_classification')
            text_content = text_content or insights.get('extracted_text', {}).get('text', '')
    
    # If we have text, generate a summary/analysis
    if text_content and analysis_prompt:
        full_prompt = f"""{analysis_prompt}

Document content:
{text_content[:5000]}"""  # Limit to prevent token overflow
        
        analysis = generate_with_tools(
            prompt=full_prompt,
            system_prompt="You are an expert research document analyst. Analyze the provided document and answer the user's question.",
            tool_choice="auto"
        )
        
        result['insights'] = analysis.get('content')
    
    return result


def calculate_for_research(expression: str = None,
                           data: List = None,
                           operation: str = "statistics") -> Dict[str, Any]:
    """
    Perform calculations for research analysis.
    
    Args:
        expression: Math expression to evaluate
        data: List of data points for statistical analysis
        operation: "calculate", "statistics", "symbolic"
    
    Returns:
        Calculation result
    """
    if operation == "calculate" and expression:
        ok, result = beep_ai_client.calculate(expression)
        if ok:
            return {'success': True, 'result': result}
        return {'success': False, 'error': result}
    
    elif operation == "statistics" and data:
        ok, result = beep_ai_client.calculate_statistics(data)
        if ok:
            return {'success': True, 'result': result}
        return {'success': False, 'error': result}
    
    elif operation == "symbolic" and expression:
        ok, result = beep_ai_client.symbolic_math(expression)
        if ok:
            return {'success': True, 'result': result}
        return {'success': False, 'error': result}
    
    return {'success': False, 'error': 'Invalid operation or missing parameters'}


def visualize_research_data(data: List[Dict],
                            chart_type: str = "bar",
                            x_field: str = None,
                            y_field: str = None,
                            title: str = "Research Data") -> Dict[str, Any]:
    """
    Create visualization for research data.
    
    Args:
        data: List of data records
        chart_type: bar, line, scatter, area, pie
        x_field: X-axis field name
        y_field: Y-axis field name
        title: Chart title
    
    Returns:
        Chart specification for frontend rendering
    """
    ok, result = beep_ai_client.visualize_research_results(
        data=data,
        chart_type=chart_type,
        x_field=x_field,
        y_field=y_field,
        title=title
    )
    
    if ok:
        return {'success': True, 'chart_spec': result}
    return {'success': False, 'error': result}
