import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
});

API.interceptors.request.use((config) => {
  const token = localStorage.getItem("careerPlatformAuthToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const uploadResume = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await API.post("/resume-upload", formData);
  return res.data;
};

export const analyzeSkillGap = async (resumeText, jobDescription) => {
  const res = await API.post("/skill-gap", {
    resume_text: resumeText,
    job_description: jobDescription,
  });
  return res.data;
};

export const generateCoverLetter = async (resumeText, jobDescription) => {
  const res = await API.post("/cover-letter", {
    resume_text: resumeText,
    job_description: jobDescription,
  });
  return res.data;
};

export const updateResume = async (resumeText, jobDescription) => {
  const res = await API.post("/resume-update", {
    resume_text: resumeText,
    job_description: jobDescription,
  });
  return res.data;
};

export const findJobRecommendations = async (
  resumeText,
  jobDescription,
  limit = 5
) => {
  const res = await API.post("/job-recommendations", {
    resume_text: resumeText,
    job_description: jobDescription,
    limit,
  });
  return res.data;
};
