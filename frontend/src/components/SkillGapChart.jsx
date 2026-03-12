import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const SkillGapChart = ({ skillGap }) => {
  if (!skillGap) return null;
  const matching = skillGap.matching_skills || skillGap.matched_skills || [];
  const missing = skillGap.missing_skills || [];

  return (
    <div>
      <h3>Skill Gap Summary</h3>
      <ul>
        <li>Matched: {matching.length}</li>
        <li>Missing: {missing.length}</li>
      </ul>
    </div>
  );
};

export default SkillGapChart;
