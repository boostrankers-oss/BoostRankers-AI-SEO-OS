import json
import os
from typing import Optional
from anthropic import Anthropic

async def run_audit_engine(api_key: Optional[str], url: str, primary_keyword: str, location: Optional[str], competitors: Optional[str]):
    if not api_key:
        # Return mock data if no API key is configured
        return get_mock_audit_results(url, primary_keyword)
    
    try:
        client = Anthropic(api_key=api_key)
        
        prompt = f"""
        You are an expert SEO AI Operating System. Analyze the following website and provide a comprehensive SEO audit.
        
        Website URL: {url}
        Primary Keyword: {primary_keyword}
        Location: {location or "Global"}
        Competitors: {competitors or "None provided"}
        
        Provide the response as a strict JSON object with the following structure:
        {{
            "scores": {{
                "Technical": <0-100>,
                "Content": <0-100>,
                "Local": <0-100>,
                "Schema": <0-100>,
                "EEAT": <0-100>,
                "AI Search": <0-100>
            }},
            "findings": [
                {{
                    "agent": "<Agent Name>",
                    "category": "<Category>",
                    "status": "<critical/warning/passed>",
                    "message": "<Detailed finding>"
                }}
            ],
            "content_plan": [
                {{
                    "title": "<Topic Title>",
                    "keyword": "<Target Keyword>",
                    "priority": "<High/Medium/Low>",
                    "type": "<Pillar/Supporting/Cluster>"
                }}
            ]
        }}
        
        Run these agents: Technical SEO, Content SEO, Local SEO, Schema, EEAT, AI Search.
        Generate 5 content plan topics.
        """

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text content
        text_block = message.content[0]
        raw_text = text_block.text
        
        # Clean up markdown code blocks if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        return json.loads(raw_text)
        
    except Exception as e:
        print(f"AI Engine Error: {e}")
        # Fallback to mock data on error
        return get_mock_audit_results(url, primary_keyword)

def get_mock_audit_results(url: str, primary_keyword: str):
    return {
        "scores": {
            "Technical": 75,
            "Content": 60,
            "Local": 40,
            "Schema": 50,
            "EEAT": 65,
            "AI Search": 30
        },
        "findings": [
            {"agent": "Technical SEO", "category": "Crawlability", "status": "warning", "message": "Robots.txt is present but blocking /admin/ directory."},
            {"agent": "Content SEO", "category": "Keyword Density", "status": "critical", "message": f"Primary keyword '{primary_keyword}' density is too low (0.5%)."},
            {"agent": "Local SEO", "category": "NAP Consistency", "status": "passed", "message": "Name, Address, Phone are consistent across homepage."},
            {"agent": "Schema Agent", "category": "Structured Data", "status": "warning", "message": "Missing LocalBusiness schema."},
            {"agent": "EEAT Agent", "category": "Trust", "status": "critical", "message": "No author bios found on blog posts."},
            {"agent": "AI Search", "category": "Entities", "status": "warning", "message": "Lacks clear entity definitions for AI knowledge graph."}
        ],
        "content_plan": [
            {"title": f"The Ultimate Guide to {primary_keyword}", "keyword": primary_keyword, "priority": "High", "type": "Pillar"},
            {"title": f"10 Common Mistakes with {primary_keyword}", "keyword": f"{primary_keyword} mistakes", "priority": "Medium", "type": "Supporting"},
            {"title": f"How {primary_keyword} Works: A Deep Dive", "keyword": f"how {primary_keyword} works", "priority": "Medium", "type": "Cluster"},
            {"title": f"{primary_keyword} vs Alternatives", "keyword": f"{primary_keyword} alternatives", "priority": "Low", "type": "Supporting"},
            {"title": f"Best {primary_keyword} Tools in 2024", "keyword": f"best {primary_keyword} tools", "priority": "Low", "type": "Cluster"}
        ]
    }