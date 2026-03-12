import { useState } from "react";
import ResumeUpload from "../components/ResumeUpload";
import JobDescriptionForm from "../components/JobDescriptionForm";
import SkillGapChart from "../components/SkillGapChart";
import CoverLetter from "../components/CoverLetter";
import ResumeUpdater from "../components/ResumeUpdater";

const Dashboard = () => {
  const [skillGap, setSkillGap] = useState(null);

  return (
    <div>
      <ResumeUpload />
      <JobDescriptionForm setSkillGap={setSkillGap} />
      <SkillGapChart skillGap={skillGap} />
      <CoverLetter />
      <ResumeUpdater />
    </div>
  );
};

export default Dashboard;
