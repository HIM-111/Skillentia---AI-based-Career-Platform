import React from "react";

const JobDescriptionForm = ({ value, onChange }) => (
  <div>
    <textarea
      placeholder="Paste Job Description here"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={8}
    />
  </div>
);

export default JobDescriptionForm;
