import React from "react";
import { uploadResume } from "../api/api";

const ResumeUpload = ({ onResumeParsed }) => {
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const extension = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx", "doc", "docs", "txt"].includes(extension)) {
      alert("Only PDF, DOCX, DOC, or TXT resumes are supported.");
      return;
    }

    try {
      const response = await uploadResume(file);
      onResumeParsed(response.resume_text);
    } catch (err) {
      console.error(err);
      alert("Failed to upload resume");
    }
  };

  return (
    <div>
      <input type="file" accept=".pdf,.docx,.doc,.docs,.txt" onChange={handleUpload} />
    </div>
  );
};

export default ResumeUpload;
