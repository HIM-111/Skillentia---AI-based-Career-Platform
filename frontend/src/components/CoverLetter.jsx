import { useState } from "react";
import { generateCoverLetter } from "../api/api";

const CoverLetter = ({ resumeText = "" }) => {
  const [jobDescription, setJobDescription] = useState("");
  const [coverLetter, setCoverLetter] = useState("");

  const handleGenerate = async () => {
    if (!resumeText || !jobDescription) {
      alert("Please upload a resume and enter a job description.");
      return;
    }

    try {
      const response = await generateCoverLetter(resumeText, jobDescription);
      setCoverLetter(response.cover_letter || "");
    } catch (error) {
      console.error("Cover letter generation failed", error);
      alert("Cover letter generation failed. Please try again.");
    }
  };

  return (
    <div>
      <h3>Cover Letter Generator</h3>

      <textarea
        rows="6"
        placeholder="Paste job description..."
        value={jobDescription}
        onChange={(e) => setJobDescription(e.target.value)}
      />

      <button onClick={handleGenerate}>Generate Cover Letter</button>

      {coverLetter && (
        <div>
          <h4>Generated Cover Letter</h4>
          <pre>{coverLetter}</pre>
        </div>
      )}
    </div>
  );
};

export default CoverLetter;
