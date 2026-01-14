"""
Economic insights generation service
Follows pattern from mie_lib/services/llm_analyst.py
"""

import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

class EconomicAnalyst:
    """Generate AI insights for economic indicators"""
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize economic analyst
        
        Args:
            model: OpenAI model to use (default: gpt-4o)
        """
        if OpenAI is None:
            raise ImportError("openai library not installed")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file"""
        # Try multiple potential locations
        potential_paths = [
            Path("/app/prompts/economic_analyst.txt"),
            Path(__file__).parent.parent.parent.parent / "prompts" / "economic_analyst.txt",
            Path("prompts/economic_analyst.txt")
        ]
        
        for prompt_file in potential_paths:
            if prompt_file.exists():
                logger.info(f"Loading prompt from {prompt_file}")
                with open(prompt_file, 'r') as f:
                    return f.read()
        
        logger.warning(f"Prompt file not found in {[str(p) for p in potential_paths]}, using default")
        return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Fallback prompt if file not found"""
        return """You are the Chief Economist at a business advisory firm.

Your role is to analyze economic indicators and provide clear, actionable insights for business owners who need to make strategic decisions about hiring, expansion, pricing, and investment.

Your analysis should:
1. Explain what the current data means in plain English
2. Identify if we're at an economic turning point or continuation
3. Highlight specific metrics business owners should monitor
4. Provide practical implications for business planning

Be direct, data-driven, and focus on what matters for business strategy."""
    
    def generate_tier1_insight(self, payload: dict) -> str:
        """
        Generate Tier 1: One-line insight for overview cards
        
        Args:
            payload: Economic state vector from build_economic_payload()
        
        Returns:
            One-line insight string (10-12 words max)
        """
        try:
            user_prompt = f"""Economic State Vector for {payload['meta']['indicator_name']}:

{json.dumps(payload, indent=2)}

Provide a one-line insight (10-12 words maximum) that captures the most important takeaway.

FORMAT: Just the insight text, no label or preamble.

EXAMPLES:
- "Unemployment rising but still historically low"
- "Consumer spending resilient despite high rates"
- "Inflation cooling toward Fed's 2% target"
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=50
            )
            
            insight = response.choices[0].message.content.strip()
            
            # Remove any prefixes like "Insight:" or bullet points
            insight = re.sub(r'^(Insight:|One-liner:|[-•*]\s*)', '', insight).strip()
            
            # Remove surrounding quotes if present
            insight = insight.strip('"').strip("'").strip()
            
            logger.info(f"Generated Tier 1 insight for {payload['meta']['indicator_id']}")
            return insight
            
        except Exception as e:
            logger.error(f"Error generating Tier 1 insight: {e}")
            return "Analysis pending..."
    
    def generate_tier2_insight(self, payload: dict) -> dict:
        """
        Generate Tier 2: Detailed analysis with takeaways
        
        Args:
            payload: Economic state vector
        
        Returns:
            Dict with detailed_insight, key_takeaways, business_impact
        """
        try:
            user_prompt = f"""Economic State Vector for {payload['meta']['indicator_name']}:

{json.dumps(payload, indent=2)}

Provide a comprehensive analysis with:

1. DETAILED ANALYSIS (2-3 paragraphs):
   - Current state and recent trend
   - What's driving current levels
   - Historical comparison
   - Economic health signal

2. KEY TAKEAWAYS (3-5 bullet points):
   - Specific data points and changes
   - Notable inflection points
   - Warning signs or positive developments

3. BUSINESS IMPACT (1-2 paragraphs):
   - Practical implications for business planning
   - What to monitor going forward
   - Impact on operations, hiring, pricing

Return as JSON:
{{
  "detailed_insight": "...",
  "key_takeaways": ["...", "...", ...],
  "business_impact": "..."
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON from response
            content = self._extract_json(content)
            insight_data = json.loads(content)
            
            logger.info(f"Generated Tier 2 insight for {payload['meta']['indicator_id']}")
            return insight_data
            
        except Exception as e:
            logger.error(f"Error generating Tier 2 insight: {e}")
            return {
                "detailed_insight": "Detailed analysis temporarily unavailable.",
                "key_takeaways": ["Data analysis in progress"],
                "business_impact": "Check back soon for updated insights."
            }
    
    def generate_tier3_insight(self, payload: dict) -> dict:
        """
        Generate Tier 3: Deep dive comprehensive analysis
        
        Args:
            payload: Economic state vector with components
        
        Returns:
            Dict with comprehensive analysis, components, forward-looking assessment
        """
        try:
            user_prompt = f"""Economic State Vector for {payload['meta']['indicator_name']}:

{json.dumps(payload, indent=2)}

Provide an exhaustive deep-dive analysis with:

1. COMPREHENSIVE ANALYSIS (4-5 paragraphs):
   - Detailed examination of current conditions
   - Component-level drivers
   - Cross-indicator relationships
   - Technical trend analysis

2. COMPONENT BREAKDOWN:
   - Analysis of each major component
   - Contribution to overall indicator
   - Notable developments

3. FORWARD-LOOKING ASSESSMENT:
   - What to watch in coming months
   - Leading indicators and warning signs
   - Potential scenarios
   - Recession risk from this indicator

4. HISTORICAL CONTEXT:
   - Comparison to past economic cycles
   - Similar periods in history
   - Typical patterns at this stage

Return as JSON:
{{
  "comprehensive_insight": "...",
  "component_analysis": {{"component1": "...", ...}},
  "forward_looking": "...",
  "historical_context": "...",
  "recession_signal": "..."
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)
            insight_data = json.loads(content)
            
            logger.info(f"Generated Tier 3 insight for {payload['meta']['indicator_id']}")
            return insight_data
            
        except Exception as e:
            logger.error(f"Error generating Tier 3 insight: {e}")
            return {
                "comprehensive_insight": "Comprehensive analysis temporarily unavailable.",
                "component_analysis": {},
                "forward_looking": "Analysis pending.",
                "historical_context": "Historical analysis pending.",
                "recession_signal": "Assessment pending."
            }
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from markdown code fences if present"""
        content = content.strip()
        
        # Remove markdown code fences
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        
        if content.endswith('```'):
            content = content[:-3]
        
        return content.strip()
    
    def save_insights(self, indicator_id: str, tier: int, insights: dict, reports_dir: Path = None):
        """Save generated insights to file"""
        if reports_dir is None:
            # Try to find reports directory
            possible_dirs = [
                Path("/app/data/reports/economic"),
                Path(__file__).parent.parent.parent.parent / "data" / "reports" / "economic",
                Path("data/reports/economic")
            ]
            
            for d in possible_dirs:
                if d.parent.exists():
                    reports_dir = d
                    break
            
            if reports_dir is None:
                logger.error("Could not find reports directory")
                return
        
        try:
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{indicator_id}_tier{tier}_latest.json"
            filepath = reports_dir / filename
            
            output = {
                "indicator_id": indicator_id,
                "tier": tier,
                "generated_at": datetime.now().isoformat(),
                "insights": insights
            }
            
            with open(filepath, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Also archive with date
            date_str = datetime.now().strftime("%Y-%m-%d")
            archive_dir = reports_dir / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_file = archive_dir / f"{indicator_id}_tier{tier}_{date_str}.json"
            with open(archive_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            logger.info(f"Saved insights to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving insights: {e}")
