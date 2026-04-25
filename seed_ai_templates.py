"""Seed AI Templates - System templates based on SciSpace."""
from app.database import db
from app.models.researcher.ai_templates import AITemplate
import json


def seed_ai_templates():
    """Create system AI templates."""
    
    templates = [
        {
            'name': 'Write Literature Review',
            'category': 'writing',
            'icon': 'file-text',
            'description': 'AI writes a comprehensive literature review based on your input',
            'prompt_template': '''You are an academic writing assistant. Based on the following topic, write a comprehensive literature review.

Topic: {{ topic }}

{% if sources %}
Sources to consider:
{{ sources }}
{% endif %}

Write a well-structured literature review that:
1. Introduces the topic and its significance
2. Reviews key theories and frameworks
3. Discusses major findings from existing research
4. Identifies gaps in the literature
5. Concludes with research implications

Use academic language and cite sources appropriately.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'topic',
                        'type': 'textarea',
                        'label': 'Topic of Literature Review',
                        'placeholder': 'Describe your study here in detail...',
                        'required': True
                    },
                    {
                        'name': 'sources',
                        'type': 'textarea',
                        'label': 'Key Sources (Optional)',
                        'placeholder': 'List relevant papers, books, or studies...',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 10000,
            'is_system': True
        },
        {
            'name': 'Write Introduction',
            'category': 'writing',
            'icon': 'file-earmark-text',
            'description': 'AI writes an introduction section based on your input',
            'prompt_template': '''Write a compelling academic introduction for the following research topic:

Topic: {{ topic }}

{% if background %}
Background information:
{{ background }}
{% endif %}

The introduction should:
1. Hook the reader with context and significance
2. State the research problem clearly
3. Outline the research objectives
4. Preview the structure of the paper

Length: Approximately {{ length }} words.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'topic',
                        'type': 'textarea',
                        'label': 'Research Topic',
                        'required': True
                    },
                    {
                        'name': 'background',
                        'type': 'textarea',
                        'label': 'Background Context (Optional)',
                        'required': False
                    },
                    {
                        'name': 'length',
                        'type': 'number',
                        'label': 'Target Word Count',
                        'default': 500,
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 2000,
            'is_system': True
        },
        {
            'name': 'Write Method Section',
            'category': 'writing',
            'icon': 'gear',
            'description': 'AI generates a method section based on your input',
            'prompt_template': '''Write a detailed methodology section for the following research:

Research Type: {{ research_type }}
Methods Used: {{ methods }}

{% if participants %}
Participants/Sample: {{ participants }}
{% endif %}

{% if procedures %}
Procedures: {{ procedures }}
{% endif %}

The methods section should be clear, detailed, and replicable.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'research_type',
                        'type': 'select',
                        'label': 'Research Type',
                        'options': ['Qualitative', 'Quantitative', 'Mixed Methods'],
                        'required': True
                    },
                    {
                        'name': 'methods',
                        'type': 'textarea',
                        'label': 'Research Methods',
                        'required': True
                    },
                    {
                        'name': 'participants',
                        'type': 'textarea',
                        'label': 'Participants/Sample',
                        'required': False
                    },
                    {
                        'name': 'procedures',
                        'type': 'textarea',
                        'label': 'Procedures',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 3000,
            'is_system': True
        },
        {
            'name': 'Write Discussion',
            'category': 'writing',
            'icon': 'chat-dots',
            'description': 'AI generates a discussion section based on your input',
            'prompt_template': '''Write a discussion section based on the following findings:

Key Findings:
{{ findings }}

{% if literature %}
Relevant Literature:
{{ literature }}
{% endif %}

The discussion should:
1. Interpret the findings
2. Connect results to existing literature
3. Address limitations
4. Suggest future research directions''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'findings',
                        'type': 'textarea',
                        'label': 'Key Findings',
                        'required': True
                    },
                    {
                        'name': 'literature',
                        'type': 'textarea',
                        'label': 'Relevant Literature (Optional)',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 4000,
            'is_system': True
        },
        {
            'name': 'Write Results',
            'category': 'writing',
            'icon': 'graph-up',
            'description': 'AI generates a results section based on your input',
            'prompt_template': '''Write a results section presenting the following data:

{{ data_description }}

{% if statistical_tests %}
Statistical Tests Used: {{ statistical_tests }}
{% endif %}

Present the results clearly, objectively, and logically. Use appropriate academic language.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'data_description',
                        'type': 'textarea',
                        'label': 'Describe Your Results/Data',
                        'required': True
                    },
                    {
                        'name': 'statistical_tests',
                        'type': 'text',
                        'label': 'Statistical Tests (Optional)',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 3000,
            'is_system': True
        },
        {
            'name': 'Write Conclusion',
            'category': 'writing',
            'icon': 'check-circle',
            'description': 'AI generates a conclusions section based on your input',
            'prompt_template': '''Write a conclusion for a research paper with the following elements:

Main Findings: {{ main_findings }}

{% if implications %}
Implications: {{ implications }}
{% endif %}

The conclusion should:
1. Summarize key findings
2. Discuss theoretical and practical implications
3. Acknowledge limitations
4. Provide final thoughts''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'main_findings',
                        'type': 'textarea',
                        'label': 'Main Findings',
                        'required': True
                    },
                    {
                        'name': 'implications',
                        'type': 'textarea',
                        'label': 'Implications (Optional)',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 2000,
            'is_system': True
        },
        {
            'name': 'Write Abstract',
            'category': 'writing',
            'icon': 'file-earmark-minus',
            'description': 'AI generates an abstract based on your input',
            'prompt_template': '''Write a structured abstract (max {{ word_limit }} words) for the following research:

Background: {{ background }}
Methods: {{ methods }}
Results: {{ results }}
Conclusion: {{ conclusion }}

Follow the structured abstract format typical for academic journals.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'background',
                        'type': 'textarea',
                        'label': 'Background/Purpose',
                        'required': True
                    },
                    {
                        'name': 'methods',
                        'type': 'textarea',
                        'label': 'Methods',
                        'required': True
                    },
                    {
                        'name': 'results',
                        'type': 'textarea',
                        'label': 'Results',
                        'required': True
                    },
                    {
                        'name': 'conclusion',
                        'type': 'textarea',
                        'label': 'Conclusion',
                        'required': True
                    },
                    {
                        'name': 'word_limit',
                        'type': 'number',
                        'label': 'Word Limit',
                        'default': 250,
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 500,
            'is_system': True
        },
        {
            'name': 'Critique This',
            'category': 'analysis',
            'icon': 'chat-square-quote',
            'description': 'AI generates an academic critique of your text',
            'prompt_template': '''Provide an academic critique of the following text:

{{ text }}

Your critique should address:
1. Strengths of the argument/writing
2. Weaknesses or gaps in reasoning
3. Suggestions for improvement
4. Overall assessment

Be constructive and specific.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'text',
                        'type': 'textarea',
                        'label': 'Text to Critique',
                        'required': True
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 2000,
            'is_system': True
        },
        {
            'name': 'Summarize Text',
            'category': 'analysis',
            'icon': 'file-earmark-zip',
            'description': 'AI summarizes text (max 1-2 pages)',
            'prompt_template': '''Summarize the following text in approximately {{ length }} words:

{{ text }}

{% if focus %}
Focus on: {{ focus }}
{% endif %}

Provide a clear, concise summary that captures the main points.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'text',
                        'type': 'textarea',
                        'label': 'Text to Summarize',
                        'required': True
                    },
                    {
                        'name': 'length',
                        'type': 'number',
                        'label': 'Summary Length (words)',
                        'default': 200,
                        'required': False
                    },
                    {
                        'name': 'focus',
                        'type': 'text',
                        'label': 'Focus Area (Optional)',
                        'required': False
                    }
                ]
            },
            'output_format': 'text',
            'max_result_length': 1500,
            'is_system': True
        },
        {
            'name': "What's the Opposite View?",
            'category': 'analysis',
            'icon': 'arrow-left-right',
            'description': 'AI gives you the opposite viewpoint',
            'prompt_template': '''Given the following position or argument:

{{ position }}

Provide a well-reasoned counter-argument or opposite viewpoint. Consider:
1. Alternative perspectives
2. Contrasting evidence
3. Different theoretical frameworks
4. Critical objections

Be balanced and intellectually honest.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'position',
                        'type': 'textarea',
                        'label': 'Position/Argument',
                        'required': True
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 1500,
            'is_system': True
        },
        {
            'name': 'Rewrite This',
            'category': 'writing',
            'icon': 'arrow-repeat',
            'description': 'AI rewrites text for you',
            'prompt_template': '''Rewrite the following text to be {{ style }}:

{{ text }}

{% if additional_instructions %}
Additional instructions: {{ additional_instructions }}
{% endif %}

Maintain the core meaning while improving clarity and style.''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'text',
                        'type': 'textarea',
                        'label': 'Text to Rewrite',
                        'required': True
                    },
                    {
                        'name': 'style',
                        'type': 'select',
                        'label': 'Target Style',
                        'options': ['more academic', 'clearer', 'more concise', 'more formal', 'simpler'],
                        'default': 'clearer',
                        'required': True
                    },
                    {
                        'name': 'additional_instructions',
                        'type': 'text',
                        'label': 'Additional Instructions (Optional)',
                        'required': False
                    }
                ]
            },
            'output_format': 'text',
            'max_result_length': 3000,
            'is_system': True
        },
        {
            'name': 'Historic Overview',
            'category': 'writing',
            'icon': 'clock-history',
            'description': 'AI generates a historic overview of a topic',
            'prompt_template': '''Provide a historical overview of the following topic:

{{ topic }}

{% if time_period %}
Focus on period: {{ time_period }}
{% endif %}

The overview should:
1. Trace the development of ideas/events chronologically
2. Identify key milestones and turning points
3. Contextualize within broader historical trends
4. Be suitable for academic writing''',
            'input_schema': {
                'fields': [
                    {
                        'name': 'topic',
                        'type': 'textarea',
                        'label': 'Topic',
                        'required': True
                    },
                    {
                        'name': 'time_period',
                        'type': 'text',
                        'label': 'Time Period (Optional)',
                        'placeholder': 'e.g., 1950-2000',
                        'required': False
                    }
                ]
            },
            'output_format': 'markdown',
            'max_result_length': 3000,
            'is_system': True
        },
    ]
    
    for template_data in templates:
        existing = AITemplate.query.filter_by(name=template_data['name'], is_system=True).first()
        if not existing:
            template = AITemplate(**template_data)
            db.session.add(template)
            print(f"Created template: {template_data['name']}")
    
    db.session.commit()
    print(f"Seeded {len(templates)} AI templates")


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_ai_templates()
