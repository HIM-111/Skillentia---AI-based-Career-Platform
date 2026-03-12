import { useState } from "react";
import { updateResume } from "../api/api";

const ResumeUpdater = ({ resumeText = "" }) => {
  const [jobDescription, setJobDescription] = useState("");
  const [updatedResume, setUpdatedResume] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  const handleUpdate = async () => {
    if (!resumeText || !jobDescription) {
      alert("Please upload a resume and enter a job description.");
      return;
    }

    try {
      const response = await updateResume(resumeText, jobDescription);
      setUpdatedResume(response.updated_resume || "");
      setSuggestions(response.suggestions || []);
    } catch (error) {
      console.error("Resume update failed", error);
      alert("Resume update failed. Please try again.");
    }
  };

  return (
    <div>
      <h3>Resume Enhancer</h3>

      <textarea
        rows="6"
        placeholder="Paste job description..."
        value={jobDescription}
        onChange={(e) => setJobDescription(e.target.value)}
      />

      <button onClick={handleUpdate}>Enhance Resume</button>

      {suggestions.length > 0 && (
        <div>
          <h4>Suggestions</h4>
          <ul>
            {suggestions.map((s, index) => (
              <li key={index}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {updatedResume && (
        <div>
          <h4>Updated Resume Draft</h4>
          <pre>{updatedResume}</pre>
        </div>
      )}
    </div>
  );
};

export default ResumeUpdater;
