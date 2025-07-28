// frontend/src/App.js

import React, { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [files, setFiles] = useState(null);
  const [service, setService] = useState("structure"); // 'structure' or 'persona'
  const [persona, setPersona] = useState("");
  const [jobTask, setJobTask] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    setFiles(e.target.files);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!files || files.length === 0) {
      setError("Please select at least one PDF file.");
      return;
    }

    // Reset state
    setIsLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    formData.append("service", service);
    if (service === "persona") {
      formData.append("persona", persona);
      formData.append("jobTask", jobTask);
    }

    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/api/analyze/",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.error || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>📄 Document Analysis Service</h1>
        <p>
          Upload PDFs to extract structure or perform persona-based analysis.
        </p>
      </header>

      <form onSubmit={handleSubmit}>
        <div className="service-toggle">
          <label>
            <input
              type="radio"
              name="service"
              value="structure"
              checked={service === "structure"}
              onChange={() => setService("structure")}
            />
            Structure Extraction (1 PDF)
          </label>
          <label>
            <input
              type="radio"
              name="service"
              value="persona"
              checked={service === "persona"}
              onChange={() => setService("persona")}
            />
            Persona Analysis (Multiple PDFs)
          </label>
        </div>

        <div className="upload-section">
          <label htmlFor="file-upload" className="file-upload-label">
            {files ? `${files.length} file(s) selected` : "Choose PDF File(s)"}
          </label>
          <input
            id="file-upload"
            type="file"
            accept=".pdf"
            multiple
            onChange={handleFileChange}
          />
        </div>

        {service === "persona" && (
          <div className="persona-inputs">
            <input
              type="text"
              placeholder="Enter Persona (e.g., 'Financial Analyst')"
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              required
            />
            <input
              type="text"
              placeholder="Enter Job Task (e.g., 'Find revenue data')"
              value={jobTask}
              onChange={(e) => setJobTask(e.target.value)}
              required
            />
          </div>
        )}

        <button type="submit" disabled={isLoading}>
          {isLoading ? "Analyzing..." : "Analyze Document"}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="result-box">
          <h2>Analysis Result</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App;
