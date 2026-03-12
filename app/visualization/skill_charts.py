import logging
from typing import List, Dict

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class SkillGapVisualizer:
    """
    Generates visual representations of skill gap analysis.
    """

    @staticmethod
    def generate_bar_chart(skill_gap: Dict[str, List[str]]) -> plt.Figure:
        """
        Generate a bar chart showing skill gap distribution.

        Args:
            skill_gap (dict): Output from SkillGapAnalyzer

        Returns:
            matplotlib.figure.Figure
        """

        matched_count = len(skill_gap.get("matched_skills", []))
        partial_count = len(skill_gap.get("partial_skills", []))
        missing_count = len(skill_gap.get("missing_skills", []))

        categories = ["Matched Skills", "Partial Skills", "Missing Skills"]
        values = [matched_count, partial_count, missing_count]

        fig = plt.figure()
        plt.bar(categories, values)
        plt.title("Skill Gap Analysis")
        plt.xlabel("Skill Category")
        plt.ylabel("Number of Skills")

        logger.info("Skill gap bar chart generated.")

        return fig

    @staticmethod
    def generate_skill_list(skill_gap: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Return categorized skill lists for UI rendering.

        Args:
            skill_gap (dict): Output from SkillGapAnalyzer

        Returns:
            dict: categorized skills
        """

        return {
            "matched_skills": skill_gap.get("matched_skills", []),
            "partial_skills": skill_gap.get("partial_skills", []),
            "missing_skills": skill_gap.get("missing_skills", [])
        }
