import ResumeUpload from "./components/ResumeUpload";
import JobDescriptionForm from "./components/JobDescriptionForm";
import { analyzeSkillGap } from "./api/api";
import { useState } from "react";

function App() {
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState(null);

  const analyze = async () => {
    const response = await analyzeSkillGap(resumeText, jobDescription);
    setResult(response);
  };

  return (
    <div>
      <h1>Skillentia</h1>

      <ResumeUpload onResumeParsed={setResumeText} />

      <JobDescriptionForm
        value={jobDescription}
        onChange={setJobDescription}
      />

      <button onClick={analyze} disabled={!resumeText || !jobDescription}>
        Analyze
      </button>

      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}

export default App;
