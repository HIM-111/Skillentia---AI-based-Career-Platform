import React from "react";
import { uploadResume } from "../api/api";

const ResumeUploader = ({ onTextExtracted }) => {
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const extension = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx", "doc", "docs", "txt"].includes(extension)) {
      alert("Only PDF, DOCX, DOC, or TXT resumes are supported.");
      return;
    }

    try {
      const response = await uploadResume(file);
      onTextExtracted(response.resume_text);
    } catch (error) {
      console.error("Resume upload failed", error);
    }
  };

  return (
    <div>
      <input type="file" accept=".pdf,.docx,.doc,.docs,.txt" onChange={handleFileUpload} />
    </div>
  );
};

export default ResumeUploader;
